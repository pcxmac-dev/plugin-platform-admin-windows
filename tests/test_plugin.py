"""Windows administration: the rights, the framework's services (started when stopped, never the SSH server, an
administrator asked for), the apps' scheduled tasks read, run, made and removed, the processes, all through a
stand-in powershell.exe (nothing changes here)."""
from __future__ import annotations

import json
import re
import sys

from liminal_libs.machines.windows import ERROR_MARK, PowerShell, decoded

from plugin_platform_admin_windows import MACHINE, TASKS, WindowsAdminPlugin, state_of


class FakeWindows:
    def __init__(self, denied=False):
        self.services = {"WSLService": "Stopped", "vmcompute": "Running", "MpsSvc": "Running", "Dnscache": "Running", "sshd": "Stopped"}
        self.tasks = {"LiminalCharts": {"State": "Running", "Execute": "C:\\venv\\pythonw.exe", "Arguments": "-m liminal_charts gui --no-browser --port 8765"},
                      "LiminalIntegrator-backtest": {"State": "Ready", "Execute": "C:\\venv\\pythonw.exe", "Arguments": "-m liminal_integrator service run --name backtest"}}
        self.denied = denied
        self.scripts: list[str] = []

    def __call__(self, args, timeout):
        s = decoded(args[6])
        self.scripts.append(s)
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


def plugin(fake, elevated=False, env=None):
    return WindowsAdminPlugin(PowerShell(runner=fake, env=env or {}), env=env or {}, elevated=elevated)


def test_the_plugin_reports_rights_services_startups_and_processes():
    assert MACHINE.name == "admin-windows" and MACHINE.KIND == "machine" and MACHINE.STEPS == ("privileges", "services", "startup")
    a = plugin(FakeWindows())
    st = a.status()
    services = {s["name"]: s for s in st["services"]}
    assert services["WSLService"]["state"] == "stopped" and services["com.docker.service"]["state"] == "absent" and not services["sshd"]["mayStart"]
    startups = {(s["app"], s["name"]): s for s in st["startups"]}
    assert startups[("charts", "LiminalCharts")]["state"] == "running" and "liminal_charts gui" in startups[("charts", "LiminalCharts")]["command"]
    assert startups[("login", "LiminalLogin")]["state"] == "absent" and ("integrator", "LiminalIntegrator-backtest") in startups
    assert [(p["pid"], p["app"]) for p in st["processes"]] == [(63336, "charts"), (51876, "integrator")]
    assert st["summary"] == "not elevated; services: 3 running, stopped: WSLService, sshd; startups: charts, integrator; 2 Liminal process(es)"
    assert "LIMINAL_ELEVATE=prompt" in st["elevation"] and plugin(FakeWindows(), env={"LIMINAL_ELEVATE": "prompt"}).elevation().endswith("(UAC)")
    assert state_of("Running") == "running" and state_of("StartPending") == "startpending"


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
    made = a.register("platform", python=sys.executable)
    script = next(s for s in fake.scripts if "Register-ScheduledTask" in s)
    assert "-TaskName 'LiminalPlatform'" in script and "New-ScheduledTaskTrigger -AtLogOn -User \"$env:USERDOMAIN\\$env:USERNAME\"" in script
    assert "-Argument '-m liminal_platform serve --no-browser'" in script and "-ExecutionTimeLimit ([TimeSpan]::Zero)" in script
    assert made.app == "platform" and made.state == "ready"
    a.startup("platform", "run")
    assert any("Start-ScheduledTask -TaskName 'LiminalPlatform'" in s for s in fake.scripts)
    a.service("WSLService", "restart")
    assert any("Restart-Service -Name 'WSLService'" in s for s in fake.scripts)
    assert a.unregister("platform") and not a.unregister("platform") and set(TASKS) == {"charts", "integrator", "login", "platform"}
    assert a.run("Write-Output", "'hello'") == "ran\r\n" and "Write-Output 'hello'" in fake.scripts[-1]
