"""The mail time reader's test cases (spec 2026-10-07-mail-event-kinds-design.md §8): reads them from the cases
document the student checked and writes them as agent/tests/fixtures/mail-times-cases.json.

Run from the repository's folder after changing the cases document:

    python -m agent.tools.mail_times_cases
"""

import json
import re
from datetime import date
from pathlib import Path

AGENT = Path(__file__).resolve().parents[1]
DOC = AGENT.parent / "docs" / "superpowers" / "specs" / "2026-10-07-mail-event-kinds-cases.md"
FIXTURE = AGENT / "tests" / "fixtures" / "mail-times-cases.json"

GROUP = re.compile(r"^## Group .*\(arrive \w{3} (\d{2})/(\d{2})/(\d{4})")
CASE = re.compile(r"^### (Mail \d+|C\d+) · (.*)$")
DAY = r"\w{3} (\d{2})/(\d{2})(?:/(\d{4}))?"
CLOCK = r"(\d{2}:\d{2})"
LABELS = {f"Round {n}": f"round_{n}" for n in range(1, 6)} | {f"Shift {n}": f"shift_{n}" for n in range(1, 6)} | {
    "Preliminary round": "preliminary", "Qualifying round": "qualifying", "Semi-final": "semifinal",
    "Final": "final", "Opening": "opening", "Closing": "closing"}
RELATIVE = {"today": "today", "tomorrow": "tomorrow", "the day after tomorrow": "day_after_tomorrow",
            "this week": "this_week", "next week": "next_week", "a weekday alone": "weekday"}
MODES = {"online": "online", "in person": "in_person"}
KINDS = {"registration opens": "opens", "register by": "register", "confirm by": "confirm", "due": "due"}


def _day(d, m, y):
    """A day as the document writes it: the year is left out when it is 2026."""
    return date(int(y or 2026), int(m), int(d)).isoformat()


def session(written):
    """One "Session:" line of the document, as the reader's session fields."""
    head, *extras = written.split(" · ")
    if m := re.fullmatch(rf"{DAY} from {CLOCK}", head):
        day, start, end, approximate, next_day = _day(*m.group(1, 2, 3)), m.group(4), None, False, False
    elif m := re.fullmatch(rf"{DAY} {CLOCK}–(~?){CLOCK}", head):
        day, start, end, approximate, next_day = _day(*m.group(1, 2, 3)), m.group(4), m.group(6), bool(m.group(5)), False
    elif m := re.fullmatch(rf"{DAY} {CLOCK} – {DAY} {CLOCK} \(ends the next day\)", head):
        day, start, end, approximate, next_day = _day(*m.group(1, 2, 3)), m.group(4), m.group(8), False, True
    else:
        raise ValueError(f"not a session: {written}")
    found = dict(day=day, start=start, end=end, end_is_approximate=approximate, ends_next_day=next_day, check_in=None,
                 link_opens=None, mode=None, relative=None, label=None)
    for extra in extras:
        if m := re.fullmatch(rf"check-in {CLOCK}", extra):
            found["check_in"] = m.group(1)
        elif m := re.fullmatch(rf"link opens {CLOCK}", extra):
            found["link_opens"] = m.group(1)
        elif extra in MODES:
            found["mode"] = MODES[extra]
        elif m := re.fullmatch(r"day from a relative word \((.+)\)", extra):
            found["relative"] = RELATIVE[m.group(1)]
        elif extra.startswith("label "):
            found["label"] = LABELS[extra.removeprefix("label ")]
        else:
            raise ValueError(f"not a session detail: {extra}")
    return found


