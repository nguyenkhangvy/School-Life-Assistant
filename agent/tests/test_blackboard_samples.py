"""The Blackboard reader against anonymized copies of real answers (saved 2026-09-26)."""

import json
from pathlib import Path

from sla_agent.blackboard_client import BASE_URL
from sla_agent.blackboard_reader import read_blackboard
from sla_agent.parsers.registration import parse_registered_courses

FIXTURES = Path(__file__).parent / "fixtures"
RAW = json.loads((FIXTURES / "blackboard-raw.json").read_text(encoding="utf-8"))
REGISTERED = parse_registered_courses({"registration": (FIXTURES / "registration.html").read_text(encoding="utf-8")})


class Replay:
    """Serves saved answers like BlackboardClient.api_all, following saved paging."""

    user_id = "_1_1"

    def api_all(self, path):
        results, next_path = [], path
        while next_path in RAW:
            body = RAW[next_path]
            results += body.get("results", [])
            next_page = (body.get("paging") or {}).get("nextPage")
            next_path = next_page.removeprefix("/learn/api/public") if next_page else None
        return results


def test_every_registered_course_is_found_on_blackboard():
    section = read_blackboard(Replay(), REGISTERED)

    assert {c.course_code for c in section.courses} == {r.code for r in REGISTERED}


def test_a_groups_lecture_and_lab_courses_are_read_and_other_groups_are_not():
    names = sorted(c.name for c in read_blackboard(Replay(), REGISTERED).courses if c.course_code == "IT093IU")

    assert names == ["Web Application Development_S1_2026-27_G02", "Web Application Development_S1_2026-27_G02_Lab01"]


def test_the_real_answers_become_valid_safe_data():
    section = read_blackboard(Replay(), REGISTERED)

    for course in section.courses:
        items = course.announcements + course.assignments + course.materials
        assert all(item.url.startswith(f"{BASE_URL}/") for item in items)
        assert all("<" not in a.text for a in course.announcements)
        assert all(a.due_at is None or a.due_at.tzinfo is not None for a in course.assignments)
    assert sum(len(c.announcements) + len(c.assignments) + len(c.materials) for c in section.courses) > 0
