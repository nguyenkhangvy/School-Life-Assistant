"""Sync run bookkeeping: settings, the latest runs, and starting a run."""

from sqlalchemy import select

from app.extensions import db
from app.school.models import SchoolSyncRun, SchoolSyncSettings
from app.school.services.scheduling import RUN_TIMEOUT, decide


class RunInProgress(Exception):
    pass


def get_settings(user_id):
    settings = db.session.get(SchoolSyncSettings, user_id)
    if settings is None:
        settings = SchoolSyncSettings(user_id=user_id, interval_hours=12)
        db.session.add(settings)
        db.session.flush()
    return settings


def latest_run(user_id, *statuses):
    query = select(SchoolSyncRun).filter_by(user_id=user_id)
    if statuses:
        query = query.where(SchoolSyncRun.status.in_(statuses))
    return db.session.execute(
        query.order_by(SchoolSyncRun.started_at.desc(), SchoolSyncRun.id.desc()).limit(1)
    ).scalar_one_or_none()


def check(user_id, now):
    settings = get_settings(user_id)
    last = latest_run(user_id)
    last_good = latest_run(user_id, "success", "partial")
    running = latest_run(user_id, "running")
    return settings, decide(
        now=now,
        interval_hours=settings.interval_hours,
        sync_requested_at=settings.sync_requested_at,
        last_attempt_started_at=last.started_at if last else None,
        last_success_started_at=last_good.started_at if last_good else None,
        running_since=running.started_at if running else None,
    )


def start_run(device, trigger, now):
    """Close stuck runs as timed out, then open a new one (caller commits)."""
    running = db.session.execute(
        select(SchoolSyncRun).filter_by(user_id=device.user_id, status="running")
    ).scalars()
    for run in running:
        if now - run.started_at < RUN_TIMEOUT:
            raise RunInProgress()
        run.status = "failed"
        run.error_code = "timeout"
        run.error_message = "The sync didn't finish within 15 minutes."
        run.finished_at = now

    run = SchoolSyncRun(
        user_id=device.user_id, device_id=device.id, trigger=trigger, started_at=now, status="running"
    )
    db.session.add(run)
    db.session.flush()
    return run
