# Changelog

## 0.4.2 (2026-11-24)

The command line's `run` asks Windows (UAC) only when `--elevated` is its first word (the review's finding PLT-H1,
checked 2026-11-23). And from the review of that change, 2026-11-24, each finding checked a second time: `register`
takes no program from an ask, and the changes are asked only from the page.

- **run's `--elevated`.** A `--elevated` among the command's own words was taken for the flag: Windows asked you (UAC),
  and the word was dropped from the command. Now it counts only as `run`'s first word: `run -- X --elevated` and
  `run X --elevated` run `X --elevated` as you, `run -- --elevated X` runs `--elevated X` as you, and
  `run --elevated -- X` asks Windows to run X. With no command, or with `--elevated` said twice before it, `run` shows
  the usage and runs nothing: in this release's first draft a second `--elevated` became the command's first word, and
  Windows asked you to run a script PowerShell then refused. `run()` is unchanged: as the platform runs, through
  Windows' prompt only when its caller says `elevated`, and a command refused as you is not asked again elevated. No
  route of the platform asks it any more (liminal-platform 0.34.1; the user, 2026-11-23: "Remove it"): this command
  line and `liminal-platform machine admin-windows run` ask it in their own process.
- **`register` takes no program from an ask** (the review's first finding, rated high; there since 0.1.0, at boot
  since 0.2.0). The library's `register(app, at, port, python)` takes the Python a task runs, and the platform's
  `POST /api/machines/admin-windows/ask` hands an ask's arguments on as they come. So a program of any account on this
  PC could put a program in `C:\Users\Public`, every account's to write, and ask `register` with
  `["platform", "logon", null, "C:\\Users\\Public\\x.exe"]`: the LiminalPlatform task was replaced and ran it at your
  next sign-in, as you, with no prompt, and `startup` ran it at once. With `["platform", "boot", 8775, ...]`
  LiminalPlatformBoot ran it at every boot, after a prompt (UAC) nobody asked for, or with none on a platform run as
  administrator. The page never sends that argument. Now the plugin's own `register(app, at, port)` has none: an ask
  naming a program is refused as too many arguments (the platform answers 400) before any script runs, and a task
  runs this Python's pythonw.exe, the platform's own.
- **The changes are asked only from the page** (`PAGE_ONLY_HOOKS`, liminal-libs 1.66.0's word; the review's second
  finding, rated medium): `service`, `startup`, `register` and `unregister`, at your logon and at boot. Another
  plugin's ask of one is refused (403), and liminal-platform 0.34.0 refuses one over HTTP (401) unless its login shows
  that you are at the page. Before, any program on this PC asked them with the two headers PLT-H1 named, the page's
  dialog being the only confirmation: on a platform run as administrator, sshd started, WSLService or Docker Desktop's
  service stopped, a boot task registered or removed (its "asked twice" an argument the asker sets), all with no
  prompt; on one that is not, Windows' prompt (UAC) for a change nobody asked for. A platform that holds no login asks
  them as before. The setup and the command line call the plugin's code directly, not through an ask, so they work as
  before; so do its reads (`present`, `status`, `processes`).
