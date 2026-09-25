"""The data the laptop agent sends to the web app after a sync.

Both sides import this file, so they always agree on the format. Unknown
fields are rejected: only what is listed here can leave the laptop.
"""

from datetime import date
from typing import Annotated, Generic, Literal, TypeVar

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = 1

ErrorCode = Literal[
    "bad_credentials",  # EduSoft rejected the student ID or password
    "session_expired",  # EduSoft logged us out mid-sync, and one re-login did not help
    "network",  # EduSoft could not be reached, timed out, or was under maintenance
    "edusoft_changed",  # a page no longer looks the way the parser expects
    "extra_verification",  # EduSoft asked for a CAPTCHA, one-time code or Microsoft sign-in
    "unknown",
]
Trigger = Literal["scheduled", "manual", "import"]

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

SECTION_NAMES = ("timetable", "exams", "tuition")


class FinishRun(_Strict):
    """Result of one sync: either a whole-run error, or a result per part."""

    schema_version: Literal[1] = SCHEMA_VERSION
    error_code: ErrorCode | None = None
    error_message: Message | None = None
    timetable: TimetableResult | None = None
    exams: ExamsResult | None = None
    tuition: TuitionResult | None = None

    @model_validator(mode="after")
    def _error_or_sections(self):
        if self.error_code is not None:
            if self.error_message is None:
                raise ValueError("error_message is required with error_code")
            if self.sections():
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
