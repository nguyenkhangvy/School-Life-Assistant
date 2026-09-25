"""Exam reader: EduSoft's final exam page (xemlichthi) and midterm page (xemlichthigk).

Only exams of the requested semester are kept. EduSoft publishes exam
schedules late in the semester; until then the result is an empty list.
"""

from sla_contract.schema import Exams, Exam

from sla_agent.errors import ParseError
from sla_agent.parsers.common import parse_clock, parse_day, selected_option, soup, term_code_from_title, text, vietnam_time

FINAL_TERM_FIELD = "ctl00$ContentPlaceHolder1$ctl00$dropNHHK"
MIDTERM_TITLE_ID = "ContentPlaceHolder1_ctl00_lblTitle"
GRID_ID = "ContentPlaceHolder1_ctl00_gvXem"
COLUMNS = {
    "code": ("Mã Môn Học",),
    "name": ("Tên Môn Học",),
    "date": ("Ngày Thi",),
    "time": ("Giờ BĐ",),
    "minutes": ("Số phút",),
    "room": ("Phòng", "Tên Phòng"),
    "note": ("Ghi chú", "Hình thức thi"),
}
REQUIRED = ("code", "name", "date", "time")


def _rows(page, exam_type):
    grid = page.find(id=GRID_ID)
    if grid is None:
        return []  # no exams published for this semester
    rows = grid.find_all("tr")
    header = [text(cell) for cell in rows[0].find_all(["th", "td"])]
    column = {key: next((header.index(n) for n in names if n in header), None) for key, names in COLUMNS.items()}
    missing = [key for key in REQUIRED if column[key] is None]
    if missing:
        raise ParseError(f"The exam table is missing columns: {', '.join(missing)}.")

    def cell(values, key):
        index = column[key]
        return values[index] if index is not None and index < len(values) else ""

    exams = []
    for row in rows[1:]:
        values = [text(td) for td in row.find_all("td", recursive=False)]
        if not any(values):
            continue
        minutes = cell(values, "minutes")
        exams.append(Exam(
            course_code=cell(values, "code"),
            course_name=cell(values, "name"),
            exam_type=exam_type,
            start_at=vietnam_time(parse_day(cell(values, "date")), parse_clock(cell(values, "time"))),
            duration_min=int(minutes) if minutes.isdigit() else None,
            room=cell(values, "room") or None,
            notes=cell(values, "note") or None,
        ))
    return exams


def parse_exams(pages):
    """pages: {"term": "20261", "final": html or None, "midterm": html or None}."""
    term = pages["term"]
    exams = []

    if pages.get("final"):
        page = soup(pages["final"])
        select = page.find("select", attrs={"name": FINAL_TERM_FIELD})
        if select is None:
            raise ParseError("The final exam page's semester list wasn't found.")
        chosen = selected_option(select)
        if chosen is not None and chosen.get("value") == term:
            exams += _rows(page, "final")

    if pages.get("midterm"):
        page = soup(pages["midterm"])
        title = page.find(id=MIDTERM_TITLE_ID)
        if title is None:
            raise ParseError("The midterm exam page's semester title wasn't found.")
        if term_code_from_title(text(title)) == term:
            exams += _rows(page, "midterm")

    return Exams(term_code=term, exams=exams)
