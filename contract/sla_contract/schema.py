"""The data the laptop agent sends to the web app after a sync.

Both sides import this file, so they always agree on the format. Unknown
fields are rejected: only what is listed here can leave the laptop.

The Java website reads the same format with
web/src/main/java/vn/edu/hcmiu/sla/school/sync/SyncContract.java: change both
together. contract/samples/ holds example uploads that both test suites check.
"""

from datetime import date, time
from typing import Annotated, Generic, Literal, TypeVar, get_args

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = 1

ErrorCode = Literal[
    "bad_credentials",  # EduSoft rejected the student ID or password
    "session_expired",  # EduSoft logged us out mid-sync, and one re-login did not help
    "network",  # EduSoft could not be reached, timed out, or was under maintenance
    "edusoft_changed",  # a page no longer looks the way the parser expects
    "source_changed",  # Blackboard's answers are in an unexpected format
    "extra_verification",  # EduSoft asked for a CAPTCHA, one-time code or Microsoft sign-in
    "outlook_not_set_up",  # classic Outlook is missing, has no account, or the chosen account is gone
    "outlook_blocked",  # Outlook refused the read or didn't answer in time (e.g. a security prompt)
    "unknown",
]
Trigger = Literal["scheduled", "manual", "import", "mail"]  # mail: a mail-only run (only the Outlook part), between full syncs

