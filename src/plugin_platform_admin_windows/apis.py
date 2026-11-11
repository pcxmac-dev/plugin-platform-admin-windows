"""What Windows administration attaches to (plugin API 2.2, liminal_libs.sources.apis; the user, 2026-11-11: "each
plugin should reflect the the API its attached to, and present links that provide documentation ... it should also
expose more of what the API is about"): Windows PowerShell itself and its elevation (UAC), the ScheduledTasks cmdlets,
Task Scheduler's COM objects, the service cmdlets and CIM's Win32_Process, each as Microsoft Learn describes it. Every
address was read on 2026-11-11 (`VERIFIED`).

The scripts are this plugin's (and the library's machines.windows.PowerShell runs them); the plugin keeps nothing of
these APIs between two reads, so it has no facts to say (the contract's api_facts: {})."""
from __future__ import annotations

from liminal_libs.sources.apis import Api, Area, Call, Link

VERIFIED = "2026-11-11"
PS51 = "?view=powershell-5.1"
WS = "?view=windowsserver2025-ps"
MODULE = "https://learn.microsoft.com/en-us/powershell/module/"
TASKS = MODULE + "scheduledtasks/"
MANAGEMENT = MODULE + "microsoft.powershell.management/"
TASKSCHD = "https://learn.microsoft.com/en-us/windows/win32/taskschd/"
WIN32 = "https://learn.microsoft.com/en-us/windows/win32/"

