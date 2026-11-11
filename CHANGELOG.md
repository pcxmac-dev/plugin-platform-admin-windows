# Changelog

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
