"""The scorecard of the mail time reader on its test set (spec 2026-10-07-mail-event-kinds-design.md §8.2): for each
part, how many cases are right, and which cases are wrong. Run from the repository's folder:

    python -m agent.tools.mail_times_score
"""

import json
from datetime import date
from pathlib import Path

from sla_agent.mail_times import read_times

FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "mail-times-cases.json"
# Each part compares these fields of every session, or a whole list or flag.
SESSION_PARTS = {
    "sessions": ("day", "start"),
    "ends": ("day", "start", "end", "end_is_approximate", "ends_next_day"),
    "check-ins and links": ("day", "start", "check_in", "link_opens"),
    "modes, relative days, labels": ("day", "start", "mode", "relative", "label"),
}
PARTS = tuple(SESSION_PARTS) + ("periods", "deadlines", "flags")


def _hm(clock):
    return clock.strftime("%H:%M") if clock else None


def as_case_fields(found):
    """A Found written as the cases write it (agent/tools/mail_times_cases.py)."""
    return dict(
        sessions=[dict(day=s.day.isoformat(), start=_hm(s.start), end=_hm(s.end), end_is_approximate=s.end_is_approximate,
                       ends_next_day=s.ends_next_day, check_in=_hm(s.check_in), link_opens=_hm(s.link_opens),
                       mode=s.mode, relative=s.relative, label=s.label) for s in found.sessions],
        periods=[dict(first_day=p.first_day.isoformat(), last_day=p.last_day.isoformat(), mode=p.mode,
                      from_time=_hm(p.from_time), to_time=_hm(p.to_time), details_later=p.details_later, label=p.label)
                 for p in found.periods],
        deadlines=[dict(kind=d.kind, day=d.day.isoformat(), time=_hm(d.at), mode=d.mode) for d in found.deadlines],
        meeting=found.meeting,
        registered=found.registered,
    )


def _part(fields, part):
    if part in SESSION_PARTS:
        return [{key: s[key] for key in SESSION_PARTS[part]} for s in fields["sessions"]]
    if part == "flags":
        return fields["meeting"], fields["registered"]
    return fields[part]


def score(cases):
    """({part: (right, all)}, [(case id, [wrong parts])]) of the reader on `cases`."""
    right, wrong = dict.fromkeys(PARTS, 0), []
    for case in cases:
        found = as_case_fields(read_times(case["subject"], case["text"], date.fromisoformat(case["arrived"])))
        parts = [part for part in PARTS if _part(found, part) != _part(case, part)]
        for part in PARTS:
            right[part] += part not in parts
        if parts:
            wrong.append((case["id"], parts))
    return {part: (n, len(cases)) for part, n in right.items()}, wrong


def main():
    totals, wrong = score(json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"])
    for part, (n, total) in totals.items():
        print(f"{part:<30} {n:>3}/{total}")
    for case_id, parts in wrong:
        print(f"wrong: {case_id}: {', '.join(parts)}")


if __name__ == "__main__":
    main()
