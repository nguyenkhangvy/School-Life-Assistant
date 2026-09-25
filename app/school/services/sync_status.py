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

BLACKBOARD_PROBLEMS = {
    "bad_credentials": ("paused", "Paused: Blackboard rejected your username or password",
                        "Run `sla-agent setup --blackboard` on your laptop to enter them again."),
    "extra_verification": ("paused", "Paused: Blackboard asked for extra verification",
                           "Automatic Blackboard sync can't pass a CAPTCHA, code or Microsoft sign-in."),
    "network": ("failed", "Sync failed: Blackboard couldn't be reached", RETRY),
    "session_expired": ("failed", "Sync failed: Blackboard ended the session", RETRY),
    "source_changed": ("failed", "Sync failed: Blackboard's data format has changed",
                       "sla-agent needs an update to read it."),
}

PART_NAMES = {"timetable": "timetable", "exams": "exam schedule", "tuition": "tuition", "blackboard": "Blackboard"}

SYSTEMS = (("EduSoft", ("timetable", "exams", "tuition")), ("Blackboard", ("blackboard",)))
PAUSE_HINTS = {
    ("EduSoft", "bad_credentials"): "paused: wrong student ID or password. Run `sla-agent setup`.",
    ("Blackboard", "bad_credentials"): "paused: wrong username or password. Run `sla-agent setup --blackboard`.",
    ("EduSoft", "extra_verification"): "paused: asked for extra verification (CAPTCHA or code).",
    ("Blackboard", "extra_verification"): "paused: asked for extra verification (CAPTCHA, code or Microsoft sign-in).",
}
FAILURE_HINTS = {
    "network": "couldn't be reached; it will be tried again automatically.",
    "session_expired": "ended the session; it will be tried again automatically.",
    "edusoft_changed": "its pages changed; sla-agent needs an update.",
    "source_changed": "its data format changed; sla-agent needs an update.",
}


class SystemLine(NamedTuple):
    name: str
    state: str  # ok / partial / failed / paused
    text: str


def system_lines(runs, now):
    """One line per system, from the newest finished run that included it (runs newest first)."""
    lines = []
    for name, parts in SYSTEMS:
        run = next((r for r in runs if r.status != "running" and any(p in (r.sections or {}) for p in parts)), None)
        if run is None:
            continue
        results = {p: r for p, r in run.sections.items() if p in parts}
        failed = [p for p, r in results.items() if r["status"] == "failed"]
        if not failed:
            lines.append(SystemLine(name, "ok", f"synced {_at(run.finished_at, now)}"))
            continue
        code = results[failed[0]].get("error_code")
        if (name, code) in PAUSE_HINTS:
            lines.append(SystemLine(name, "paused", PAUSE_HINTS[(name, code)]))
        elif len(failed) < len(results):
            names = ", ".join(PART_NAMES.get(p, p) for p in failed)
            lines.append(SystemLine(name, "partial", f"synced {_at(run.finished_at, now)}, but couldn't read: {names}"))
        else:
            lines.append(SystemLine(name, "failed", FAILURE_HINTS.get(code, "sync failed; it will be tried again automatically.")))
    return lines


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
        problems = PROBLEMS
        if code is None:
            failed = _failed_parts(latest.sections)
            code = latest.sections[failed[0]]["error_code"] if failed else None
            if failed and failed[0] == "blackboard":
                problems = BLACKBOARD_PROBLEMS
        return make(*problems.get(code, UNKNOWN))
    if latest.status == "partial":
        parts = ", ".join(PART_NAMES.get(name, name) for name in _failed_parts(latest.sections))
        return make("partial", f"Partly synced {_at(latest.finished_at, now)}",
                    f"Couldn't read: {parts}. The previous data for it is still shown.")
    return make("success", f"Synced {_at(latest.finished_at, now)}")
