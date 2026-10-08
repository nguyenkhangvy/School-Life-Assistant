"""Sorting one email on the laptop: who sent it, its categories, its dates, its times, and the class changes it
announces. Pure functions. The rules are in docs/superpowers/specs/2026-09-28-outlook-mailbox-design.md,
section 5; the times are read by mail_times (docs/superpowers/specs/2026-10-07-mail-event-kinds-design.md).

The email's text is only read here, in memory. What leaves this module is a MailItem, which has no
field for text."""

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from pydantic import ValidationError
from sla_contract.schema import MailClassChange, MailDeadline, MailItem, MailPeriod, MailSession

from sla_agent.class_changes import dates_in, fold, read_announcement
from sla_agent.mail_times import Found, clean, read_times
from sla_agent.mail_words import Words

log = logging.getLogger(__name__)

VIETNAM_OFFSET = timedelta(hours=7)
BLACKBOARD_SENDER = "bb@hcmiu.edu.vn"
IU_DOMAIN = "hcmiu.edu.vn"
STUDENT_DOMAIN = "student.hcmiu.edu.vn"
MICROSOFT_DOMAINS = ("microsoft.com", "sharepointonline.com")
IU_ADDRESS = re.compile(r"([\w.+-]+)@hcmiu\.edu\.vn", re.IGNORECASE)

# The order categories are kept in when more than two match (spec 5.3).
ORDER = ("class", "school_task", "money", "event", "training_points", "requests_account", "system_notice",
         "promotion")
MAX_CATEGORIES = 2
MAX_DATES = 30
MAX_CLASS_CHANGES = 10

# Words are written as they are read; they are compared without letter case, and with accents only when the email
# writes them (see mail_words.Words).
SCHOOL_TASK_WORDS = ("khảo sát", "survey", "tạm trú", "cư trú", "sinh hoạt công dân", "bảo hiểm y tế", "BHYT")
REQUIRED_WORDS = ("bắt buộc",)  # a school task too, but not right after NOT: "không bắt buộc" is optional
NOT = "không"
MONEY_WORDS = ("học bổng", "scholarship", "hóa đơn", "invoice", "học phí", "tuition", "thanh toán", "payment",
               "lệ phí")
EVENT_WORDS = ("thư mời", "workshop", "talkshow", "chuyên đề", "hội thảo", "seminar", "webinar", "cuộc thi",
               "contest", "casting", "hội thao", "khai mạc", "bế mạc", "ngày hội", "tuần lễ", "đăng ký tham gia",
               "đăng ký tham dự")
ACCOUNT_WORDS = ("password", "mật khẩu")
PROMOTION_WORDS = ("ưu đãi", "khuyến mãi", "giảm giá", "voucher", "discount")
TRAINING_POINTS = "điểm rèn luyện"
TEAMS_ADDED_WORDS = ("được thêm", "đã thêm", "added you")


@dataclass(frozen=True)
class Email:
    """One email as Outlook gives it to the agent. `text` stays on the laptop."""

    key: str
    entry_id: str
    thread_id: str | None
    received_at: datetime  # aware
    sender_name: str
    sender_address: str
    subject: str
    text: str


@dataclass(frozen=True)
class Context:
    """What the laptop knows about this semester, from the last EduSoft and Blackboard reads."""

    courses: tuple = ()  # (course code, course name, lecturer as EduSoft writes it, e.g. "P.Q.Hùng")
    bb_courses: tuple = ()  # (Blackboard course name, course code)


SCHOOL_TASK = Words(SCHOOL_TASK_WORDS)
REQUIRED = Words(REQUIRED_WORDS, unless_after=NOT)
MONEY = Words(MONEY_WORDS)
EVENT = Words(EVENT_WORDS)
ACCOUNT = Words(ACCOUNT_WORDS)
PROMOTION = Words(PROMOTION_WORDS)
TRAINING = Words([TRAINING_POINTS])
TEAMS_ADDED = Words(TEAMS_ADDED_WORDS)
TICKET = re.compile(r"\s*(?:(?:re|fw|fwd)\s*:\s*)*\[ticket:")  # on folded text; replies and forwards too


def _domain(address):
    return address.rpartition("@")[2].lower()


def _local(address):
    return address.rpartition("@")[0].lower()


