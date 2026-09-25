import logging
from datetime import date, datetime, timezone

import pytest
from sla_contract.schema import Blackboard, Exams, Timetable, Tuition

from agent.tests.fakes import FakeBlackboard, FakeEduSoft, FakeServer
from sla_agent.errors import (
    BadCredentials,
    ExtraVerification,
    NetworkError,
    ParseError,
    SessionExpired,
)
from sla_agent.log import setup_logging
from sla_agent.state import State
from sla_agent.sync import run_sync

NOW = datetime(2026, 10, 1, 7, 0, tzinfo=timezone.utc)
PASSWORD = "s3cret-pass"


def parse_timetable(html):
    return Timetable(term_code="20261", courses=[])


def parse_exams(html):
    return Exams(term_code="20261", exams=[])


def parse_tuition(html):
    return Tuition(term_code="20261", amount_due=1, amount_paid=0, balance=1, due_date=date(2026, 10, 15))


PARSERS = {"timetable": parse_timetable, "exams": parse_exams, "tuition": parse_tuition}


def broken_parser(html):
    raise ParseError("Tuition table not found")


@pytest.fixture
def state():
    return State(server_url="https://sla.example.com", student_id="ITITIU20001")



BB_PASSWORD = "bb-s3cret"


def empty_blackboard(client, registered):
    return Blackboard(courses=[])


def sync(state, edusoft, server=None, parsers=PARSERS, trigger="scheduled", blackboard=None, read=None):
    server = server or FakeServer()
    outcome = run_sync(trigger, state=state, edusoft=edusoft, server=server, parsers=parsers,
                       password=PASSWORD, now=NOW, blackboard=blackboard,
                       blackboard_password=BB_PASSWORD if blackboard else None,
                       read_blackboard=read or empty_blackboard)
    return outcome, server


def only_finish(server):
    [(run_id, result)] = server.finishes
    assert run_id == 41
    return result


def test_a_good_sync_uploads_all_three_parts(state):
    outcome, server = sync(state, FakeEduSoft())

    result = only_finish(server)
    assert result.overall_status() == "success"
    assert set(result.sections()) == {"timetable", "exams", "tuition"}
    assert outcome.status == "success"
    assert state.last_attempt_at == NOW.isoformat()
    assert state.last_result["status"] == "success"


def test_a_wrong_password_pauses_after_exactly_one_login_attempt(state):
    edusoft = FakeEduSoft(login_error=BadCredentials("EduSoft rejected the student ID or password."))

    outcome, server = sync(state, edusoft)

    assert len(edusoft.logins) == 1
    assert edusoft.page_calls == []
    result = only_finish(server)
    assert {name: part.error_code for name, part in result.sections().items()} == {
        "timetable": "bad_credentials", "exams": "bad_credentials", "tuition": "bad_credentials"}
    assert state.paused == "bad_credentials"
    assert "sla-agent setup" in outcome.message


def test_a_paused_agent_contacts_nobody(state):
    state.paused = "bad_credentials"
    edusoft = FakeEduSoft()

    outcome, server = sync(state, edusoft)

    assert (edusoft.logins, server.starts, server.finishes) == ([], [], [])
    assert outcome.status == "paused"


def test_extra_verification_pauses_and_suggests_import(state):
    outcome, server = sync(state, FakeEduSoft(login_error=ExtraVerification("CAPTCHA shown")))

    assert only_finish(server).timetable.error_code == "extra_verification"
    assert state.paused == "extra_verification"
    assert "sla-agent import" in outcome.message


def test_edusoft_unreachable_is_reported_but_does_not_pause(state):
    outcome, server = sync(state, FakeEduSoft(login_error=NetworkError("timed out")))

    assert only_finish(server).timetable.error_code == "network"
    assert state.paused is None


def test_a_page_the_parser_cannot_read_fails_only_that_part(state):
    outcome, server = sync(state, FakeEduSoft(), parsers={**PARSERS, "tuition": broken_parser})

    result = only_finish(server)
    assert result.overall_status() == "partial"
    assert (result.tuition.status, result.tuition.error_code) == ("failed", "edusoft_changed")
    assert result.timetable.status == "ok"


def test_an_expired_session_logs_in_again_once_and_retries_the_page(state):
    edusoft = FakeEduSoft(pages={"exams": [SessionExpired("login form shown"), {"term": "20261", "final": "", "midterm": ""}]})

    sync(state, edusoft)

    assert len(edusoft.logins) == 2
    assert edusoft.page_calls.count("exams") == 2


def test_a_session_that_keeps_expiring_fails_that_part_without_looping(state):
    edusoft = FakeEduSoft(pages={"exams": [SessionExpired("login form shown")]})

    outcome, server = sync(state, edusoft)

    assert len(edusoft.logins) == 2
    assert only_finish(server).exams.error_code == "session_expired"


def test_an_unexpected_parser_crash_still_finishes_the_run(state):
    def crashing(html):
        raise AttributeError("'NoneType' object has no attribute 'find_all'")

    outcome, server = sync(state, FakeEduSoft(), parsers={**PARSERS, "timetable": crashing})

    result = only_finish(server)
    assert result.timetable.status == "failed"
    assert result.exams.status == "ok"


