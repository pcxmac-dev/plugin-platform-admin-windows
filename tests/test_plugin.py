"""Windows administration: the rights, the framework's services (started when stopped, never the SSH server, an
administrator asked for), the apps' scheduled tasks read, run, made and removed, the processes; the platform's boot
task (0.2.0) read, registered through UAC, started, stopped and removed (asked twice); all through a stand-in
powershell.exe and stand-in apps (nothing changes here: no task is registered, nothing is started)."""
from __future__ import annotations

import inspect
import json
import re
import sys
from pathlib import Path

import pytest

from liminal_libs.machines.admin import ACCEPT_REMOVAL, PLATFORM_APP, BootApp, BootRefused, RemovalRefused, interpreter
from liminal_libs.machines.plugin import CommandError
from liminal_libs.machines.windows import ERROR_MARK, PowerShell, decoded

import plugin_platform_admin_windows.__main__ as cli
from plugin_platform_admin_windows import MACHINE, TASKS, WindowsAdminPlugin, app_of_task, boot_task, result_of, state_of

ME = {"USERNAME": "ciara", "USERDOMAIN": "PC"}


class FakeWindows:
    def __init__(self, denied=False, denied_tasks=False):
        self.services = {"WSLService": "Stopped", "vmcompute": "Running", "MpsSvc": "Running", "Dnscache": "Running", "sshd": "Stopped"}
        self.tasks = {"LiminalCharts": {"State": "Running", "Execute": "C:\\venv\\pythonw.exe", "Arguments": "-m liminal_charts gui --no-browser --port 8765"},
                      "LiminalIntegrator-backtest": {"State": "Ready", "Execute": "C:\\venv\\pythonw.exe", "Arguments": "-m liminal_integrator service run --name backtest"}}
        self.denied = denied
        self.denied_tasks = denied_tasks  # starting or stopping a boot task wants an administrator
        self.boot_tasks: dict[str, dict] = {}  # the boot tasks, as Task Scheduler's COM answers (TASK_STATE numbers)
        self.hidden: set[str] = set()  # boot tasks only an administrator may read
        self.scripts: list[str] = []

    def __call__(self, args, timeout):
        s = decoded(args[6])
        self.scripts.append(s)
        if "Schedule.Service" in s:  # the boot tasks' read, through Task Scheduler's COM
            asked = re.findall(r"'(Liminal[A-Za-z0-9]+Boot)'", s)
            rows = [{"Name": n, "Seen": "yes", **t} for n, t in self.boot_tasks.items() if n not in self.hidden]
            return 0, json.dumps(rows + [{"Name": n, "Seen": "denied"} for n in asked if n in self.hidden]), ""
        if "-AtStartup" in s:  # a boot task registered
            task = re.search(r"-TaskName '([^']+)'", s).group(1)
            self.boot_tasks[task] = {"State": 3, "Enabled": True, "Boot": True, "UserId": re.search(r"-UserId '([^']+)'", s).group(1),
                                     "LogonType": 2 if "-LogonType S4U" in s else 3, "RunLevel": 0 if "-RunLevel Limited" in s else 1,
                                     "Execute": re.search(r"-Execute '([^']+)'", s).group(1),
                                     "Arguments": re.search(r"-Argument '((?:[^']|'')*)'", s).group(1).replace("''", "'"),
                                     "LastRun": "1899-12-30 00:00", "LastResult": 0x41303}
            return 0, "registered\r\n", ""
        if "Unregister-ScheduledTask -TaskPath" in s:
            task = re.search(r"-TaskName '([^']+)'", s).group(1)
            return 0, ("removed\r\n" if self.boot_tasks.pop(task, None) else "absent\r\n"), ""
        boot = re.search(r"(Start|Stop)-ScheduledTask -TaskPath '\\' -TaskName '([^']+)'", s)
        if boot:
            if self.denied_tasks:
                return 1, ERROR_MARK + "Access is denied.", ""
            if boot.group(2) in self.boot_tasks:
                self.boot_tasks[boot.group(2)]["State"] = 4 if boot.group(1) == "Start" else 3
            return 0, "", ""
        if re.search(r"(Start|Stop|Restart)-Service ", s):
            if self.denied:
                return 1, ERROR_MARK + "Service 'WSLService' cannot be started: Access is denied.", ""
            name = re.search(r"-Service -Name '([^']+)'", s).group(1)
            self.services[name] = "Stopped" if "Stop-Service" in s else "Running"
            return 0, "", ""
        if "Get-Service" in s:
            return 0, json.dumps([{"Name": n, "Status": st, "StartType": "Automatic", "Title": n} for n, st in self.services.items()]), ""
        if "Register-ScheduledTask" in s:
            task = re.search(r"-TaskName '([^']+)'", s).group(1)
            self.tasks[task] = {"State": "Ready", "Execute": re.search(r"-Execute '([^']+)'", s).group(1),
                                "Arguments": re.search(r"-Argument '([^']+)'", s).group(1)}
            return 0, "", ""
        if "Unregister-ScheduledTask" in s:
            task = re.search(r"-TaskName '([^']+)'", s).group(1)
            return 0, ("removed\r\n" if self.tasks.pop(task, None) else "absent\r\n"), ""
        if re.search(r"(Start|Stop|Enable|Disable)-ScheduledTask ", s):
            return 0, "", ""
        if "Get-ScheduledTask" in s:
            return 0, json.dumps([{"Name": n, **t, "LastRun": "11/7/2026 9:00:00 AM", "LastResult": "0"} for n, t in self.tasks.items()]), ""
        if "Win32_Process" in s:
            return 0, json.dumps([{"Pid": 63336, "Command": '"C:\\venv\\pythonw.exe" -m liminal_charts gui --no-browser --port 8765', "MemoryMb": 512},
                                  {"Pid": 51876, "Command": '"C:\\venv\\pythonw.exe" -m liminal_integrator service run --daemon', "MemoryMb": 300}]), ""
        return 0, "ran\r\n", ""


