"""sla-agent: the laptop side of School-Life-Assistant.

    sla-agent setup                  enter your details once; schedules automatic sync
    sla-agent run                    what the scheduled task calls every 15 minutes
    sla-agent sync-now               sync right away
    sla-agent status                 show the last result and whether sync is paused
    sla-agent fetch --save-html DIR  save your EduSoft pages on this laptop (for building the readers)
    sla-agent import FILE --kind K   read a page you saved from your browser and upload it
    sla-agent forget                 delete the saved secrets and the scheduled task
"""

import argparse
import getpass
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sla_contract.schema import SECTION_NAMES, FinishRun

from sla_agent import credentials
from sla_agent.edusoft_client import EduSoftClient
from sla_agent.errors import (
    AgentError,
    BadCredentials,
    DeviceKeyRejected,
    ExtraVerification,
    ParseError,
    RunInProgress,
    ServerError,
)
from sla_agent.log import protect, setup_logging
from sla_agent.parsers import PARSERS
from sla_agent.scheduler import SchedulerError, current_user, install_task, remove_task, windowless_python
from sla_agent.server_client import ServerClient, check_server_url
from sla_agent.state import agent_home, load_state, save_state
from sla_agent.sync import PAUSE_MESSAGES, run_sync

log = logging.getLogger(__name__)

MIN_MANUAL_GAP = timedelta(minutes=5)
NOT_SET_UP = "sla-agent isn't set up yet. Run `sla-agent setup` first."

# Replaced in tests.
ask = input
ask_secret = getpass.getpass


def make_edusoft():
    return EduSoftClient()


def make_server(url, key):
    return ServerClient(url, key)


def say(message):
    print(message)


def _now():
    return datetime.now(timezone.utc)


def _load():
    """(state, password, device key), or None if setup hasn't been done."""
    state = load_state()
    if not state.server_url or not state.student_id:
        return None
    password = credentials.load_edusoft(state.student_id)
    key = credentials.load_device_key(state.server_url)
    if not password or not key:
        return None
    return state, password, key


# ---- setup -------------------------------------------------------------------


def cmd_setup(args):
    state = load_state()
    server_url = ask(f"Web app address [{state.server_url or 'https://...'}]: ").strip() or state.server_url or ""
    try:
        check_server_url(server_url)
    except ValueError as error:
        say(str(error))
        return 1
    device_key = ask_secret("Device key (from the Devices page, not shown): ").strip()
    student_id = ask(f"EduSoft student ID [{state.student_id or ''}]: ").strip() or state.student_id or ""
    password = ask_secret("EduSoft password (not shown): ")
    protect(device_key)
    protect(password)
    if not (device_key and student_id and password):
        say("All answers are needed. Nothing was saved.")
        return 1

    say("Checking the device key with the web app...")
    try:
        make_server(server_url, device_key).check()
    except DeviceKeyRejected:
        say("The web app rejected this device key. Create a new one on the Devices page. Nothing was saved.")
        return 1
    except ServerError as error:
        say(f"Couldn't reach the web app: {error} Nothing was saved.")
        return 1

    say("Checking your EduSoft login (one attempt)...")
    try:
        make_edusoft().login(student_id, password)
    except BadCredentials:
        say("EduSoft rejected the student ID or password. Nothing was saved.")
        return 1
    except ExtraVerification:
        say("EduSoft asked for extra verification (CAPTCHA or code), so automatic sync can't be used. "
            "Nothing was saved. You can still use `sla-agent import` with pages saved from your browser.")
        return 1
    except AgentError as error:
        say(f"Couldn't check your EduSoft login: {error} Nothing was saved; try again later.")
        return 1

    if state.student_id and state.student_id != student_id:
        credentials.forget(state.student_id, None)
    credentials.save_edusoft(student_id, password)
    credentials.save_device_key(server_url, device_key)
    state.server_url, state.student_id, state.paused = server_url, student_id, None
    save_state(state)
    say("Saved. Your password is in Windows Credential Manager, not in any file.")

    if not args.no_schedule:
        try:
            install_task(windowless_python(), current_user(), folder=agent_home())
        except SchedulerError as error:
            say(f"{error} You can still sync by hand with `sla-agent sync-now`.")
            return 1
        say("Automatic sync is on: this laptop checks in every 15 minutes while you're logged in.")
    say("Run `sla-agent sync-now` to sync right away.")
    return 0


# ---- syncing -----------------------------------------------------------------


def _sync(trigger, state, password, server):
    try:
        outcome = run_sync(trigger, state=state, edusoft=make_edusoft(), server=server, parsers=PARSERS,
                           password=password, now=_now())
    except RunInProgress:
        say("A sync is already running.")
        return 0
    except DeviceKeyRejected as error:
        say(f"{error} Run `sla-agent setup` with a new key.")
        return 1
    except ServerError as error:
        log.warning("Web app problem: %s", error)
        say(f"Couldn't reach the web app: {error}")
        save_state(state)
        return 1
    save_state(state)
    say(outcome.message)
    return 0 if outcome.status in ("success", "partial") else 1


