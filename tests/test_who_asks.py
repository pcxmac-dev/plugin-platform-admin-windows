"""Who may ask the plugin's changes, and what an ask may name (0.4.2, the review of PLT-H1's fix, 2026-11-24). Its
changes are asked only from its page (PAGE_ONLY_HOOKS, as liminal-libs 1.66.0's apps/asking.py and liminal-platform
0.34.0 read them): a service started, stopped or restarted, and a startup run, ended, turned on or off, made or removed,
at your logon or at boot. Another plugin's ask is refused, and so is an ask that names no one; over HTTP the platform
also asks its login whether you are at the page. Before, any program on this PC asked them with two headers: on a
platform run as administrator, sshd started or WSLService stopped with no prompt. Its reads are asked by anyone, as
before. And register takes no program from an ask, the page's included: a task runs this Python (the test's, given to
the constructor). Before, a fourth argument named the program, which the LiminalPlatform task then ran at your next
sign-in, or LiminalPlatformBoot at every boot. Asked through the library's own App (its ask names who asks as the
platform's does), over a stand-in powershell.exe and a stand-in for Windows' prompt: nothing runs, nothing is elevated,
no task is registered."""
from __future__ import annotations

import sys

import pytest

from liminal_libs import internal
from liminal_libs.apps import App, asking
from liminal_libs.apps.authorization import EnvironmentLogin
from liminal_libs.machines.admin import interpreter
from liminal_libs.machines.plugin import MachinePlugin
from liminal_libs.machines.windows import wrapped

from plugin_platform_admin_windows import MACHINE
from test_plugin import ME, PLATFORM, FakeWindows, plugin, through_uac

CHANGES = ("service", "startup", "register", "unregister")
READS = ("present", "status", "processes")
PROGRAM = "C:\\Users\\Public\\x.exe"  # a program any account here could put there; nothing runs it


class Neighbour(MachinePlugin):
    """Another plugin of the platform, asking the admin plugin through its app as any plugin may (a container plugin,
    or the MCP plugin for a local agent)."""

    name, title = "neighbour", "Neighbour"

    def wants(self, hook, *args):
        """Not a hook: one of the admin plugin's asked through the app."""
        return self.app.ask("admin-windows", hook, *args)


class Platform(App):
    """The library's App asking as the platform does: from its page's route, the page named in so many words, or from
    its own code, no one named."""

    NAME, TITLE, ICON = "platform", "Platform", "chip"

    def from_page(self, hook, *args):
        """As the page's route asks a hook."""
        with asking.asking(asking.PAGE):
            return self.ask("admin-windows", hook, *args)

    def on_its_own(self, hook, *args):
        """As the app's own code asks a hook."""
        return self.ask("admin-windows", hook, *args)


@pytest.fixture
def attached(tmp_path):
    """The plugin on a platform run as administrator, where no change asks Windows (UAC) first: the review's worse case.
    Its boot app the platform, its logs in the test's folder, Windows' prompt a stand-in that records what it is asked;
    attached with another plugin to an app, let go after."""
    fake = FakeWindows()
    admin, neighbour = plugin(fake, elevated=True, env=ME, apps=[PLATFORM], logs=tmp_path), Neighbour()
    asked = through_uac(admin)
    app = Platform(log=lambda m: None, login=EnvironmentLogin(env={}))
    app.attach(admin)
    app.attach(neighbour)
    yield app, admin, neighbour, fake, asked
    app.detach(neighbour.name)
    app.detach(admin.name)


def test_its_changes_are_said_to_be_asked_only_from_its_page_and_its_reads_by_anyone():
    assert set(internal.page_only(MACHINE)) == set(CHANGES)  # what the platform reads
    assert internal.plugin_only(MACHINE) == ()
    assert internal.problems(MACHINE) == []  # its own register says what it does, on the Internal API tab
    for hook in CHANGES:
        assert asking.refusal(MACHINE, hook, asking.PAGE) == ""
        assert asking.refusal(MACHINE, hook, "neighbour") == (f"admin-windows's {hook} is asked only from its page, "
                                                              "never by another plugin: neighbour asked it.")
        assert asking.refusal(MACHINE, hook, None).endswith("This ask names no asker: neither the page nor a plugin.")
    for hook in READS:
        assert {asking.refusal(MACHINE, hook, who) for who in (asking.PAGE, "neighbour", None)} == {""}


def test_another_plugin_or_no_one_asking_a_change_runs_nothing_and_its_page_does(attached):
    app, admin, neighbour, fake, asked = attached
    for ask in (lambda: neighbour.wants("service", "sshd", "start"),  # the SSH server, which the setup never starts
                lambda: neighbour.wants("service", "WSLService", "stop"),
                lambda: app.on_its_own("service", "com.docker.service", "stop"),
                lambda: neighbour.wants("register", "platform"),
                lambda: neighbour.wants("startup", "charts", "end"),
                lambda: neighbour.wants("unregister", "charts"),
                lambda: neighbour.wants("register", "platform", "boot", 8775),
                lambda: neighbour.wants("startup", "platform", "start", "boot"),
                lambda: neighbour.wants("unregister", "platform", "boot", True)):  # its second confirmation said
        with pytest.raises(asking.AskRefused, match="is asked only from its page"):
            ask()
    assert fake.scripts == [] and asked == [] and fake.boot_tasks == {}  # nothing run nor read, Windows not asked
    assert "LiminalCharts" in fake.tasks and fake.services["sshd"] == "Stopped"
    assert neighbour.wants("present") is True and neighbour.wants("processes")[0]["app"] == "charts"  # reads, as before
    assert app.from_page("service", "WSLService", "start") is None
    assert fake.scripts[-1] == wrapped("Start-Service -Name 'WSLService'") and fake.services["WSLService"] == "Running"
    assert asked == []  # run as administrator: as it is, no prompt


def test_register_takes_no_program_from_an_ask_the_pages_included(attached):
    """The review's case: the library's register took the program a task runs as its fourth argument, and the platform
    hands an ask's arguments on as they come. Asked from the page too, or of the plugin itself (as the platform's ask
    calls it): refused before any script runs. Asked as the page asks it, the task runs this Python (the test's)."""
    app, admin, neighbour, fake, asked = attached
    for ask in (lambda: app.from_page("register", "platform", "logon", None, PROGRAM),  # at your next sign-in, as you
                lambda: app.from_page("register", "platform", "boot", 8775, PROGRAM),  # at every boot
                lambda: admin.ask("register", "charts", "logon", None, PROGRAM),
                lambda: admin.ask("register", "platform", "boot", 8775, PROGRAM),
                lambda: admin.ask("register", "charts", python=PROGRAM)):
        with pytest.raises(TypeError):
            ask()
    assert fake.scripts == [] and asked == [] and "LiminalPlatform" not in fake.tasks and fake.boot_tasks == {}
    mine = interpreter(sys.executable)  # this Python, or its pythonw.exe beside it on Windows
    assert app.from_page("register", "platform").app == "platform"  # the page's form: the app and when, nothing more
    assert fake.tasks["LiminalPlatform"]["Execute"] == mine
    assert app.from_page("register", "platform", "boot", 8775).at == "boot"  # and at boot, its port
    assert fake.boot_tasks["LiminalPlatformBoot"]["Execute"] == mine
    assert not any(PROGRAM in s for s in fake.scripts) and asked == []