def plugin(fake, elevated=False, env=None, apps=(), logs=Path("logs"), answering=(), interactive=None):
    """The plugin through the stand-in; its boot apps the test's (none by default: nothing of the platform imported)."""
    return WindowsAdminPlugin(PowerShell(runner=fake, env=env or {}, interactive=interactive), env=env or {}, elevated=elevated,
                              apps=list(apps), logs=logs, python=sys.executable, listening=lambda port: port in answering)


PLATFORM = BootApp("platform", "Liminal Platform", "liminal_platform", 8775, PLATFORM_APP, "C:\\data\\platform\\logs\\platform.log")
LAB = BootApp("lab", "Liminal Lab", "liminal_lab", 8790, "liminal_lab.app.LabApp")


def table_of(st, title):
    return next(t for t in st["tables"] if t["title"] == title)


def boot_table(st):
    return table_of(st, "At boot, before anyone signs in")


def through_uac(a):
    """Windows' prompt answered yes, as a stand-in: the elevated scripts recorded and run through the stand-in."""
    asked: list[str] = []

    def elevated(script, timeout=600.0):
        asked.append(script)
        return a.ps.run(script)
    a.ps.run_elevated = elevated
    return asked


def test_the_plugin_reports_rights_services_startups_and_processes():
    assert MACHINE.name == "admin-windows" and MACHINE.KIND == "machine" and MACHINE.STEPS == ("privileges", "services", "startup")
    a = plugin(FakeWindows())
    st = a.status()
    services = {s["name"]: s for s in st["frameworkServices"]}
    assert services["WSLService"]["state"] == "stopped" and services["com.docker.service"]["state"] == "absent" and not services["sshd"]["mayStart"]
    startups = {(s["app"], s["name"]): s for s in st["logonStartups"]}
    assert startups[("charts", "LiminalCharts")]["state"] == "running" and "liminal_charts gui" in startups[("charts", "LiminalCharts")]["command"]
    assert startups[("login", "LiminalLogin")]["state"] == "absent" and ("integrator", "LiminalIntegrator-backtest") in startups
    assert [(p["pid"], p["app"]) for p in st["frameworkProcesses"]] == [(63336, "charts"), (51876, "integrator")]
    assert st["summary"] == "not elevated; services: 3 running, stopped: WSLService, sshd; startups: charts, integrator; 2 Liminal process(es)"
    assert "LIMINAL_ELEVATE=prompt" in st["elevation"] and plugin(FakeWindows(), env={"LIMINAL_ELEVATE": "prompt"}).elevation().endswith("(UAC)")
    assert state_of("Running") == "running" and state_of("StartPending") == "startpending"
    # valid while not elevated (it reads): the page draws its own tables, each change through a confirmed form
    assert st["valid"] and st["why"] == "" and not {"services", "startups", "processes"} & set(st)
    assert [t["title"] for t in st["tables"]] == ["Services the framework relies on", "Startups at your logon",
                                                  "At boot, before anyone signs in", "The framework's processes"]
    services = table_of(st, "Services the framework relies on")
    assert "Windows asks you (UAC) when it wants an administrator" in services["note"]
    rows = {r[0]["text"]: r for r in services["rows"]}
    assert rows["WSLService"][4]["values"] == {"name": "WSLService", "action": "start"} and rows["com.docker.service"][4] == ""
    logon = {r[0]: r for r in table_of(st, "Startups at your logon")["rows"] if r[1]["text"] in TASKS.values()}
    assert logon["charts"][3]["title"] == "End…" and logon["login"][3]["form"] == "logon-register:login"
    integrator_own = [r for r in table_of(st, "Startups at your logon")["rows"] if r[1]["text"] == "LiminalIntegrator-backtest"][0]
    assert integrator_own[3] == "" and integrator_own[4] == ""  # an integrator of its own: shown, changed by the integrator's own command
    forms = {f["id"] for f in st["forms"]}
    assert {"service", "logon-startup", "logon-remove", "logon-register:login", "logon-register:platform"} <= forms


