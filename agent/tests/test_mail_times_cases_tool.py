"""The tool that turns the checked cases document into agent/tests/fixtures/mail-times-cases.json (spec
2026-10-07-mail-event-kinds-design.md §8)."""

import json

import pytest

from agent.tools.mail_times_cases import DOC, FIXTURE, deadline, period, read, session

NO_DETAILS = dict(end=None, end_is_approximate=False, ends_next_day=False, check_in=None, link_opens=None, mode=None,
                  relative=None, label=None)


@pytest.mark.parametrize("line, expected", [
    ("Thu 15/10 from 14:00 · check-in 13:45", dict(NO_DETAILS, day="2026-10-15", start="14:00", check_in="13:45")),
    ("Thu 08/10 10:00–~11:00 · day from a relative word (this week)",
     dict(NO_DETAILS, day="2026-10-08", start="10:00", end="11:00", end_is_approximate=True, relative="this_week")),
    ("Thu 31/12 22:00 – Fri 01/01/2027 00:30 (ends the next day) · check-in 21:30",
     dict(NO_DETAILS, day="2026-12-31", start="22:00", end="00:30", ends_next_day=True, check_in="21:30")),
    ("Sun 18/10 from 09:30 · link opens 09:00 · online",
     dict(NO_DETAILS, day="2026-10-18", start="09:30", link_opens="09:00", mode="online")),
    ("Thu 03/12 09:00–12:00 · online · label Qualifying round",
     dict(NO_DETAILS, day="2026-12-03", start="09:00", end="12:00", mode="online", label="qualifying")),
])
def test_session_lines(line, expected):
    assert session(line) == expected


@pytest.mark.parametrize("line, expected", [
    ("Mon 26/10 → Fri 30/10 · all day", dict(first_day="2026-10-26", last_day="2026-10-30", mode="all_day")),
    ("Tue 20/10 · all day · label Round 1", dict(first_day="2026-10-20", last_day="2026-10-20", mode="all_day",
                                                 label="round_1")),
    ("Mon 02/11 → Thu 05/11 · 09:00–17:00 each day",
     dict(first_day="2026-11-02", last_day="2026-11-05", mode="daily_window", from_time="09:00", to_time="17:00")),
    ("Sat 28/11 09:00 → Sun 29/11 16:00",
     dict(first_day="2026-11-28", last_day="2026-11-29", mode="one_window", from_time="09:00", to_time="16:00")),
    ("Wed 18/11 · 09:00–16:00 · details later",
     dict(first_day="2026-11-18", last_day="2026-11-18", mode="one_window", from_time="09:00", to_time="16:00",
          details_later=True)),
])
def test_period_lines(line, expected):
    assert period(line) == dict(dict(from_time=None, to_time=None, details_later=False, label=None), **expected)


@pytest.mark.parametrize("text, expected", [
    ("registration opens Thu 08/10", dict(kind="opens", day="2026-10-08", time=None, mode=None)),
    ("register by 17:00 Mon 12/10", dict(kind="register", day="2026-10-12", time="17:00", mode=None)),
    ("confirm by 12:00 Wed 14/10", dict(kind="confirm", day="2026-10-14", time="12:00", mode=None)),
    ("due 23:59 Sun 25/10", dict(kind="due", day="2026-10-25", time="23:59", mode=None)),
    ("register by 12:00 Sat 03/10 (in person)", dict(kind="register", day="2026-10-03", time="12:00", mode="in_person")),
])
def test_deadlines(text, expected):
    assert deadline(text) == expected


DOCUMENT = """# Mail event kinds: test cases

## Group A: mails 01–50 (arrive Wed 07/10/2026; the student's key)

### Mail 01 · Hội thảo

```text
Hội thảo vào 14:00 ngày 15/10/2026.
Có mặt trước 13:45.
```

- **Session:** Thu 15/10 from 14:00 · check-in 13:45
- **Deadlines:** registration opens Thu 08/10 · register by 17:00 Mon 12/10 (online)
- **Flags:** meeting

## Group C: short cases (arrive Mon 28/09/2026; checked by the student)

### C01 · Lịch ca

```text
Ca 1: 8:00–10:00; Ca 2: 13:00–15:00 ngày 30/9
```

- **Sessions:**
  - Wed 30/09 08:00–10:00 · label Shift 1
  - Wed 30/09 13:00–15:00 · label Shift 2
- *Note:* two shifts.

### C02 · Nothing

```text
Hello.
```

- **Nothing.**
"""


def test_reading_a_document():
    one, two, three = read(DOCUMENT)

    assert one == dict(
        id="Mail 01", arrived="2026-10-07", subject="Hội thảo", text="Hội thảo vào 14:00 ngày 15/10/2026.\nCó mặt trước 13:45.",
        sessions=[dict(NO_DETAILS, day="2026-10-15", start="14:00", check_in="13:45")], periods=[],
        deadlines=[dict(kind="opens", day="2026-10-08", time=None, mode=None),
                   dict(kind="register", day="2026-10-12", time="17:00", mode="online")],
        meeting=True, registered=False)
    assert (two["id"], two["arrived"], [s["label"] for s in two["sessions"]]) == ("C01", "2026-09-28", ["shift_1", "shift_2"])
    assert (three["sessions"], three["periods"], three["deadlines"], three["meeting"]) == ([], [], [], False)


def test_a_line_it_does_not_understand_stops_it():
    with pytest.raises(ValueError):
        read(DOCUMENT.replace("- **Nothing.**", "- **Sesions:** Thu 15/10 from 14:00"))


def test_the_fixture_is_the_cases_document():
    if not DOC.exists():
        pytest.skip("the docs folder is not next to the agent")

    assert json.loads(FIXTURE.read_text(encoding="utf-8")) == {"cases": read(DOC.read_text(encoding="utf-8"))}
