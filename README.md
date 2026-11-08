# plugin-platform-admin-windows

Windows administration for Liminal: the platform's rights, the Windows services the framework relies on, the apps' scheduled tasks at logon, the framework's processes.

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
- The framework's processes: their app, command line and memory.

## From the command line

```
python -m plugin_platform_admin_windows status
python -m plugin_platform_admin_windows setup            # everything; or one step: setup services
python -m plugin_platform_admin_windows services
python -m plugin_platform_admin_windows startups
python -m plugin_platform_admin_windows register platform
python -m plugin_platform_admin_windows startup platform run
python -m plugin_platform_admin_windows processes
```

The platform app drives the same hooks from its page.