def test_the_password_never_reaches_the_log_file(state, tmp_path):
    log_path = setup_logging(tmp_path)
    edusoft = FakeEduSoft(login_error=BadCredentials(f"rejected {PASSWORD}"))

    sync(state, edusoft)
    logging.getLogger("sla_agent.test").info("password was %s", PASSWORD)

    for handler in logging.getLogger().handlers:
        if str(tmp_path) in getattr(handler, "baseFilename", ""):
            handler.flush()
            logging.getLogger().removeHandler(handler)
            handler.close()
    text = log_path.read_text(encoding="utf-8")
    assert PASSWORD not in text
    assert "***" in text


def test_a_password_rejected_during_re_login_pauses_and_stops(state):
    class PasswordChangedMidSync(FakeEduSoft):
        def login(self, student_id, password):
            self.logins.append((student_id, password))
            if len(self.logins) > 1:
                raise BadCredentials("EduSoft rejected the student ID or password.")

    edusoft = PasswordChangedMidSync(pages={"timetable": [SessionExpired("login form shown")]})

    outcome, server = sync(state, edusoft)

    assert len(edusoft.logins) == 2
    assert edusoft.page_calls == ["timetable"]
    assert only_finish(server).timetable.error_code == "bad_credentials"
    assert state.paused == "bad_credentials"


@pytest.fixture
def bb_state(state):
    state.blackboard_username = "bbuser"
    state.registered_courses = [["IT093IU", "02"]]
    return state


def test_blackboard_syncs_after_edusoft_and_logs_out(bb_state):
    blackboard = FakeBlackboard()
    seen = []

    def read(client, registered):
        seen.append(registered)
        return Blackboard(courses=[])

    outcome, server = sync(bb_state, FakeEduSoft(), blackboard=blackboard, read=read)

    assert list(only_finish(server).sections()) == ["timetable", "exams", "tuition", "blackboard"]
    assert blackboard.logins == [("bbuser", BB_PASSWORD)]
    assert blackboard.logouts == 1
    assert outcome.status == "success"
    assert len(seen) == 1


def test_a_wrong_edusoft_password_still_syncs_blackboard_with_the_last_known_courses(bb_state):
    edusoft = FakeEduSoft(login_error=BadCredentials("rejected"))
    seen = []

    outcome, server = sync(bb_state, edusoft, blackboard=FakeBlackboard(),
                           read=lambda client, registered: seen.append(registered) or Blackboard(courses=[]))

    result = only_finish(server)
    assert result.timetable.error_code == "bad_credentials"
    assert result.blackboard.status == "ok"
    assert bb_state.paused == "bad_credentials"
    assert [tuple(r) for r in seen[0]] == [("IT093IU", "02")]


def test_a_wrong_blackboard_password_pauses_only_blackboard(bb_state):
    blackboard = FakeBlackboard(login_error=BadCredentials("rejected"))

    outcome, server = sync(bb_state, FakeEduSoft(), blackboard=blackboard)

    result = only_finish(server)
    assert (result.timetable.status, result.blackboard.error_code) == ("ok", "bad_credentials")
    assert (bb_state.paused, bb_state.blackboard_paused) == (None, "bad_credentials")
    assert len(blackboard.logins) == 1
    assert "sla-agent setup --blackboard" in outcome.message


def test_a_paused_blackboard_is_not_contacted(bb_state):
    bb_state.blackboard_paused = "bad_credentials"
    blackboard = FakeBlackboard()

    sync(bb_state, FakeEduSoft(), blackboard=blackboard)

    assert blackboard.logins == []


def test_both_paused_contacts_nobody(bb_state):
    bb_state.paused, bb_state.blackboard_paused = "bad_credentials", "bad_credentials"
    edusoft, blackboard = FakeEduSoft(), FakeBlackboard()

    outcome, server = sync(bb_state, edusoft, blackboard=blackboard)

    assert (edusoft.logins, blackboard.logins, server.starts) == ([], [], [])
    assert outcome.status == "paused"


def test_an_expired_blackboard_session_logs_in_again_once(bb_state):
    blackboard = FakeBlackboard()
    calls = []

    def read(client, registered):
        calls.append(1)
        if len(calls) == 1:
            raise SessionExpired("expired")
        return Blackboard(courses=[])

    _, server = sync(bb_state, FakeEduSoft(), blackboard=blackboard, read=read)

    assert len(blackboard.logins) == 2
    assert only_finish(server).blackboard.status == "ok"


def test_blackboard_without_a_known_course_list_waits_for_edusoft(state):
    state.blackboard_username, state.paused = "bbuser", "bad_credentials"

    _, server = sync(state, FakeEduSoft(), blackboard=FakeBlackboard())

    result = only_finish(server)
    assert result.blackboard.status == "failed"
    assert "course list" in result.blackboard.error_message


def test_the_registered_course_list_is_remembered(bb_state):
    from pathlib import Path

    page = (Path(__file__).parent / "fixtures" / "registration.html").read_text(encoding="utf-8")
    bb_state.registered_courses = None
    edusoft = FakeEduSoft(pages={"registration": [{"registration": page}]})

    sync(bb_state, edusoft)

    assert ["IT093IU", "02"] in bb_state.registered_courses
    assert len(bb_state.registered_courses) == 8
