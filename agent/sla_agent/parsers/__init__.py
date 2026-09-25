"""Page readers: EduSoft pages -> the shared data format.

Each reader takes the dict of pages that EduSoftClient.read(section) returns.
"""

from sla_agent.errors import ParseError
from sla_agent.parsers.exams import parse_exams
from sla_agent.parsers.timetable import parse_timetable


def parse_tuition(pages):
    raise ParseError("The tuition reader isn't written yet: EduSoft's tuition report hasn't been located.")


PARSERS = {"timetable": parse_timetable, "exams": parse_exams, "tuition": parse_tuition}