def _is_iu_staff_address(address):
    domain = _domain(address)
    return "@" in address and domain != STUDENT_DOMAIN and (domain == IU_DOMAIN or domain.endswith("." + IU_DOMAIN))


def name_handles(name):
    """The address beginnings an IU person's own name gives, in both word orders: "Vo Minh Khoa" ->
    vmkhoa, vominhkhoa, kmvo, khoaminhvo. Needs at least two words."""
    words = re.findall(r"[a-z]+", fold(name))
    if len(words) < 2:
        return set()
    handles = set()
    for order in (words, words[::-1]):
        handles.add("".join(word[0] for word in order[:-1]) + order[-1])
        handles.add("".join(order))
    return handles


def lecturer_handle(lecturer):
    """EduSoft's short lecturer name as an address beginning: "P.Q.Hùng" -> "pqhung"."""
    return re.sub(r"[^a-z]", "", fold(lecturer))


def is_microsoft_notice(email):
    """Teams "added you to a group" notices and anything Microsoft sends by itself."""
    domain = _domain(email.sender_address)
    if any(domain == d or domain.endswith("." + d) for d in MICROSOFT_DOMAINS):
        return True
    return "microsoft teams" in fold(email.subject) and TEAMS_ADDED.search(email.subject)


def blackboard_lecturer(email):
    """For a Blackboard announcement, the lecturer's address beginning from the sender name
    ("Đặng Văn Long - dvlong@hcmiu.edu.vn" -> "dvlong"); else None. Receipts named "bb@hcmiu.edu.vn" have none."""
    if email.sender_address.lower() != BLACKBOARD_SENDER:
        return None
    for local in IU_ADDRESS.findall(email.sender_name or ""):
        if local.lower() != "bb":
            return local.lower()
    return None


def sender_handle(email):
    """The address beginning of the person behind the email: the lecturer in a Blackboard announcement, else
    the sender, when the address is an IU staff address; else None."""
    lecturer = blackboard_lecturer(email)
    if lecturer:
        return lecturer
    return _local(email.sender_address) if _is_iu_staff_address(email.sender_address) else None


def is_from_lecturer(email, context):
    """Spec 5.1: a Blackboard announcement, a timetable lecturer, or an IU person writing from their own address."""
    if is_microsoft_notice(email):
        return False
    if blackboard_lecturer(email):
        return True
    handle = sender_handle(email)
    if not handle:
        return False
    if any(lecturer and handle == lecturer_handle(lecturer) for _, _, lecturer in context.courses):
        return True
    return handle in name_handles(email.sender_name)


def categories(email, from_lecturer):
    """Spec 5.2 and 5.3: at most two categories, in ORDER."""
    subject = email.subject
    both = subject + "\n" + email.text
    found = set()
    if from_lecturer or email.sender_address.lower() == BLACKBOARD_SENDER:
        found.add("class")
    if _is_iu_staff_address(email.sender_address) and (SCHOOL_TASK.search(subject) or REQUIRED.search(subject)):
        found.add("school_task")
    if MONEY.search(subject):
        found.add("money")
    if EVENT.search(subject):
        found.add("event")
    if TRAINING.search(both):
        found.add("training_points")
    if TICKET.match(fold(subject)) or ACCOUNT.search(subject):
        found.add("requests_account")
    if is_microsoft_notice(email):
        found.update(("system_notice", "class") if TEAMS_ADDED.search(subject) else ("system_notice",))
    if PROMOTION.search(both):
        found.add("promotion")
    return [name for name in ORDER if name in found][:MAX_CATEGORIES]


def course_of(email, context):
    """Spec 5.5: the one course a lecturer's email is about, or None."""
    for name, code in context.bb_courses:
        if code and email.subject.startswith(name + ": "):
            return code
    subject_and_text = email.subject + "\n" + email.text
    folded = fold(subject_and_text)
    named = {code for code, name, _ in context.courses
             if re.search(rf"\b{re.escape(code)}\b", subject_and_text, re.IGNORECASE)
             or (name and re.search(r"\b" + re.escape(fold(name)) + r"\b", folded))}
    if len(named) == 1:
        return named.pop()
    handle = sender_handle(email)
    taught = {code for code, _, lecturer in context.courses if lecturer and handle == lecturer_handle(lecturer)}
    return taught.pop() if len(taught) == 1 else None