def cmd_run(args):
    loaded = _load()
    if loaded is None:
        say(NOT_SET_UP)
        return 1
    state, password, key = loaded
    server = make_server(state.server_url, key)
    try:
        decision = server.check()  # also tells the web app this laptop is alive
    except ServerError as error:
        log.warning("Check-in failed: %s", error)
        return 1
    if state.paused:
        log.info("Automatic sync is paused (%s); not syncing", state.paused)
        return 0
    if not decision.due:
        log.info("No sync due (%s)", decision.reason)
        return 0
    return _sync("manual" if decision.reason == "requested" else "scheduled", state, password, server)


def cmd_sync_now(args):
    loaded = _load()
    if loaded is None:
        say(NOT_SET_UP)
        return 1
    state, password, key = loaded
    if state.paused:
        say(PAUSE_MESSAGES.get(state.paused, "Automatic sync is paused."))
        return 1
    if state.last_attempt_at and _now() - datetime.fromisoformat(state.last_attempt_at) < MIN_MANUAL_GAP:
        say("The last sync was less than 5 minutes ago. Please try again in a few minutes.")
        return 1
    return _sync("manual", state, password, make_server(state.server_url, key))


# ---- saved pages ----------------------------------------------------------------


def cmd_fetch(args):
    loaded = _load()
    if loaded is None:
        say(NOT_SET_UP)
        return 1
    state, password, _ = loaded
    if state.paused:
        say(PAUSE_MESSAGES.get(state.paused, "Automatic sync is paused."))
        return 1
    folder = Path(args.save_html)
    edusoft = make_edusoft()
    try:
        edusoft.login(state.student_id, password)
        pages = {name: edusoft.get_page(name) for name in ("home", *SECTION_NAMES)}
    except (BadCredentials, ExtraVerification) as error:
        state.paused = error.code
        save_state(state)
        say(PAUSE_MESSAGES[error.code])
        return 1
    except AgentError as error:
        say(f"Couldn't read EduSoft: {error}")
        return 1
    folder.mkdir(parents=True, exist_ok=True)
    for name, html in pages.items():
        (folder / f"{name}.html").write_text(html, encoding="utf-8")
    say(f"Saved {len(pages)} pages to {folder.resolve()}.\n"
        "They contain your personal data. Before sharing them, remove your name, student ID and "
        "date of birth. Never commit them to GitHub.")
    return 0


def cmd_import(args):
    state = load_state()
    key = credentials.load_device_key(state.server_url) if state.server_url else None
    if not key:
        say(NOT_SET_UP)
        return 1
    html = Path(args.file).read_text(encoding="utf-8")
    try:
        data = PARSERS[args.kind](html)
    except ParseError as error:
        say(f"Couldn't read this page: {error}")
        return 1
    server = make_server(state.server_url, key)
    try:
        run_id = server.start("import")
        status = server.finish(run_id, FinishRun.model_validate({args.kind: {"status": "ok", "data": data}}))
    except ServerError as error:
        say(f"Couldn't upload: {error}")
        return 1
    say(f"Imported your {args.kind} ({status}).")
    return 0


# ---- status / forget ----------------------------------------------------------------


def cmd_status(args):
    state = load_state()
    if not state.server_url:
        say(NOT_SET_UP)
        return 1
    say(f"Web app:     {state.server_url}")
    say(f"Student ID:  {state.student_id}")
    if state.paused:
        say(f"Automatic sync: PAUSED. {PAUSE_MESSAGES.get(state.paused, '')}")
    else:
        say("Automatic sync: on")
    if state.last_result:
        say(f"Last sync:   {state.last_result['status']} at {state.last_result['at']}: {state.last_result['message']}")
    else:
        say("Last sync:   never")
    return 0


def cmd_forget(args):
    state = load_state()
    credentials.forget(state.student_id, state.server_url)
    remove_task()
    (agent_home() / "state.json").unlink(missing_ok=True)
    say("Removed your saved EduSoft password, the device key and the scheduled task from this laptop.")
    return 0


COMMANDS = {
    "setup": cmd_setup,
    "run": cmd_run,
    "sync-now": cmd_sync_now,
    "status": cmd_status,
    "fetch": cmd_fetch,
    "import": cmd_import,
    "forget": cmd_forget,
}


def main(argv=None):
    parser = argparse.ArgumentParser(prog="sla-agent", description="School-Life-Assistant laptop sync agent.")
    commands = parser.add_subparsers(dest="command", required=True)
    setup = commands.add_parser("setup", help="enter your details once; schedules automatic sync")
    setup.add_argument("--no-schedule", action="store_true", help="don't create the scheduled task")
    commands.add_parser("run", help="scheduled check-in: sync if the web app says it's due")
    commands.add_parser("sync-now", help="sync right away")
    commands.add_parser("status", help="show the last result and whether sync is paused")
    fetch = commands.add_parser("fetch", help="save your EduSoft pages on this laptop")
    fetch.add_argument("--save-html", metavar="FOLDER", required=True)
    importer = commands.add_parser("import", help="upload a page you saved from your browser")
    importer.add_argument("file")
    importer.add_argument("--kind", choices=SECTION_NAMES, required=True)
    commands.add_parser("forget", help="delete saved secrets and the scheduled task")

    args = parser.parse_args(argv)
    # Output piped or redirected on Windows uses cp1252; never crash on Vietnamese text.
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    setup_logging()
    return COMMANDS[args.command](args)
