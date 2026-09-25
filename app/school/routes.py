from datetime import date, datetime, timedelta

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import select

from app.extensions import db
from app.school.forms import DeviceForm
from app.school.models import (
    SchoolBbAnnouncement,
    SchoolBbAssignment,
    SchoolBbCourse,
    SchoolChange,
    SchoolExam,
    SchoolSyncDevice,
    SchoolSyncRun,
    SchoolTuition,
)
from app.school.services import schedule
from app.school.services.changes import WEEKDAYS, to_vietnam, when
from app.school.services.devices import create_device
from app.school.services.sync_runs import get_settings, latest_run
from app.school.services.sync_status import RunInfo, describe, system_lines
from app.timeutil import utcnow

bp = Blueprint("school", __name__, url_prefix="/school")


@bp.app_template_filter("vn_time")
def vn_time(moment):
    return when(moment) if moment else "never"


@bp.app_template_filter("vn_clock")
def vn_clock(moment):
    """Naive UTC -> '08:00' in Vietnam."""
    return to_vietnam(moment).strftime("%H:%M")


@bp.app_template_filter("vn_date")
def vn_date(moment):
    return to_vietnam(moment).strftime("%d/%m/%Y")


@bp.app_template_filter("day_label")
def day_label(day):
    return f"{WEEKDAYS[day.weekday()]} {day:%d/%m}"


@bp.app_template_filter("money")
def money(amount):
    return f"{amount:,}"


@bp.app_template_filter("score")
def score(value):
    return f"{value:g}"


def _active_devices():
    """The user's devices that can still sync. Cancelled ones stay in the database (sync
    history refers to them) but are no longer shown."""
    return db.session.execute(
        select(SchoolSyncDevice)
        .filter_by(user_id=current_user.id, revoked_at=None)
        .order_by(SchoolSyncDevice.created_at)
    ).scalars().all()


def _own_device(device_id):
    return db.first_or_404(select(SchoolSyncDevice).filter_by(id=device_id, user_id=current_user.id))


def _status(now):
    settings = get_settings(current_user.id)
    latest = latest_run(current_user.id)
    last_good = latest_run(current_user.id, "success", "partial")
    active = _active_devices()
    return describe(
        now=now,
        interval_hours=settings.interval_hours,
        sync_requested_at=settings.sync_requested_at,
        latest=None if latest is None else RunInfo(
            latest.status, latest.started_at, latest.finished_at,
            latest.error_code, latest.error_message, latest.sections,
        ),
        last_good_finished_at=last_good.finished_at if last_good else None,
        has_device=bool(active),
        last_seen_at=max((d.last_seen_at for d in active if d.last_seen_at), default=None),
    )


@bp.get("/")
@login_required
def index():
    now = utcnow()
    status = _status(now)
    db.session.commit()
    today = schedule.vietnam_date(now)
    next_exam = db.session.execute(
        select(SchoolExam).filter_by(user_id=current_user.id).where(SchoolExam.start_at >= now)
        .order_by(SchoolExam.start_at).limit(1)
    ).scalar_one_or_none()
    changes = db.session.execute(
        select(SchoolChange).filter_by(user_id=current_user.id).order_by(SchoolChange.id.desc()).limit(10)
    ).scalars().all()
    recent = db.session.execute(
        select(SchoolSyncRun).filter_by(user_id=current_user.id)
        .order_by(SchoolSyncRun.started_at.desc(), SchoolSyncRun.id.desc()).limit(10)
    ).scalars().all()
    lines = system_lines([RunInfo(r.status, r.started_at, r.finished_at, r.error_code, r.error_message, r.sections)
                          for r in recent], now)
    due_soon = db.session.execute(
        select(SchoolBbAssignment).filter_by(user_id=current_user.id)
        .where(SchoolBbAssignment.due_at >= now, SchoolBbAssignment.due_at < now + timedelta(days=7))
        .order_by(SchoolBbAssignment.due_at)
    ).scalars().all()
    latest_announcements = db.session.execute(
        select(SchoolBbAnnouncement).filter_by(user_id=current_user.id)
        .order_by(SchoolBbAnnouncement.posted_at.desc(), SchoolBbAnnouncement.id.desc()).limit(3)
    ).scalars().all()
    return render_template(
        "school/index.html",
        status=status,
        system_lines=lines,
        today=today,
        today_items=schedule.items_on(current_user.id, today),
        tomorrow_items=schedule.items_on(current_user.id, today + timedelta(days=1)),
        next_exam=next_exam,
        changes=changes,
        due_soon=due_soon,
        latest_announcements=latest_announcements,
    )


@bp.get("/timetable")
@login_required
def timetable():
    return render_template("school/timetable.html")


MAX_CALENDAR_DAYS = 62  # a month view asks for about 6 weeks


def _wall_clock(moment_utc):
    """Naive UTC -> Vietnam wall-clock time without an offset, e.g. '2026-09-29T08:00:00'.
    The calendar shows these as they are, so times stay in Vietnam time on any device."""
    return (moment_utc + schedule.VIETNAM_OFFSET).isoformat(timespec="seconds")


