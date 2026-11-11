# plugin-platform-admin-windows

Windows administration for Liminal: the platform's rights, the Windows services the framework relies on, the apps' scheduled tasks at logon, the platform's at boot, the framework's processes.

The user's words (2026-11-07): "the platform is the interface for the software/hardware which facilitates the
liminal framework"; "i also need a windows and linux firewall plugin for the platform"; "and a windows and
linux admin plugin for platform".

## What it does

A machine plugin of the platform (`liminal_libs.machines.admin.Admin`, plugin API 2.1), through PowerShell (the
library's `machines.windows.PowerShell`):

- The rights: whether the platform runs as administrator; with `LIMINAL_ELEVATE=prompt` a step needing them asks
  you (UAC) instead of failing.
- The services the framework relies on: WSLService, vmcompute (WSL 2's virtual machine), com.docker.service,
  MpsSvc (the firewall), Dnscache; the setup starts those stopped (an administrator's step); sshd is shown and
  never started by it.
- The apps' startups, scheduled tasks at your logon, as the integrator makes its own: LiminalCharts,
  LiminalIntegrator (and LiminalIntegrator-<name>), LiminalLogin, LiminalPlatform: read, run, ended, enabled,
  disabled, made (`register`) or removed (`unregister`) when asked; the setup makes none (nothing runs while you
  are not using it).
- The platform at boot, before anyone signs in (below).
- The framework's processes: their app, command line and memory.

Its page is its own tables, each change through a form confirmed in the page's dialog: **Services the framework relies
on** (Start…, Stop…, Restart…), **Startups at your logon** (Register…, Run…, End…, Remove…), **At boot, before anyone
signs in** (below) and **The framework's processes**.

The plugin is valid whenever it reads this PC, running as administrator or not (0.3.0): the rights are a fact on its
page. A change you confirm asks Windows (UAC) when Windows wants an administrator: a service's start, stop or restart,
a boot task's registration or removal. On no desktop (a platform a boot task started) Windows cannot ask, and the
change says so. A startup at your logon needs no administrator. The setup's own starts ask only with
`LIMINAL_ELEVATE=prompt`.

## At boot, before anyone signs in

The user's words (2026-11-11): "also windows and linux admin, need sections for starting the platform, or an app that
inherits the platform object as a service, headless"; "on boot".

The plugin's page has a section, **At boot, before anyone signs in**: a row for each app a boot task may start, the
platform first, then any app whose App class inherits the platform's (`liminal_platform.app.PlatformApp`: the app the
plugin is attached to, or one an installed distribution names under the `liminal.apps` entry points, as
`lab = "liminal_lab.app:LabApp"`). Each row says whether a boot task is registered for it, its state (running,
starting, stopped, disabled, not registered), the command it runs, the account it runs as and where its log goes, with
its buttons: **Register…** (its port), **Start…**, **Stop…**, **Remove…**. Each change is confirmed in the page's
dialog with the exact change; a removal is asked twice.

How a boot task differs from the startups at your logon:

| | At your logon (Startups) | At boot (this section) |
|---|---|---|
| Task | `LiminalPlatform` (`LiminalCharts`, `LiminalIntegrator`, `LiminalLogin`) | `LiminalPlatformBoot` (`Liminal<App>Boot`) |
| Trigger | At log on: yours | At startup |
| Runs | once you sign in, on your desktop | whether anyone is signed in or not, on no desktop |
| As | you, with your session | you, no password stored (S4U), your ordinary rights (never the highest) |
| Runs what | `pythonw.exe -m liminal_platform serve --no-browser` | `pythonw.exe -m liminal_libs.machines.keep --log …\<app>-boot.log -- pythonw.exe -m liminal_platform serve --no-browser --port N` |
| After a failure | as it ended | started again: 10 s, the wait doubling to 10 min while it keeps failing |
| Made | as you | as an administrator: Windows asks you (UAC) unless the platform is elevated |

- **No window, no browser.** pythonw.exe and `--no-browser`; never `--until-quiet`, so it stays up until stopped.
- **S4U** (no password stored) gives the task this PC's own resources only: no network shares, and what Windows keeps
  under your password (Credential Manager) may not be readable. The platform serves 127.0.0.1 and needs neither. The
  account needs "Log on as a batch job", which Administrators have by default; this plugin never changes that right.
- **Started again after a failure.** Task Scheduler starts a task again only when it could not start it (here 3
  times, 1 min apart), never when its program ends with an error, so the task runs the app through the library's
  keeper (`liminal_libs.machines.keep`, liminal-libs 1.47.0). The keeper holds the app in a job object: ending the
  task (Stop…) ends the app with it.
- **Its log**: `<platform folder>\logs\<app>-boot.log` (the keeper's starts and ends, the app's error output), beside
  the app's own `platform.log`.
- **One port each.** A boot task and the platform at your logon cannot share a port: the one started second finds it
  taken. The port field says what wants which port; a confirmation says so when it is the same.
- **Run as you.** Registered and removed through Windows' prompt (UAC) unless the platform runs as administrator;
  started and stopped as you, through UAC only when Windows wants an administrator. A task only an administrator may
  read is said as registered, its state unknown.
- **From the platform at your logon.** The platform a boot task serves runs on no desktop, where Windows cannot ask:
  its admin page still reads everything, and says so of each change; register, start, stop and remove boot tasks from
  the platform at your logon, or from the command line.

## From the command line

```
python -m plugin_platform_admin_windows status
python -m plugin_platform_admin_windows setup            # everything; or one step: setup services
python -m plugin_platform_admin_windows services
python -m plugin_platform_admin_windows startups
python -m plugin_platform_admin_windows register platform
python -m plugin_platform_admin_windows startup platform run
python -m plugin_platform_admin_windows boot                                    # the boot tasks
python -m plugin_platform_admin_windows register platform --boot --port 8775    # Windows asks (UAC)
python -m plugin_platform_admin_windows startup platform start --boot
python -m plugin_platform_admin_windows unregister platform --boot --accept-removal
python -m plugin_platform_admin_windows processes
```

The platform app drives the same hooks from its page.