def period(written):
    """One "Period:" line of the document, as the reader's period fields."""
    pieces = written.split(" · ")
    found = dict(first_day=None, last_day=None, mode=None, from_time=None, to_time=None, details_later=False, label=None)
    if m := re.fullmatch(rf"{DAY} {CLOCK} → {DAY} {CLOCK}", pieces[0]):
        found.update(first_day=_day(*m.group(1, 2, 3)), last_day=_day(*m.group(5, 6, 7)), mode="one_window",
                     from_time=m.group(4), to_time=m.group(8))
        rest = pieces[1:]
    else:
        if m := re.fullmatch(rf"{DAY} → {DAY}", pieces[0]):
            first, last = _day(*m.group(1, 2, 3)), _day(*m.group(4, 5, 6))
        elif m := re.fullmatch(DAY, pieces[0]):
            first = last = _day(*m.group(1, 2, 3))
        else:
            raise ValueError(f"not a period: {written}")
        found.update(first_day=first, last_day=last)
        if len(pieces) > 1 and pieces[1] == "all day":
            found["mode"] = "all_day"
        elif len(pieces) > 1 and (m := re.fullmatch(rf"{CLOCK}–{CLOCK} each day", pieces[1])):
            found.update(mode="daily_window", from_time=m.group(1), to_time=m.group(2))
        elif len(pieces) > 1 and (m := re.fullmatch(rf"{CLOCK}–{CLOCK}", pieces[1])) and first == last:
            found.update(mode="one_window", from_time=m.group(1), to_time=m.group(2))
        else:
            raise ValueError(f"not a period: {written}")
        rest = pieces[2:]
    for extra in rest:
        if extra == "details later":
            found["details_later"] = True
        elif extra.startswith("label "):
            found["label"] = LABELS[extra.removeprefix("label ")]
        else:
            raise ValueError(f"not a period detail: {extra}")
    return found


def deadline(written):
    """One deadline of a "Deadlines:" line, as the reader's deadline fields."""
    m = re.fullmatch(rf"(registration opens|register by|confirm by|due) (?:{CLOCK} )?{DAY}(?: \((online|in person)\))?",
                     written)
    if not m:
        raise ValueError(f"not a deadline: {written}")
    return dict(kind=KINDS[m.group(1)], day=_day(*m.group(3, 4, 5)), time=m.group(2),
                mode=MODES[m.group(6)] if m.group(6) else None)


def read(doc):
    """[case] in the order of the document."""
    cases, arrived, case, lines, listing = [], None, None, iter(doc.splitlines()), None
    for line in lines:
        if m := GROUP.match(line):
            arrived = date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat()
        elif m := CASE.match(line):
            case = dict(id=m.group(1), arrived=arrived, subject=m.group(2), text=None, sessions=[], periods=[],
                        deadlines=[], meeting=False, registered=False)
            cases.append(case)
            listing = None
        elif case is None:
            continue
        elif line == "```text":
            body = []
            for line in lines:
                if line == "```":
                    break
                body.append(line)
            case["text"] = "\n".join(body)
        elif m := re.fullmatch(r"- \*\*(Session|Period):\*\* (.+)", line):
            case["sessions" if m.group(1) == "Session" else "periods"].append(
                (session if m.group(1) == "Session" else period)(m.group(2)))
        elif m := re.fullmatch(r"- \*\*(Sessions|Periods):\*\*", line):
            listing = m.group(1).lower()
        elif listing and (m := re.fullmatch(r"  - (.+)", line)):
            case[listing].append((session if listing == "sessions" else period)(m.group(1)))
        elif m := re.fullmatch(r"- \*\*Deadlines:\*\* (.+)", line):
            case["deadlines"] = [deadline(d) for d in m.group(1).split(" · ")]
        elif m := re.fullmatch(r"- \*\*Flags:\*\* (.+)", line):
            for flag in m.group(1).split(", "):
                case[flag] = True
        elif line.startswith("- ") and not line.startswith(("- *Note:*", "- **Nothing.**")):
            raise ValueError(f"{case['id']}: not understood: {line}")
    return cases


def main():
    cases = read(DOC.read_text(encoding="utf-8"))
    FIXTURE.write_text(json.dumps({"cases": cases}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(cases)} cases written to {FIXTURE}")


if __name__ == "__main__":
    main()