POWERSHELL = Api(
    name="Windows PowerShell 5.1",
    maker="Microsoft",
    about=("The shell every Windows 11 has, its cmdlets returning objects. The plugin runs each read and each change as "
           "one windowless powershell.exe, its script given encoded, the objects back as JSON; a change that needs an "
           "administrator runs in a second PowerShell started elevated, which Windows asks you to allow (UAC), or is "
           "refused where Windows cannot ask (on no desktop)."),
    kind="powershell",
    base="powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -EncodedCommand <script>",
    version="Windows PowerShell 5.1 (Windows' own; not PowerShell 7)",
    auth=("the platform's Windows user; an administrator's rights when the platform runs elevated, else through UAC: "
          "Windows asks you, on your desktop"),
    limits="",
    costs="",
    links=(
        Link("What is Windows PowerShell?", "https://learn.microsoft.com/en-us/powershell/scripting/what-is-windows-powershell" + PS51,
             "docs"),
        Link("about_PowerShell_exe", MODULE + "microsoft.powershell.core/about/about_powershell_exe" + PS51, "reference"),
        Link("Start-Process", MANAGEMENT + "start-process" + PS51, "reference"),
        Link("ConvertTo-Json", MODULE + "microsoft.powershell.utility/convertto-json" + PS51, "reference"),
        Link("User Account Control", "https://learn.microsoft.com/en-us/windows/security/application-security/application-control/user-account-control/",
             "guide"),
        Link("Differences from Windows PowerShell 5.1 (PowerShell 7)",
             "https://learn.microsoft.com/en-us/powershell/scripting/whats-new/differences-from-windows-powershell?view=powershell-7.6",
             "changelog"),
    ),
    areas=(
        Area("The command line", "powershell.exe's switches: no profile, no prompts, a script given encoded",
             MODULE + "microsoft.powershell.core/about/about_powershell_exe" + PS51,
             covered="every read and change: windowless, its words back as one line when it fails"),
        Area("Objects as JSON", "a cmdlet's objects written out as JSON", MODULE + "microsoft.powershell.utility/convertto-json" + PS51,
             covered="each read's rows"),
        Area("Elevation (UAC)", "an administrator's rights, asked of you by Windows",
             "https://learn.microsoft.com/en-us/windows/security/application-security/application-control/user-account-control/",
             covered="a change that needs them runs elevated: Windows asks you; on no desktop it is refused at once"),
        Area("Execution policies", "which scripts PowerShell runs", MODULE + "microsoft.powershell.core/about/about_execution_policies" + PS51,
             covered="Bypass, for the plugin's own scripts only"),
        Area("COM objects", "Windows' COM objects made from PowerShell", MODULE + "microsoft.powershell.utility/new-object" + PS51,
             covered="Task Scheduler's (its own card)"),
        Area("Profiles", "the scripts PowerShell runs as it starts, for each user and host",
             MODULE + "microsoft.powershell.core/about/about_profiles" + PS51),
        Area("Remoting", "commands run on other computers (WinRM)", MODULE + "microsoft.powershell.core/about/about_remote" + PS51),
        Area("PowerShell 7", "the newer, cross-platform PowerShell (pwsh), installed beside 5.1",
             "https://learn.microsoft.com/en-us/powershell/scripting/install/install-powershell-on-windows?view=powershell-7.6"),
    ),
    calls=(
        Call("powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -EncodedCommand <script>",
             "a script run windowless", "The command line", used="every read and change",
             docs=MODULE + "microsoft.powershell.core/about/about_powershell_exe" + PS51),
        Call("ConvertTo-Json -Compress -Depth 5", "objects as JSON", "Objects as JSON", used="each read's rows",
             docs=MODULE + "microsoft.powershell.utility/convertto-json" + PS51),
        Call("Start-Process -FilePath powershell.exe -Verb RunAs -Wait", "a second PowerShell started elevated: Windows asks",
             "Elevation (UAC)", used="a change that needs an administrator (its words back through a file)",
             docs=MANAGEMENT + "start-process" + PS51, writes=True),
        Call("IsUserAnAdmin (shell32)", "whether this process has an administrator's rights", "Elevation (UAC)",
             used="the rights the page says, and whether a change runs as it is",
             docs=WIN32 + "api/shlobj_core/nf-shlobj_core-isuseranadmin"),
        Call("GetUserObjectInformationW (user32, UOI_FLAGS)", "whether this process's window station is visible",
             "Elevation (UAC)", used="whether Windows can ask you here (a boot service's platform has no desktop)",
             docs=WIN32 + "api/winuser/nf-winuser-getuserobjectinformationw"),
        Call("New-Object -ComObject <name>", "a COM object", "COM objects", used="Task Scheduler's Schedule.Service",
             docs=MODULE + "microsoft.powershell.utility/new-object" + PS51),
        Call("New-TimeSpan -Minutes <n>", "a span of time", "The command line", used="a boot task's restart interval",
             docs=MODULE + "microsoft.powershell.utility/new-timespan" + PS51),
        Call("Invoke-Command -ComputerName <computer>", "a script run on another computer", "Remoting",
             docs=MODULE + "microsoft.powershell.core/invoke-command" + PS51),
    ),
    verified=VERIFIED,
)

