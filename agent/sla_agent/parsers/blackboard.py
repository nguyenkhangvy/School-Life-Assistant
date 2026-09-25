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


def _mentions(text, code):
    return re.search(rf"(?<![A-Z0-9]){re.escape(code)}(?![A-Z0-9])", text.upper()) is not None


def _describes(course):
    return f"{course.get('courseId', '')} {course.get('name', '')}".upper()


def _group_matches(course, course_code, group):
    if not group or not group.isdigit():
        return False
    # Leave the course code out: "IT093IU" must not count as group "03".
    text = _describes(course).replace(course_code, " ")
    return re.search(rf"(?<![0-9])0*{int(group)}(?![0-9])", text) is not None


def select_current_courses(courses, registered):
    """(course, code) for each registered course found on Blackboard. Ties: same group, then newest."""
    chosen = []
    for course_code, group in registered:
        candidates = [c for c in courses if _mentions(_describes(c), course_code)]
        if not candidates:
            continue
        same_group = [c for c in candidates if _group_matches(c, course_code, group)]
        pool = same_group or candidates
        pool.sort(key=lambda c: c.get("created") or "", reverse=True)
        chosen.append((pool[0], course_code))
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
            url=course_url(course_id),
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
