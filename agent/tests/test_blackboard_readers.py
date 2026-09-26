from datetime import datetime, timezone

import pytest

from sla_agent.blackboard_reader import read_blackboard
from sla_agent.errors import SourceChanged
from sla_agent.parsers.blackboard import (
    announcements_from,
    assignments_from,
    html_to_text,
    materials_from,
    select_current_courses,
    walk_contents,
)
from sla_agent.parsers.registration import RegisteredCourse

BB = "https://blackboard.hcmiu.edu.vn"


def course(bb_id, course_id, name, created="2026-08-20T03:00:00.000Z"):
    return {"id": bb_id, "courseId": course_id, "name": name, "created": created}


# ---- Which courses -------------------------------------------------------------

def test_courses_are_chosen_by_their_registered_code():
    courses = [course("_1_1", "IT093IU-2026-1-02", "Web Application Development"),
               course("_2_1", "IT013IU-2025-2-01", "Algorithms"),
               course("_3_1", "PH012IU-2026-1-01", "Physics 4")]

    chosen = select_current_courses(courses, [RegisteredCourse("IT093IU", "02"), RegisteredCourse("PH012IU", "01")])

    assert [(c["id"], code) for c, code in chosen] == [("_1_1", "IT093IU"), ("_3_1", "PH012IU")]


def test_a_code_inside_a_longer_code_does_not_match():
    courses = [course("_1_1", "XIT093IU2", "Something else")]

    assert select_current_courses(courses, [RegisteredCourse("IT093IU", "02")]) == []


# IU's real format (seen 2026-09-26): a group has a lecture course "<name>_S1_2026-27_G02"
# with course ID "IT093IU_1_2026-2702", and lab courses "<name>_S1_2026-27_G02_Lab01" / "IT093IU_1_2026-270201".

def test_a_groups_lecture_and_lab_courses_are_both_kept_and_other_groups_are_not():
    courses = [course("_1_1", "IT093IU_1_2026-2701", "Web Application Development_S1_2026-27_G01"),
               course("_2_1", "IT093IU_1_2026-2702", "Web Application Development_S1_2026-27_G02"),
               course("_3_1", "IT093IU_1_2026-270201", "Web Application Development_S1_2026-27_G02_Lab01")]

    chosen = select_current_courses(courses, [RegisteredCourse("IT093IU", "02")])

    assert sorted(c["id"] for c, _ in chosen) == ["_2_1", "_3_1"]


def test_the_semester_digit_and_lab_number_are_not_taken_for_group_1():
    courses = [course("_1_1", "IT090IU_1_2026-2701", "Object-Oriented Analysis and Design_S1_2026-27_G01"),
               course("_2_1", "IT090IU_1_2026-270101", "Object-Oriented Analysis and Design_S1_2026-27_G01_Lab01"),
               course("_3_1", "IT090IU_1_2026-2702", "Object-Oriented Analysis and Design_S1_2026-27_G02"),
               course("_4_1", "IT090IU_1_2026-270201", "Object-Oriented Analysis and Design_S1_2026-27_G02_Lab01")]

    chosen = select_current_courses(courses, [RegisteredCourse("IT090IU", "01")])

    assert sorted(c["id"] for c, _ in chosen) == ["_1_1", "_2_1"]


def test_a_course_taken_again_keeps_only_the_newest_terms_courses():
    courses = [course("_1_1", "IT093IU_1_2025-2602", "Web Application Development_S1_2025-26_G02",
                      created="2025-08-01T00:00:00.000Z"),
               course("_2_1", "IT093IU_1_2026-2702", "Web Application Development_S1_2026-27_G02",
                      created="2026-08-01T00:00:00.000Z"),
               course("_3_1", "IT093IU_1_2026-270201", "Web Application Development_S1_2026-27_G02_Lab01",
                      created="2026-08-02T00:00:00.000Z")]

    chosen = select_current_courses(courses, [RegisteredCourse("IT093IU", "02")])

    assert sorted(c["id"] for c, _ in chosen) == ["_2_1", "_3_1"]


def test_the_digits_of_the_course_code_are_not_mistaken_for_the_group():
    # "EN011IU" contains "011", which looks like group 11.
    courses = [course("_1_1", "EN011IU_1_2026-2701", "Writing AE2_S1_2026-27_G01"),
               course("_2_1", "EN011IU_1_2026-2711", "Writing AE2_S1_2026-27_G11")]

    assert [c["id"] for c, _ in select_current_courses(courses, [RegisteredCourse("EN011IU", "11")])] == ["_2_1"]
    assert [c["id"] for c, _ in select_current_courses(courses, [RegisteredCourse("EN011IU", "01")])] == ["_1_1"]


