"""Windows administration for Liminal (the user, 2026-11-07: "a windows and linux admin plugin for platform"; the
platform is "the interface for the software/hardware which facilitates the liminal framework"): whether the
platform runs as administrator and how the rights are had (LIMINAL_ELEVATE=prompt: Windows asks, UAC, when a
step needs them); the Windows services the framework relies on (WSL, its virtual machine's host, Docker
Desktop's, the firewall, DNS), started when stopped, and the SSH server shown but never started on its own;
the framework's startups as scheduled tasks at your logon (LiminalCharts, LiminalIntegrator, LiminalLogin,
LiminalPlatform, and an integrator of its own's LiminalIntegrator-<name>), read, run, ended, made or removed
when asked; the framework's processes running. Through the library's machines.windows.PowerShell; the
library's Admin base holds the checks, the status and the setup.

At boot, before anyone signs in (0.2.0; the user, 2026-11-11: "also windows and linux admin, need sections for
starting the platform, or an app that inherits the platform object as a service, headless"; "on boot"): the platform,
or an app inheriting it, as a scheduled task Liminal<App>Boot (LiminalPlatformBoot beside the logon task
LiminalPlatform) with an At startup trigger, run whether anyone is signed in or not, as the platform's own user with
no password stored (S4U: this PC's own resources only) and its ordinary rights (never highest), on no desktop, through
pythonw.exe and the library's keeper (liminal_libs.machines.keep: Task Scheduler starts a task again only when it could
not start it, so the keeper starts the app again after a failure, and ends it with itself when the task is ended).
Registered and removed through Windows' prompt (UAC: PowerShell.run_elevated) unless the platform is elevated, each
change confirmed on the page, a removal twice; started and stopped as you, or through UAC when Windows wants an
administrator. Its log beside the platform's: <platform>\\logs\\<app>-boot.log.

What it attaches to (0.4.0, plugin API 2.2; the user, 2026-11-11: "each plugin should reflect the the API its attached
to, and present links that provide documentation"): Windows PowerShell and its elevation (UAC), the ScheduledTasks
cmdlets, Task Scheduler's COM objects, the service cmdlets and CIM's Win32_Process, each with Microsoft Learn's pages,
its parts and its calls (apis.py), drawn on the plugin's page. It keeps nothing of them between two reads, so it has no
facts to say beside them (api_facts: the contract's, {}).

    python -m plugin_platform_admin_windows status | setup [STEP ...] | services | startups | boot | processes
                                            | service NAME start|stop|restart | startup APP run|end|enable|disable
                                            | startup APP start|stop --boot | register APP [--boot [--port N]]
                                            | unregister APP [--boot --accept-removal] | run [--elevated] -- COMMAND
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from liminal_libs import web
from liminal_libs.machines.admin import Admin, BootApp, BootRefused, Startup, SystemService, app_of, boot_command
from liminal_libs.machines.plugin import CommandError
from liminal_libs.machines.windows import ELEVATE_VAR, PowerShell, is_elevated, quote

from .apis import APIS

__version__ = "0.4.1"
TASKS = {"charts": "LiminalCharts", "integrator": "LiminalIntegrator", "login": "LiminalLogin", "platform": "LiminalPlatform"}
VERBS = {"start": "Start-Service", "stop": "Stop-Service", "restart": "Restart-Service"}
TASK_VERBS = {"run": "Start-ScheduledTask", "end": "Stop-ScheduledTask", "enable": "Enable-ScheduledTask", "disable": "Disable-ScheduledTask"}
# the boot tasks (0.2.0)
BOOT_TASK = re.compile(r"Liminal([A-Za-z][A-Za-z0-9]*)Boot", re.IGNORECASE)
BOOT_VERBS = {"start": "Start-ScheduledTask", "stop": "Stop-ScheduledTask"}
KEEP = "liminal_libs.machines.keep"  # the library's keeper: the app started again after a failure, ended with the task
TASK_STATES = {0: "unknown", 1: "disabled", 2: "starting", 3: "stopped", 4: "running"}  # TASK_STATE, in the framework's words
S4U = 2  # TASK_LOGON_S4U: no password stored
BOOT_TRIGGER = 8  # TASK_TRIGGER_BOOT
RESULTS = {0: "0 (ok)", 0x41301: "running", 0x41303: "not run yet", 0x41306: "ended by request"}
RESTARTS = (3, 1)  # Task Scheduler's own retries of a start that failed: how many, minutes apart
BOOT_READ = r"""$svc = New-Object -ComObject Schedule.Service
$svc.Connect()
$root = $svc.GetFolder('\')
$found = @{}
$denied = @()
foreach ($t in $root.GetTasks(1)) { if ($t.Name -match '^Liminal[A-Za-z][A-Za-z0-9]*Boot$') { $found[$t.Name] = $t } }
foreach ($n in @(@NAMES@)) {
  if (-not $found.ContainsKey($n)) {
    try { $found[$n] = $root.GetTask($n) }
    catch {
      $e = $_.Exception
      while ($e.InnerException) { $e = $e.InnerException }
      if ($e -is [System.UnauthorizedAccessException] -or $e.HResult -eq -2147024891) { $denied += $n }
    }
  }
}
foreach ($t in $found.Values) {
  $d = $t.Definition
  $a = @($d.Actions | Where-Object { $_.Type -eq 0 }) | Select-Object -First 1
  [pscustomobject]@{ Name = [string]$t.Name; Seen = 'yes'; State = [int]$t.State; Enabled = [bool]$t.Enabled
    Boot = [bool](@($d.Triggers | Where-Object { $_.Type -eq 8 }).Count); UserId = [string]$d.Principal.UserId
    LogonType = [int]$d.Principal.LogonType; RunLevel = [int]$d.Principal.RunLevel
    Execute = [string]$a.Path; Arguments = [string]$a.Arguments
    LastRun = $t.LastRunTime.ToString('yyyy-MM-dd HH:mm'); LastResult = [int64]$t.LastTaskResult }
}
foreach ($n in $denied) { [pscustomobject]@{ Name = [string]$n; Seen = 'denied' } }"""


def state_of(status: str) -> str:
    """A service's status in the framework's words: running, stopped, or the system's own lowercased."""
    s = str(status or "").strip().lower()
    return {"running": "running", "stopped": "stopped"}.get(s, s or "unknown")


def boot_task(app: str) -> str:
    """An app's boot task: Liminal<App>Boot (LiminalPlatformBoot), beside its logon task Liminal<App> (LiminalPlatform)."""
    return f"Liminal{app.capitalize()}Boot"


def app_of_task(name: str) -> str:
    """The app a boot task is for ("" for a task not named as one: LiminalPlatform, LiminalIntegrator-backtest)."""
    m = BOOT_TASK.fullmatch(name or "")
    return m.group(1).lower() if m else ""


def result_of(value) -> str:
    """A task's last result in words: ok, not run yet, running, else Windows' own code in hexadecimal."""
    try:
        code = int(value)
    except (TypeError, ValueError):
        return str(value or "")
    return RESULTS.get(code, f"0x{code & 0xFFFFFFFF:08X}")


class WindowsAdminPlugin(Admin):
    name = "admin-windows"
    title = "Windows administration"
    about = ("This PC for the framework: whether the platform runs as administrator, the Windows services it relies on, "
             "the apps' scheduled tasks at your logon, the platform's at boot, the framework's processes")
    api = "2.2"
    apis = APIS  # what it attaches to: PowerShell and UAC, ScheduledTasks, Task Scheduler (COM), services, Win32_Process
    order = 720
    SECTION = "os"  # drawn under the platform's OS plugins (liminal-platform 0.26.0)
    BOOT_SERVICES = True
    SERVICES = (("WSLService", "Windows Subsystem for Linux", "the WSL distributions and Docker inside them", True),
                ("vmcompute", "Hyper-V Host Compute Service", "WSL 2's virtual machine", True),
                ("com.docker.service", "Docker Desktop Service", "Docker Desktop's engine", True),
                ("MpsSvc", "Windows Defender Firewall", "the firewall plugin", True),
                ("Dnscache", "DNS Client", "every lookup: the mail record, the feeds", True),
                ("sshd", "OpenSSH SSH Server", "remote access to this PC (shown; never started by the setup)", False))

    def __init__(self, powershell: PowerShell | None = None, env=None, elevated=None, apps=None, logs: Path | None = None,
                 python: str | None = None, listening=None):
        self.ps = powershell if powershell is not None else PowerShell()
        self._env = env
        self._elevated = elevated  # a test's answer; None: Windows'
        self._apps = apps  # a test's boot apps; None: the library's (the platform, the apps inheriting it)
        self._logs = logs  # a test's logs folder; None: the platform's
        self._python = python  # a test's Python; None: this one
        self._listening = listening or web.listening  # whether something answers at a port (a test's stand-in)

    def present(self) -> bool:
        return self.ps.here

    def elevated(self) -> bool:
        return is_elevated() if self._elevated is None else bool(self._elevated)

    def may_elevate(self) -> bool:
        """Windows can ask you (UAC) when a change needs an administrator: on a desktop (not a boot service's platform)."""
        return self.ps.can_ask()

    def elevation(self) -> str:
        if self.elevated():
            return "the platform runs as administrator"
        if not self.ps.can_ask():
            return ("not elevated, and on no desktop (a boot service, before anyone signs in): Windows cannot ask you (UAC) "
                    "here; change what needs an administrator from the platform at your logon")
        env = os.environ if self._env is None else self._env
        if (env.get(ELEVATE_VAR) or "").strip().lower() == "prompt":
            return "not elevated: a step needing an administrator asks you first (UAC)"
        return ("not elevated: a change you confirm on this page asks you (UAC) when Windows wants an administrator; the "
                f"setup's own steps ask only with {ELEVATE_VAR}=prompt (or run the platform as administrator)")

    def services(self) -> list[SystemService]:
        names = ",".join(quote(s[0]) for s in self.SERVICES)
        rows = {str(r["Name"]).lower(): r for r in self.ps.json(
            f"Get-Service -Name {names} -ErrorAction SilentlyContinue | ForEach-Object {{ [pscustomobject]@{{ "
            "Name = $_.Name; Status = $_.Status.ToString(); StartType = $_.StartType.ToString(); Title = $_.DisplayName } }")}
        out = []
        for name, title, used, may in self.SERVICES:
            r = rows.get(name.lower())
            out.append(SystemService(name, str(r.get("Title") or title) if r else title, state_of(r.get("Status")) if r else "absent",
                                     str(r.get("StartType") or "").lower() if r else "", used, may))
        return out

    def _service_action(self, name: str, action: str) -> None:
        self.ps.run_admin(f"{VERBS[action]} -Name {quote(name)}")

    def _service_change(self, name: str, action: str) -> None:
        """A service changed as you asked on the page: as it is when the platform is elevated, else through Windows' prompt
        (UAC) once Windows says an administrator is wanted (the setup's starts still ask only with LIMINAL_ELEVATE=prompt)."""
        self._as_admin(f"{VERBS[action]} -Name {quote(name)}")

    def rights_words(self, kind: str) -> str:
        if kind == "logon":
            return "As you: no administrator is needed"
        if self.elevated():
            return ""
        if self.ps.can_ask():
            return "Windows asks you first (UAC)" if kind == "boot" else "Windows asks you (UAC) when it wants an administrator"
        return ("It needs an administrator, and Windows cannot ask you here (on no desktop): run this platform as administrator, "
                "or make the change from the platform at your logon")

    def startups(self) -> list[Startup]:
        rows = self.ps.json("Get-ScheduledTask -TaskName 'Liminal*' -ErrorAction SilentlyContinue | ForEach-Object { "
                            "$i = $_ | Get-ScheduledTaskInfo; [pscustomobject]@{ Name = $_.TaskName; State = $_.State.ToString(); "
                            "Execute = [string]$_.Actions[0].Execute; Arguments = [string]$_.Actions[0].Arguments; "
                            "LastRun = [string]$i.LastRunTime; LastResult = [string]$i.LastTaskResult } }")
        by_name = {str(r["Name"]): r for r in rows}
        out = []

        def made(app: str, task: str, r: dict) -> Startup:
            return Startup(app, task, str(r.get("State") or "").lower() or "unknown",
                           f"{r.get('Execute', '')} {r.get('Arguments', '')}".strip(),
                           f"last run {r.get('LastRun') or 'never'}, result {r.get('LastResult', '')}")
        for app, task in TASKS.items():
            out.append(made(app, task, by_name[task]) if task in by_name else Startup(app, task, "absent"))
        for task, r in by_name.items():
            if task.startswith("LiminalIntegrator-"):  # an integrator of its own (liminal-integrator service install --name)
                out.append(made("integrator", task, r))
        return out

    def _startup_action(self, app: str, action: str) -> None:
        self.ps.run(f"{TASK_VERBS[action]} -TaskName {quote(TASKS[app])} | Out-Null")

    def _register(self, app: str, command: list[str]) -> None:
        exe, *args = command
        self.ps.run(f"$a = New-ScheduledTaskAction -Execute {quote(exe)} -Argument {quote(' '.join(args))}; "
                    "$t = New-ScheduledTaskTrigger -AtLogOn -User \"$env:USERDOMAIN\\$env:USERNAME\"; "
                    "$s = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew "
                    "-AllowStartIfOnBatteries -DontStopIfGoingOnBatteries; "
                    f"Register-ScheduledTask -TaskName {quote(TASKS[app])} -Action $a -Trigger $t -Settings $s "
                    f"-Description {quote('The Liminal ' + app + ' app at your logon (made by the Liminal platform)')} -Force | Out-Null")

    def _unregister(self, app: str) -> bool:
        task = quote(TASKS[app])
        out = self.ps.run(f"if (Get-ScheduledTask -TaskName {task} -ErrorAction SilentlyContinue) {{ "
                          f"Unregister-ScheduledTask -TaskName {task} -Confirm:$false; 'removed' }} else {{ 'absent' }}")
        return "removed" in out

    # -- at boot, before anyone signs in (0.2.0) ---------------------------------------------------------------------
    def boot_account(self) -> str:
        """Who a boot task runs as: the platform's own user, DOMAIN\\name ("" when not known, or Windows' own account)."""
        env = os.environ if self._env is None else self._env
        user, domain = str(env.get("USERNAME") or "").strip(), str(env.get("USERDOMAIN") or "").strip()
        if not user or user.upper() == "SYSTEM" or user.endswith("$") or any(c in user + domain for c in "'\"\r\n"):
            return ""
        return f"{domain}\\{user}" if domain else user

    def boot_env(self):
        return os.environ if self._env is None else self._env

    def boot_logs(self) -> Path:
        return Path(self._logs) if self._logs is not None else super().boot_logs()

    def boot_apps(self) -> list[BootApp]:
        return list(self._apps) if self._apps is not None else super().boot_apps()

    def boot_log(self, app: str) -> Path:
        """Where a boot task's keeper writes its starts, its ends and the app's error output: beside the platform's log."""
        return self.boot_logs() / f"{app}-boot.log"

    def boot_how(self) -> str:
        return ("a scheduled task At startup (Liminal<App>Boot), as you with no password stored (S4U), on no desktop, kept "
                "up by the library's keeper")

    def boot_details(self) -> str:
        return ("a scheduled task At startup, Liminal<App>Boot, beside the task at your logon: run whether anyone is signed in "
                "or not, as you with no password stored (S4U: this PC's own resources only, no network shares nor what "
                "Windows keeps under your password) and your ordinary rights, never the highest, on no desktop, through "
                "pythonw.exe and the library's keeper: started again 10 s after a failure, waiting up to 10 min while it keeps "
                f"failing (Task Scheduler alone retries only a start that failed, {RESTARTS[0]} times {RESTARTS[1]} min apart); "
                "ending the task ends the app with its keeper")

    def boot_stopping(self) -> str:
        return "Task Scheduler ends its keeper, and the app with it"

    def boot_startups(self, apps: list[BootApp]) -> list[Startup]:
        try:
            rows = self.ps.json(BOOT_READ.replace("@NAMES@", ",".join(quote(boot_task(a.name)) for a in apps)))
        except ValueError as e:  # an answer that is not the tasks' JSON
            raise CommandError(f"Task Scheduler's answer could not be read: {e}") from None
        by_app: dict[str, dict] = {}
        for r in rows:
            app = app_of_task(str(r.get("Name") or ""))
            if app:
                by_app.setdefault(app, r)
        out = [self._boot(a.name, by_app.pop(a.name, None), a) for a in apps]
        return out + [self._boot(app, r, None) for app, r in sorted(by_app.items())]

    def _boot(self, app: str, row: dict | None, known: BootApp | None) -> Startup:
        """One boot task as the framework sees it (row None: not registered, what registering it would make)."""
        log = str(self.boot_log(app))
        if row is None:
            port = known.port if known is not None else 0
            would = subprocess.list2cmdline(boot_command(known, port, self._python)) if known is not None else ""
            return Startup(app, boot_task(app), "absent", would, "", "boot", self.boot_account() or "you", log, port)
        task = str(row.get("Name") or boot_task(app))
        if row.get("Seen") == "denied":
            return Startup(app, task, "unknown", "", "registered, but only an administrator may read it: run the platform as "
                           "administrator to see its state", "boot", "", log, known.port if known is not None else 0)
        args = str(row.get("Arguments") or "")
        command = args.split(" -- ", 1)[1].strip() if " -- " in args else f"{row.get('Execute') or ''} {args}".strip()
        m = re.search(r"--port\s+(\d+)", args)
        port = int(m.group(1)) if m else 0
        state = TASK_STATES.get(int(row.get("State") or 0), "unknown")
        answers = bool(port) and self._listening(port)
        notes = []
        if state == "running" and not answers:
            state = "starting"  # its keeper runs; nothing answers yet (if it lasts, its log says why)
        elif state in ("stopped", "disabled") and answers:
            notes.append(f"something else answers at port {port}")
        if not row.get("Boot"):
            notes.append("no At startup trigger: register it again")
        if int(row.get("LogonType") or 0) != S4U:
            notes.append("it stores a password or needs you signed in: register it again")
        if int(row.get("RunLevel") or 0):
            notes.append("it runs with the highest rights: register it again to run with yours")
        last = str(row.get("LastRun") or "")
        when = "never" if not last or last[:4] < "2000" else last
        detail = "; ".join([f"last run {when}, result {result_of(row.get('LastResult'))}", *notes])
        return Startup(app, task, state, command, detail, "boot", str(row.get("UserId") or ""), log, port)

    def _as_admin(self, script: str, always: bool = False) -> str:
        """A boot task's change: run as it is when the platform is elevated; else through Windows' prompt (UAC), at once
        (`always`) or once Windows says an administrator is wanted."""
        if self.elevated():
            return self.ps.run(script)
        if always:
            return self.ps.run_elevated(script)
        try:
            return self.ps.run(script)
        except CommandError as e:
            if not e.denied:
                raise
            return self.ps.run_elevated(script)

    def _boot_register(self, app: BootApp, port: int, python: str | None = None) -> None:
        account = self.boot_account()
        if not account:
            raise BootRefused("who the platform runs as is not known (USERNAME), or it is Windows' own account: a boot task "
                              "runs as you, never as SYSTEM")
        command = boot_command(app, port, python or self._python)
        exe, *args = [command[0], "-m", KEEP, "--log", str(self.boot_log(app.name)), "--", *command]
        task = boot_task(app.name)
        out = self._as_admin(
            f"$a = New-ScheduledTaskAction -Execute {quote(exe)} -Argument {quote(subprocess.list2cmdline(args))}; "
            "$t = New-ScheduledTaskTrigger -AtStartup; "
            f"$p = New-ScheduledTaskPrincipal -UserId {quote(account)} -LogonType S4U -RunLevel Limited; "
            "$s = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew "
            f"-AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount {RESTARTS[0]} -RestartInterval (New-TimeSpan -Minutes {RESTARTS[1]}); "
            f"Register-ScheduledTask -TaskPath '\\' -TaskName {quote(task)} -Action $a -Trigger $t -Principal $p -Settings $s "
            f"-Description {quote(app.title + ' at boot, before anyone signs in: headless, as you, no password stored (made by the Liminal platform)')} "
            "-Force | Out-Null; 'registered'", always=True)
        if "registered" not in out:
            raise CommandError(f"{task} was not registered: {out.strip() or 'no answer'}")

    def _boot_action(self, boot: Startup, action: str) -> None:
        self._as_admin(f"{BOOT_VERBS[action]} -TaskPath '\\' -TaskName {quote(boot.name)}")

    def _boot_unregister(self, boot: Startup) -> bool:
        task = quote(boot.name)
        out = self._as_admin(f"if (Get-ScheduledTask -TaskPath '\\' -TaskName {task} -ErrorAction SilentlyContinue) {{ "
                             f"Stop-ScheduledTask -TaskPath '\\' -TaskName {task} -ErrorAction SilentlyContinue; "
                             f"Unregister-ScheduledTask -TaskPath '\\' -TaskName {task} -Confirm:$false; 'removed' }} else {{ 'absent' }}",
                             always=True)
        return "removed" in out

    def processes(self) -> list[dict]:
        rows = self.ps.json("Get-CimInstance Win32_Process -Filter \"Name LIKE 'python%'\" | "
                            "Where-Object { $_.CommandLine -match 'liminal_' } | ForEach-Object { [pscustomobject]@{ "
                            "Pid = $_.ProcessId; Command = [string]$_.CommandLine; MemoryMb = [math]::Round($_.WorkingSetSize / 1MB) } }")
        return [{"pid": int(r["Pid"]), "app": app_of(str(r["Command"])), "command": str(r["Command"]), "memoryMb": int(r.get("MemoryMb") or 0)}
                for r in rows]

    def run(self, *command: str, elevated: bool = False, **options) -> str:
        """A PowerShell command line on this PC, its output; `elevated`: through Windows' prompt (UAC)."""
        script = " ".join(command)
        return self.ps.run_elevated(script) if elevated else self.ps.run(script)


MACHINE = WindowsAdminPlugin()