def test_the_setup_starts_what_it_may_and_says_when_an_administrator_is_wanted():
    fake = FakeWindows()
    done = plugin(fake, elevated=True).setup(log=lambda m: None)
    assert [(d["step"], d["ok"]) for d in done] == [("privileges", True), ("services", True), ("startup", None)]
    assert fake.services["WSLService"] == "Running" and fake.services["sshd"] == "Stopped"  # never the SSH server on its own
    assert "not registered: integrator, login, platform" in done[2]["detail"] and "integrator (LiminalIntegrator-backtest: ready)" in done[2]["detail"]
    refused = plugin(FakeWindows(denied=True)).setup(log=lambda m: None, steps=("services",))
    assert refused[0]["ok"] is False and "needs an administrator" in refused[0]["detail"] and "WSLService" in refused[0]["detail"]


def test_an_apps_task_is_made_run_and_removed_as_the_integrator_makes_its_own():
    fake = FakeWindows()
    a = plugin(fake)
    made = a.register("platform")
    script = next(s for s in fake.scripts if "Register-ScheduledTask" in s)
    assert "-TaskName 'LiminalPlatform'" in script and "New-ScheduledTaskTrigger -AtLogOn -User \"$env:USERDOMAIN\\$env:USERNAME\"" in script
    assert "-Argument '-m liminal_platform serve --no-browser'" in script and "-ExecutionTimeLimit ([TimeSpan]::Zero)" in script
    assert fake.tasks["LiminalPlatform"]["Execute"] == interpreter(sys.executable)  # this Python: the test's
    assert made.app == "platform" and made.state == "ready"
    a.startup("platform", "run")
    assert any("Start-ScheduledTask -TaskName 'LiminalPlatform'" in s for s in fake.scripts)
    a.service("WSLService", "restart")
    assert any("Restart-Service -Name 'WSLService'" in s for s in fake.scripts)
    assert a.unregister("platform") and not a.unregister("platform") and set(TASKS) == {"charts", "integrator", "login", "platform"}
    # a service changed from the page: Windows asked (UAC) once it says an administrator is wanted; the setup's starts are not
    denied = FakeWindows(denied=True)
    b = plugin(denied)
    prompted: list[str] = []
    b.ps.run_elevated = lambda script, timeout=600.0: prompted.append(script) or ""  # Windows' prompt answered yes
    b.service("WSLService", "start")
    assert prompted == ["Start-Service -Name 'WSLService'"]
    assert b.setup(log=lambda m: None, steps=("services",))[0]["ok"] is False and len(prompted) == 1
    assert a.run("Write-Output", "'hello'") == "ran\r\n" and "Write-Output 'hello'" in fake.scripts[-1]


