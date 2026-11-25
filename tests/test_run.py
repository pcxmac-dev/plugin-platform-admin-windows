"""The plugin's run(): a PowerShell command on this PC, as the platform runs, and through Windows' prompt (UAC) only when
its caller says `elevated` (the review's PLT-H1, 2026-11-23); a command refused as you is not asked again elevated. The
platform's POST /api/machines/{name}/run let any local program hand it any words; that route is gone (liminal-platform
0.34.1), and the command lines ask run() in their own process. This one's `--elevated` counts only as run's first word
(0.4.2): one among the command's words was taken for the flag, so Windows asked and the word was dropped; one said
twice went to Windows' prompt as the command's first word. Over a stand-in powershell.exe and a stand-in for Windows'
prompt: nothing runs, nothing is elevated."""
from __future__ import annotations

import pytest

from liminal_libs.machines.plugin import CommandError
from liminal_libs.machines.windows import wrapped

import plugin_platform_admin_windows.__main__ as cli
from test_plugin import FakeWindows, plugin


def windows_asked(a) -> list[str]:
    """Windows' prompt (UAC) as a stand-in answering yes that runs nothing: the scripts it was asked to run elevated."""
    asked: list[str] = []

    def elevated(script, timeout=600.0):
        asked.append(script)
        return "elevated\r\n"
    a.ps.run_elevated = elevated
    return asked


def test_a_command_runs_as_the_platform_runs_and_through_uac_only_when_elevated():
    fake = FakeWindows()
    a = plugin(fake)
    asked = windows_asked(a)
    assert a.run("Write-Output", "'as you'") == "ran\r\n" and asked == []
    assert fake.scripts == [wrapped("Write-Output 'as you'")]  # its words as one script, nothing in front
    assert a.run("Write-Output", "'as you'", elevated=False) == "ran\r\n" and asked == [] and len(fake.scripts) == 2
    assert a.run("Restart-Service", "-Name", "'WSLService'", elevated=True) == "elevated\r\n"
    assert asked == ["Restart-Service -Name 'WSLService'"] and len(fake.scripts) == 2  # Windows asked: nothing ran as you
    assert fake.services["WSLService"] == "Stopped"


def test_a_command_refused_as_you_is_not_asked_again_elevated():
    """Unlike a change confirmed on the page (a service's, a boot task's: through UAC once Windows says an administrator
    is wanted), run() says the refusal, LIMINAL_ELEVATE=prompt or not."""
    fake = FakeWindows(denied=True)
    a = plugin(fake, env={"LIMINAL_ELEVATE": "prompt"})
    asked = windows_asked(a)
    with pytest.raises(CommandError, match="Access is denied") as refused:
        a.run("Start-Service", "-Name", "'WSLService'")
    assert refused.value.denied and asked == [] and len(fake.scripts) == 1 and fake.services["WSLService"] == "Stopped"


def test_elevated_where_windows_cannot_ask_runs_nothing():
    fake = FakeWindows()
    a = plugin(fake, interactive=False)  # a boot task's own platform, on no desktop: the library's prompt refuses at once
    with pytest.raises(CommandError, match="cannot ask you") as refused:
        a.run("Restart-Service", "-Name", "'WSLService'", elevated=True)
    assert refused.value.denied and fake.scripts == []  # not run as you instead


def test_the_command_line_asks_windows_only_when_elevated_is_its_first_word(monkeypatch, capsys):
    """`run -- X` as you; `run --elevated -- X` through Windows' prompt (UAC); `run -- X --elevated` and, without the
    `--`, `run X --elevated`: X with its own word, as you (until 0.4.2 the word was taken out of X, and Windows asked);
    `run -- --elevated X`: the command's first word, as you; `run --elevated X` and `run --elevated -- X --elevated`:
    through UAC, the command's words as they are. A parse taking `--elevated` from anywhere before the command's `--`,
    or the `--` first and `--elevated` after it, passed 0.4.2's first draft of this test and asked Windows for X."""
    fake = FakeWindows()
    a = plugin(fake)
    asked = windows_asked(a)
    monkeypatch.setattr(cli, "MACHINE", a)
    assert cli.main(["run", "--", "Write-Output", "'as you'"]) == 0
    assert asked == [] and fake.scripts == [wrapped("Write-Output 'as you'")]
    assert cli.main(["run", "--elevated", "--", "Restart-Service", "-Name", "'WSLService'"]) == 0
    assert asked == ["Restart-Service -Name 'WSLService'"] and len(fake.scripts) == 1
    # a --elevated that is not run's first word is the command's own: run as you, the word kept, Windows not asked
    assert cli.main(["run", "--", "Write-Output", "--elevated"]) == 0
    assert cli.main(["run", "Write-Output", "--elevated"]) == 0  # without the `--`, still the first word only
    assert cli.main(["run", "--", "--elevated", "Write-Output"]) == 0  # the command's own first word, after its `--`
    assert len(asked) == 1
    assert fake.scripts[1:] == [wrapped("Write-Output --elevated")] * 2 + [wrapped("--elevated Write-Output")]
    assert cli.main(["run", "--elevated", "Write-Output", "'elevated'"]) == 0  # the flag first, without the `--`
    assert cli.main(["run", "--elevated", "--", "Write-Output", "--elevated"]) == 0  # through UAC, its own word kept
    assert asked[1:] == ["Write-Output 'elevated'", "Write-Output --elevated"] and len(fake.scripts) == 4
    assert capsys.readouterr().out == "ran\r\nelevated\r\n" + "ran\r\n" * 3 + "elevated\r\n" * 2


def test_the_command_line_runs_nothing_without_a_command_or_with_elevated_said_twice(monkeypatch, capsys):
    """No command, or `--elevated` said twice before it: the usage, nothing run and Windows not asked. In 0.4.2's first
    draft a second `--elevated` became the command's first word: Windows asked you (UAC) to run `--elevated -- X`, a
    script PowerShell refuses, so you said yes and X did not run."""
    fake = FakeWindows()
    a = plugin(fake)
    asked = windows_asked(a)
    monkeypatch.setattr(cli, "MACHINE", a)
    for alone in (["run"], ["run", "--"], ["run", "--elevated"], ["run", "--elevated", "--"],
                  ["run", "--elevated", "--elevated"],
                  ["run", "--elevated", "--elevated", "--", "Restart-Service", "-Name", "'WSLService'"]):
        assert cli.main(alone) == 2, alone
        assert "run [--elevated] -- COMMAND" in capsys.readouterr().err
    assert asked == [] and fake.scripts == []  # nothing run, Windows not asked