SCHEDULED_TASKS = Api(
    name="ScheduledTasks (PowerShell)",
    maker="Microsoft",
    about=("Windows' Task Scheduler through PowerShell: tasks read with their state and last result, run and ended, turned "
           "on and off, and defined from an action, a trigger, a principal and settings, then registered or removed. The "
           "plugin keeps each Liminal app's startup at your logon as such a task, and the platform's start at boot "
           "(Liminal<App>Boot: At startup, as you with no password stored)."),
    kind="powershell",
    base="the ScheduledTasks module (Windows PowerShell 5.1)",
    version="the ScheduledTasks module of Windows 11 and Windows Server 2025",
    auth=("a task at your logon: as you, no administrator; a boot task: registered and removed as an administrator "
          "(Windows asks, UAC), started and stopped as you, or through UAC when Windows wants an administrator"),
    limits="",
    costs="",
    links=(
        Link("ScheduledTasks module", TASKS + WS, "reference"),
        Link("Task Scheduler", TASKSCHD + "task-scheduler-start-page", "docs"),
        Link("New-ScheduledTaskPrincipal", TASKS + "new-scheduledtaskprincipal" + WS, "reference"),
        Link("Register-ScheduledTask", TASKS + "register-scheduledtask" + WS, "reference"),
        Link("Security contexts for running tasks", TASKSCHD + "security-contexts-for-running-tasks", "auth"),
        Link("Schtasks.exe", TASKSCHD + "schtasks", "tool"),
    ),
    areas=(
        Area("Reading tasks", "a task's definition, its state, its last run and result", TASKS + "get-scheduledtask" + WS,
             covered="the apps' tasks at your logon (Liminal*): their state, command, last run and result"),
        Area("Running and ending", "a task started now, or every running instance ended", TASKS + "start-scheduledtask" + WS,
             covered="Run and End (at logon); Start and Stop (at boot)"),
        Area("Turning on and off", "a task enabled or disabled", TASKS + "enable-scheduledtask" + WS,
             covered="Enable and Disable (at logon)"),
        Area("Defining a task", "its action, trigger, principal and settings", TASKS + "new-scheduledtaskaction" + WS,
             covered=("at logon: the app's command, at your logon, as you; at boot: the keeper's command, At startup, S4U "
                      "with your ordinary rights, three restarts a minute apart, no time limit")),
        Area("Registering and removing", "a task registered on this PC, or unregistered", TASKS + "register-scheduledtask" + WS,
             covered="Register and Remove, each confirmed; a boot task's removal asked twice"),
        Area("Changing a task", "a registered task's triggers, actions or settings changed", TASKS + "set-scheduledtask" + WS),
        Area("Exporting", "a task as Task Scheduler's XML", TASKS + "export-scheduledtask" + WS),
        Area("Clustered tasks", "tasks of a failover cluster", TASKS + "get-clusteredscheduledtask" + WS),
    ),
    calls=(
        Call("Get-ScheduledTask -TaskName 'Liminal*'", "the tasks whose names start so", "Reading tasks",
             used="the startups at your logon", docs=TASKS + "get-scheduledtask" + WS),
        Call("Get-ScheduledTaskInfo", "a task's last run time and result", "Reading tasks", used="each startup's last run",
             docs=TASKS + "get-scheduledtaskinfo" + WS),
        Call("Start-ScheduledTask", "a task run now", "Running and ending", used="Run (logon), Start (boot)",
             docs=TASKS + "start-scheduledtask" + WS, writes=True),
        Call("Stop-ScheduledTask", "every running instance of a task ended", "Running and ending",
             used="End (logon), Stop (boot), before a boot task's removal", docs=TASKS + "stop-scheduledtask" + WS, writes=True),
        Call("Enable-ScheduledTask", "a task turned on", "Turning on and off", used="Enable (logon)",
             docs=TASKS + "enable-scheduledtask" + WS, writes=True),
        Call("Disable-ScheduledTask", "a task turned off", "Turning on and off", used="Disable (logon)",
             docs=TASKS + "disable-scheduledtask" + WS, writes=True),
        Call("New-ScheduledTaskAction -Execute <program> -Argument <words>", "what a task runs", "Defining a task",
             used="the app's command; at boot, the keeper's", docs=TASKS + "new-scheduledtaskaction" + WS),
        Call("New-ScheduledTaskTrigger -AtLogOn -User <you>", "a trigger at your logon", "Defining a task",
             used="a startup at your logon", docs=TASKS + "new-scheduledtasktrigger" + WS),
        Call("New-ScheduledTaskTrigger -AtStartup", "a trigger at boot", "Defining a task", used="the platform at boot",
             docs=TASKS + "new-scheduledtasktrigger" + WS),
        Call("New-ScheduledTaskPrincipal -UserId <you> -LogonType S4U -RunLevel Limited",
             "who a task runs as: you, no password stored, your ordinary rights", "Defining a task",
             used="the platform at boot (S4U: this PC's own resources only)", docs=TASKS + "new-scheduledtaskprincipal" + WS),
        Call("New-ScheduledTaskSettingsSet", "a task's settings: time limit, instances, batteries, restarts", "Defining a task",
             used="no time limit, one instance, on batteries too; at boot, three restarts a minute apart",
             docs=TASKS + "new-scheduledtasksettingsset" + WS),
        Call("Register-ScheduledTask", "a task registered (replaced with -Force)", "Registering and removing",
             used="Register… (at logon; at boot through UAC)", docs=TASKS + "register-scheduledtask" + WS, writes=True),
        Call("Unregister-ScheduledTask", "a task removed", "Registering and removing", used="Remove… (at boot asked twice)",
             docs=TASKS + "unregister-scheduledtask" + WS, writes=True),
        Call("Set-ScheduledTask", "a registered task changed", "Changing a task", docs=TASKS + "set-scheduledtask" + WS,
             writes=True),
        Call("Export-ScheduledTask", "a task's XML", "Exporting", docs=TASKS + "export-scheduledtask" + WS),
        Call("New-ScheduledTask", "a task definition made whole, not registered", "Defining a task",
             docs=TASKS + "new-scheduledtask" + WS),
    ),
    verified=VERIFIED,
)