# -- at boot, before anyone signs in (0.2.0) ---------------------------------------------------------------------------
def test_a_boot_task_is_named_beside_the_logon_task_and_never_taken_for_one():
    assert boot_task("platform") == "LiminalPlatformBoot" and TASKS["platform"] == "LiminalPlatform"
    assert app_of_task("LiminalPlatformBoot") == "platform" and app_of_task("liminallabboot") == "lab"
    assert app_of_task("LiminalPlatform") == "" and app_of_task("LiminalIntegrator-backtest") == "" and app_of_task("LiminalBoot") == ""
    fake = FakeWindows()
    fake.tasks["LiminalPlatformBoot"] = {"State": "Ready", "Execute": "C:\\venv\\pythonw.exe", "Arguments": "-m liminal_libs.machines.keep"}
    assert "LiminalPlatformBoot" not in {s.name for s in plugin(fake).startups()}  # the logon startups leave it out
    assert result_of(0) == "0 (ok)" and result_of(0x41303) == "not run yet" and result_of(-2147024891) == "0x80070005"


def test_the_platform_is_registered_at_boot_through_uac_started_stopped_and_removed(tmp_path):
    fake = FakeWindows()
    a = plugin(fake, env=ME, apps=[PLATFORM, LAB], logs=tmp_path)
    asked = through_uac(a)
    st = a.status()
    assert st["valid"] and st["why"] == ""  # not elevated: Windows asks (UAC) for each change, on this desktop
    rows = boot_table(st)["rows"]
    assert [(r[1]["text"], r[2]) for r in rows] == [("LiminalPlatformBoot", "not registered"), ("LiminalLabBoot", "not registered")]
    assert rows[0][1]["sub"].endswith("-m liminal_platform serve --no-browser --port 8775") and rows[0][3] == "PC\\ciara"
    assert rows[0][4] == {"text": "platform-boot.log", "sub": f"in {tmp_path}; its own: C:\\data\\platform\\logs\\platform.log"}
    register = {f["id"]: f for f in st["forms"]}["boot-register:platform"]
    words = register["confirm"]["words"]
    assert "LiminalPlatformBoot starts Liminal Platform at every boot" in words and "--port {port}" in words and "as PC\\ciara" in words
    assert words.endswith("Windows asks you first (UAC).") and "S4U" in boot_table(st)["note"]
    assert "Unlike the startups at your logon" in boot_table(st)["note"] and register["note"].startswith("A scheduled task At startup")
    assert "never the highest" in register["note"] and "Task Scheduler alone retries only a start that failed" in register["note"]
    made = a.register("platform", "boot", 8775)
    (script,) = asked
    assert "New-ScheduledTaskTrigger -AtStartup" in script and "-UserId 'PC\\ciara' -LogonType S4U -RunLevel Limited" in script
    assert "-TaskPath '\\' -TaskName 'LiminalPlatformBoot'" in script and "-ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew" in script
    assert "-RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)" in script and "-Force" in script
    task = fake.boot_tasks["LiminalPlatformBoot"]
    assert task["Arguments"].startswith(f"-m liminal_libs.machines.keep --log {tmp_path / 'platform-boot.log'} -- ")
    assert task["Arguments"].endswith(" -m liminal_platform serve --no-browser --port 8775") and "--until-quiet" not in task["Arguments"]
    assert "python" in Path(task["Execute"]).name.lower()  # pythonw.exe beside this Python on Windows: no window
    assert (made.state, made.port, made.account, made.at) == ("stopped", 8775, "PC\\ciara", "boot")
    assert made.command.endswith("-m liminal_platform serve --no-browser --port 8775") and "keep" not in made.command
    assert made.detail == "last run never, result not run yet"
    # started as you (Windows is asked only when it wants an administrator), its page not answering yet: starting
    said = a.startup("platform", "start", "boot")
    assert len(asked) == 1 and said["said"] == "LiminalPlatformBoot started" and task["State"] == 4
    assert {b["app"]: b["state"] for b in a.status()["bootServices"]}["platform"] == "starting"
    up = plugin(fake, env=ME, apps=[PLATFORM, LAB], logs=tmp_path, answering={8775})
    st = up.status()
    assert {b["app"]: b["state"] for b in st["bootServices"]}["platform"] == "running" and "at boot: platform (running)" in st["summary"]
    assert boot_table(st)["rows"][0][5]["form"] == "boot-stop:platform"
    with pytest.raises(BootRefused, match="8775 is platform's boot service's"):
        a.register("lab", "boot", 8775)
    a.startup("platform", "stop", "boot")
    assert task["State"] == 3 and len(asked) == 1
    # removed once accepted a second time, through UAC
    with pytest.raises(RemovalRefused) as refused:
        a.unregister("platform", "boot")
    assert refused.value.accept == ACCEPT_REMOVAL and "LiminalPlatformBoot" in fake.boot_tasks and len(asked) == 1
    gone = a.unregister("platform", "boot", accept_removal=True)
    assert gone["removed"] and "LiminalPlatformBoot" not in fake.boot_tasks and len(asked) == 2
    assert "Stop-ScheduledTask -TaskPath '\\' -TaskName 'LiminalPlatformBoot'" in asked[1] and "Unregister-ScheduledTask" in asked[1]