- Tests: `tests/test_run.py`, over a stand-in powershell.exe and a stand-in for Windows' prompt (nothing runs, nothing
  is elevated): run() as you, and through UAC only when elevated; the command line's cases, `run X --elevated` and
  `run -- --elevated X` among them (a parse taking `--elevated` from anywhere before the command's `--`, as the review
  found, or one taking the `--` first, passed the first draft's test and asked Windows), and the usage for no command
  and for `--elevated` said twice. `tests/test_who_asks.py`, through the library's own App: the changes
  refused to another plugin and to no one, nothing run, the page's ask run, the reads asked by anyone; `register`
  refusing a program, the page's ask included, no script sent.

## 0.4.1 (2026-11-15)

Drawn under the platform's OS plugins section, in the list on the left (the user: "then OS plugins" (the WSL distributions, the admin and the firewall plugins, as chosen)): `SECTION = "os"`, liminal-libs 1.51.0's machine-plugin attribute. liminal-platform 0.26.0 draws it; an older platform keeps the plugin under Machine plugins. Nothing else changes.

## 0.4.0 (2026-11-11)

Its API on its page, plugin API 2.2 (the user: "each plugin should reflect the the API its attached to, and present
links that provide documentation, the plugin interface should more or less contain what it already has, BUT, it should
also expose more of what the API is about"). Five cards (`apis.py`), each with Microsoft Learn's pages, every part of
the API said covered or not, and every call the plugin makes beside the API's other notable ones:
- Windows PowerShell 5.1: the command line it runs every script with, JSON, elevation through Start-Process -Verb RunAs
  (UAC), IsUserAnAdmin and the desktop check.
- ScheduledTasks: the tasks at your logon and the platform's at boot, read, run, ended, turned on and off, defined
  (the action, the logon or startup trigger, the S4U principal, the settings), registered and removed.
- Task Scheduler (COM): the boot tasks' read (the service, the root folder, each task's state, definition and
  principal).
- Windows services: Get-Service, Start-, Stop- and Restart-Service.
- CIM: Win32_Process: the framework's processes.

It keeps nothing of them between two reads: `api_facts()` stays the contract's ({}). Tests: the cards name every cmdlet
the plugin's scripts send over every read and change (a stand-in powershell.exe), the COM members of the boot read and
the library's own PowerShell calls; a link check runs with LIMINAL_VENDOR_PAGES=1. Needs liminal-libs>=1.49.0.

## 0.3.0 (2026-11-11)

Its page works unelevated (the user: "the administration plugins don't seem to work right"), on liminal-libs 1.48.0:
- Valid whenever it reads this PC: not running as administrator no longer disables it and takes it out of the tray. The
  rights are a fact on its page; each change confirmed there asks Windows (UAC) when Windows wants an administrator, or
  says it needs one where Windows cannot ask (on no desktop).
- Its page draws its own tables with confirmed forms: the services the framework relies on (Start…, Stop…, Restart…:
  through UAC when Windows wants an administrator; the setup's own starts still ask only with LIMINAL_ELEVATE=prompt),
  the startups at your logon (Register…, Run…, End…, Remove…: as you, no administrator), at boot (0.2.0's section), and
  the framework's processes. The status's lists are frameworkServices, logonStartups, bootServices, frameworkProcesses.

## 0.2.0 (2026-11-11)

The platform at boot, before anyone signs in (the user: "also windows and linux admin, need sections for starting the
platform, or an app that inherits the platform object as a service, headless"; "on boot"), on liminal-libs 1.47.0:
- A section on the plugin's page, At boot, before anyone signs in: the platform and each app inheriting it, its boot
  task's state, command, account and log, and its buttons: Register… (the port), Start…, Stop…, Remove… (asked twice),
  each confirmed in the page's dialog. Through the startups' own hooks: `register(app, "boot", port)`,
  `startup(app, "start" | "stop", "boot")`, `unregister(app, "boot", accept_removal)`.
- The boot task, `Liminal<App>Boot` (LiminalPlatformBoot beside the logon task LiminalPlatform): At startup, as the
  platform's user with no password stored (S4U) and its ordinary rights, on no desktop, running `pythonw.exe -m
  liminal_libs.machines.keep --log <platform>\logs\<app>-boot.log -- pythonw.exe -m <module> serve --no-browser --port
  N`; Task Scheduler's own retries (3, 1 min apart) for a start that failed, the keeper's after a failure.
- Read through Task Scheduler's COM, one read for them all: a task only an administrator may read is said as
  registered, its state unknown; one not At startup, storing a password or with the highest rights is said with what
  to do; one running whose page does not answer yet is starting.
- Registered and removed through Windows' prompt (UAC) unless the platform is elevated; started and stopped as you,
  through UAC when Windows wants an administrator.
- Valid when not elevated but Windows can ask you (on a desktop); on no desktop (a boot task's own platform) it says
  Windows cannot ask there.
- The command line: `boot`, `register APP --boot [--port N]`, `startup APP start|stop --boot`, `unregister APP --boot
  --accept-removal`.

## 0.1.0 (2026-11-07)

The first release: windows administration for the platform, on the library's Admin base
(liminal-libs 1.20.1).