def blackboard_title(email):
    """The announcement's own title in a Blackboard email: the subject after its first ": "."""
    if not blackboard_lecturer(email) or ": " not in email.subject:
        return None
    return email.subject.split(": ", 1)[1].strip()[:255] or None


def class_changes(email, code):
    posted = email.received_at.astimezone(timezone.utc).replace(tzinfo=None)
    found = dict.fromkeys(read_announcement(email.subject, email.text, posted))
    return [MailClassChange(course_code=code, kind=a.kind, day=a.day, start=a.start, end=a.end, room=a.room)
            for a in found][:MAX_CLASS_CHANGES]


def times_of(email, arrived):
    """The email's sessions, Periods, deadlines and flags (mail_times), read in every email so they are ready when
    the student moves one to Event. An empty Found when the reader fails on it."""
    try:
        return read_times(email.subject, email.text, arrived)
    except Exception as error:  # the message could quote the email
        log.warning("Couldn't read the times in an email (%s); it is uploaded without them",
                    error.__class__.__name__)
        return Found()


def upload_session(session):
    """One FoundSession as the upload holds it (spec 2026-10-07-mail-event-kinds-design.md §3.1), with its check-in and
    link time apart from its start (from stage 2; mailbox-events addendum A.1 moved the start). What the format
    can't hold is left out of it: an end not after the start (without the next day), a check-in or link after it."""
    end = session.end
    if end is not None and not session.ends_next_day and end <= session.start:
        end = None
    return MailSession(
        day=session.day, start=session.start, end=end, end_is_approximate=session.end_is_approximate and end is not None,
        ends_next_day=session.ends_next_day and end is not None,
        check_in=session.check_in if session.check_in and session.check_in <= session.start else None,
        link_opens=session.link_opens if session.link_opens and session.link_opens <= session.start else None,
        mode=session.mode, relative=session.relative, label=session.label)


def upload_sessions(found):
    """The sessions as the upload holds them: each day and start once, in time order."""
    kept = {}
    for session in found.sessions:
        kept.setdefault((session.day, session.start), upload_session(session))
    return [kept[key] for key in sorted(kept)]


def _each(make, items):
    """make(item) for each item the format can hold; one it can't (a Period whose times don't fit its mode) is left
    out, not the whole email."""
    kept = []
    for item in items:
        try:
            kept.append(make(item))
        except ValidationError:
            log.debug("Left out a time the upload format can't hold")
    return kept


def upload_periods(found):
    return _each(lambda p: MailPeriod(first_day=p.first_day, last_day=p.last_day, mode=p.mode, from_time=p.from_time,
                                      to_time=p.to_time, details_later=p.details_later, label=p.label), found.periods)


def upload_deadlines(found):
    return _each(lambda d: MailDeadline(kind=d.kind, day=d.day, time=d.at, mode=d.mode), found.deadlines)


def sort_email(email, context):
    """The MailItem for one email. If the rules fail on it, it is uploaded unsorted (sorted=False)."""
    known = dict(key=email.key, entry_id=email.entry_id, thread_id=email.thread_id, received_at=email.received_at,
                 sender_name=(email.sender_name or "")[:255], sender_address=(email.sender_address or "").lower()[:255],
                 subject=(email.subject or "")[:500])
    try:
        lecturer = is_from_lecturer(email, context)
        arrived = (email.received_at.astimezone(timezone.utc) + VIETNAM_OFFSET).date()
        code = course_of(email, context) if lecturer else None
        found = times_of(email, arrived)
        changes = class_changes(email, code) if code else []
        return MailItem(
            **known,
            categories=categories(email, lecturer),
            from_lecturer=lecturer,
            dates=dates_in(email.subject + "\n" + clean(email.subject, email.text), arrived)[:MAX_DATES],
            sessions=upload_sessions(found),
            periods=upload_periods(found),
            deadlines=upload_deadlines(found),
            register_by=found.register_by,
            # An email announcing a class change is not a meeting: its classes already reach the Timetable
            # (Blackboard's "Please join the meeting on time" for an online class; spec §2).
            meeting=found.meeting and not changes,
            registered=found.registered,
            blackboard_title=blackboard_title(email),
            class_changes=changes,
        )
    except Exception as error:  # one email must never stop the others; the message could quote the email
        log.warning("Couldn't sort an email (%s); it is uploaded unsorted", error.__class__.__name__)
        return MailItem(**known, sorted=False)