def test_an_elevated_platform_asks_windows_nothing_and_a_denied_start_goes_through_uac(tmp_path):
    fake = FakeWindows()
    a = plugin(fake, elevated=True, env=ME, apps=[PLATFORM], logs=tmp_path)
    asked = through_uac(a)
    a.register("platform", "boot", 8780)
    assert asked == [] and fake.boot_tasks["LiminalPlatformBoot"]["Arguments"].endswith("--port 8780")
    assert "Windows asks" not in boot_table(a.status())["note"]
    fake.denied_tasks = True  # starting it wants an administrator: Windows is asked then
    b = plugin(fake, env=ME, apps=[PLATFORM], logs=tmp_path)
    prompted: list[str] = []
    b.ps.run_elevated = lambda script, timeout=600.0: prompted.append(script) or ""  # Windows' prompt answered yes
    b.startup("platform", "start", "boot")
    assert prompted == ["Start-ScheduledTask -TaskPath '\\' -TaskName 'LiminalPlatformBoot'"]


def test_on_no_desktop_windows_cannot_ask_so_the_plugin_says_so_and_changes_nothing(tmp_path):
    fake = FakeWindows()
    a = plugin(fake, env=ME, apps=[PLATFORM], logs=tmp_path, interactive=False)  # a boot service's own platform
    st = a.status()
    assert st["valid"] is True and st["why"] == "" and "cannot ask you (UAC)" in st["elevation"]  # it reads: valid
    assert "Windows cannot ask you here (on no desktop)" in boot_table(st)["note"]  # each change says what it needs
    with pytest.raises(CommandError, match="cannot ask you"):
        a.register("platform", "boot", 8775)
    assert fake.boot_tasks == {} and not any("Register-ScheduledTask" in s for s in fake.scripts)


