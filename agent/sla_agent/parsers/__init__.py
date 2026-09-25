"""Page readers: EduSoft HTML -> the shared data format.

They are written against real (anonymized) EduSoft pages in build step 4.
Until then each one reports clearly that it isn't written yet.
"""

from sla_agent.errors import ParseError


def _not_written_yet(name):
    def parse(html):
        raise ParseError(f"The {name} reader isn't written yet: it needs real EduSoft pages (build step 4).")

    return parse


PARSERS = {name: _not_written_yet(name) for name in ("timetable", "exams", "tuition")}
