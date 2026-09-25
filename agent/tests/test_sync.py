import logging
from datetime import date, datetime, timezone

import pytest
from sla_contract.schema import Exams, Timetable, Tuition

from agent.tests.fakes import FakeEduSoft, FakeServer
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


def sync(state, edusoft, server=None, parsers=PARSERS, trigger="scheduled"):
    server = server or FakeServer()
    outcome = run_sync(trigger, state=state, edusoft=edusoft, server=server, parsers=parsers,
                       password=PASSWORD, now=NOW)
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
    assert only_finish(server).error_code == "bad_credentials"
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

    assert only_finish(server).error_code == "extra_verification"
    assert state.paused == "extra_verification"
    assert "sla-agent import" in outcome.message


def test_edusoft_unreachable_is_reported_but_does_not_pause(state):
    outcome, server = sync(state, FakeEduSoft(login_error=NetworkError("timed out")))

    assert only_finish(server).error_code == "network"
    assert state.paused is None


def test_a_page_the_parser_cannot_read_fails_only_that_part(state):
    outcome, server = sync(state, FakeEduSoft(), parsers={**PARSERS, "tuition": broken_parser})

    result = only_finish(server)
    assert result.overall_status() == "partial"
    assert (result.tuition.status, result.tuition.error_code) == ("failed", "edusoft_changed")
    assert result.timetable.status == "ok"


def test_an_expired_session_logs_in_again_once_and_retries_the_page(state):
    edusoft = FakeEduSoft(pages={"exams": [SessionExpired("login form shown"), "<html>exams</html>"]})

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
    assert only_finish(server).error_code == "bad_credentials"
    assert state.paused == "bad_credentials"
