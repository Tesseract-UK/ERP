"""Manager views: team attendance, team calendar."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import client_info, require_manager
from ..models import Attendance, User
from ..serializers import attendance_out, user_brief
from ..utils import audit
from .attendance import build_month_calendar

router = APIRouter(prefix="/team", tags=["team"])


def team_query(db: Session, user: User):
    """Direct reports for managers; active staff for HR; all staff for Admin."""
    q = db.query(User)
    if user.role != "admin":
        q = q.filter(User.is_active.is_(True))
    if user.role == "manager":
        q = q.filter(User.manager_id == user.id)
    return q


@router.get("/members")
def members(user: User = Depends(require_manager), db: Session = Depends(get_db)):
    return [user_brief(u) for u in team_query(db, user).order_by(User.full_name).all()]


@router.get("/attendance")
def team_attendance(
    user: User = Depends(require_manager), db: Session = Depends(get_db),
    employee_id: int | None = None, department_id: int | None = None,
    status: str | None = None,
    date_from: date | None = None, date_to: date | None = None,
    page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100),
):
    member_ids = [u.id for u in team_query(db, user).all()]
    q = db.query(Attendance).filter(Attendance.user_id.in_(member_ids))
    if employee_id:
        q = q.filter(Attendance.user_id == employee_id)
    if department_id:
        q = q.join(User, Attendance.user_id == User.id) \
             .filter(User.department_id == department_id)
    if status:
        q = q.filter(Attendance.status == status)
    if date_from:
        q = q.filter(Attendance.date >= date_from)
    if date_to:
        q = q.filter(Attendance.date <= date_to)
    total = q.count()
    rows = q.order_by(Attendance.date.desc()) \
        .offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size,
            "items": [attendance_out(
                a,
                include_user=True,
                include_admin_audit=user.role == "admin",
            ) for a in rows]}


@router.get("/calendar/{employee_id}")
def member_calendar(employee_id: int, year: int, month: int, request: Request,
                    user: User = Depends(require_manager), db: Session = Depends(get_db)):
    target = db.get(User, employee_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    if user.role == "manager" and target.manager_id != user.id:
        raise HTTPException(status_code=403, detail="Not a member of your team")
    if not (1 <= month <= 12):
        raise HTTPException(status_code=400, detail="Invalid month")
    if user.role == "admin":
        audit(db, user.id, "view_employee_attendance", "admin",
              f"Viewed attendance calendar for employee #{target.id} ({year}-{month:02d})",
              client_info(request))
        db.commit()
    return {"employee": user_brief(target),
            **build_month_calendar(
                db,
                target,
                year,
                month,
                include_location=user.role == "admin",
                include_admin_audit=user.role == "admin",
            )}
