"""The "What changed" feed: compare old and new data, describe differences.

Pure functions over small tuples, shown in Vietnam time. Only upcoming
classes and exams count, so weeks that are simply over aren't reported.
"""

from datetime import date, datetime, timedelta, timezone
from typing import NamedTuple

VIETNAM = timezone(timedelta(hours=7))
WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
MAX_DATES = 3


class Meeting(NamedTuple):
    course_code: str
    course_name: str
    start_at: datetime  # naive UTC
    end_at: datetime
    room: str | None


class ExamInfo(NamedTuple):
    course_code: str
    course_name: str
    exam_type: str
    start_at: datetime  # naive UTC
    room: str | None


class TuitionInfo(NamedTuple):
    term_code: str
    balance: int
    due_date: date | None
    status_text: str | None


class Change(NamedTuple):
    kind: str  # added / removed / changed
    summary: str


def to_vietnam(moment):
    """Naive UTC (as stored) -> aware Vietnam time."""
    return moment.replace(tzinfo=timezone.utc).astimezone(VIETNAM)


def when(moment):
    local = to_vietnam(moment)
    return f"{WEEKDAYS[local.weekday()]} {local:%d/%m %H:%M}"


def _dates(moments):
    moments = sorted(moments)
    text = ", ".join(when(m) for m in moments[:MAX_DATES])
    if len(moments) > MAX_DATES:
        text += f" and {len(moments) - MAX_DATES} more"
    return text


def _count(n, singular, plural=None):
    return f"{n} {singular if n == 1 else plural or singular + 's'}"


def _day(value):
    return value.strftime("%d/%m/%Y")


def timetable_changes(old, new, now):
    """old is None on the first sync of a term (or while it had no classes)."""
    if old is None:
        if not new:
            return []  # nothing to announce yet
        courses = len({m.course_code for m in new})
        upcoming = sum(1 for m in new if m.start_at >= now)
        return [Change("added", f"Timetable loaded: {_count(courses, 'course')}, "
                                f"{_count(upcoming, 'upcoming class', 'upcoming classes')}")]

    before = {(m.course_code, m.start_at): m for m in old if m.start_at >= now}
    after = {(m.course_code, m.start_at): m for m in new if m.start_at >= now}
    labels = {m.course_code: f"{m.course_code} {m.course_name}" for m in [*before.values(), *after.values()]}

    changes = []
    for code in sorted(labels):
        label = labels[code]
        removed = [start for (c, start) in before.keys() - after.keys() if c == code]
        added = [after[key] for key in after.keys() - before.keys() if key[0] == code]
        kept = [(before[key], after[key]) for key in before.keys() & after.keys() if key[0] == code]

        if removed:
            what = "class cancelled" if len(removed) == 1 else f"{len(removed)} classes cancelled"
            changes.append(Change("removed", f"{label}: {what} on {_dates(removed)}"))

        if len(added) == 1:
            room = f" ({added[0].room})" if added[0].room else ""
            changes.append(Change("added", f"{label}: new class on {when(added[0].start_at)}{room}"))
        elif added:
            changes.append(Change("added", f"{label}: {len(added)} new classes on {_dates(m.start_at for m in added)}"))

        room_moves = {}
        for old_meeting, new_meeting in kept:
            if old_meeting.room != new_meeting.room:
                room_moves.setdefault((old_meeting.room, new_meeting.room), []).append(new_meeting.start_at)
        for (old_room, new_room), starts in sorted(room_moves.items(), key=lambda item: min(item[1])):
            changes.append(Change("changed", f"{label}: room {old_room or '?'} → {new_room or '?'} on {_dates(starts)}"))

        for old_meeting, new_meeting in sorted(kept, key=lambda pair: pair[1].start_at):
            if old_meeting.end_at != new_meeting.end_at:
                changes.append(Change(
                    "changed",
                    f"{label}: class on {when(new_meeting.start_at)} now ends at {to_vietnam(new_meeting.end_at):%H:%M}",
                ))
    return changes


def exam_changes(old, new, now):
    """old is None on the first sync of a term (or while no exams were published)."""
    if old is None:
        if not new:
            return []  # nothing published yet; announced once exams appear
        return [Change("added", f"Exam schedule loaded: {_count(len(new), 'exam')}")]

    before = {(e.course_code, e.exam_type): e for e in old if e.start_at >= now}
    after = {(e.course_code, e.exam_type): e for e in new if e.start_at >= now}

    changes = []
    for key in sorted(before.keys() | after.keys()):
        old_exam, new_exam = before.get(key), after.get(key)
        exam = new_exam or old_exam
        label = f"{exam.course_code} {exam.course_name}"
        if old_exam is None:
            room = f" ({new_exam.room})" if new_exam.room else ""
            changes.append(Change("added", f"New {exam.exam_type} exam: {label}, {when(new_exam.start_at)}{room}"))
        elif new_exam is None:
            changes.append(Change("removed", f"{exam.exam_type.capitalize()} exam removed: {label}"))
        else:
            if old_exam.start_at != new_exam.start_at:
                changes.append(Change(
                    "changed",
                    f"{label} {exam.exam_type} exam moved: {when(old_exam.start_at)} → {when(new_exam.start_at)}",
                ))
            if old_exam.room != new_exam.room:
                changes.append(Change(
                    "changed",
                    f"{label} {exam.exam_type} exam room: {old_exam.room or '?'} → {new_exam.room or '?'}",
                ))
    return changes


