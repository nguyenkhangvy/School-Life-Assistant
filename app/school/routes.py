from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import current_user, login_required
from sqlalchemy import select

from app.extensions import db
from app.school.forms import DeviceForm
from app.school.models import SchoolSyncDevice
from app.school.services.changes import when
from app.school.services.devices import create_device
from app.school.services.sync_runs import get_settings, latest_run
from app.school.services.sync_status import RunInfo, describe
from app.timeutil import utcnow

bp = Blueprint("school", __name__, url_prefix="/school")


@bp.app_template_filter("vn_time")
def vn_time(moment):
    return when(moment) if moment else "never"


def _my_devices():
    return db.session.execute(
        select(SchoolSyncDevice).filter_by(user_id=current_user.id).order_by(SchoolSyncDevice.created_at)
    ).scalars().all()


def _own_device(device_id):
    return db.first_or_404(select(SchoolSyncDevice).filter_by(id=device_id, user_id=current_user.id))


def _status(now):
    settings = get_settings(current_user.id)
    latest = latest_run(current_user.id)
    last_good = latest_run(current_user.id, "success", "partial")
    active = [d for d in _my_devices() if d.revoked_at is None]
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
    status = _status(utcnow())
    db.session.commit()
    return render_template("school/index.html", status=status)


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
    response = render_template("school/devices.html", form=form, devices=_my_devices(), new_key=new_key)
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
