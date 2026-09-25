from datetime import datetime

import pytest

from app.school.services.scheduling import decide

NOW = datetime(2026, 10, 1, 12, 0)


def t(hhmm, day=1):
    hours, minutes = map(int, hhmm.split(":"))
    return datetime(2026, 10, day, hours, minutes)


@pytest.mark.parametrize(
    "case, inputs, due, reason",
    [
        ("first ever check", {}, True, "never"),
        (
            "a sync is running",
            {"last_attempt": t("11:55"), "last_success": t("00:00"), "running_since": t("11:55")},
            False, "running",
        ),
        (
            "a run stuck for 20 minutes no longer blocks Sync now",
            {"requested": t("11:50"), "last_attempt": t("11:40"), "last_success": t("00:00"),
             "running_since": t("11:40")},
            True, "requested",
        ),
        (
            "Sync now pressed after the last attempt",
            {"requested": t("11:59"), "last_attempt": t("11:00"), "last_success": t("11:00")},
            True, "requested",
        ),
        (
            "Sync now pressed but the last attempt was 4 minutes ago",
            {"requested": t("11:59"), "last_attempt": t("11:56"), "last_success": t("09:00")},
            False, "too_soon",
        ),
        (
            "Sync now pressed exactly 5 minutes after the last attempt",
            {"requested": t("11:59"), "last_attempt": t("11:55"), "last_success": t("09:00")},
            True, "requested",
        ),
        (
            "an old Sync now request that was already served",
            {"requested": t("10:00"), "last_attempt": t("10:05"), "last_success": t("10:05")},
            False, "not_due",
        ),
        (
            "12h interval passed since the last success",
            {"last_attempt": t("00:00"), "last_success": t("00:00")},
            True, "interval",
        ),
        (
            "12h interval not yet passed",
            {"last_attempt": t("00:01"), "last_success": t("00:01")},
            False, "not_due",
        ),
        (
            "last sync failed 30 minutes ago: wait for the hourly retry",
            {"last_attempt": t("11:30"), "last_success": t("00:00")},
            False, "too_soon",
        ),
        (
            "last sync failed an hour ago: retry",
            {"last_attempt": t("11:00"), "last_success": t("00:00")},
            True, "interval",
        ),
        (
            "never succeeded, last attempt failed 2 hours ago",
            {"last_attempt": t("10:00")},
            True, "interval",
        ),
    ],
    ids=lambda value: value if isinstance(value, str) and " " in value else None,
)
def test_decide(case, inputs, due, reason):
    decision = decide(
        now=NOW,
        interval_hours=12,
        sync_requested_at=inputs.get("requested"),
        last_attempt_started_at=inputs.get("last_attempt"),
        last_success_started_at=inputs.get("last_success"),
        running_since=inputs.get("running_since"),
    )

    assert (decision.due, decision.reason) == (due, reason)


def test_a_6_hour_interval_is_due_sooner_than_12():
    kwargs = dict(
        now=NOW,
        sync_requested_at=None,
        last_attempt_started_at=t("05:00"),
        last_success_started_at=t("05:00"),
        running_since=None,
    )

    assert decide(interval_hours=6, **kwargs).due is True
    assert decide(interval_hours=12, **kwargs).due is False
