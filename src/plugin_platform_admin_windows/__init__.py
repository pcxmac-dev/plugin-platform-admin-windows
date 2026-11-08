"""Windows administration for Liminal (the user, 2026-11-07: "a windows and linux admin plugin for platform"; the
platform is "the interface for the software/hardware which facilitates the liminal framework"): whether the
platform runs as administrator and how the rights are had (LIMINAL_ELEVATE=prompt: Windows asks, UAC, when a
step needs them); the Windows services the framework relies on (WSL, its virtual machine's host, Docker
Desktop's, the firewall, DNS), started when stopped, and the SSH server shown but never started on its own;
the framework's startups as scheduled tasks at your logon (LiminalCharts, LiminalIntegrator, LiminalLogin,
LiminalPlatform, and an integrator of its own's LiminalIntegrator-<name>), read, run, ended, made or removed
when asked; the framework's processes running. Through the library's machines.windows.PowerShell; the
library's Admin base holds the checks, the status and the setup.

    python -m plugin_platform_admin_windows status | setup [STEP ...] | services | startups | processes
                                            | service NAME start|stop|restart | startup APP run|end|enable|disable
                                            | register APP | unregister APP | run [--elevated] -- COMMAND
"""
from __future__ import annotations

import os

from liminal_libs.machines.admin import Admin, Startup, SystemService, app_of
from liminal_libs.machines.windows import ELEVATE_VAR, PowerShell, is_elevated, quote

__version__ = "0.1.0"
TASKS = {"charts": "LiminalCharts", "integrator": "LiminalIntegrator", "login": "LiminalLogin", "platform": "LiminalPlatform"}
VERBS = {"start": "Start-Service", "stop": "Stop-Service", "restart": "Restart-Service"}
TASK_VERBS = {"run": "Start-ScheduledTask", "end": "Stop-ScheduledTask", "enable": "Enable-ScheduledTask", "disable": "Disable-ScheduledTask"}


def state_of(status: str) -> str:
    """A service's status in the framework's words: running, stopped, or the system's own lowercased."""
    s = str(status or "").strip().lower()
    return {"running": "running", "stopped": "stopped"}.get(s, s or "unknown")


class WindowsAdminPlugin(Admin):
    name = "admin-windows"
    title = "Windows administration"
    about = ("This PC for the framework: whether the platform runs as administrator, the Windows services it relies on, "
             "the apps' scheduled tasks at your logon, the framework's processes")
    api = "2.1"
    order = 720
    SERVICES = (("WSLService", "Windows Subsystem for Linux", "the WSL distributions and Docker inside them", True),
                ("vmcompute", "Hyper-V Host Compute Service", "WSL 2's virtual machine", True),
                ("com.docker.service", "Docker Desktop Service", "Docker Desktop's engine", True),
                ("MpsSvc", "Windows Defender Firewall", "the firewall plugin", True),
                ("Dnscache", "DNS Client", "every lookup: the mail record, the feeds", True),
                ("sshd", "OpenSSH SSH Server", "remote access to this PC (shown; never started by the setup)", False))

    def __init__(self, powershell: PowerShell | None = None, env=None, elevated=None):
        self.ps = powershell if powershell is not None else PowerShell()
        self._env = env
        self._elevated = elevated  # a test's answer; None: Windows'

    def present(self) -> bool:
        return self.ps.here

    def elevated(self) -> bool:
        return is_elevated() if self._elevated is None else bool(self._elevated)

    def elevation(self) -> str:
        if self.elevated():
            return "the platform runs as administrator"
        env = os.environ if self._env is None else self._env
        if (env.get(ELEVATE_VAR) or "").strip().lower() == "prompt":
            return "not elevated: a step needing an administrator asks you first (UAC)"
        return f"not elevated: run the platform as administrator, or set {ELEVATE_VAR}=prompt to be asked (UAC) when a step needs it"

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