def _calendar_event(item):
    event = {
        "title": f"{item.label}: {item.title}" if item.label else item.title,
        "start": _wall_clock(item.start_at),
        "classNames": [f"event-{item.kind}"],
        "extendedProps": {"kind": item.kind, "code": item.code, "room": item.room},
    }
    if item.end_at:
        event["end"] = _wall_clock(item.end_at)
    return event


@bp.get("/api/calendar")
@login_required
def calendar_feed():
    """Events for FullCalendar. start/end are Vietnam dates (end exclusive)."""
    try:
        start = date.fromisoformat(request.args["start"][:10])
        end = date.fromisoformat(request.args["end"][:10])
    except (KeyError, ValueError):
        return jsonify(error="start and end dates are required"), 400
    if not start < end or (end - start).days > MAX_CALENDAR_DAYS:
        return jsonify(error=f"the range must be 1 to {MAX_CALENDAR_DAYS} days"), 400
    items = schedule.items_between(current_user.id, schedule.day_start_utc(start), schedule.day_start_utc(end))
    events = [_calendar_event(item) for item in items]
    for deadline in schedule.deadlines_between(current_user.id, schedule.day_start_utc(start), schedule.day_start_utc(end)):
        events.append({
            "title": f"Due {vn_clock(deadline.due_at)}: {deadline.name} · {deadline.course.name}",
            "start": schedule.vietnam_date(deadline.due_at).isoformat(),
            "allDay": True,
            "classNames": ["event-due"],
            "extendedProps": {"kind": "due", "code": deadline.course.course_code, "room": None},
        })
    return jsonify(events)


@bp.get("/courses")
@login_required
def courses():
    rows = db.session.execute(
        select(SchoolBbCourse).filter_by(user_id=current_user.id).order_by(SchoolBbCourse.name)
    ).scalars().all()
    return render_template("school/courses.html", courses=rows)


@bp.get("/courses/<int:course_id>")
@login_required
def course(course_id):
    row = db.first_or_404(select(SchoolBbCourse).filter_by(id=course_id, user_id=current_user.id))
    far_future = datetime.max
    return render_template(
        "school/course.html",
        course=row,
        announcements=sorted(row.announcements, key=lambda a: a.posted_at or datetime.min, reverse=True),
        assignments=sorted(row.assignments, key=lambda a: a.due_at or far_future),
        materials=sorted(row.materials, key=lambda m: m.created_at or datetime.min, reverse=True),
        now=utcnow(),
    )


@bp.get("/exams")
@login_required
def exams():
    now = utcnow()
    mine = select(SchoolExam).filter_by(user_id=current_user.id)
    upcoming = db.session.execute(mine.where(SchoolExam.start_at >= now).order_by(SchoolExam.start_at)).scalars().all()
    past = db.session.execute(
        mine.where(SchoolExam.start_at < now).order_by(SchoolExam.start_at.desc()).limit(20)
    ).scalars().all()
    return render_template("school/exams.html", upcoming=upcoming, past=past, labels=schedule.EXAM_LABELS)


@bp.get("/tuition")
@login_required
def tuition():
    rows = db.session.execute(
        select(SchoolTuition).filter_by(user_id=current_user.id).order_by(SchoolTuition.term_code.desc())
    ).scalars().all()
    return render_template("school/tuition.html", rows=rows)


@bp.post("/sync-now")
@login_required
def sync_now():
    get_settings(current_user.id).sync_requested_at = utcnow()
    db.session.commit()
    flash("Sync requested. Your laptop will pick it up at its next check-in.")
    return redirect(url_for("school.index"))


@bp.route("/devices", methods=["GET", "POST"])
@login_required
def devices():
    form = DeviceForm()
    new_key = None
    if form.validate_on_submit():
        _, new_key = create_device(current_user.id, form.name.data)
        db.session.commit()
        form = DeviceForm(formdata=None)
    response = render_template("school/devices.html", form=form, devices=_active_devices(), new_key=new_key)
    if new_key:
        # The key is shown once; don't let the browser keep a copy.
        return response, 200, {"Cache-Control": "no-store"}
    return response


@bp.post("/devices/<int:device_id>/rename")
@login_required
def rename_device(device_id):
    device = _own_device(device_id)
    form = DeviceForm()
    if form.validate_on_submit():
        device.name = form.name.data
        db.session.commit()
        flash("Device renamed.")
    else:
        flash("A device name is required (up to 100 characters).", "error")
    return redirect(url_for("school.devices"))


@bp.post("/devices/<int:device_id>/revoke")
@login_required
def revoke_device(device_id):
    device = _own_device(device_id)
    if device.revoked_at is None:
        device.revoked_at = utcnow()
        db.session.commit()
    flash(f"“{device.name}” can no longer sync.")
    return redirect(url_for("school.devices"))
