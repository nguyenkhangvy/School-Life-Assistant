"""Turn the sync history into the status the user sees. A pure function."""

from dataclasses import dataclass
from datetime import timedelta
from typing import NamedTuple

from app.school.services.changes import to_vietnam, when
from app.school.services.scheduling import RUN_TIMEOUT

RETRY = "It will be tried again automatically."

# error code -> (state, headline, what to do)
PROBLEMS = {
    "bad_credentials": (
        "paused",
        "Paused: EduSoft rejected your student ID or password",
        "Run `sla-agent setup` on your laptop to enter them again.",
    ),
    "extra_verification": (
        "paused",
        "Paused: EduSoft asked for extra verification",
        "Automatic sync can't pass a CAPTCHA or code. Save the pages from your browser "
        "and use `sla-agent import`.",
    ),
    "network": ("failed", "Sync failed: EduSoft couldn't be reached", RETRY),
    "session_expired": ("failed", "Sync failed: EduSoft ended the session", RETRY),
    "edusoft_changed": (
        "failed",
        "Sync failed: EduSoft's pages have changed",
        "sla-agent needs an update to read the new pages.",
    ),
    "timeout": ("failed", "The last sync didn't finish", RETRY),
}
UNKNOWN = ("failed", "Sync failed", RETRY)

PART_NAMES = {"timetable": "timetable", "exams": "exam schedule", "tuition": "tuition"}


class RunInfo(NamedTuple):
    status: str
    started_at: object
    finished_at: object
    error_code: str | None
    error_message: str | None
    sections: dict | None


@dataclass(frozen=True)
class SyncStatus:
    state: str  # no_device / never / requested / syncing / success / partial / failed / paused
    headline: str
    detail: str | None = None
    last_synced_at: object = None
    laptop_warning: str | None = None


def _at(moment, now):
    local, today = to_vietnam(moment), to_vietnam(now)
    if local.date() == today.date():
        return f"at {local:%H:%M}"
    return f"on {local:%d/%m %H:%M}"


def _laptop_warning(now, interval_hours, last_seen_at):
    if last_seen_at is None:
        return "Your laptop hasn't checked in yet. Run `sla-agent setup` on it."
    if now - last_seen_at > timedelta(hours=2 * interval_hours):
        return f"Your laptop hasn't checked in since {when(last_seen_at)}."
    return None


def _failed_parts(sections):
    return [name for name, result in (sections or {}).items() if result["status"] == "failed"]


def describe(now, interval_hours, sync_requested_at, latest, last_good_finished_at, has_device, last_seen_at):
    if not has_device:
        return SyncStatus(
            "no_device",
            "Not set up yet",
            "Add your laptop on the Devices page, then run `sla-agent setup` on it.",
        )

    def make(state, headline, detail=None):
        return SyncStatus(
            state, headline, detail, last_good_finished_at, _laptop_warning(now, interval_hours, last_seen_at)
        )

    running = latest is not None and latest.status == "running"
    if running and now - latest.started_at < RUN_TIMEOUT:
        return make("syncing", "Syncing…")
    if sync_requested_at is not None and (latest is None or sync_requested_at > latest.started_at):
        return make("requested", "Sync requested, waiting for your laptop",
                    "Your laptop checks in every 15 minutes while it's on.")
    if latest is None:
        return make("never", "Never synced", "Your laptop will sync at its next check-in.")

    if running:
        return make(*PROBLEMS["timeout"])
    if latest.status == "failed":
        code = latest.error_code
        if code is None:
            failed = _failed_parts(latest.sections)
            code = latest.sections[failed[0]]["error_code"] if failed else None
        return make(*PROBLEMS.get(code, UNKNOWN))
    if latest.status == "partial":
        parts = ", ".join(PART_NAMES.get(name, name) for name in _failed_parts(latest.sections))
        return make("partial", f"Partly synced {_at(latest.finished_at, now)}",
                    f"Couldn't read: {parts}. The previous data for it is still shown.")
    return make("success", f"Synced {_at(latest.finished_at, now)}")
