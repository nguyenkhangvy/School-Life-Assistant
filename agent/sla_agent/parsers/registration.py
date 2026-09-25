"""Registered courses: EduSoft's "DANH SÁCH MÔN HỌC ĐÃ CHỌN" on the registration page.

Only rows saved to EduSoft's database ("Đã lưu vào CSDL") count as registered."""

import re
from typing import NamedTuple

from sla_agent.errors import ParseError
from sla_agent.parsers.common import soup, text

LIST_TITLE_ID = "ContentPlaceHolder1_ctl00_lblDaChon"
SAVED = "Đã lưu vào CSDL"
COURSE_CODE = re.compile(r"^[A-Z]{2}\d{3}[A-Z]{2}$")


class RegisteredCourse(NamedTuple):
    code: str
    group: str


def parse_registered_courses(pages):
    page = soup(pages["registration"])
    title = page.find(id=LIST_TITLE_ID)
    if title is None:
        raise ParseError("The registered-course list wasn't found on EduSoft's registration page.")

    header_cells = None
    for table in title.find_all_next("table"):
        cells = [text(cell) for cell in table.find_all(["td", "th"])]
        if "Regis ID" in cells and "Mã MH" in cells:
            header_cells = cells[cells.index("STT"):] if "STT" in cells else cells
            break
    if header_cells is None or not {"Mã MH", "NMH", "Trạng Thái môn học"} <= set(header_cells):
        raise ParseError("The registered-course list's columns have changed.")
    code_at, group_at, status_at = (header_cells.index(h) for h in ("Mã MH", "NMH", "Trạng Thái môn học"))

    courses = []
    for table in title.find_all_next("table", class_="body-table"):
        for row in table.find_all("tr"):
            values = [text(cell) for cell in row.find_all("td", recursive=False)]
            if len(values) <= status_at or not COURSE_CODE.match(values[code_at]):
                continue
            if SAVED in values[status_at]:
                courses.append(RegisteredCourse(values[code_at], values[group_at]))
        if courses:
            break
    return courses
