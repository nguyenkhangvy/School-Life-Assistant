"""Small helpers shared by the EduSoft page readers."""

import re
from datetime import datetime, time, timedelta, timezone

from bs4 import BeautifulSoup

from sla_agent.errors import ParseError

VIETNAM = timezone(timedelta(hours=7))
TERM_TITLE = re.compile(r"Học kỳ\s*(\d)\s*-\s*Năm học\s*(\d{4})\s*-\s*\d{4}", re.IGNORECASE)
CLOCK = re.compile(r"^(\d{1,2})\s*[:gh]\s*(\d{2})$")


def soup(html):
    return BeautifulSoup(html, "html.parser")


def text(element):
    return element.get_text(" ", strip=True) if element is not None else ""


def selected_option(select):
    return select.find("option", selected=True) or select.find("option")


def term_code_from_title(title):
    """'Học kỳ 1 - Năm học 2026-2027' -> '20261'."""
    match = TERM_TITLE.search(title)
    if not match:
        raise ParseError(f"Couldn't read the semester from {title!r}.")
    return f"{match.group(2)}{match.group(1)}"


def parse_day(value):
    try:
        return datetime.strptime(value.strip(), "%d/%m/%Y").date()
    except ValueError:
        raise ParseError(f"Couldn't read the date {value!r}.") from None


def parse_clock(value):
    match = CLOCK.match(value.strip())
    if not match:
        raise ParseError(f"Couldn't read the time {value!r}.")
    return time(int(match.group(1)), int(match.group(2)))


def vietnam_time(day, clock):
    return datetime.combine(day, clock, tzinfo=VIETNAM)