Code = Annotated[str, Field(min_length=1, max_length=20)]
Name = Annotated[str, Field(min_length=1, max_length=255)]
Room = Annotated[str, Field(max_length=50)]
Message = Annotated[str, Field(min_length=1, max_length=500)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ClassMeeting(_Strict):
    start_at: AwareDatetime
    end_at: AwareDatetime
    room: Room | None = None

    @model_validator(mode="after")
    def _ends_after_it_starts(self):
        if self.end_at <= self.start_at:
            raise ValueError("end_at must be after start_at")
        return self


class Course(_Strict):
    course_code: Code
    course_name: Name
    group: Annotated[str, Field(max_length=20)] | None = None
    credits: Annotated[float, Field(ge=0, le=50)] | None = None
    lecturer: Annotated[str, Field(max_length=255)] | None = None
    meetings: Annotated[list[ClassMeeting], Field(max_length=200)] = []


class Timetable(_Strict):
    term_code: Code
    term_name: Annotated[str, Field(max_length=100)] | None = None
    courses: Annotated[list[Course], Field(max_length=40)]


class Exam(_Strict):
    course_code: Code
    course_name: Name
    exam_type: Literal["midterm", "final", "other"]
    start_at: AwareDatetime
    duration_min: Annotated[int, Field(ge=1, le=600)] | None = None
    room: Room | None = None
    notes: Annotated[str, Field(max_length=500)] | None = None


class Exams(_Strict):
    term_code: Code
    exams: Annotated[list[Exam], Field(max_length=60)]


class TuitionItem(_Strict):
    description: Name
    amount: int  # VND


class Tuition(_Strict):
    term_code: Code
    amount_due: Annotated[int, Field(ge=0)]  # VND
    amount_paid: Annotated[int, Field(ge=0)]  # VND
    balance: int  # VND; negative means overpaid
    due_date: date | None = None
    status_text: Annotated[str, Field(max_length=255)] | None = None
    items: Annotated[list[TuitionItem], Field(max_length=60)] = []


BillStatus = Literal["unpaid", "paid", "paying", "partly_paid"]


class TuitionBill(_Strict):
    """One IUPay bill. Amounts are VND; due_date and paid_on are Vietnam dates."""

    bill_no: Annotated[str, Field(min_length=1, max_length=40)]
    term_code: Code
    term_name: Name | None = None
    description: Annotated[str, Field(min_length=1, max_length=1000)]
    fee_type: Name | None = None
    amount: Annotated[int, Field(ge=0)]
    discount: Annotated[int, Field(ge=0)] = 0
    fee: Annotated[int, Field(ge=0)] = 0  # IUPay's transaction fee
    status: BillStatus
    due_date: date | None = None  # bills not paid yet
    paid_on: date | None = None  # paid bills
    channel: Annotated[str, Field(max_length=100)] | None = None  # paid bills: how they were paid


class Iupay(_Strict):
    """Every bill IUPay lists for the student, paid or not."""

    bills: Annotated[list[TuitionBill], Field(max_length=500)] = []

    @model_validator(mode="after")
    def _each_bill_once(self):
        numbers = [bill.bill_no for bill in self.bills]
        if len(set(numbers)) != len(numbers):
            raise ValueError("bill_no must differ")
        return self


BbId = Annotated[str, Field(min_length=1, max_length=64)]
BbUrl = Annotated[str, Field(max_length=500, pattern=r"^https://blackboard\.hcmiu\.edu\.vn/")]


class BbAnnouncement(_Strict):
    bb_id: BbId
    title: Name
    text: Annotated[str, Field(max_length=5000)] = ""
    posted_at: AwareDatetime | None = None
    url: BbUrl


class BbAssignment(_Strict):
    bb_id: BbId
    name: Name
    due_at: AwareDatetime | None = None
    points_possible: Annotated[float, Field(ge=0)] | None = None
    score: float | None = None
    grade_text: Annotated[str, Field(max_length=50)] | None = None
    status: Literal["not_graded", "needs_grading", "graded", "exempt"]
    feedback: Annotated[str, Field(max_length=1000)] | None = None
    url: BbUrl


class BbMaterial(_Strict):
    bb_id: BbId
    title: Name
    kind: Literal["file", "folder", "link", "document", "other"]
    path: Annotated[str, Field(max_length=500)] = ""
    created_at: AwareDatetime | None = None
    url: BbUrl


class BbCourse(_Strict):
    bb_id: BbId
    course_code: Code | None = None
    name: Name
    url: BbUrl
    announcements: Annotated[list[BbAnnouncement], Field(max_length=300)] = []
    assignments: Annotated[list[BbAssignment], Field(max_length=300)] = []
    materials: Annotated[list[BbMaterial], Field(max_length=1000)] = []


class Blackboard(_Strict):
    courses: Annotated[list[BbCourse], Field(max_length=40)]


MailCategory = Literal["class", "event", "training_points", "school_task", "money", "requests_account",
                       "system_notice", "promotion"]
MAIL_CATEGORIES = get_args(MailCategory)


class MailClassChange(_Strict):
    """A class change a lecturer's email announces. day and times are Vietnam time."""

    course_code: Code
    kind: Literal["online", "cancelled", "makeup"]
    day: date
    start: time | None = None  # make-up classes only
    end: time | None = None
    room: Room | None = None


# Codes from fixed lists, never the email's words (spec 2026-10-07-mail-event-kinds-design.md §3.2).
MailLabel = Literal["round_1", "round_2", "round_3", "round_4", "round_5", "preliminary", "qualifying", "semifinal",
                    "final", "opening", "closing", "shift_1", "shift_2", "shift_3", "shift_4", "shift_5"]
MailRelativeDay = Literal["today", "tomorrow", "day_after_tomorrow", "this_week", "next_week", "weekday"]
MailMode = Literal["online", "in_person"]
TimeOfDay = time  # for the deadline's field called "time", which would hide the type


class MailSession(_Strict):
    """One time an event or school task takes place, as the laptop found it in the email. Vietnam time.
    check_in: when to be there by; link_opens: when an online event's link becomes available. relative: the day came
    from a word such as "ngày mai"."""

    day: date
    start: time
    end: time | None = None
    end_is_approximate: bool = False  # "khoảng 1 tiếng", "dự kiến"
    ends_next_day: bool = False  # the end is on the next day, and may be earlier than the start
    check_in: time | None = None
    link_opens: time | None = None
    mode: MailMode | None = None
    relative: MailRelativeDay | None = None
    label: MailLabel | None = None

    @model_validator(mode="after")
    def _end_after_start(self):
        if self.end is None and (self.end_is_approximate or self.ends_next_day):
            raise ValueError("end_is_approximate and ends_next_day need an end")
        if self.end is not None and not self.ends_next_day and self.end <= self.start:
            raise ValueError("end must be after start")
        if any(t is not None and t > self.start for t in (self.check_in, self.link_opens)):
            raise ValueError("check_in and link_opens can't be after start")
        return self


class MailPeriod(_Strict):
    """A range of days in which the student may come or do something at any time. Vietnam time. all_day: days only;
    daily_window: from_time to to_time each day; one_window: from from_time on first_day to to_time on last_day."""

    first_day: date
    last_day: date
    mode: Literal["all_day", "daily_window", "one_window"]
    from_time: time | None = None
    to_time: time | None = None
    details_later: bool = False  # the student's own time comes later
    label: MailLabel | None = None

    @model_validator(mode="after")
    def _times_match_mode(self):
        if self.last_day < self.first_day:
            raise ValueError("last_day can't be before first_day")
        if self.mode == "all_day":
            if self.from_time is not None or self.to_time is not None:
                raise ValueError("an all_day Period has no times")
        elif self.from_time is None or self.to_time is None:
            raise ValueError("a daily_window or one_window Period needs from_time and to_time")
        elif (self.mode == "daily_window" or self.first_day == self.last_day) and self.to_time <= self.from_time:
            raise ValueError("to_time must be after from_time")
        return self


class MailDeadline(_Strict):
    """A deadline: information only, never event time. opens: registration opens; register: it closes; confirm:
    confirming a place closes; due: something must be handed in or paid. Vietnam time."""

    kind: Literal["opens", "register", "confirm", "due"]
    day: date
    time: TimeOfDay | None = None
    mode: MailMode | None = None


class MailItem(_Strict):
    """What the website may know about one email: never its text."""

    key: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]  # SHA-256 of the internet message ID
    entry_id: Annotated[str, Field(pattern=r"^[0-9A-F]{2,512}$")]  # Outlook's ID: opens it on the laptop
    thread_id: Annotated[str, Field(max_length=64)] | None = None
    received_at: AwareDatetime
    sender_name: Annotated[str, Field(max_length=255)] = ""
    sender_address: Annotated[str, Field(max_length=255)] = ""
    subject: Annotated[str, Field(max_length=500)] = ""
    categories: Annotated[list[MailCategory], Field(max_length=2)] = []
    from_lecturer: bool = False
    dates: Annotated[list[date], Field(max_length=30)] = []
    sessions: Annotated[list[MailSession], Field(max_length=10)] = []  # found in any email; shown for events
    periods: Annotated[list[MailPeriod], Field(max_length=5)] = []
    deadlines: Annotated[list[MailDeadline], Field(max_length=5)] = []
    register_by: date | None = None  # the latest register deadline's day, for servers older than the deadlines
    meeting: bool = False  # a meeting or class activity the student may need to join
    registered: bool = False  # the email confirms the student is registered
    invitation: Literal["request", "cancelled"] | None = None  # an Outlook meeting request or its cancellation
    sorted: bool = True  # False: the sorting rules failed on this email
    blackboard_title: Annotated[str, Field(max_length=255)] | None = None
    class_changes: Annotated[list[MailClassChange], Field(max_length=10)] = []

    @model_validator(mode="after")
    def _categories_differ(self):
        if len(set(self.categories)) != len(self.categories):
            raise ValueError("categories must differ")
        return self


