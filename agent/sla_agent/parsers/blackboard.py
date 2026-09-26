"""Blackboard readers: Blackboard REST answers -> the shared data format. Pure functions."""

import re
from datetime import datetime
from urllib.parse import quote

from bs4 import BeautifulSoup
from pydantic import ValidationError
from sla_contract.schema import BbAnnouncement, BbAssignment, BbMaterial

from sla_agent.blackboard_client import BASE_URL
from sla_agent.errors import SourceChanged

ANNOUNCEMENT_LIMIT = 5000
FEEDBACK_LIMIT = 1000
KINDS = {
    "resource/x-bb-file": "file",
    "resource/x-bb-folder": "folder",
    "resource/x-bb-externallink": "link",
    "resource/x-bb-document": "document",
}
GRADE_STATUS = {"Graded": "graded", "NeedsGrading": "needs_grading"}


def html_to_text(html, limit):
    """Plain text: scripts, styles and embedded frames dropped, entities decoded, cut at `limit`."""
    page = BeautifulSoup(html or "", "html.parser")
    for tag in page(["script", "style", "iframe", "object", "embed", "noscript"]):
        tag.decompose()
    text = re.sub(r"\s+", " ", page.get_text(" ")).replace(" .", ".").strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def parse_time(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        raise SourceChanged(f"Blackboard sent an unreadable time {value!r}.") from None


def course_url(course_id):
    return f"{BASE_URL}/webapps/blackboard/execute/launcher?type=Course&id={quote(course_id)}&url="


BB_ID = re.compile(r"_\d+_\d+")


def content_url(course_id, content_id):
    """Blackboard's own page for one item of a course, e.g. an assignment."""
    return (f"{BASE_URL}/webapps/blackboard/execute/displayIndividualContent"
            f"?course_id={quote(course_id)}&content_id={quote(content_id)}")


def _assignment_url(column, course_id):
    content_id = column.get("contentId")
    if isinstance(content_id, str) and BB_ID.fullmatch(content_id):
        return content_url(course_id, content_id)
    return course_url(course_id)


def _mentions(text, code):
    return re.search(rf"(?<![A-Z0-9]){re.escape(code)}(?![A-Z0-9])", text.upper()) is not None


def _describes(course):
    return f"{course.get('courseId', '')} {course.get('name', '')}".upper()


# IU names a group's lecture course "<name>_S1_2026-27_G02" with course ID "IT093IU_1_2026-2702",
# and its lab courses "<name>_S1_2026-27_G02_Lab01" / "IT093IU_1_2026-270201".
TERM_AND_GROUP_IN_ID = re.compile(r"_(\d)_(\d{4}-\d{2})(\d{2})")
GROUP_IN_NAME = re.compile(r"(?:^|[_\s-])G(?:ROUP)?\s*0*(\d+)(?![0-9])")


def _group(course):
    match = TERM_AND_GROUP_IN_ID.search(course.get("courseId") or "")
    if match:
        return int(match.group(3))
    match = GROUP_IN_NAME.search((course.get("name") or "").upper())
    return int(match.group(1)) if match else None


def _term(course):
    match = TERM_AND_GROUP_IN_ID.search(course.get("courseId") or "")
    return match.group(1, 2) if match else None


def select_current_courses(courses, registered):
    """(course, code) for the Blackboard courses of each registered course.

    All courses in the student's group are kept (a lecture course and its lab courses), from the
    newest term only (a course taken again also has older ones). When no course shows the group,
    the newest course with the code is kept."""
    chosen = []
    for course_code, group in registered:
        candidates = [c for c in courses if _mentions(_describes(c), course_code)]
        newest_first = sorted(candidates, key=lambda c: c.get("created") or "", reverse=True)
        same_group = [c for c in newest_first if group.isdigit() and _group(c) == int(group)]
        if same_group:
            term = _term(same_group[0])
            picked = [c for c in same_group if term is not None and _term(c) == term] or same_group[:1]
        else:
            picked = newest_first[:1]
        chosen += [(c, course_code) for c in picked]
    return chosen


def _model(model, **fields):
    try:
        return model(**fields)
    except ValidationError as error:
        raise SourceChanged(f"Blackboard data doesn't fit: {error.errors()[0]['msg']}") from None


def announcements_from(items, course_id):
    result = []
    for item in items:
        if not isinstance(item, dict) or "id" not in item:
            raise SourceChanged("An announcement has an unexpected format.")
        if item.get("draft"):
            continue
        start = ((item.get("availability") or {}).get("duration") or {}).get("start")
        result.append(_model(
            BbAnnouncement,
            bb_id=item["id"],
            title=(item.get("title") or "").strip()[:255] or "(no title)",
            text=html_to_text(item.get("body"), ANNOUNCEMENT_LIMIT),
            posted_at=parse_time(start or item.get("created")),
            url=course_url(course_id),
        ))
    return result


def assignments_from(columns, grades, course_id):
    by_column = {g.get("columnId"): g for g in grades if isinstance(g, dict)}
    result = []
    for column in columns:
        if not isinstance(column, dict) or "id" not in column:
            raise SourceChanged("A gradebook column has an unexpected format.")
        grading = column.get("grading") or {}
        if grading.get("type") == "Calculated" or (column.get("availability") or {}).get("available") == "No":
            continue
        grade = by_column.get(column["id"]) or {}
        if grade.get("exempt"):
            status = "exempt"
        else:
            status = GRADE_STATUS.get(grade.get("status"), "not_graded")
        display = grade.get("displayGrade") or {}
        score = grade.get("score", display.get("score")) if status == "graded" else None
        feedback = html_to_text(grade.get("feedback"), FEEDBACK_LIMIT) or None
        result.append(_model(
            BbAssignment,
            bb_id=column["id"],
            name=(column.get("name") or column.get("displayName") or "(no name)").strip()[:255],
            due_at=parse_time(grading.get("due")),
            points_possible=(column.get("score") or {}).get("possible"),
            score=score,
            grade_text=(display.get("text") or None) if status == "graded" else None,
            status=status,
            feedback=feedback,
            url=_assignment_url(column, course_id),
        ))
    return result


def walk_contents(top_items, fetch_children, max_depth=2, max_folder_requests=15):
    """[(item, folder path)] for the top level and folders up to `max_depth` levels below it."""
    found, queue, requests_left = [], [(item, "", 0) for item in top_items], max_folder_requests
    while queue:
        item, path, depth = queue.pop(0)
        found.append((item, path))
        is_folder = (item.get("contentHandler") or {}).get("id") == "resource/x-bb-folder" or item.get("hasChildren")
        if is_folder and depth < max_depth and requests_left > 0:
            requests_left -= 1
            child_path = f"{path} / {item.get('title', '')}".strip(" /")
            queue += [(child, child_path, depth + 1) for child in fetch_children(item["id"])]
    return found


def materials_from(tree, course_id):
    result = []
    for item, path in tree:
        if not isinstance(item, dict) or "id" not in item:
            raise SourceChanged("A course item has an unexpected format.")
        if (item.get("availability") or {}).get("available") == "No":
            continue
        link = next((l.get("href") for l in item.get("links") or [] if (l.get("href") or "").startswith("/")), None)
        result.append(_model(
            BbMaterial,
            bb_id=item["id"],
            title=(item.get("title") or "(no title)").strip()[:255],
            kind=KINDS.get((item.get("contentHandler") or {}).get("id"), "other"),
            path=path[:500],
            created_at=parse_time(item.get("created")),
            url=f"{BASE_URL}{link}" if link else course_url(course_id),
        ))
    return result
