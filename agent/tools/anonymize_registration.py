"""Make an anonymized test copy of EduSoft's registration page.

Usage: python -m agent.tools.anonymize_registration SAVED_PAGE OUTPUT
Keeps the layout, course codes, names, groups and statuses. Removes the student
box, the greeting, view state, the advisor's message and every fee amount."""

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def anonymize(html):
    soup = BeautifulSoup(html, "html.parser")
    personal = set()
    for tag in soup.find_all(id=re.compile(r"ucThongTinSV_lb")):
        text = tag.get_text(" ", strip=True)
        if text and len(text) > 2:
            personal.add(text)
        tag.string = "-"
    greeting = soup.find(id="Header1_Logout1_lblNguoiDung")
    if greeting:
        match = re.search(r"Chào bạn (.+?) \((\w+)\)", greeting.get_text(" ", strip=True))
        if match:
            personal.update(match.groups())
        greeting.string = "Chào bạn STUDENT (STUDENT)"
    for tag in soup.find_all("input", attrs={"name": "__VIEWSTATE"}):
        tag["value"] = "VIEWSTATE-REMOVED"
    for tag in soup.find_all(id=re.compile(r"(lblLoiNhan|txtLoiNhan|lblNoiDungLoiNhan)")):
        tag.string = ""
    for td in soup.find_all("td"):
        if re.fullmatch(r"-?\d{1,3}(,\d{3})+", td.get_text(strip=True)):
            td.string = "1,000,000"
    out = str(soup)
    for value in sorted(personal, key=len, reverse=True):
        out = out.replace(value, "STUDENT")
    return out, personal


if __name__ == "__main__":
    source, target = Path(sys.argv[1]), Path(sys.argv[2])
    result, personal = anonymize(source.read_text(encoding="utf-8"))
    target.write_text(result, encoding="utf-8")
    leaks = [v for v in personal if v in result]
    print(f"personal values removed: {len(personal)}, still present: {len(leaks)}")
