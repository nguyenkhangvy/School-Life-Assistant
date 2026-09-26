"""The sync API used only by the laptop agent (JSON, device key instead of login)."""

from flask import Blueprint, abort, g, jsonify, request
from pydantic import ValidationError
from sla_contract.schema import CheckResult, FinishResult, FinishRun, StartResult, StartRun
from werkzeug.exceptions import RequestEntityTooLarge

from app.extensions import db
from app.school.models import SchoolSyncRun
from app.school.services.devices import authenticate
from app.school.services.ingest import finish_run
from app.school.services.sync_runs import RunInProgress, check, start_run
from app.timeutil import utcnow

bp = Blueprint("school_api", __name__, url_prefix="/api/school/sync")

MAX_UPLOAD_BYTES = 5_000_000  # a full semester of Blackboard text, JSON-escaped, stays well under this


def _error(code, status, **extra):
    return jsonify(error=code, **extra), status


@bp.before_request
def _authenticate_device():
    scheme, _, raw_key = request.headers.get("Authorization", "").partition(" ")
    device = authenticate(raw_key.strip()) if scheme == "Bearer" else None
    if device is None:
        return _error("invalid_device_key", 401)
    device.last_seen_at = utcnow()
    db.session.commit()
    g.device = device
    request.max_content_length = MAX_UPLOAD_BYTES


@bp.errorhandler(RequestEntityTooLarge)
def _too_large(_error_):
    return _error("payload_too_large", 413)


def _validate(model):
    """Parse the JSON body, or return a 422 response. Never echoes the input back."""
    try:
        return model.model_validate(request.get_json(silent=True) or {}), None
    except ValidationError as error:
        details = [
            {"loc": list(e["loc"]), "msg": e["msg"]}
            for e in error.errors(include_url=False, include_input=False, include_context=False)
        ]
        return None, _error("invalid_payload", 422, details=details)


@bp.get("/check")
def check_due():
    settings, decision = check(g.device.user_id, utcnow())
    db.session.commit()
    return jsonify(
        CheckResult(due=decision.due, reason=decision.reason, interval_hours=settings.interval_hours).model_dump()
    )


@bp.post("/runs")
def start():
    body, error = _validate(StartRun)
    if error:
        return error
    try:
        run = start_run(g.device, body.trigger, utcnow())
    except RunInProgress:
        db.session.rollback()
        return _error("run_in_progress", 409)
    db.session.commit()
    return jsonify(StartResult(run_id=run.id).model_dump()), 201


@bp.post("/runs/<int:run_id>/finish")
def finish(run_id):
    run = db.session.get(SchoolSyncRun, run_id)
    if run is None or run.user_id != g.device.user_id:
        abort(404)
    if run.status != "running":
        return _error("run_not_running", 409)
    body, error = _validate(FinishRun)
    if error:
        return error
    finish_run(run, body, utcnow())
    db.session.commit()
    return jsonify(FinishResult(status=run.status).model_dump())
