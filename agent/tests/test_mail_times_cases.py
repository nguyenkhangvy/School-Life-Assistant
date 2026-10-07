"""The whole test set of the mail time reader (spec 2026-10-07-mail-event-kinds-design.md §8.1): the student's test
mails and the short cases of the design discussion, each with the result the student checked. They come from
docs/superpowers/specs/2026-10-07-mail-event-kinds-cases.md, made into fixtures/mail-times-cases.json by
agent/tools/mail_times_cases.py."""

import json
from datetime import date
from pathlib import Path

import pytest

from agent.tools.mail_times_score import as_case_fields
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