def test_the_group_is_read_from_the_name_when_the_course_id_has_none():
    courses = [course("_1_1", "ENTP031_2024-2501", "Intensive English 3_S1_2024-25-Group01"),
               course("_2_1", "ENTP031_2024-2502", "Intensive English 3_S1_2024-25-Group02")]

    assert [c["id"] for c, _ in select_current_courses(courses, [RegisteredCourse("ENTP031", "02")])] == ["_2_1"]


def test_without_a_matching_group_the_newest_course_with_the_code_is_kept():
    courses = [course("_1_1", "MA026IU-old", "Probability", created="2025-08-01T00:00:00.000Z"),
               course("_2_1", "MA026IU-new", "Probability", created="2026-08-01T00:00:00.000Z")]

    assert [c["id"] for c, _ in select_current_courses(courses, [RegisteredCourse("MA026IU", "02")])] == ["_2_1"]


# ---- Text --------------------------------------------------------------------------

def test_html_becomes_safe_plain_text_within_its_limit():
    html = ("<p>Class on <b>Thursday</b>&nbsp;is cancelled.</p><script>alert(1)</script>"
            "<style>p{}</style><iframe src='x'></iframe>" + "<p>more</p>" * 3000)

    result = html_to_text(html, 5000)

    assert result.startswith("Class on Thursday is cancelled.")
    assert "<" not in result and "alert" not in result and "p{}" not in result
    assert len(result) <= 5000
    assert result.endswith("…")


# ---- Announcements ---------------------------------------------------------------

def test_announcements_skip_drafts_and_use_the_posting_date():
    items = [
        {"id": "_501_1", "title": "No class on Thursday", "body": "<p>Cancelled.</p>", "draft": False,
         "availability": {"duration": {"type": "Restricted", "start": "2026-09-28T02:00:00.000Z"}},
         "created": "2026-09-27T10:00:00.000Z"},
        {"id": "_502_1", "title": "Draft", "body": "x", "draft": True, "created": "2026-09-27T10:00:00.000Z"},
        {"id": "_503_1", "title": "", "body": "Untitled", "created": "2026-09-26T10:00:00.000Z"},
    ]

    result = announcements_from(items, "_101_1")

    assert [(a.bb_id, a.title, a.text) for a in result] == [
        ("_501_1", "No class on Thursday", "Cancelled."), ("_503_1", "(no title)", "Untitled")]
    assert result[0].posted_at == datetime(2026, 9, 28, 2, 0, tzinfo=timezone.utc)
    assert result[0].url.startswith(f"{BB}/")


# ---- Assignments and grades -------------------------------------------------------

COLUMNS = [
    {"id": "_701_1", "name": "Lab 3", "score": {"possible": 10.0}, "availability": {"available": "Yes"},
     "grading": {"type": "Attempts", "due": "2026-10-02T16:59:00.000Z"}},
    {"id": "_702_1", "name": "Participation", "score": {"possible": 5.0}, "availability": {"available": "Yes"},
     "grading": {"type": "Manual"}},
    {"id": "_703_1", "name": "Total", "score": {"possible": 100.0}, "availability": {"available": "Yes"},
     "grading": {"type": "Calculated"}},
    {"id": "_704_1", "name": "Hidden", "availability": {"available": "No"}, "grading": {"type": "Manual"}},
    {"id": "_705_1", "name": "Quiz 1", "score": {"possible": 20.0}, "availability": {"available": "Yes"},
     "grading": {"type": "Attempts", "due": "2026-10-09T16:59:00.000Z"}},
]
GRADES = [
    {"columnId": "_701_1", "status": "Graded", "score": 8.5,
     "displayGrade": {"scaleType": "Score", "score": 8.5, "possible": 10.0, "text": "8.5"},
     "feedback": "<p>Good <b>work</b></p>", "exempt": False},
    {"columnId": "_705_1", "status": "NeedsGrading", "exempt": False},
]


def test_assignments_merge_due_dates_and_my_grades_and_leave_out_totals_and_hidden_items():
    result = {a.bb_id: a for a in assignments_from(COLUMNS, GRADES, "_101_1")}

    assert sorted(result) == ["_701_1", "_702_1", "_705_1"]
    lab = result["_701_1"]
    assert (lab.name, lab.due_at, lab.points_possible, lab.score, lab.status, lab.feedback) == (
        "Lab 3", datetime(2026, 10, 2, 16, 59, tzinfo=timezone.utc), 10.0, 8.5, "graded", "Good work")
    assert (result["_702_1"].due_at, result["_702_1"].status) == (None, "not_graded")
    assert result["_705_1"].status == "needs_grading"


# ---- Materials ---------------------------------------------------------------------

