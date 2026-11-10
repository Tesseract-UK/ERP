"""Shift-aware attendance, HR-set leave balances, and help-request recipients."""
from datetime import date, datetime, timedelta

import pytest

from app.config import OFFICE_LATITUDE, OFFICE_LONGITUDE
from app.models import Attendance, Shift
from app.routers import attendance as attendance_router
from app.shifts import check_in_work_date, is_late_arrival

AT_OFFICE = {"latitude": OFFICE_LATITUDE, "longitude": OFFICE_LONGITUDE, "accuracy_meters": 20}
WORK_DAY = date(2026, 11, 9)  # a Monday


class Clock:
    def __init__(self, monkeypatch):
        self.now = None
        monkeypatch.setattr(attendance_router, "attendance_now", lambda: self.now)

    def at(self, day: date, hhmm: str):
        h, m = map(int, hhmm.split(":"))
        self.now = datetime(day.year, day.month, day.day, h, m)


@pytest.fixture()
def clock(monkeypatch):
    return Clock(monkeypatch)


def _shift(db, name, start, end):
    s = db.query(Shift).filter(Shift.start_time == start, Shift.end_time == end).first()
    if s is None:
        s = Shift(name=name, start_time=start, end_time=end)
        db.add(s)
        db.flush()
    return s


# ---------- pure shift rules ----------

def test_lateness_follows_the_employees_shift():
    afternoon = Shift(name="A", start_time="13:30", end_time="22:30")
    assert not is_late_arrival(afternoon, WORK_DAY, datetime(2026, 11, 9, 13, 55))
    assert is_late_arrival(afternoon, WORK_DAY, datetime(2026, 11, 9, 14, 1))
    # No shift: company-wide cut-off (09:30) still applies.
    assert not is_late_arrival(None, WORK_DAY, datetime(2026, 11, 9, 9, 30))
    assert is_late_arrival(None, WORK_DAY, datetime(2026, 11, 9, 9, 31))


def test_overnight_late_arrival_after_midnight_counts_for_previous_day():
    night = Shift(name="N", start_time="17:30", end_time="02:30")
    assert check_in_work_date(night, datetime(2026, 11, 10, 0, 40)) == WORK_DAY
    assert check_in_work_date(night, datetime(2026, 11, 9, 17, 25)) == WORK_DAY
    day = Shift(name="D", start_time="10:00", end_time="19:00")
    assert check_in_work_date(day, datetime(2026, 11, 10, 0, 40)) == date(2026, 11, 10)


def test_requested_shifts_are_standard():
    from app.shifts import STANDARD_SHIFTS
    assert {("10:00", "19:00"), ("13:30", "22:30"), ("16:30", "01:30"),
            ("17:30", "02:30")} <= {(s, e) for _n, s, e in STANDARD_SHIFTS}


# ---------- overnight attendance end to end ----------

def test_overnight_shift_checks_out_after_midnight(org, clock):
    org.alice.shift_id = _shift(org.db, "Late Evening", "17:30", "02:30").id
    org.db.commit()
    alice = org.client(org.alice)

    clock.at(WORK_DAY, "17:40")
    r = alice.post("/attendance/check-in", json=AT_OFFICE)
    assert r.status_code == 200, r.text
    assert r.json()["is_late"] is False

    clock.at(WORK_DAY + timedelta(days=1), "01:00")
    today = alice.get("/attendance/today").json()
    assert today and today["date"] == WORK_DAY.isoformat()  # still on the shift
    assert alice.post("/attendance/break/start", json={}).status_code == 200
    clock.at(WORK_DAY + timedelta(days=1), "01:15")
    assert alice.post("/attendance/break/end", json={}).status_code == 200

    clock.at(WORK_DAY + timedelta(days=1), "02:35")
    r = alice.post("/attendance/check-out", json=AT_OFFICE)
    assert r.status_code == 200, r.text
    assert r.json()["date"] == WORK_DAY.isoformat()
    assert 8.5 < r.json()["work_hours"] < 8.8

    rows = org.db.query(Attendance).filter(Attendance.user_id == org.alice.id).all()
    assert len(rows) == 1  # no stray record for the next calendar day

    # That evening the next shift starts a fresh record.
    clock.at(WORK_DAY + timedelta(days=1), "17:30")
    assert alice.get("/attendance/today").json() is None
    r = alice.post("/attendance/check-in", json=AT_OFFICE)
    assert r.status_code == 200, r.text
    assert r.json()["date"] == (WORK_DAY + timedelta(days=1)).isoformat()


def test_day_shift_employee_is_late_by_their_own_start(org, clock):
    org.bob.shift_id = _shift(org.db, "Afternoon", "13:30", "22:30").id
    org.db.commit()
    clock.at(WORK_DAY, "13:45")
    r = org.client(org.bob).post("/attendance/check-in", json=AT_OFFICE)
    assert r.status_code == 200, r.text
    assert r.json()["is_late"] is False  # would have been "late" under the old 09:30 rule


# ---------- leave balances ----------

def test_balances_are_zero_until_hr_sets_them(org):
    # Company policy exists but is not applied automatically.
    new_joiner = org._user("joiner", "employee", manager=org.manager)
    org.db.commit()
    bal = org.client(new_joiner).get("/leaves/balance").json()
    assert bal["casual"]["allocated"] == 0 and bal["wfh"]["annual_cap"] == 0


def test_hr_cannot_set_their_own_allocation(org):
    hr = org.client(org.hr)
    r = hr.put(f"/hr/employees/{org.hr.id}/leave-overrides", json={"allocations": {"casual": 30}})
    assert r.status_code == 403
    second_hr = org._user("hr2", "hr", manager=org.admin)
    org.db.commit()
    assert org.client(second_hr).put(f"/hr/employees/{org.hr.id}/leave-overrides",
                                     json={"allocations": {"casual": 12}}).status_code == 200
    assert org.client(org.admin).put(f"/hr/employees/{org.hr.id}/leave-overrides",
                                     json={"allocations": {"casual": 14}}).status_code == 200


# ---------- help-request recipients ----------

def test_recipient_search_lists_each_person_once_and_filters(org):
    alice = org.client(org.alice)
    everyone = alice.get("/requests/recipients").json()
    ids = [p["id"] for p in everyone]
    assert len(ids) == len(set(ids))
    assert everyone[0]["role"] == "manager" and everyone[0]["id"] == org.manager.id
    assert org.bob.id not in ids  # plain colleagues are not addressable
    hits = alice.get("/requests/recipients?search=adm").json()
    assert {p["id"] for p in hits} == {org.admin.id, org.admin2.id}


def test_manager_who_is_admin_listed_once(org):
    # hr reports to admin: admin is hr's manager and also an admin.
    rows = org.client(org.hr).get("/requests/recipients").json()
    admin_rows = [p for p in rows if p["id"] == org.admin.id]
    assert len(admin_rows) == 1 and admin_rows[0]["role"] == "manager"
