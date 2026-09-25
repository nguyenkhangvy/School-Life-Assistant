"""One sync: EduSoft (timetable, exams, tuition) then Blackboard, each on its own.

Stop-don't-retry rules: a rejected password or an extra-verification request pauses
that system only (no second login attempt). An expired session gets one re-login and
one retry. One system failing never stops the other from uploading.
"""

import logging
from dataclasses import dataclass

from sla_contract.schema import EDUSOFT_SECTIONS, FinishRun

from sla_agent.blackboard_reader import read_blackboard as default_read_blackboard
from sla_agent.errors import AgentError, BadCredentials, ExtraVerification, SessionExpired
from sla_agent.log import protect
from sla_agent.parsers.registration import RegisteredCourse, parse_registered_courses

log = logging.getLogger(__name__)

PAUSE_MESSAGES = {
    "bad_credentials": "EduSoft rejected your student ID or password. EduSoft sync is paused; "
                       "run `sla-agent setup` to enter them again.",
    "extra_verification": "EduSoft asked for extra verification (CAPTCHA or code). EduSoft sync is "
                          "paused; save the pages from your browser and use `sla-agent import`.",
}
BLACKBOARD_PAUSE_MESSAGES = {
    "bad_credentials": "Blackboard rejected your username or password. Blackboard sync is paused; "
                       "run `sla-agent setup --blackboard` to enter them again.",
    "extra_verification": "Blackboard asked for extra verification (CAPTCHA, code or Microsoft sign-in). "
                          "Blackboard sync is paused.",
}
PAUSING_ERRORS = (BadCredentials, ExtraVerification)
NO_COURSE_LIST = "Blackboard needs this semester's course list from EduSoft first; it will sync after EduSoft does."


@dataclass
class Outcome:
    status: str  # success / partial / failed / paused
    message: str


def _failed(error):
    return {"status": "failed", "error_code": error.code, "error_message": str(error)[:500] or error.code}


def _unexpected(what, error):
    log.exception("Unexpected problem reading %s", what)
    return {"status": "failed", "error_code": "unknown",
            "error_message": f"Unexpected problem reading {what}: {error.__class__.__name__}"}


def blackboard_ready(state):
    return bool(state.blackboard_username) and not state.blackboard_paused


def everything_paused(state):
    return bool(state.paused) and not blackboard_ready(state)


def _read_section(name, edusoft, parsers, student_id, password):
    """One EduSoft part's result. Pausing errors are raised to stop EduSoft."""
    try:
        try:
            pages = edusoft.read(name)
        except SessionExpired:
            log.info("EduSoft session expired while reading %s; logging in again once", name)
            edusoft.login(student_id, password)
            pages = edusoft.read(name)
        return {"status": "ok", "data": parsers[name](pages)}
    except PAUSING_ERRORS:
        raise
    except AgentError as error:
        log.warning("Couldn't read %s: %s", name, error)
        return _failed(error)
    except Exception as error:  # a parser bug must not leave the run unfinished
        return _unexpected(name, error)


def _remember_registered_courses(state, edusoft, sections):
    """This semester's courses for Blackboard: EduSoft's registration list, else the timetable's codes."""
    try:
        registered = parse_registered_courses(edusoft.read("registration"))
    except Exception as error:  # the registration page is optional; fall back to the timetable
        log.info("Registration list not read (%s); using the timetable's courses", error.__class__.__name__)
        timetable = sections.get("timetable", {})
        data = timetable.get("data") if timetable.get("status") == "ok" else None
        registered = [RegisteredCourse(c.course_code, c.group or "") for c in data.courses] if data else []
    if registered:
        state.registered_courses = [[r.code, r.group] for r in registered]


def _collect_edusoft(state, edusoft, parsers, password):
    try:
        edusoft.login(state.student_id, password)
        sections = {name: _read_section(name, edusoft, parsers, state.student_id, password)
                    for name in EDUSOFT_SECTIONS}
        _remember_registered_courses(state, edusoft, sections)
        return sections
    except PAUSING_ERRORS as error:
        log.warning("Pausing EduSoft sync: %s", error)
        state.paused = error.code
        return {name: _failed(error) for name in EDUSOFT_SECTIONS}
    except AgentError as error:
        log.warning("EduSoft sync failed: %s", error)
        return {name: _failed(error) for name in EDUSOFT_SECTIONS}
    except Exception as error:
        failure = _unexpected("EduSoft", error)
        return {name: failure for name in EDUSOFT_SECTIONS}


def _collect_blackboard(state, blackboard, password, read):
    registered = [RegisteredCourse(code, group) for code, group in state.registered_courses or []]
    if not registered:
        return {"status": "failed", "error_code": "unknown", "error_message": NO_COURSE_LIST}
    try:
        blackboard.login(state.blackboard_username, password)
        try:
            data = read(blackboard, registered)
        except SessionExpired:
            log.info("Blackboard session expired; logging in again once")
            blackboard.login(state.blackboard_username, password)
            data = read(blackboard, registered)
        return {"status": "ok", "data": data}
    except PAUSING_ERRORS as error:
        log.warning("Pausing Blackboard sync: %s", error)
        state.blackboard_paused = error.code
        return _failed(error)
    except AgentError as error:
        log.warning("Blackboard sync failed: %s", error)
        return _failed(error)
    except Exception as error:
        return _unexpected("Blackboard", error)
    finally:
        blackboard.logout()


def _message(state, result, used_edusoft, used_blackboard):
    notes = []
    if used_edusoft and state.paused:
        notes.append(PAUSE_MESSAGES.get(state.paused, "EduSoft sync is paused."))
    if used_blackboard and state.blackboard_paused:
        notes.append(BLACKBOARD_PAUSE_MESSAGES.get(state.blackboard_paused, "Blackboard sync is paused."))
    if notes:
        return " ".join(notes)
    failed = [name for name, part in result.sections().items() if part.status == "failed"]
    return "Sync finished." if not failed else f"Sync finished, but couldn't read: {', '.join(failed)}."


def _paused_message(state):
    messages = [PAUSE_MESSAGES.get(state.paused, "EduSoft sync is paused.")]
    if state.blackboard_username and state.blackboard_paused:
        messages.append(BLACKBOARD_PAUSE_MESSAGES.get(state.blackboard_paused, "Blackboard sync is paused."))
    return " ".join(messages)


def run_sync(trigger, *, state, edusoft, server, parsers, password, now,
             blackboard=None, blackboard_password=None, read_blackboard=default_read_blackboard):
    """Run one sync and update `state` (the caller saves it). Server errors are raised."""
    protect(password)
    protect(blackboard_password)
    use_edusoft = not state.paused
    use_blackboard = blackboard is not None and bool(blackboard_password) and blackboard_ready(state)
    if not use_edusoft and not use_blackboard:
        return Outcome("paused", _paused_message(state))

    run_id = server.start(trigger)
    state.last_attempt_at = now.isoformat()
    sections = {}
    if use_edusoft:
        sections.update(_collect_edusoft(state, edusoft, parsers, password))
    if use_blackboard:
        sections["blackboard"] = _collect_blackboard(state, blackboard, blackboard_password, read_blackboard)
    result = FinishRun.model_validate(sections)
    status = server.finish(run_id, result)

    message = _message(state, result, use_edusoft, use_blackboard)
    state.last_result = {"at": now.isoformat(), "status": status, "message": message}
    log.info("Sync %s (%s): %s", status, trigger, message)
    return Outcome(status, message)
