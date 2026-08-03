"""Employee attendance: check-in/out, breaks, monthly calendar."""
import calendar as pycalendar
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import client_info, get_current_user
from ..models import (
    Attendance, AttendanceBreak, Holiday, LeaveRequest, User, WFHRequest,
)
from ..schemas import CheckInRequest, CheckOutRequest
from ..serializers import attendance_out
from ..utils import audit, parse_dt, recompute_attendance

router = APIRouter(prefix="/attendance", tags=["attendance"])


def _today_record(db: Session, user_id: int, for_date: date) -> Attendance | None:
    return db.query(Attendance).filter(
        Attendance.user_id == user_id, Attendance.date == for_date).first()


@router.get("/today")
def today(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    att = _today_record(db, user.id, date.today())
    return attendance_out(att) if att else None


@router.post("/check-in")
def check_in(body: CheckInRequest, request: Request,
             user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    now = parse_dt(body.local_time)
    att = _today_record(db, user.id, now.date())
    if att and att.check_in:
        raise HTTPException(status_code=400, detail="You have already checked in today")
    info = client_info(request)
    if att is None:
        att = Attendance(user_id=user.id, date=now.date())
        db.add(att)
    att.check_in = now
    att.status = "present"
    att.latitude, att.longitude = body.latitude, body.longitude
    att.ip_address, att.browser = info["ip"], info["browser"]
    att.os, att.device = info["os"], info["device"]
    recompute_attendance(att)
    audit(db, user.id, "check_in", "attendance", f"Checked in at {now:%H:%M}", info)
    db.commit()
    db.refresh(att)
    return attendance_out(att)


@router.post("/check-out")
def check_out(body: CheckOutRequest, request: Request,
              user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    now = parse_dt(body.local_time)
    att = _today_record(db, user.id, now.date())
    if att is None or att.check_in is None:
        raise HTTPException(status_code=400, detail="You have not checked in today")
    if att.check_out:
        raise HTTPException(status_code=400, detail="You have already checked out today")
    # Auto-close any open break at checkout.
    for br in att.breaks:
        if br.end_time is None:
            br.end_time = now
    att.check_out = now
    recompute_attendance(att)
    audit(db, user.id, "check_out", "attendance",
          f"Checked out at {now:%H:%M}", client_info(request))
    db.commit()
    db.refresh(att)
    return attendance_out(att)


@router.post("/break/start")
def break_start(body: CheckOutRequest, request: Request,
                user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    now = parse_dt(body.local_time)
    att = _today_record(db, user.id, now.date())
    if att is None or att.check_in is None:
        raise HTTPException(status_code=400, detail="Check in before starting a break")
    if att.check_out:
        raise HTTPException(status_code=400, detail="You have already checked out today")
    if any(b.end_time is None for b in att.breaks):
        raise HTTPException(status_code=400, detail="A break is already in progress")
    db.add(AttendanceBreak(attendance_id=att.id, start_time=now))
    audit(db, user.id, "break_start", "attendance", client=client_info(request))
    db.commit()
    db.refresh(att)
    return attendance_out(att)


@router.post("/break/end")
def break_end(body: CheckOutRequest, request: Request,
              user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    now = parse_dt(body.local_time)
    att = _today_record(db, user.id, now.date())
    open_break = next((b for b in (att.breaks if att else []) if b.end_time is None), None)
    if open_break is None:
        raise HTTPException(status_code=400, detail="No break in progress")
    open_break.end_time = now
    recompute_attendance(att)
    audit(db, user.id, "break_end", "attendance", client=client_info(request))
    db.commit()
    db.refresh(att)
    return attendance_out(att)


def build_month_calendar(db: Session, target_user: User, year: int, month: int) -> dict:
    """Merge attendance rows, approved leave/WFH and holidays into day cells."""
    first = date(year, month, 1)
    last = date(year, month, pycalendar.monthrange(year, month)[1])

    records = {a.date: a for a in db.query(Attendance).filter(
        Attendance.user_id == target_user.id,
        Attendance.date >= first, Attendance.date <= last).all()}
    holidays = {h.date: h for h in db.query(Holiday).filter(
        Holiday.date >= first, Holiday.date <= last).all()}
    leaves = db.query(LeaveRequest).filter(
        LeaveRequest.user_id == target_user.id, LeaveRequest.status == "approved",
        LeaveRequest.start_date <= last, LeaveRequest.end_date >= first).all()
    wfh_dates = {w.date for w in db.query(WFHRequest).filter(
        WFHRequest.user_id == target_user.id, WFHRequest.status == "approved",
        WFHRequest.date >= first, WFHRequest.date <= last).all()}

    leave_dates = {}
    for lv in leaves:
        d = max(lv.start_date, first)
        while d <= min(lv.end_date, last):
            leave_dates[d] = lv.leave_type
            d += timedelta(days=1)

    days, today_d, d = [], date.today(), first
    while d <= last:
        cell = {"date": d.isoformat(), "status": None, "detail": None}
        att = records.get(d)
        if att:
            cell.update(status=att.status, detail=attendance_out(att))
        elif d in holidays and holidays[d].holiday_type != "optional":
            cell.update(status="holiday", detail={"name": holidays[d].name})
        elif d in leave_dates:
            cell.update(status="leave", detail={"leave_type": leave_dates[d]})
        elif d in wfh_dates:
            cell["status"] = "wfh"
        elif d.weekday() >= 5:
            cell["status"] = "weekend"
        elif d < today_d and (target_user.joining_date is None or d >= target_user.joining_date):
            cell["status"] = "absent"
        days.append(cell)
        d += timedelta(days=1)
    return {"year": year, "month": month, "days": days}


@router.get("/calendar")
def my_calendar(year: int, month: int, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    if not (1 <= month <= 12):
        raise HTTPException(status_code=400, detail="Invalid month")
    return build_month_calendar(db, user, year, month)
