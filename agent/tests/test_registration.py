from pathlib import Path

import pytest
import responses

from sla_agent.edusoft_client import EduSoftClient
from sla_agent.errors import ParseError
from sla_agent.parsers.registration import RegisteredCourse, parse_registered_courses

FIXTURE = (Path(__file__).parent / "fixtures" / "registration.html").read_text(encoding="utf-8")
REGISTRATION_URL = "https://edusoftweb.hcmiu.edu.vn/default.aspx?page=dkmonhoc"

# Hand-checked against the timetable copy: same 8 courses and groups.
EXPECTED = [
    RegisteredCourse("IT090IU", "01"), RegisteredCourse("IT007WE", "01"), RegisteredCourse("PH012IU", "01"),
    RegisteredCourse("IT093IU", "02"), RegisteredCourse("EN011IU", "03"), RegisteredCourse("IT120IU", "01"),
    RegisteredCourse("MA026IU", "02"), RegisteredCourse("IT013IU", "02"),
]


def test_reads_the_registered_courses_with_their_groups():
    assert parse_registered_courses({"registration": FIXTURE}) == EXPECTED


def test_rows_not_saved_to_the_database_are_left_out():
    page = FIXTURE.replace("Đã lưu vào CSDL", "Chưa lưu", 1)

    assert len(parse_registered_courses({"registration": page})) == 7


@pytest.mark.parametrize("old, new", [("lblDaChon", "lblRenamed"), (">Regis ID <", ">ID <")],
                         ids=["list-title-missing", "header-changed"])
def test_a_page_that_does_not_look_right_raises_parse_error(old, new):
    assert old in FIXTURE

    with pytest.raises(ParseError):
        parse_registered_courses({"registration": FIXTURE.replace(old, new)})


@responses.activate
def test_the_registration_page_is_only_ever_read_with_get():
    responses.get(REGISTRATION_URL, body=FIXTURE)

    pages = EduSoftClient().read("registration")

    assert pages == {"registration": FIXTURE}
    assert [c.request.method for c in responses.calls] == ["GET"]
