"""School module tables. All times are naive UTC; every row belongs to one user."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.timeutil import utcnow


def _user_id():
    return mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)


# ---- Data synced from EduSoft ------------------------------------------------


class SchoolCourse(db.Model):
    __tablename__ = "school_courses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = _user_id()
    term_code: Mapped[str] = mapped_column(String(20), nullable=False)
    course_code: Mapped[str] = mapped_column(String(20), nullable=False)
    course_name: Mapped[str] = mapped_column(String(255), nullable=False)
    group_code: Mapped[str | None] = mapped_column(String(20))
    credits: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    lecturer: Mapped[str | None] = mapped_column(String(255))

    meetings: Mapped[list["SchoolClassMeeting"]] = relationship(
        back_populates="course", cascade="all, delete-orphan", passive_deletes=True
    )


class SchoolClassMeeting(db.Model):
    """One real class session (EduSoft's week pattern expanded to dates)."""

    __tablename__ = "school_class_meetings"
    __table_args__ = (Index("ix_school_class_meetings_user_start", "user_id", "start_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = _user_id()
    course_id: Mapped[int] = mapped_column(
        ForeignKey("school_courses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    start_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    room: Mapped[str | None] = mapped_column(String(50))

    course: Mapped[SchoolCourse] = relationship(back_populates="meetings")


class SchoolExam(db.Model):
    __tablename__ = "school_exams"
    __table_args__ = (Index("ix_school_exams_user_start", "user_id", "start_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = _user_id()
    term_code: Mapped[str] = mapped_column(String(20), nullable=False)
    course_code: Mapped[str] = mapped_column(String(20), nullable=False)
    course_name: Mapped[str] = mapped_column(String(255), nullable=False)
    exam_type: Mapped[str] = mapped_column(String(10), nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    duration_min: Mapped[int | None] = mapped_column(Integer)
    room: Mapped[str | None] = mapped_column(String(50))
    notes: Mapped[str | None] = mapped_column(String(500))


class SchoolTuition(db.Model):
    __tablename__ = "school_tuition"
    __table_args__ = (UniqueConstraint("user_id", "term_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = _user_id()
    term_code: Mapped[str] = mapped_column(String(20), nullable=False)
    amount_due: Mapped[int] = mapped_column(BigInteger, nullable=False)
    amount_paid: Mapped[int] = mapped_column(BigInteger, nullable=False)
    balance: Mapped[int] = mapped_column(BigInteger, nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date)
    status_text: Mapped[str | None] = mapped_column(String(255))
    items: Mapped[list] = mapped_column(JSON, nullable=False, default=list)


# ---- The user's own data -----------------------------------------------------


class SchoolEvent(db.Model):
    """A personal event the user creates, edits and deletes."""

    __tablename__ = "school_events"
    __table_args__ = (Index("ix_school_events_user_start", "user_id", "start_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = _user_id()
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    all_day: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    location: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)


# ---- Sync bookkeeping --------------------------------------------------------


class SchoolSyncDevice(db.Model):
    """A laptop allowed to upload EduSoft data. Only the key's SHA-256 hash is stored."""

    __tablename__ = "school_sync_devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = _user_id()
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime)


class SchoolSyncSettings(db.Model):
    __tablename__ = "school_sync_settings"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    interval_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=12)
    sync_requested_at: Mapped[datetime | None] = mapped_column(DateTime)


class SchoolSyncRun(db.Model):
    __tablename__ = "school_sync_runs"
    __table_args__ = (Index("ix_school_sync_runs_user_started", "user_id", "started_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = _user_id()
    device_id: Mapped[int | None] = mapped_column(ForeignKey("school_sync_devices.id", ondelete="SET NULL"))
    trigger: Mapped[str] = mapped_column(String(20), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(10), nullable=False)  # running/success/partial/failed
    error_code: Mapped[str | None] = mapped_column(String(40))
    error_message: Mapped[str | None] = mapped_column(String(500))
    sections: Mapped[dict | None] = mapped_column(JSON)


class SchoolChange(db.Model):
    """One line in the "What changed" feed."""

    __tablename__ = "school_changes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = _user_id()
    sync_run_id: Mapped[int] = mapped_column(
        ForeignKey("school_sync_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    section: Mapped[str] = mapped_column(String(20), nullable=False)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)  # added/removed/changed
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    seen_at: Mapped[datetime | None] = mapped_column(DateTime)


# ---- Blackboard --------------------------------------------------------------


def _bb_course_id():
    return mapped_column(ForeignKey("school_bb_courses.id", ondelete="CASCADE"), nullable=False, index=True)


class SchoolBbCourse(db.Model):
    __tablename__ = "school_bb_courses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = _user_id()
    bb_id: Mapped[str] = mapped_column(String(64), nullable=False)
    course_code: Mapped[str | None] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)

    announcements: Mapped[list["SchoolBbAnnouncement"]] = relationship(
        back_populates="course", cascade="all, delete-orphan", passive_deletes=True)
    assignments: Mapped[list["SchoolBbAssignment"]] = relationship(
        back_populates="course", cascade="all, delete-orphan", passive_deletes=True)
    materials: Mapped[list["SchoolBbMaterial"]] = relationship(
        back_populates="course", cascade="all, delete-orphan", passive_deletes=True)


class SchoolBbAnnouncement(db.Model):
    __tablename__ = "school_bb_announcements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = _user_id()
    course_id: Mapped[int] = _bb_course_id()
    bb_id: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    posted_at: Mapped[datetime | None] = mapped_column(DateTime)
    url: Mapped[str] = mapped_column(String(500), nullable=False)

    course: Mapped[SchoolBbCourse] = relationship(back_populates="announcements")


class SchoolBbAssignment(db.Model):
    __tablename__ = "school_bb_assignments"
    __table_args__ = (Index("ix_school_bb_assignments_user_due", "user_id", "due_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = _user_id()
    course_id: Mapped[int] = _bb_course_id()
    bb_id: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime)
    points_possible: Mapped[float | None] = mapped_column(Float)
    score: Mapped[float | None] = mapped_column(Float)
    grade_text: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    feedback: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str] = mapped_column(String(500), nullable=False)

    course: Mapped[SchoolBbCourse] = relationship(back_populates="assignments")


class SchoolBbMaterial(db.Model):
    __tablename__ = "school_bb_materials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = _user_id()
    course_id: Mapped[int] = _bb_course_id()
    bb_id: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    path: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    created_at: Mapped[datetime | None] = mapped_column(DateTime)
    url: Mapped[str] = mapped_column(String(500), nullable=False)

    course: Mapped[SchoolBbCourse] = relationship(back_populates="materials")