TASK_SCHEDULER = Api(
    name="Task Scheduler (COM)",
    maker="Microsoft",
    about=("Task Scheduler 2.0's scripting objects: the service, its folders, each registered task with its definition "
           "(triggers, actions, principal) and its run-time state. The plugin reads its boot tasks through them, which "
           "tells a task an administrator alone may read (said as registered) from one that is not there, and shows who a "
           "task runs as and how."),
    kind="system",
    base="Schedule.Service, made from PowerShell (New-Object -ComObject)",
    version="Task Scheduler 2.0 (Windows Vista and later)",
    auth=("the platform's Windows user: a task only an administrator may read is denied, and said as registered with its "
          "state unknown"),
    limits="",
    costs="",
    links=(
        Link("Task Scheduler", TASKSCHD + "task-scheduler-start-page", "docs"),
        Link("Task Scheduler reference", TASKSCHD + "task-scheduler-reference", "reference"),
        Link("Task Scheduler scripting objects", TASKSCHD + "task-scheduler-objects", "reference"),
        Link("Task Scheduler schema", TASKSCHD + "task-scheduler-schema", "spec"),
        Link("Task Scheduler error and success constants", TASKSCHD + "task-scheduler-error-and-success-constants", "reference"),
        Link("Security contexts for running tasks", TASKSCHD + "security-contexts-for-running-tasks", "auth"),
    ),
    areas=(
        Area("TaskService", "the connection to Task Scheduler and its root folder", TASKSCHD + "taskservice",
             covered="connected on this PC, its root folder opened"),
        Area("TaskFolder", "a folder's tasks, registering and deleting them", TASKSCHD + "taskfolder",
             covered="the root folder's tasks named Liminal<App>Boot, hidden ones too, and each boot task asked by name"),
        Area("RegisteredTask", "a task's name, state, whether it is on, its last run and result", TASKSCHD + "registeredtask",
             covered="each boot task's state (TASK_STATE), last run and last result in words"),
        Area("TaskDefinition", "a task's triggers, actions, principal and settings", TASKSCHD + "taskdefinition",
             covered="whether it has an At startup trigger, and what it runs"),
        Area("Principal", "who a task runs as, its logon type and run level", TASKSCHD + "principal",
             covered="a boot task that stores a password or runs with the highest rights is said, to be registered again"),
        Area("Triggers", "when a task starts: at boot, at logon, on a schedule, on an event", TASKSCHD + "boottrigger",
             covered="the boot trigger looked for (type 8)"),
        Area("Actions", "what a task does: a command (ExecAction), a COM handler", TASKSCHD + "execaction",
             covered="the command and its arguments; the app's own port read from them"),
        Area("Running tasks", "a running instance's state, stopping it", TASKSCHD + "runningtask"),
        Area("Results", "the codes a task's last run ends with", TASKSCHD + "task-scheduler-error-and-success-constants",
             covered="0, running, not run yet and ended by request said in words; any other as Windows' hexadecimal code"),
    ),
    calls=(
        Call("TaskService.Connect()", "connected to Task Scheduler on this PC", "TaskService", used="the boot tasks' read",
             docs=TASKSCHD + "taskservice-connect"),
        Call("TaskService.GetFolder('\\')", "the root folder", "TaskService", used="the boot tasks' read",
             docs=TASKSCHD + "taskservice-getfolder"),
        Call("TaskFolder.GetTasks(1)", "the folder's tasks, hidden ones included", "TaskFolder",
             used="every Liminal<App>Boot task", docs=TASKSCHD + "taskfolder-gettasks"),
        Call("TaskFolder.GetTask(<name>)", "one task by name", "TaskFolder",
             used="each boot app's task: denied means only an administrator may read it", docs=TASKSCHD + "taskfolder-gettask"),
        Call("RegisteredTask.State, .Enabled, .LastRunTime, .LastTaskResult", "a task's run-time state", "RegisteredTask",
             used="each boot task's state and last result", docs=TASKSCHD + "registeredtask-state"),
        Call("RegisteredTask.Definition", "a task's definition", "TaskDefinition",
             used="its triggers, its first ExecAction, its principal", docs=TASKSCHD + "registeredtask-definition"),
        Call("Principal.UserId, .LogonType, .RunLevel", "who it runs as and how", "Principal",
             used="as you, S4U (2), your ordinary rights (0)", docs=TASKSCHD + "principal-logontype"),
        Call("TaskFolder.RegisterTaskDefinition()", "a task registered through COM", "TaskFolder",
             docs=TASKSCHD + "taskfolder-registertaskdefinition", writes=True),
        Call("TaskFolder.DeleteTask()", "a task deleted through COM", "TaskFolder", docs=TASKSCHD + "taskfolder-deletetask",
             writes=True),
        Call("RegisteredTask.Run()", "a task run now through COM", "RegisteredTask", docs=TASKSCHD + "registeredtask-run",
             writes=True),
    ),
    verified=VERIFIED,
)

