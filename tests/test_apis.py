"""What Windows administration attaches to (plugin API 2.2): its cards are sound; they name every cmdlet and COM call
its scripts send (the plugin driven through a stand-in powershell.exe over every read and change it makes) and the
library's PowerShell calls it runs them with; it keeps nothing to say of them (api_facts {}); and the cards' pages answer
(LIMINAL_VENDOR_PAGES=1 only, the one test that reaches the network)."""
from __future__ import annotations

import inspect
import os
import re

import pytest

from liminal_libs.machines import windows
from liminal_libs.sources.apis import dead_links, problems
from plugin_platform_admin_windows import BOOT_READ, MACHINE
from plugin_platform_admin_windows import apis as cards
from test_plugin import PLATFORM, FakeWindows, plugin, through_uac

YOU = {"USERNAME": "you", "USERDOMAIN": "PC"}
CMDLET = re.compile(r"\b(?:Get|Set|New|Start|Stop|Restart|Enable|Disable|Register|Unregister|Remove|Invoke|Export)-[A-Z][A-Za-z]+")


def drive(tmp_path):
    """Every read and every change the plugin makes, through the stand-in: the status (services, startups, boot tasks,
    processes), each service change, each startup task change, a startup registered and removed, the platform registered
    at boot through UAC, started, stopped and removed; the scripts it sent."""
    fake = FakeWindows()
    a = plugin(fake, apps=[PLATFORM], logs=tmp_path, env=YOU)
    through_uac(a)
    a.status()
    for action in ("start", "stop", "restart"):
        a.service("WSLService", action)
    for action in ("run", "end", "enable", "disable"):
        a.startup("charts", action)
    a.register("login")
    assert a.unregister("login")
    a.register("platform", at="boot", port=8775)
    assert a.startup("platform", "start", at="boot")["ok"] and a.startup("platform", "stop", at="boot")["ok"]
    assert a.unregister("platform", at="boot", accept_removal=True)["removed"]
    return a, fake


def used_cmdlets() -> set[str]:
    return {m for api in MACHINE.apis for c in api.used for m in CMDLET.findall(c.name)}


def test_the_cards_are_sound_and_each_says_where_its_documentation_is():
    assert problems(MACHINE.apis) == [] and MACHINE.apis == cards.APIS
    assert [a.name for a in MACHINE.apis] == ["Windows PowerShell 5.1", "ScheduledTasks (PowerShell)", "Task Scheduler (COM)",
                                              "Windows services (Microsoft.PowerShell.Management)", "CIM: Win32_Process"]
    assert all(a.docs.startswith("https://learn.microsoft.com/") and a.verified == "2026-11-11" for a in MACHINE.apis)
    assert all(a.used and a.covered and len(a.areas) > len(a.covered) for a in MACHINE.apis)  # more of each API than it uses
    assert not any(c.costs for a in MACHINE.apis for c in a.calls)  # nothing here costs money
    assert MACHINE.api_facts() == {}  # nothing kept between two reads


def test_the_cards_name_every_cmdlet_the_plugins_scripts_send(tmp_path):
    a, fake = drive(tmp_path)
    sent = {m for s in fake.scripts for m in CMDLET.findall(s)}
    named = used_cmdlets()
    assert sent <= named, sorted(sent - named)
    assert named - {"Start-Process"} <= sent, sorted(named - sent)  # Start-Process: the library's own (below)
    for c in cards.SCHEDULED_TASKS.used:  # each one's switches as the scripts send them
        words = [w for w in re.split(r"<[^>]+>", c.name) if w.strip()]
        assert any(all(w.strip() in s for w in words) for s in fake.scripts), c.name


def test_the_task_scheduler_card_names_the_com_calls_of_the_boot_read():
    for c in cards.TASK_SCHEDULER.used:
        for member in re.findall(r"\.([A-Z][A-Za-z]+)", c.name):
            assert member in BOOT_READ, f"{c.name}: {member} is not read"
    assert "New-Object -ComObject Schedule.Service" in BOOT_READ and ".GetTasks(1)" in BOOT_READ


def test_the_powershell_card_names_how_the_library_runs_and_elevates_the_scripts():
    args = windows.PowerShell(runner=lambda a, t: (0, "", "")).args("Get-Date")
    assert " ".join(args[:6]) + " <script>" == cards.POWERSHELL.calls[0].name
    assert "ConvertTo-Json -Compress -Depth 5" in inspect.getsource(windows.PowerShell.json)
    assert "Start-Process -FilePath powershell.exe -Verb RunAs -Wait" in inspect.getsource(windows.PowerShell.run_elevated)
    assert "IsUserAnAdmin" in inspect.getsource(windows.is_elevated)
    assert "GetUserObjectInformationW" in inspect.getsource(windows.interactive)


@pytest.mark.skipif(os.environ.get("LIMINAL_VENDOR_PAGES") != "1", reason="reaches the makers' pages: LIMINAL_VENDOR_PAGES=1")
def test_the_cards_pages_answer():
    assert dead_links(MACHINE.apis) == []
