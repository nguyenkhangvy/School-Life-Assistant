from datetime import datetime

from app.school.services.sync_status import RunInfo, describe

# Naive UTC. 07:05 UTC = 14:05 in Vietnam.
NOW = datetime(2026, 10, 1, 7, 30)


def run(status, started="07:00", finished="07:05", error_code=None, sections=None):
    started_at = datetime(2026, 10, 1, *map(int, started.split(":")))
    finished_at = None if finished is None else datetime(2026, 10, 1, *map(int, finished.split(":")))
    return RunInfo(status, started_at, finished_at, error_code, None, sections)


def status(latest=None, requested=None, has_device=True, last_seen=NOW, last_good=None):
    return describe(
        now=NOW,
        interval_hours=12,
        sync_requested_at=requested,
        latest=latest,
        last_good_finished_at=last_good,
        has_device=has_device,
        last_seen_at=last_seen,
    )


def test_no_device_yet_points_to_the_devices_page():
    result = status(has_device=False, last_seen=None)

    assert result.state == "no_device"
    assert "Devices page" in result.detail
    assert result.laptop_warning is None


def test_never_synced():
    assert status().state == "never"


def test_a_successful_sync_shows_vietnam_time():
    result = status(latest=run("success"), last_good=datetime(2026, 10, 1, 7, 5))

    assert (result.state, result.headline) == ("success", "Synced at 14:05")
    assert result.last_synced_at == datetime(2026, 10, 1, 7, 5)


def test_a_sync_from_an_earlier_day_shows_the_date():
    earlier = RunInfo("success", datetime(2026, 9, 29, 7, 0), datetime(2026, 9, 29, 7, 5), None, None, None)

    result = status(latest=earlier)

    assert result.headline == "Synced on 29/09 14:05"


def test_running():
    assert status(latest=run("running", started="07:25", finished=None)).state == "syncing"


def test_a_run_stuck_for_20_minutes_shows_as_failed():
    result = status(latest=run("running", started="07:10", finished=None))

    assert result.state == "failed"


def test_sync_now_waiting_for_the_laptop():
    result = status(latest=run("success"), requested=datetime(2026, 10, 1, 7, 20))

    assert result.state == "requested"


def test_a_request_already_served_is_not_shown():
    assert status(latest=run("success"), requested=datetime(2026, 10, 1, 6, 0)).state == "success"


def test_wrong_password_pauses_and_says_how_to_fix_it():
    result = status(latest=run("failed", error_code="bad_credentials"))

    assert result.state == "paused"
    assert "sla-agent setup" in result.detail


def test_extra_verification_pauses_and_suggests_import():
    result = status(latest=run("failed", error_code="extra_verification"))

    assert result.state == "paused"
    assert "sla-agent import" in result.detail


def test_a_network_failure_will_retry():
    result = status(latest=run("failed", error_code="network"))

    assert result.state == "failed"
    assert "automatically" in result.detail


def test_all_parts_failed_uses_their_error():
    sections = {
        "timetable": {"status": "failed", "error_code": "edusoft_changed", "error_message": "x"},
        "tuition": {"status": "failed", "error_code": "edusoft_changed", "error_message": "x"},
    }

    result = status(latest=run("failed", sections=sections))

    assert result.state == "failed"
    assert "changed" in result.headline


def test_partial_names_the_parts_that_failed():
    sections = {
        "timetable": {"status": "ok"},
        "tuition": {"status": "failed", "error_code": "edusoft_changed", "error_message": "x"},
    }

    result = status(latest=run("partial", sections=sections), last_good=datetime(2026, 10, 1, 7, 5))

    assert (result.state, result.headline) == ("partial", "Partly synced at 14:05")
    assert "tuition" in result.detail
    assert "timetable" not in result.detail


def test_laptop_that_never_checked_in():
    assert "hasn't checked in yet" in status(last_seen=None).laptop_warning


def test_laptop_silent_for_more_than_twice_the_interval():
    result = status(last_seen=datetime(2026, 9, 30, 7, 0))

    assert result.laptop_warning == "Your laptop hasn't checked in since Wed 30/09 14:00."


def test_laptop_seen_recently_gives_no_warning():
    assert status(last_seen=datetime(2026, 9, 30, 20, 0)).laptop_warning is None