SERVICES = Api(
    name="Windows services (Microsoft.PowerShell.Management)",
    maker="Microsoft",
    about=("Windows' services through PowerShell: each service's state and start type, and starting, stopping or "
           "restarting one, which Windows reserves for an administrator. The plugin shows the services the framework "
           "relies on (WSL, its virtual machine's host, Docker Desktop's, the firewall, DNS, and the SSH server, shown "
           "only) and starts, stops or restarts one when you confirm it."),
    kind="powershell",
    base="Get-Service and its companions (Windows PowerShell 5.1)",
    version="Microsoft.PowerShell.Management of Windows PowerShell 5.1",
    auth=("reading: no rights needed; starting, stopping, restarting: an administrator (UAC when Windows asks; the setup's "
          "own starts ask only with LIMINAL_ELEVATE=prompt)"),
    limits="",
    costs="",
    links=(
        Link("Get-Service", MANAGEMENT + "get-service" + PS51, "reference"),
        Link("Services", WIN32 + "services/services", "docs"),
        Link("Microsoft.PowerShell.Management module", MANAGEMENT + PS51, "reference"),
    ),
    areas=(
        Area("Reading services", "each service's name, display name, state and start type", MANAGEMENT + "get-service" + PS51,
             covered="the framework's services: running, stopped or absent, and how each starts"),
        Area("Starting, stopping, restarting", "a service started, stopped, or both", MANAGEMENT + "start-service" + PS51,
             covered="Start…, Stop…, Restart…, each confirmed; the setup starts those stopped, never the SSH server"),
        Area("A service's settings", "its start type, display name, description", MANAGEMENT + "set-service" + PS51),
        Area("Pausing", "a service suspended and resumed, where it can be", MANAGEMENT + "suspend-service" + PS51),
        Area("Making services", "a new Windows service", MANAGEMENT + "new-service" + PS51),
    ),
    calls=(
        Call("Get-Service -Name <names>", "the services named", "Reading services", used="the framework's services table",
             docs=MANAGEMENT + "get-service" + PS51),
        Call("Start-Service -Name <name>", "a service started", "Starting, stopping, restarting", used="Start…; the setup",
             docs=MANAGEMENT + "start-service" + PS51, writes=True),
        Call("Stop-Service -Name <name>", "a service stopped", "Starting, stopping, restarting", used="Stop…",
             docs=MANAGEMENT + "stop-service" + PS51, writes=True),
        Call("Restart-Service -Name <name>", "a service stopped and started", "Starting, stopping, restarting",
             used="Restart…", docs=MANAGEMENT + "restart-service" + PS51, writes=True),
        Call("Set-Service", "a service's start type or names changed", "A service's settings",
             docs=MANAGEMENT + "set-service" + PS51, writes=True),
        Call("Suspend-Service", "a service paused", "Pausing", docs=MANAGEMENT + "suspend-service" + PS51, writes=True),
        Call("Resume-Service", "a paused service resumed", "Pausing", docs=MANAGEMENT + "resume-service" + PS51, writes=True),
        Call("New-Service", "a Windows service made", "Making services", docs=MANAGEMENT + "new-service" + PS51, writes=True),
    ),
    verified=VERIFIED,
)

