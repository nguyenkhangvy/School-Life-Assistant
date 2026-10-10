"""The whole test set of the mail time reader (spec 2026-10-07-mail-event-kinds-design.md §8.1): the student's test
mails and the short cases of the design discussion, each with the result the student checked. They come from
docs/superpowers/specs/2026-10-07-mail-event-kinds-cases.md, made into fixtures/mail-times-cases.json by
agent/tools/mail_times_cases.py. Each case also checks that its text never reaches its upload (§7.5)."""

import json
import re
from datetime import date, datetime, time, timezone
from pathlib import Path

import pytest

from agent.tools.mail_times_score import as_case_fields
from sla_agent.class_changes import fold
from sla_agent.mail_rules import Context, Email, sort_email
from sla_agent.mail_times import read_times

CASES = json.loads((Path(__file__).parent / "fixtures" / "mail-times-cases.json").read_text(encoding="utf-8"))["cases"]
FIELDS = ("sessions", "periods", "deadlines", "meeting", "registered")
# Ids of cases the student agreed the reader may get wrong; the cases document lists them too.
KNOWN_MISSES = set()


@pytest.mark.parametrize("case", CASES, ids=[case["id"] for case in CASES])
def test_each_case_reads_as_the_student_checked(case):
    if case["id"] in KNOWN_MISSES:
        pytest.xfail("a known miss the student agreed to")

    found = read_times(case["subject"], case["text"], date.fromisoformat(case["arrived"]))

    assert as_case_fields(found) == {field: case[field] for field in FIELDS}


# Fields holding a code from a fixed list of the upload format (spec §3.2), never the email's words.
CODES = ("categories", "mode", "relative", "label", "kind", "invitation")


def _strings(value, leave_out=("subject",) + CODES):
    """Every string inside an upload, but its subject (already shown) and its codes."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, inner in value.items():
            if key not in leave_out:
                yield from _strings(inner)
    elif isinstance(value, list):
        for inner in value:
            yield from _strings(inner)


@pytest.mark.parametrize("case", CASES, ids=[case["id"] for case in CASES])
def test_no_part_of_a_mails_text_reaches_its_upload(case):
    email = Email(key="0" * 64, entry_id="00AB", thread_id=None,
                  received_at=datetime.combine(date.fromisoformat(case["arrived"]), time(2), tzinfo=timezone.utc),
                  sender_name="Someone", sender_address="someone@example.com", subject=case["subject"], text=case["text"])

    upload = " ".join(fold(s) for s in _strings(sort_email(email, Context()).model_dump(mode="json")))

    words = set(re.findall(r"[^\W\d_]{5,}", fold(case["text"]))) - set(re.findall(r"\w+", fold(case["subject"])))
    assert words & set(re.findall(r"[^\W\d_]{5,}", upload)) == set()


SAMPLES = json.loads((Path(__file__).parent / "fixtures" / "mail-samples.json").read_text(encoding="utf-8"))["emails"]
ODD_ENDS = [
    "Workshop bắt đầu lúc 13h30 ngày 10/10/2026 tại phòng A2.301.\nKết thúc lúc 4h30.",
    "Chương trình diễn ra lúc 18h00 tối ngày 10/10/2026 tại hội trường A2.\nDự kiến kết thúc lúc 9h.",
    "The webinar runs 10:00 AM - 2:00 PM EST on October 20, 2026.",
    "Sự kiện diễn ra từ 22h00 ngày 31/12/2026 đến 02h00 ngày 01/01/2026.",
    "Sự kiện diễn ra từ 14h00 ngày 15/10/2026 đến 11h00 ngày 15/10/2026.",
]


def test_every_session_ends_after_it_starts():
    """Spec §3.1: an end is after its start unless the session ends the next day, in every case, every real sample
    and some odd ends."""
    mails = ([(c["subject"], c["text"], date.fromisoformat(c["arrived"])) for c in CASES]
             + [(s["subject"], s["text"], datetime.fromisoformat(s["received_at"]).date()) for s in SAMPLES]
             + [("", text, date(2026, 10, 7)) for text in ODD_ENDS])

    wrong = [(subject[:40], s) for subject, text, arrived in mails for s in read_times(subject, text, arrived).sessions
             if s.end is not None and not s.ends_next_day and s.end <= s.start]

    assert wrong == []
