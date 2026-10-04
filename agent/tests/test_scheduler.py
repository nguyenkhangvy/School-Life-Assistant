import subprocess
import xml.etree.ElementTree as ET
from types import SimpleNamespace

import pytest

from sla_agent import scheduler
from sla_agent.scheduler import (
    OLD_TASK_NAME,
    SchedulerError,
    install_task,
    remove_task,
    task_name,
    task_program,
    task_xml,
)

NS = {"t": "http://schemas.microsoft.com/windows/2004/02/mit/task"}
PYTHONW = r"C:\IU SCHOOL\School-Life-Assistant\.venv\Scripts\pythonw.exe"
USER = r"LAPTOP-AN\an & co"


@pytest.fixture
def task():
    return ET.fromstring(task_xml(PYTHONW, USER))


def text(task, path):
    return task.find(path, NS).text


def test_runs_every_minute_and_after_logon(task):
    assert text(task, "t:Triggers/t:TimeTrigger/t:Repetition/t:Interval") == "PT1M"
    assert text(task, "t:Triggers/t:LogonTrigger/t:UserId") == USER


def test_runs_the_agent_without_a_console_window(task):
    assert text(task, "t:Actions/t:Exec/t:Command") == PYTHONW
    assert text(task, "t:Actions/t:Exec/t:Arguments") == "-m sla_agent run"


def test_runs_as_the_logged_in_user_without_admin_rights_or_a_stored_windows_password(task):
    assert text(task, "t:Principals/t:Principal/t:UserId") == USER
    assert text(task, "t:Principals/t:Principal/t:LogonType") == "InteractiveToken"
    assert text(task, "t:Principals/t:Principal/t:RunLevel") == "LeastPrivilege"


def test_catches_up_never_overlaps_works_on_battery_and_has_a_time_limit(task):
    assert text(task, "t:Settings/t:StartWhenAvailable") == "true"
    assert text(task, "t:Settings/t:MultipleInstancesPolicy") == "IgnoreNew"
    assert text(task, "t:Settings/t:DisallowStartIfOnBatteries") == "false"
    assert text(task, "t:Settings/t:StopIfGoingOnBatteries") == "false"
    assert text(task, "t:Settings/t:ExecutionTimeLimit") == "PT10M"


class FakeRunner:
    def __init__(self, returncode=0, stderr=""):
        self.calls = []
        self.returncode = returncode
        self.stderr = stderr

    def __call__(self, args, **kwargs):
        xml_path = args[args.index("/XML") + 1] if "/XML" in args else None
        xml = open(xml_path, encoding="utf-16").read() if xml_path else None
        self.calls.append((args, xml))

        class Result:
            pass

        result = Result()
        result.returncode, result.stdout, result.stderr = self.returncode, "", self.stderr
        return result


def test_each_windows_user_gets_their_own_task():
    """One name for every user let a second Windows user on the laptop get "Access is denied": one user can't
    replace another's task."""
    assert task_name(r"LAPTOP-AN\an") == r"\SchoolLifeAssistant\Sync (an)"
    assert task_name(r"LAPTOP-AN\binh") != task_name(r"LAPTOP-AN\an")
    assert task_name("an") == task_name(r"LAPTOP-AN\an")  # with or without the computer's name


def test_install_creates_this_users_task_from_the_xml(tmp_path):
    runner = FakeRunner()

    install_task(PYTHONW, USER, folder=tmp_path, runner=runner, service=FakeTaskScheduler())

    [(args, xml)] = runner.calls
    assert args[:2] == ["schtasks", "/Create"]
    assert args[args.index("/TN") + 1] == r"\SchoolLifeAssistant\Sync (an & co)"
    assert "/F" in args
    assert "PT1M" in xml


def test_install_replaces_this_users_task_from_before_0_4_1(tmp_path):
    runner = FakeRunner()
    old = FakeTaskScheduler({OLD_TASK_NAME: (PYTHONW, "an & co")})  # Task Scheduler leaves out the computer's name

    install_task(PYTHONW, USER, folder=tmp_path, runner=runner, service=old)

    assert [args for args, _ in runner.calls][1:] == [["schtasks", "/Delete", "/F", "/TN", OLD_TASK_NAME]]


def test_install_leaves_another_users_task_alone(tmp_path):
    runner = FakeRunner()

    install_task(PYTHONW, USER, folder=tmp_path, runner=runner,
                 service=FakeTaskScheduler({OLD_TASK_NAME: (PYTHONW, "binh")}))

    assert [args[1] for args, _ in runner.calls] == ["/Create"]