class Outlook(_Strict):
    since: date
    connected: bool  # False: Outlook was offline, so the newest mail may be missing
    emails: Annotated[list[MailItem], Field(max_length=2000)]


T = TypeVar("T")


class SectionOk(_Strict, Generic[T]):
    status: Literal["ok"]
    data: T


class SectionFailed(_Strict):
    status: Literal["failed"]
    error_code: ErrorCode
    error_message: Message


TimetableResult = Annotated[SectionOk[Timetable] | SectionFailed, Field(discriminator="status")]
ExamsResult = Annotated[SectionOk[Exams] | SectionFailed, Field(discriminator="status")]
TuitionResult = Annotated[SectionOk[Tuition] | SectionFailed, Field(discriminator="status")]
IupayResult = Annotated[SectionOk[Iupay] | SectionFailed, Field(discriminator="status")]
BlackboardResult = Annotated[SectionOk[Blackboard] | SectionFailed, Field(discriminator="status")]
OutlookResult = Annotated[SectionOk[Outlook] | SectionFailed, Field(discriminator="status")]

EDUSOFT_SECTIONS = ("timetable", "exams")
SECTION_NAMES = ("timetable", "exams", "iupay", "blackboard", "outlook")


class FinishRun(_Strict):
    """Result of one sync: either a whole-run error, or a result per part."""

    schema_version: Literal[1] = SCHEMA_VERSION
    error_code: ErrorCode | None = None
    error_message: Message | None = None
    timetable: TimetableResult | None = None
    exams: ExamsResult | None = None
    tuition: TuitionResult | None = None  # sent by agents from before IUPay: accepted, never counted or saved
    iupay: IupayResult | None = None
    blackboard: BlackboardResult | None = None
    outlook: OutlookResult | None = None

    @model_validator(mode="after")
    def _error_or_sections(self):
        if self.error_code is not None:
            if self.error_message is None:
                raise ValueError("error_message is required with error_code")
            if self.sections() or self.tuition is not None:
                raise ValueError("a whole-run error cannot carry section results")
        elif not self.sections():
            raise ValueError("send either error_code or at least one section")
        return self

    def sections(self):
        """The parts that were sent, by name."""
        return {name: getattr(self, name) for name in SECTION_NAMES if getattr(self, name) is not None}

    def overall_status(self):
        if self.error_code is not None:
            return "failed"
        statuses = {result.status for result in self.sections().values()}
        if statuses == {"ok"}:
            return "success"
        if statuses == {"failed"}:
            return "failed"
        return "partial"


class StartRun(_Strict):
    trigger: Trigger


class CheckResult(BaseModel):
    due: bool
    reason: str
    interval_hours: int


class StartResult(BaseModel):
    run_id: int


class FinishResult(BaseModel):
    status: Literal["success", "partial", "failed"]


# ---- Connect this laptop (spec 2026-10-04-connect-button-design.md, 3) --------------------------------------
# The trade-in: the app sends the one-time code the browser brought back and the verifier only it knows; the website
# answers with this laptop's new device key and the account it belongs to. The Java twin is SyncContract.ConnectRequest.

Secret = Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{43}$")]  # 32 random bytes, URL-safe Base64 without padding
DeviceKey = Annotated[str, Field(pattern=r"^sla_[A-Za-z0-9_-]{43}$")]


class ConnectRequest(_Strict):
    code: Secret
    verifier: Secret


class ConnectResult(BaseModel):
    key: DeviceKey
    email: str