def tuition_changes(old, new):
    """old is None on the first sync of a term."""
    title = f"Tuition {new.term_code}"
    if old is None:
        due = f", due {_day(new.due_date)}" if new.due_date else ""
        return [Change("added", f"{title}: balance {new.balance:,} VND{due}")]

    changes = []
    if old.balance != new.balance:
        changes.append(Change("changed", f"{title}: balance {old.balance:,} → {new.balance:,} VND"))
    if old.due_date != new.due_date:
        if old.due_date is None:
            text = f"due date {_day(new.due_date)}"
        elif new.due_date is None:
            text = "due date removed"
        else:
            text = f"due date {_day(old.due_date)} → {_day(new.due_date)}"
        changes.append(Change("changed", f"{title}: {text}"))
    if old.status_text != new.status_text:
        changes.append(Change("changed", f"{title}: status {old.status_text or '-'} → {new.status_text or '-'}"))
    return changes


class BbItem(NamedTuple):
    kind: str  # announcement / assignment / material
    course: str
    bb_id: str
    title: str
    due_at: datetime | None = None  # naive UTC
    status: str | None = None
    score: float | None = None
    points_possible: float | None = None
    grade_text: str | None = None
    material_kind: str | None = None


def _number(value):
    return f"{value:g}"


def _grade(item):
    if item.score is not None and item.points_possible:
        return f"{_number(item.score)}/{_number(item.points_possible)}"
    if item.score is not None:
        return _number(item.score)
    return item.grade_text or "graded"


MATERIALS_NAMED = 3  # titles named in a "new materials" line


def _bb_counts(items):
    def count(kind):
        return sum(1 for i in items if i.kind == kind)
    return (f"{_count(count('announcement'), 'announcement')}, {_count(count('assignment'), 'assignment')}, "
            f"{_count(count('material'), 'material')}")


def _materials_line(course, titles):
    if len(titles) == 1:
        return Change("added", f"New material · {course}: {titles[0]}")
    more = f" and {len(titles) - MATERIALS_NAMED} more" if len(titles) > MATERIALS_NAMED else ""
    return Change("added", f"{len(titles)} new materials · {course}: {', '.join(titles[:MATERIALS_NAMED])}{more}")


def blackboard_changes(old, new):
    """old/new: (course names, [BbItem]). old is None on the first Blackboard sync.

    A newly seen course and a batch of new materials each give one line, so a folder of
    uploads doesn't push the other news off the short list on the Overview."""
    courses, items = new
    if old is None:
        if not courses:
            return []
        return [Change("added", f"Blackboard loaded: {_count(len(courses), 'course')}, {_bb_counts(items)}")]

    known = set(old[0])
    changes = [Change("added", f"New course on Blackboard · {course}: "
                               f"{_bb_counts([i for i in items if i.course == course])}")
               for course in courses if course not in known]
    before = {(i.kind, i.bb_id): i for i in old[1]}
    new_materials = {}
    for item in items:
        if item.course not in known:
            continue
        previous = before.get((item.kind, item.bb_id))
        if item.kind == "announcement" and previous is None:
            changes.append(Change("added", f"New announcement · {item.course}: {item.title}"))
        elif item.kind == "assignment" and previous is None:
            due = f", due {when(item.due_at)}" if item.due_at else ""
            changes.append(Change("added", f"New assignment · {item.course}: {item.title}{due}"))
        elif item.kind == "assignment":
            if item.due_at and previous.due_at and item.due_at != previous.due_at:
                changes.append(Change("changed", f"Due date changed · {item.course}, {item.title}: "
                                                 f"{when(previous.due_at)} → {when(item.due_at)}"))
            elif item.due_at and previous.due_at is None:
                changes.append(Change("changed", f"Due date set · {item.course}, {item.title}: {when(item.due_at)}"))
            if item.status == "graded" and (previous.status != "graded" or previous.score != item.score):
                changes.append(Change("changed", f"New grade · {item.course}, {item.title}: {_grade(item)}"))
        elif item.kind == "material" and previous is None and item.material_kind != "folder":
            new_materials.setdefault(item.course, []).append(item.title)
    changes += [_materials_line(course, titles) for course, titles in new_materials.items()]
    return changes