def item(bb_id, title, handler, has_children=False, available="Yes"):
    return {"id": bb_id, "title": title, "created": "2026-09-28T01:00:00.000Z", "hasChildren": has_children,
            "availability": {"available": available}, "contentHandler": {"id": handler}}


def test_materials_walk_folders_two_levels_deep_with_their_path():
    top = [item("_1", "Week 5", "resource/x-bb-folder", True), item("_2", "Syllabus", "resource/x-bb-file")]
    children = {
        "_1": [item("_3", "Slides", "resource/x-bb-folder", True), item("_4", "Reading", "resource/x-bb-document")],
        "_3": [item("_5", "Lecture 5.pdf", "resource/x-bb-file"), item("_6", "Extra", "resource/x-bb-folder", True)],
        "_6": [item("_7", "Too deep.pdf", "resource/x-bb-file")],
    }
    asked = []

    def fetch(folder_id):
        asked.append(folder_id)
        return children[folder_id]

    tree = walk_contents(top, fetch)
    materials = {m.title: m for m in materials_from(tree, "_101_1")}

    assert asked == ["_1", "_3"]  # "_6" is a third level down: not opened
    assert (materials["Lecture 5.pdf"].kind, materials["Lecture 5.pdf"].path) == ("file", "Week 5 / Slides")
    assert materials["Reading"].kind == "document"
    assert "Too deep.pdf" not in materials


def test_unavailable_materials_are_left_out():
    tree = walk_contents([item("_1", "Hidden.pdf", "resource/x-bb-file", available="No")], lambda _: [])

    assert materials_from(tree, "_101_1") == []


# ---- The whole section --------------------------------------------------------------

class FakeApi:
    """Answers like BlackboardClient.api_all; `refused` paths answer [] (HTTP 403)."""

    def __init__(self, answers, refused=()):
        self.answers, self.refused, self.user_id, self.asked = answers, set(refused), "_77_1", []

    def api_all(self, path):
        self.asked.append(path)
        if any(path.startswith(r) for r in self.refused):
            return []
        return self.answers.get(path.split("?")[0], [])


def section_answers():
    return {
        "/v1/users/_77_1/courses": [{"courseId": "_101_1", "course": course("_101_1", "IT093IU-2026-1-02", "Web Application Development")},
                                    {"courseId": "_102_1", "course": course("_102_1", "IT013IU-2025-2-01", "Algorithms")}],
        "/v1/courses/_101_1/announcements": [{"id": "_501_1", "title": "Hi", "body": "Welcome", "created": "2026-09-01T00:00:00.000Z"}],
        "/v2/courses/_101_1/gradebook/columns": COLUMNS,
        "/v2/courses/_101_1/gradebook/users/_77_1": GRADES,
        "/v1/courses/_101_1/contents": [item("_2", "Syllabus", "resource/x-bb-file")],
    }


def test_read_blackboard_builds_the_section_for_current_courses_only():
    api = FakeApi(section_answers())

    result = read_blackboard(api, [RegisteredCourse("IT093IU", "02")])

    [web] = result.courses
    assert (web.bb_id, web.course_code, web.name) == ("_101_1", "IT093IU", "Web Application Development")
    assert (len(web.announcements), len(web.assignments), len(web.materials)) == (1, 3, 1)
    assert not any("/_102_1/" in path for path in api.asked)


def test_a_course_that_hides_its_grades_still_syncs_the_rest():
    api = FakeApi(section_answers(), refused=["/v2/courses/_101_1/gradebook/users"])

    [web] = read_blackboard(api, [RegisteredCourse("IT093IU", "02")]).courses

    assert {a.status for a in web.assignments} == {"not_graded"}
    assert len(web.announcements) == 1


def test_answers_in_an_unexpected_shape_raise_source_changed():
    answers = section_answers()
    answers["/v1/courses/_101_1/announcements"] = [{"unexpected": True}]

    with pytest.raises(SourceChanged):
        read_blackboard(FakeApi(answers), [RegisteredCourse("IT093IU", "02")])


def test_an_assignment_links_to_its_own_page_when_blackboard_names_it():
    columns = [{**COLUMNS[0], "contentId": "_452089_1"}, COLUMNS[1], {**COLUMNS[4], "contentId": "javascript:alert(1)"}]

    urls = {a.bb_id: a.url for a in assignments_from(columns, GRADES, "_101_1")}

    assert urls == {
        "_701_1": f"{BB}/webapps/blackboard/execute/displayIndividualContent?course_id=_101_1&content_id=_452089_1",
        "_702_1": f"{BB}/webapps/blackboard/execute/launcher?type=Course&id=_101_1&url=",
        "_705_1": f"{BB}/webapps/blackboard/execute/launcher?type=Course&id=_101_1&url=",
    }
