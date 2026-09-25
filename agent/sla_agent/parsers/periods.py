"""IU class periods (tiết). Confirmed by the student and by EduSoft's own labels,
e.g. "Tiết 1 (từ 08:00 đến 08:50)"."""

from datetime import time

from sla_agent.errors import ParseError

PERIODS = {
    1: (time(8, 0), time(8, 50)),
    2: (time(8, 50), time(9, 40)),
    3: (time(9, 40), time(10, 30)),
    4: (time(10, 35), time(11, 25)),
    5: (time(11, 25), time(12, 15)),
    6: (time(12, 15), time(13, 5)),
    7: (time(13, 15), time(14, 5)),
    8: (time(14, 5), time(14, 55)),
    9: (time(14, 55), time(15, 45)),
    10: (time(15, 50), time(16, 40)),
    11: (time(16, 40), time(17, 30)),
    12: (time(17, 30), time(18, 20)),
}


def class_hours(first_period, number_of_periods):
    """(start, end) clock times of a class covering these periods."""
    last_period = first_period + number_of_periods - 1
    if first_period not in PERIODS or last_period not in PERIODS or number_of_periods < 1:
        raise ParseError(f"Unknown periods {first_period}-{last_period}.")
    return PERIODS[first_period][0], PERIODS[last_period][1]
