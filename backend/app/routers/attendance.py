"""Employee attendance: check-in/out, breaks, monthly calendar."""
import calendar as pycalendar
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import client_info, get_current_user
from ..attendance_location import (
    attendance_now,
    validate_attendance_location,
)
from ..models import (
    Attendance, AttendanceBreak, CompanyWFHDay, Holiday, LeaveRequest, User, WFHRequest,
)
from ..schemas import CheckInRequest, CheckOutRequest
from ..serializers import attendance_out
from ..shifts import OVERNIGHT_CHECKOUT_WINDOW, check_in_work_date, is_overnight
from ..utils import audit, recompute_attendance

router = APIRouter(prefix="/attendance", tags=["attendance"])


def _today_record(db: Session, user_id: int, for_date: date) -> Attendance | None:
    return db.query(Attendance).filter(
        Attendance.user_id == user_id, Attendance.date == for_date).first()


def _active_record(db: Session, user: User, now) -> Attendance | None:
    """The record a punch at `now` belongs to.

    Normally today's. For an overnight shift (e.g. 17:30-02:30), a record
    from yesterday that is still open — or was closed under a minute ago, so
    it can be undone — is the one being worked, even after midnight."""
    att = _today_record(db, user.id, now.date())
    if att is not None and att.check_in is not None:
        return att
    if is_overnight(user.shift):
        prev = _today_record(db, user.id, now.date() - timedelta(days=1))
        if (prev is not None and prev.check_in is not None
                and now - prev.check_in < OVERNIGHT_CHECKOUT_WINDOW
                and (prev.check_out is None or (now - prev.check_out).total_seconds() <= 60)):
            return prev
    return att


def _has_approved_wfh(db: Session, user_id: int, for_date: date) -> bool:
    """Approved personal WFH, or a company-wide WFH day declared by an Admin."""
    if db.query(CompanyWFHDay.id).filter(CompanyWFHDay.date == for_date).first():
        return True
    return db.query(WFHRequest.id).filter(
        WFHRequest.user_id == user_id,
        WFHRequest.date == for_date,
        WFHRequest.status == "approved",
    ).first() is not None


def attendance_user(user: User = Depends(get_current_user)) -> User:
    """Admins sit outside attendance tracking: they never check in or out."""
    if user.role == "admin":
        raise HTTPException(status_code=403, detail="Administrators do not record attendance")
    return user


def _require_checkout_location(body: CheckOutRequest) -> tuple[float, float, float]:
    if (
        body.latitude is None
        or body.longitude is None
        or body.accuracy_meters is None
    ):
        raise HTTPException(
            status_code=400,
            detail="Allow location access to check out.",
        )
    return body.latitude, body.longitude, body.accuracy_meters