def test_a_task_only_an_administrator_reads_and_one_not_made_here_are_said(tmp_path):
    fake = FakeWindows()
    fake.boot_tasks["LiminalPlatformBoot"] = {"State": 3, "Enabled": True, "Boot": False, "UserId": "PC\\ciara", "LogonType": 1,
                                              "RunLevel": 1, "Execute": "C:\\venv\\pythonw.exe",
                                              "Arguments": "-m liminal_platform serve --no-browser --port 8775",
                                              "LastRun": "2026-11-11 08:00", "LastResult": 1}
    fake.boot_tasks["LiminalGoneBoot"] = dict(fake.boot_tasks["LiminalPlatformBoot"], Arguments="-m liminal_gone serve --port 8799")
    a = plugin(fake, env=ME, apps=[PLATFORM], logs=tmp_path, answering={8775})
    boots = {b.app: b for b in a.boot_startups(a.boot_apps())}
    p = boots["platform"]
    assert p.state == "stopped" and p.port == 8775 and "something else answers at port 8775" in p.detail
    assert "no At startup trigger" in p.detail and "stores a password" in p.detail and "highest rights" in p.detail
    assert "last run 2026-11-11 08:00, result 0x00000001" in p.detail
    assert boots["gone"].name == "LiminalGoneBoot" and boots["gone"].port == 8799  # registered for an app not known here
    fake.hidden.add("LiminalPlatformBoot")
    hidden = {b.app: b for b in a.boot_startups(a.boot_apps())}["platform"]
    assert hidden.state == "unknown" and "only an administrator" in hidden.detail
    st = a.status()
    row = next(r for r in boot_table(st)["rows"] if r[1]["text"] == "LiminalPlatformBoot")
    assert row[5]["form"] == "boot-start:platform" and row[6]["form"] == "boot-remove:platform"
    assert {"form": "boot-stop:platform", "title": "Stop Liminal Platform…"} in boot_table(st)["actions"]


def test_the_forms_ask_the_startups_hooks_with_their_arguments_in_order(tmp_path):
    fake = FakeWindows()
    a = plugin(fake, elevated=True, env=ME, apps=[PLATFORM], logs=tmp_path)
    a.register("platform", "boot", 8775)
    forms = {f["id"]: f for f in a.status()["forms"]}
    assert {i for i in forms if i.startswith("boot-")} == {"boot-register:platform", "boot-start:platform", "boot-stop:platform",
                                                            "boot-remove:platform"}
    for f in forms.values():
        params = list(inspect.signature(getattr(a, f["hook"])).parameters)
        assert f["hook"] in a.HOOKS and [x["name"] for x in f["fields"]] == params[:len(f["fields"])]
    assert "Task Scheduler ends its keeper" in forms["boot-stop:platform"]["confirm"]["words"]
    assert forms["boot-remove:platform"]["confirm"]["danger"] and forms["boot-remove:platform"]["fields"][2]["type"] == "accept"


def test_the_command_line_registers_and_removes_a_boot_task(monkeypatch, tmp_path, capsys):
    fake = FakeWindows()
    a = plugin(fake, elevated=True, env=ME, apps=[PLATFORM], logs=tmp_path)
    monkeypatch.setattr(cli, "MACHINE", a)
    assert cli.main(["register", "platform", "--boot", "--port", "8781"]) == 0
    assert json.loads(capsys.readouterr().out)["port"] == 8781 and "LiminalPlatformBoot" in fake.boot_tasks
    assert cli.main(["startup", "platform", "start", "--boot"]) == 0 and "started" in capsys.readouterr().out
    assert cli.main(["unregister", "platform", "--boot"]) == 1 and "--accept-removal" in capsys.readouterr().err
    assert cli.main(["unregister", "platform", "--boot", "--accept-removal"]) == 0 and "LiminalPlatformBoot" not in fake.boot_tasks
    assert "removed" in capsys.readouterr().out
    assert cli.main(["boot"]) == 0 and json.loads(capsys.readouterr().out)[0]["state"] == "absent"
