"""The Windows scheduled task that runs `sla-agent run` every minute and at logon.

It runs as the logged-in user (no admin rights, no stored Windows password),
which is also what gives it access to that user's Credential Manager. Each
Windows user has their own task (task_name): task names are shared by the whole
computer, and one user can't replace another's task.
"""

import getpass
import os
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

from sla_agent.launcher import arguments

TASK_FOLDER = r"\SchoolLifeAssistant"
# Before 0.4.1 every Windows user's task had this one name, so where one user had set up School-Life-Assistant,
# Windows refused a second user's task ("Access is denied").
OLD_TASK_NAME = TASK_FOLDER + r"\Sync"
NS = "http://schemas.microsoft.com/windows/2004/02/mit/task"
# schtasks is a console program: started from the window (pythonw, no console) it would flash a console window.
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class SchedulerError(Exception):
    pass


def current_user():
    domain = os.environ.get("USERDOMAIN")
    user = os.environ.get("USERNAME") or getpass.getuser()
    return f"{domain}\\{user}" if domain else user


def _user_name(user):
    """The user without the computer's or domain's name, as Task Scheduler gives a task's user."""
    return (user or "").rsplit("\\", 1)[-1]


def task_name(user):
    r"""This Windows user's own task, e.g. \SchoolLifeAssistant\Sync (khang)."""
    return rf"{TASK_FOLDER}\Sync ({_user_name(user)})"


def _runs_as(task, user):
    return _user_name(task.Definition.Principal.UserId).casefold() == _user_name(user).casefold()


def _old_task_is_theirs(user, service):
    """Whether the task of before 0.4.1 is there and runs as `user`. Another user's is theirs to keep (Task Scheduler
    doesn't even show it to this user)."""
    try:
        return _runs_as((_task_scheduler() if service is None else service).GetFolder("\\").GetTask(OLD_TASK_NAME),
                        user)
    except Exception:  # no old task, Task Scheduler refused, or not Windows (ImportError)
        return False


def _delete(name, runner):
    runner(["schtasks", "/Delete", "/F", "/TN", name], capture_output=True, text=True, creationflags=NO_WINDOW)


def _add(parent, tag, text=None, **attrs):
    element = ET.SubElement(parent, f"{{{NS}}}{tag}", attrs)
    if text is not None:
        element.text = text
    return element


def task_xml(program, user):
    ET.register_namespace("", NS)
    task = ET.Element(f"{{{NS}}}Task", version="1.2")

    info = _add(task, "RegistrationInfo")
    _add(info, "Description", "School-Life-Assistant: new mail every minute; EduSoft, IUPay, Blackboard and "
                              "Outlook every 30 minutes.")

    triggers = _add(task, "Triggers")
    every_minute = _add(triggers, "TimeTrigger")
    repetition = _add(every_minute, "Repetition")
    _add(repetition, "Interval", "PT1M")
    _add(every_minute, "StartBoundary", "2026-01-01T00:00:00")
    _add(every_minute, "Enabled", "true")
    at_logon = _add(triggers, "LogonTrigger")
    _add(at_logon, "Enabled", "true")
    _add(at_logon, "UserId", user)
    _add(at_logon, "Delay", "PT2M")

    principal = _add(_add(task, "Principals"), "Principal", id="Author")
    _add(principal, "UserId", user)
    _add(principal, "LogonType", "InteractiveToken")
    _add(principal, "RunLevel", "LeastPrivilege")

    settings = _add(task, "Settings")
    for tag, value in (
        ("MultipleInstancesPolicy", "IgnoreNew"),
        ("DisallowStartIfOnBatteries", "false"),
        ("StopIfGoingOnBatteries", "false"),
        ("StartWhenAvailable", "true"),
        ("RunOnlyIfNetworkAvailable", "true"),
        ("AllowStartOnDemand", "true"),
        ("Enabled", "true"),
        ("ExecutionTimeLimit", "PT10M"),
    ):
        _add(settings, tag, value)

    action = _add(_add(task, "Actions", Context="Author"), "Exec")
    _add(action, "Command", program)
    _add(action, "Arguments", arguments(program, "run"))

    return ET.tostring(task, encoding="unicode")


def install_task(program, user, folder, runner=subprocess.run, service=None):
    """This user's task (task_name), made or remade; their task of before 0.4.1, if any, goes, so sync never runs
    twice."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    xml_path = folder / "sync-task.xml"
    xml_path.write_text('<?xml version="1.0" encoding="UTF-16"?>\n' + task_xml(program, user), encoding="utf-16")
    result = runner(
        ["schtasks", "/Create", "/F", "/TN", task_name(user), "/XML", str(xml_path)],
        capture_output=True, text=True, creationflags=NO_WINDOW,
    )
    if result.returncode != 0:
        raise SchedulerError(f"Couldn't create the scheduled task: {(result.stderr or result.stdout).strip()}")
    if _old_task_is_theirs(user, service):
        _delete(OLD_TASK_NAME, runner)


def _task_scheduler():
    """Task Scheduler's own COM interface (through pywin32), connected."""
    import pythoncom
    import win32com.client

    pythoncom.CoInitialize()  # COM is per thread: this may run on any of the window's threads
    service = win32com.client.Dispatch("Schedule.Service")
    service.Connect()
    return service


def task_program(service=None, user=None):
    """The program this Windows user's task starts (their own task, or their task of before 0.4.1, which an update
    doesn't remake), or None when there is none or it can't be read. Read through Task Scheduler's COM interface, not
    `schtasks /Query`: schtasks prints in the console's code page, which turns the letters of a Vietnamese user folder
    into '?' (and the program would seem to be gone)."""
    user = user or current_user()
    try:
        folder = (_task_scheduler() if service is None else service).GetFolder("\\")
    except Exception:  # not Windows (ImportError), or Task Scheduler can't be reached
        return None
    for name in (task_name(user), OLD_TASK_NAME):
        try:
            task = folder.GetTask(name)
        except Exception:  # no such task, or Task Scheduler refused (pywin32's com_error)
            continue
        if name == OLD_TASK_NAME and not _runs_as(task, user):
            continue  # another Windows user's
        return task.Definition.Actions.Item(1).Path
    return None


def remove_task(user=None, runner=subprocess.run, service=None):
    """This Windows user's task, and their task of before 0.4.1 (`sla-agent forget`)."""
    user = user or current_user()
    _delete(task_name(user), runner)
    if _old_task_is_theirs(user, service):
        _delete(OLD_TASK_NAME, runner)
