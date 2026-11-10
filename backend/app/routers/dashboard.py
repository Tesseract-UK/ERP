"""Role-aware dashboard: one endpoint returns everything the home page needs,
keeping the number of API calls minimal."""
from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..attendance_location import attendance_now, get_geofence_settings
from ..models import (
    Announcement, Attendance, CompanyWFHDay, EmployeeRequest, Holiday, LeaveRequest, RegularizationRequest,
    User, WFHRequest,
)
from ..serializers import announcement_out, attendance_out, holiday_out, user_brief
from .leaves import compute_balances

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _pending_counts(db: Session, user: User) -> dict:
    """The user's own open requests, plus what is waiting on their decision."""
    counts = {}
    awaiting_review = 0
    for key, model in [("leave", LeaveRequest), ("wfh", WFHRequest),
                       ("regularization", RegularizationRequest)]:
        counts[key] = db.query(func.count(model.id)).filter(
            model.status == "pending", model.user_id == user.id).scalar() or 0
        review = db.query(func.count(model.id)).join(User, model.user_id == User.id).filter(
            model.status == "pending", model.user_id != user.id)
        if user.role != "admin":
            review = review.filter(User.manager_id == user.id)
        awaiting_review += review.scalar() or 0
    counts["total"] = sum(counts.values())
    counts["awaiting_my_review"] = awaiting_review
    counts["employee_request"] = db.query(func.count(EmployeeRequest.id)).filter(
        EmployeeRequest.requester_id == user.id,
        EmployeeRequest.status.in_(["open", "in_progress"]),
    ).scalar() or 0
    counts["total"] += counts["employee_request"]
    return counts


def _team_snapshot(db: Session, member_ids: list[int]) -> dict:
    today = attendance_now().date()
    atts = db.query(Attendance).filter(Attendance.user_id.in_(member_ids),
                                       Attendance.date == today).all()
    on_leave = db.query(func.count(LeaveRequest.id)).filter(
        LeaveRequest.user_id.in_(member_ids), LeaveRequest.status == "approved",
        LeaveRequest.start_date <= today, LeaveRequest.end_date >= today).scalar() or 0
    wfh_today = db.query(func.count(WFHRequest.id)).filter(
        WFHRequest.user_id.in_(member_ids), WFHRequest.status == "approved",
        WFHRequest.date == today).scalar() or 0
    return {
        "total_members": len(member_ids),
        "present_today": sum(1 for a in atts if a.check_in),
        "late_today": sum(1 for a in atts if a.is_late),
        "on_leave_today": on_leave,
        "wfh_today": wfh_today,
    }


@router.get("")
def dashboard(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    today = attendance_now().date()
    in_30 = today + timedelta(days=30)

    holidays = db.query(Holiday).filter(Holiday.date >= today, Holiday.date <= in_30) \
        .order_by(Holiday.date).limit(5).all()
    announcements = db.query(Announcement) \
        .order_by(Announcement.created_at.desc()).limit(5).all()

    # Colleagues with birthdays in the next 14 days (month/day comparison).
    upcoming_bdays = []
    for u in db.query(User).filter(User.is_active.is_(True),
                                   User.date_of_birth.isnot(None)).all():
        try:
            bday = u.date_of_birth.replace(year=today.year)
        except ValueError:  # Feb 29
            bday = u.date_of_birth.replace(year=today.year, day=28)
        if bday < today:
            bday = bday.replace(year=today.year + 1)
        if (bday - today).days <= 14:
            upcoming_bdays.append({"name": u.full_name, "date": bday.isoformat()})
    upcoming_bdays.sort(key=lambda b: b["date"])

    att_today = db.query(Attendance).filter(Attendance.user_id == user.id,
                                            Attendance.date == today).first()
    payload = {
        "user": user_brief(user),
        "today_attendance": attendance_out(att_today) if att_today else None,
        "recheck_in_seconds": max(
            0,
            min(60, 60 - int((attendance_now() - att_today.check_out).total_seconds())),
        ) if att_today and att_today.check_out else 0,
        "location_policy": {
            "max_gps_accuracy_meters": get_geofence_settings(db)[
                "max_gps_accuracy_meters"
            ],
        },
        "balances": compute_balances(db, user.id),
        "pending_requests": _pending_counts(db, user),
        "upcoming_holidays": [holiday_out(h) for h in holidays],
        "upcoming_company_wfh": [
            {"id": d.id, "date": d.date.isoformat(), "note": d.note}
            for d in db.query(CompanyWFHDay).filter(CompanyWFHDay.date >= today,
                                                     CompanyWFHDay.date <= in_30)
            .order_by(CompanyWFHDay.date).limit(5).all()
        ],
        "birthdays": upcoming_bdays[:8],
        "announcements": [announcement_out(a) for a in announcements],
    }

    if user.role == "manager":
        member_ids = [u.id for u in db.query(User).filter(
            User.manager_id == user.id, User.is_active.is_(True)).all()]
        payload["team"] = _team_snapshot(db, member_ids)

    if user.role in ("hr", "admin"):
        all_ids = [u.id for u in db.query(User).filter(User.is_active.is_(True)).all()]
        payload["organization"] = _team_snapshot(db, all_ids)
        payload["recent_employees"] = [
            user_brief(u) for u in db.query(User).order_by(User.created_at.desc()).limit(5).all()]
        payload["pending_onboarding"] = [
            user_brief(u) for u in db.query(User).filter(
                User.is_active.is_(True), User.role != "admin", User.manager_id.is_(None)
            ).order_by(User.created_at.desc()).limit(20).all()]

    return payload
