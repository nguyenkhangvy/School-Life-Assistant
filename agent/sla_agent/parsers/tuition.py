"""Tuition reader: EduSoft's report "Tổng Hợp Học Phí Một Sinh Viên" (template HP1SV.001).

The report comes from EduSoft's report viewer as JSON holding the page as an
HTML grid. Cells span several columns and blank values are left as empty
cells, so each value is matched to its header by column position.
"""

import json
import re

from pydantic import ValidationError
from sla_contract.schema import Tuition, TuitionItem

from sla_agent.errors import ParseError
from sla_agent.parsers.common import soup, term_code_from_title, text

SEMESTER = "Niên học học kỳ"
COLUMNS = {
    "before_discount": "Hp (chưa giảm)",
    "discount": "Miễn giảm",
    "payable": "Phải thu",
    "paid": "Đã thu",
    "owed": "Còn nợ",
}
NOT_BILLED = "No tuition listed for this semester yet"


def _amount(value):
    value = value.strip()
    if not value:
        return 0
    digits = value.replace(",", "").replace(".", "")
    if not re.fullmatch(r"-?\d+", digits):
        raise ParseError(f"Couldn't read the amount {value!r}.")
    return int(digits)


def _by_column(row):
    """{starting column: cell text}, counting column spans."""
    column, cells = 0, {}
    for cell in row.find_all("td", recursive=False):
        cells[column] = text(cell)
        column += int(cell.get("colspan") or 1)
    return cells


def _report_page(report_json):
    try:
        report = json.loads(report_json)
    except ValueError:
        raise ParseError("The tuition report isn't in the expected format.") from None
    pages = report.get("pagesArray") if isinstance(report, dict) else None
    contents = [p["content"] for p in pages or [] if isinstance(p, dict) and isinstance(p.get("content"), str)]
    if not contents:
        raise ParseError("The tuition report has no pages.")
    return soup("".join(contents))


def parse_tuition(pages):
    """pages: {"term": "20261", "report": the report viewer's JSON reply}."""
    term = pages["term"]
    rows = _report_page(pages["report"]).find_all("tr")

    header_row = next((r for r in rows if set(_by_column(r).values()) >= {SEMESTER, *COLUMNS.values()}), None)
    if header_row is None:
        raise ParseError("The tuition report's column headers have changed.")
    position = {label: column for column, label in _by_column(header_row).items()}

    for row in rows:
        cells = _by_column(row)
        label = cells.get(position[SEMESTER], "")
        if not label.startswith("Học kỳ"):
            continue
        if term_code_from_title(label) != term:
            continue
        value = {key: _amount(cells.get(position[header], "")) for key, header in COLUMNS.items()}
        items = [TuitionItem(description="Học phí (chưa giảm)", amount=value["before_discount"])]
        if value["discount"]:
            items.append(TuitionItem(description=COLUMNS["discount"], amount=-abs(value["discount"])))
        try:
            return Tuition(term_code=term, amount_due=value["payable"], amount_paid=value["paid"],
                           balance=value["owed"], items=items)
        except ValidationError as error:
            raise ParseError(f"Unexpected tuition amounts: {error.errors()[0]['msg']}") from None

    return Tuition(term_code=term, amount_due=0, amount_paid=0, balance=0, status_text=NOT_BILLED)