def test_install_reports_a_schtasks_failure(tmp_path):
    with pytest.raises(SchedulerError, match="Access is denied"):
        install_task(PYTHONW, USER, folder=tmp_path, runner=FakeRunner(returncode=1, stderr="ERROR: Access is denied."),
                     service=FakeTaskScheduler())


def test_remove_deletes_this_users_task_and_their_task_from_before_0_4_1():
    runner = FakeRunner()

    remove_task(USER, runner=runner, service=FakeTaskScheduler({OLD_TASK_NAME: (PYTHONW, "AN & CO")}))

    assert [args for args, _ in runner.calls] == [["schtasks", "/Delete", "/F", "/TN", task_name(USER)],
                                                  ["schtasks", "/Delete", "/F", "/TN", OLD_TASK_NAME]]


def test_remove_leaves_another_users_task_alone():
    runner = FakeRunner()

    remove_task(USER, runner=runner, service=FakeTaskScheduler({OLD_TASK_NAME: (PYTHONW, "binh")}))

    assert [args for args, _ in runner.calls] == [["schtasks", "/Delete", "/F", "/TN", task_name(USER)]]


class Answer:
    def __init__(self, returncode, stdout):
        self.returncode, self.stdout, self.stderr = returncode, stdout, ""


class FakeTaskScheduler:
    """Stands in for Task Scheduler's COM interface (Schedule.Service). `tasks` maps a task's name to (the program it
    starts, the user it runs as, which Task Scheduler gives without the computer's name). A task that isn't there, or
    that Task Scheduler won't show this user, raises as pywin32's com_error does."""

    def __init__(self, tasks=None):
        self.tasks = tasks or {}
        self.asked = []

    def GetFolder(self, path):
        self.asked.append(("folder", path))
        return self

    def GetTask(self, path):
        self.asked.append(("task", path))
        if path not in self.tasks:
            raise OSError("The system cannot find the file specified.")  # pywin32 raises its com_error here
        program, user = self.tasks[path]
        action = SimpleNamespace(Path=program)
        return SimpleNamespace(Definition=SimpleNamespace(
            Actions=SimpleNamespace(Item=lambda number: action if number == 1 else None),
            Principal=SimpleNamespace(UserId=user)))


def test_the_tasks_program_is_read_from_task_scheduler_with_vietnamese_letters_intact():
    """schtasks /Query prints in the console's code page, which turns "Nguyễn Văn" into "Nguy?n V?n" (review I2)."""
    program = r"C:\Users\Nguyễn Văn An\AppData\Local\SchoolLifeAssistant\app\School-Life-Assistant.exe"
    task_scheduler = FakeTaskScheduler({task_name(USER): (program, "an & co")})

    assert task_program(service=task_scheduler, user=USER) == program
    assert task_scheduler.asked == [("folder", "\\"), ("task", task_name(USER))]


def test_this_users_task_from_before_0_4_1_still_counts():
    """An update doesn't remake the task, so a laptop set up before 0.4.1 keeps its old one until Repair."""
    assert task_program(service=FakeTaskScheduler({OLD_TASK_NAME: (PYTHONW, "an & co")}), user=USER) == PYTHONW


def test_another_users_task_from_before_0_4_1_is_not_this_users():
    assert task_program(service=FakeTaskScheduler({OLD_TASK_NAME: (PYTHONW, "binh")}), user=USER) is None


def test_no_program_when_the_task_is_missing():
    assert task_program(service=FakeTaskScheduler(), user=USER) is None


def test_no_program_where_task_scheduler_cannot_be_reached(monkeypatch):
    def unreachable():
        raise ImportError("No module named 'win32com'")

    monkeypatch.setattr(scheduler, "_task_scheduler", unreachable)

    assert task_program() is None


def test_schtasks_never_opens_a_console_window(tmp_path):
    """The window runs under pythonw: without CREATE_NO_WINDOW each schtasks call would flash a console."""
    flags = []

    def runner(args, **kwargs):
        flags.append(kwargs.get("creationflags"))
        return Answer(0, "")

    install_task(PYTHONW, USER, folder=tmp_path, runner=runner, service=FakeTaskScheduler())
    remove_task(USER, runner=runner, service=FakeTaskScheduler())

    assert flags == [getattr(subprocess, "CREATE_NO_WINDOW", 0)] * 2
