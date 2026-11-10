"""Shift timing rules used by attendance.

A shift whose end time is at or before its start time runs past midnight
(e.g. 17:30-02:30). Attendance for such a shift belongs to the date the shift
*started*, so a 02:30 check-out closes the previous day's record instead of
failing with "you have not checked in today".

Late arrival is measured against the employee's own shift start plus a grace
period. Employees with no shift fall back to the company-wide
LATE_ARRIVAL_TIME.
"""
from datetime import date, datetime, time, timedelta

from .config import LATE_ARRIVAL_TIME, LATE_GRACE_MINUTES

# Shifts every installation should offer. Matched on start/end time, so an
# Admin renaming one does not cause a duplicate to be re-created.
STANDARD_SHIFTS = [
    ("General", "09:00", "18:00"),
    ("Morning", "10:00", "19:00"),
    ("Afternoon", "13:30", "22:30"),
    ("Evening", "16:30", "01:30"),
    ("Late Evening", "17:30", "02:30"),
]

# After an overnight shift ends, how long a still-open record from the
# previous day keeps accepting a check-out / break punch.
OVERNIGHT_CHECKOUT_WINDOW = timedelta(hours=20)


def _clock(value: str) -> time:
    return time.fromisoformat(value)


def is_overnight(shift) -> bool:
    return shift is not None and _clock(shift.end_time) <= _clock(shift.start_time)


def shift_start(shift, work_date: date) -> datetime:
    return datetime.combine(work_date, _clock(shift.start_time))


def is_late_arrival(shift, work_date: date, check_in: datetime) -> bool:
    if shift is not None:
        return check_in > shift_start(shift, work_date) + timedelta(minutes=LATE_GRACE_MINUTES)
    cutoff = _clock(LATE_ARRIVAL_TIME)
    return (check_in.hour, check_in.minute) > (cutoff.hour, cutoff.minute)


def check_in_work_date(shift, now: datetime) -> date:
    """The attendance date a check-in at `now` counts towards.

    Someone on 17:30-02:30 who arrives (late) at 00:40 is still working the
    shift that began yesterday."""
    if is_overnight(shift) and now.time() < _clock(shift.end_time):
        return now.date() - timedelta(days=1)
    return now.date()
