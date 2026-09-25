"""One sync: log in to EduSoft, read the three pages, upload what they contain.

Stop-don't-retry rules: a rejected password or an extra-verification request
pauses automatic sync (no second login attempt). An expired session gets one
re-login and one retry of that page.
"""

import logging
from dataclasses import dataclass

from sla_contract.schema import SECTION_NAMES, FinishRun

from sla_agent.errors import AgentError, BadCredentials, ExtraVerification, SessionExpired
from sla_agent.log import protect

log = logging.getLogger(__name__)

PAUSE_MESSAGES = {
    "bad_credentials": "EduSoft rejected your student ID or password. Automatic sync is paused; "
                       "run `sla-agent setup` to enter them again.",
    "extra_verification": "EduSoft asked for extra verification (CAPTCHA or code). Automatic sync is "
                          "paused; save the pages from your browser and use `sla-agent import`.",
}
PAUSING_ERRORS = (BadCredentials, ExtraVerification)


@dataclass
class Outcome:
    status: str  # success / partial / failed / paused
    message: str


def _failed(error):
    return {"status": "failed", "error_code": error.code, "error_message": str(error)[:500] or error.code}


def _read_section(name, edusoft, parsers, student_id, password):
    """One part's result for the upload. Pausing errors are raised to stop the whole run."""
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
        log.exception("Unexpected problem reading %s", name)
        return {"status": "failed", "error_code": "unknown",
                "error_message": f"Unexpected problem reading {name}: {error.__class__.__name__}"}


def _collect(state, edusoft, parsers, password):
    try:
        edusoft.login(state.student_id, password)
        sections = {name: _read_section(name, edusoft, parsers, state.student_id, password)
                    for name in SECTION_NAMES}
        return FinishRun.model_validate(sections)
    except PAUSING_ERRORS as error:
        log.warning("Pausing automatic sync: %s", error)
        state.paused = error.code
        return FinishRun(error_code=error.code, error_message=str(error)[:500])
    except AgentError as error:
        log.warning("Sync failed: %s", error)
        return FinishRun(error_code=error.code, error_message=str(error)[:500] or error.code)
    except Exception as error:
        log.exception("Unexpected problem during sync")
        return FinishRun(error_code="unknown", error_message=f"Unexpected problem: {error.__class__.__name__}")


def run_sync(trigger, *, state, edusoft, server, parsers, password, now):
    """Run one sync and update `state` (the caller saves it). Server errors are raised."""
    protect(password)
    if state.paused:
        return Outcome("paused", PAUSE_MESSAGES.get(state.paused, "Automatic sync is paused."))

    run_id = server.start(trigger)
    state.last_attempt_at = now.isoformat()
    result = _collect(state, edusoft, parsers, password)
    status = server.finish(run_id, result)

    if state.paused:
        message = PAUSE_MESSAGES[state.paused]
    elif result.error_code:
        message = f"Sync failed: {result.error_message}"
    else:
        failed = [name for name, part in result.sections().items() if part.status == "failed"]
        message = "Sync finished." if not failed else f"Sync finished, but couldn't read: {', '.join(failed)}."
    state.last_result = {"at": now.isoformat(), "status": status, "message": message}
    log.info("Sync %s (%s): %s", status, trigger, message)
    return Outcome(status, message)
