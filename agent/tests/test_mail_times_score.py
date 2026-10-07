"""The scorecard of the mail time reader (spec 2026-10-07-mail-event-kinds-design.md §8.2)."""

from agent.tools.mail_times_score import PARTS, score

SESSION = dict(day="2026-10-15", start="14:00", end=None, end_is_approximate=False, ends_next_day=False,
               check_in="13:45", link_opens=None, mode=None, relative=None, label=None)
CASE = dict(id="Mail 01", arrived="2026-10-07", subject="Hội thảo",
            text="Hội thảo lúc 14:00 ngày 15/10/2026.\nCó mặt trước 13:45.\nHạn đăng ký: 12/10.",
            sessions=[SESSION], periods=[], deadlines=[dict(kind="register", day="2026-10-12", time=None, mode=None)],
            meeting=False, registered=False)


def test_a_right_case_counts_in_every_part():
    totals, wrong = score([CASE])

    assert totals == {part: (1, 1) for part in PARTS}
    assert wrong == []


def test_a_wrong_part_is_named():
    totals, wrong = score([dict(CASE, sessions=[dict(SESSION, check_in="13:30")])])

    assert totals["check-ins and links"] == (0, 1)
    assert totals["sessions"] == totals["deadlines"] == (1, 1)
    assert wrong == [("Mail 01", ["check-ins and links"])]
