"""When should the laptop agent sync? A pure function, so it is easy to test."""

from dataclasses import dataclass
from datetime import timedelta

RUN_TIMEOUT = timedelta(minutes=15)  # a run older than this is treated as stuck
MIN_MANUAL_GAP = timedelta(minutes=5)  # "Sync now" can't start syncs closer than this
MIN_SCHEDULED_GAP = timedelta(hours=1)  # failed scheduled syncs retry at most hourly


@dataclass(frozen=True)
class Decision:
    due: bool
    reason: str  # never / running / requested / too_soon / interval / not_due


def decide(
    now,
    interval_hours,
    sync_requested_at,
    last_attempt_started_at,
    last_success_started_at,
    running_since,
):
    if running_since is not None and now - running_since < RUN_TIMEOUT:
        return Decision(False, "running")

    since_attempt = None if last_attempt_started_at is None else now - last_attempt_started_at

    if sync_requested_at is not None and (
        last_attempt_started_at is None or sync_requested_at > last_attempt_started_at
    ):
        if since_attempt is not None and since_attempt < MIN_MANUAL_GAP:
            return Decision(False, "too_soon")
        return Decision(True, "requested")

    if last_attempt_started_at is None:
        return Decision(True, "never")

    interval = timedelta(hours=interval_hours)
    if last_success_started_at is None or now - last_success_started_at >= interval:
        if since_attempt < MIN_SCHEDULED_GAP:
            return Decision(False, "too_soon")
        return Decision(True, "interval")

    return Decision(False, "not_due")