@router.get("/today")
def today(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    att = _active_record(db, user, attendance_now())
    return attendance_out(att) if att else None


@router.post("/check-in")
def check_in(body: CheckInRequest, request: Request,
             user: User = Depends(attendance_user), db: Session = Depends(get_db)):
    now = attendance_now()
    work_date = check_in_work_date(user.shift, now)
    att = _today_record(db, user.id, work_date)
    if att and att.check_in:
        raise HTTPException(status_code=400, detail="You have already checked in today")

    approved_wfh = _has_approved_wfh(db, user.id, work_date)
    distance = validate_attendance_location(
        db,
        body.latitude,
        body.longitude,
        body.accuracy_meters,
        allow_outside_office=approved_wfh,
    )
    info = client_info(request)
    if att is None:
        att = Attendance(user_id=user.id, date=work_date)
        db.add(att)
    att.check_in = now
    att.status = "wfh" if approved_wfh else "present"
    att.latitude, att.longitude = body.latitude, body.longitude
    att.location_accuracy_meters = body.accuracy_meters
    att.distance_from_office_meters = distance
    att.ip_address, att.browser = info["ip"], info["browser"]
    att.os, att.device = info["os"], info["device"]
    recompute_attendance(att)
    audit(db, user.id, "check_in", "attendance", f"Checked in at {now:%H:%M}", info)
    db.commit()
    db.refresh(att)
    return attendance_out(att)


@router.post("/check-out")
def check_out(body: CheckOutRequest, request: Request,
              user: User = Depends(attendance_user), db: Session = Depends(get_db)):
    now = attendance_now()
    att = _active_record(db, user, now)
    if att is None or att.check_in is None:
        raise HTTPException(status_code=400, detail="You have not checked in today")
    if att.check_out:
        raise HTTPException(status_code=400, detail="You have already checked out today")

    latitude, longitude, accuracy = _require_checkout_location(body)
    approved_wfh = _has_approved_wfh(db, user.id, att.date)
    distance = validate_attendance_location(
        db,
        latitude,
        longitude,
        accuracy,
        allow_outside_office=approved_wfh,
    )
    # Auto-close any open break at checkout.
    for br in att.breaks:
        if br.end_time is None:
            br.end_time = now
    att.check_out = now
    att.checkout_latitude = latitude
    att.checkout_longitude = longitude
    att.checkout_accuracy_meters = accuracy
    att.checkout_distance_from_office_meters = distance
    recompute_attendance(att)
    audit(db, user.id, "check_out", "attendance",
          f"Checked out at {now:%H:%M}", client_info(request))
    db.commit()
    db.refresh(att)
    return attendance_out(att)


@router.post("/recheck-in")
def recheck_in(body: CheckInRequest, request: Request,
               user: User = Depends(attendance_user), db: Session = Depends(get_db)):
    """Undo a mistaken checkout for up to 60 seconds, keeping evidence in audit."""
    now = attendance_now()
    att = _active_record(db, user, now)
    if att is None or att.check_in is None or att.check_out is None:
        raise HTTPException(status_code=400, detail="There is no recent checkout to undo")
    elapsed = (now - att.check_out).total_seconds()
    if elapsed < 0 or elapsed > 60:
        raise HTTPException(status_code=400, detail="The one-minute recheck-in window has expired")

    approved_wfh = _has_approved_wfh(db, user.id, att.date)
    distance = validate_attendance_location(
        db, body.latitude, body.longitude, body.accuracy_meters,
        allow_outside_office=approved_wfh,
    )
    previous_checkout = att.check_out.isoformat()
    previous_location = (
        f"; previous checkout location={att.checkout_latitude},{att.checkout_longitude}"
        f" accuracy={att.checkout_accuracy_meters}m"
    )
    att.check_out = None
    att.checkout_latitude = None
    att.checkout_longitude = None
    att.checkout_accuracy_meters = None
    att.checkout_distance_from_office_meters = None
    att.status = "wfh" if approved_wfh else "present"
    recompute_attendance(att)
    audit(
        db, user.id, "undo_check_out", "attendance",
        f"Reopened attendance within one minute of checkout at {previous_checkout}"
        f"; recheck location={body.latitude},{body.longitude}; accuracy={body.accuracy_meters}m; "
        f"distance={distance}m{previous_location}",
        client_info(request),
    )
    db.commit()
    db.refresh(att)
    return attendance_out(att)


@router.post("/break/start")
def break_start(body: CheckOutRequest, request: Request,
                user: User = Depends(attendance_user), db: Session = Depends(get_db)):
    now = attendance_now()
    att = _active_record(db, user, now)
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
              user: User = Depends(attendance_user), db: Session = Depends(get_db)):
    now = attendance_now()
    att = _active_record(db, user, now)
    open_break = next((b for b in (att.breaks if att else []) if b.end_time is None), None)
    if open_break is None:
        raise HTTPException(status_code=400, detail="No break in progress")
    open_break.end_time = now
    recompute_attendance(att)
    audit(db, user.id, "break_end", "attendance", client=client_info(request))
    db.commit()
    db.refresh(att)
    return attendance_out(att)


def build_month_calendar(
    db: Session,
    target_user: User,
    year: int,
    month: int,
    *,
    include_location: bool = True,
    include_admin_audit: bool = False,
) -> dict:
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
    company_wfh = {w.date: w for w in db.query(CompanyWFHDay).filter(
        CompanyWFHDay.date >= first, CompanyWFHDay.date <= last).all()}

    leave_dates = {}
    for lv in leaves:
        d = max(lv.start_date, first)
        while d <= min(lv.end_date, last):
            leave_dates[d] = lv.leave_type
            d += timedelta(days=1)

    days, today_d, d = [], attendance_now().date(), first
    while d <= last:
        cell = {"date": d.isoformat(), "status": None, "detail": None}
        att = records.get(d)
        if att:
            cell.update(
                status=att.status,
                detail=attendance_out(
                    att,
                    include_location=include_location,
                    include_admin_audit=include_admin_audit,
                ),
            )
        elif d in holidays and holidays[d].holiday_type != "optional":
            cell.update(status="holiday", detail={"name": holidays[d].name})
        elif d in leave_dates:
            cell.update(status="leave", detail={"leave_type": leave_dates[d]})
        elif d in company_wfh:
            cell.update(status="wfh", detail={"company_wfh": True, "name": company_wfh[d].note})
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
