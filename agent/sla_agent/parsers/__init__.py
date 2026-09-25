"""Page readers: EduSoft pages -> the shared data format.

Each reader takes the dict of pages that EduSoftClient.read(section) returns.
"""

from sla_agent.parsers.exams import parse_exams
from sla_agent.parsers.timetable import parse_timetable
from sla_agent.parsers.tuition import parse_tuition


PARSERS = {"timetable": parse_timetable, "exams": parse_exams, "tuition": parse_tuition}