PROCESSES = Api(
    name="CIM: Win32_Process",
    maker="Microsoft",
    about=("Windows Management Instrumentation's class for a process, read through PowerShell's CIM cmdlets: its id, "
           "command line, memory and more, filtered by a WQL condition. The plugin lists the framework's processes with "
           "it: the Python processes whose command line names a Liminal app, and their memory."),
    kind="powershell",
    base="Get-CimInstance Win32_Process (root/cimv2)",
    version="the Win32_Process class of Windows Vista and later, through CimCmdlets",
    auth="the platform's Windows user: another user's process may show no command line",
    limits="",
    costs="",
    links=(
        Link("Win32_Process class", WIN32 + "cimwin32prov/win32-process", "reference"),
        Link("Get-CimInstance", MODULE + "cimcmdlets/get-ciminstance" + PS51, "reference"),
        Link("WMI", WIN32 + "wmisdk/wmi-start-page", "docs"),
        Link("WQL (SQL for WMI)", WIN32 + "wmisdk/wql-sql-for-wmi", "guide"),
        Link("CimCmdlets module", MODULE + "cimcmdlets/" + PS51, "reference"),
    ),
    areas=(
        Area("Win32_Process", "a process: its id, name, command line, memory, times, owner", WIN32 + "cimwin32prov/win32-process",
             covered="ProcessId, CommandLine and WorkingSetSize of the framework's Python processes"),
        Area("Querying (WQL)", "instances filtered by a condition", WIN32 + "wmisdk/wql-sql-for-wmi",
             covered="Name LIKE 'python%', then the command lines naming liminal_"),
        Area("Methods", "a process made, ended, its owner or priority asked", WIN32 + "cimwin32prov/terminate-method-in-class-win32-process"),
        Area("Remote computers", "CIM sessions to another machine", MODULE + "cimcmdlets/new-cimsession" + PS51),
        Area("Other classes", "Win32_Service and the rest of the Win32 provider", WIN32 + "cimwin32prov/win32-provider"),
    ),
    calls=(
        Call("Get-CimInstance Win32_Process -Filter \"Name LIKE 'python%'\"", "the Python processes", "Win32_Process",
             used="the framework's processes table: id, app, command, memory", docs=MODULE + "cimcmdlets/get-ciminstance" + PS51),
        Call("Invoke-CimMethod -MethodName Terminate", "a process ended", "Methods",
             docs=WIN32 + "cimwin32prov/terminate-method-in-class-win32-process", writes=True),
        Call("Win32_Process.Create", "a process started", "Methods",
             docs=WIN32 + "cimwin32prov/create-method-in-class-win32-process", writes=True),
        Call("Win32_Process.GetOwner", "who a process runs as", "Methods",
             docs=WIN32 + "cimwin32prov/getowner-method-in-class-win32-process"),
        Call("Get-CimInstance Win32_Service", "the services as WMI holds them", "Other classes",
             docs=WIN32 + "cimwin32prov/win32-service"),
    ),
    verified=VERIFIED,
)

APIS = (POWERSHELL, SCHEDULED_TASKS, TASK_SCHEDULER, SERVICES, PROCESSES)
