"""HR module: employee management, leave policies, holidays, reports."""
import csv
import io
from datetime import date, datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import client_info, require_hr
from ..models import (
    Attendance, EmployeeDocument, Holiday, LeavePolicy, LeaveRequest, User,
)
from ..schemas import (
    EmployeeUpsertRequest, HolidayRequest, PolicyUpdateRequest, ResetPasswordRequest,
)
from ..security import hash_password
from ..serializers import holiday_out, user_brief, user_full
from ..utils import audit, check_email_domain, notify, save_upload

router = APIRouter(prefix="/hr", tags=["hr"])


# ---------- employees ----------

@router.get("/employees")
def list_employees(
    user: User = Depends(require_hr), db: Session = Depends(get_db),
    search: str | None = None, department_id: int | None = None,
    include_inactive: bool = False,
    page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100),
):
    q = db.query(User)
    if not include_inactive:
        q = q.filter(User.is_active.is_(True))
    if search:
        like = f"%{search}%"
        q = q.filter(or_(User.full_name.ilike(like), User.email.ilike(like),
                         User.employee_code.ilike(like)))
    if department_id:
        q = q.filter(User.department_id == department_id)
    total = q.count()
    rows = q.order_by(User.full_name).offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size,
            "items": [{**user_brief(u), "is_active": u.is_active,
                       "manager_name": u.manager.full_name if u.manager else None}
                      for u in rows]}


@router.get("/employees/{employee_id}")
def get_employee(employee_id: int, user: User = Depends(require_hr),
                 db: Session = Depends(get_db)):
    emp = db.get(User, employee_id)
    if emp is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    return user_full(emp, include_sensitive=True)


def _next_employee_code(db: Session) -> str:
    count = db.query(func.count(User.id)).scalar() or 0
    return f"EMP{count + 1:04d}"


@router.post("/employees")
def create_employee(body: EmployeeUpsertRequest, request: Request,
                    user: User = Depends(require_hr), db: Session = Depends(get_db)):
    if body.role == "admin" and user.role != "admin":
        raise HTTPException(status_code=403, detail="Only an admin can create admin users")
    check_email_domain(body.email)
    if db.query(User).filter(User.email == body.email.lower()).first():
        raise HTTPException(status_code=400, detail="An account with this email already exists")
    if not body.password:
        raise HTTPException(status_code=400, detail="Password is required for new employees")

    emp = User(email=body.email.lower(), full_name=body.full_name,
               employee_code=body.employee_code or _next_employee_code(db),
               password_hash=hash_password(body.password),
               # New joiners must change the temp password and complete
               # the onboarding form on first login.
               must_change_password=True, profile_completed=False)
    _apply_employee_fields(emp, body)
    db.add(emp)
    audit(db, user.id, "create_employee", "hr",
          f"Created {body.full_name} ({body.email})", client_info(request))
    db.commit()
    db.refresh(emp)
    return user_full(emp, include_sensitive=True)


def _apply_employee_fields(emp: User, body: EmployeeUpsertRequest) -> None:
    for field in ("role", "phone", "department_id", "designation_id", "location_id",
                  "shift_id", "manager_id", "joining_date", "date_of_birth",
                  "pan_number", "aadhaar_number", "passport_number", "bank_account",
                  "ifsc_code", "emergency_contact_name", "emergency_contact_phone",
                  "address"):
        setattr(emp, field, getattr(body, field))


@router.put("/employees/{employee_id}")
def update_employee(employee_id: int, body: EmployeeUpsertRequest, request: Request,
                    user: User = Depends(require_hr), db: Session = Depends(get_db)):
    emp = db.get(User, employee_id)
    if emp is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    if (body.role == "admin" or emp.role == "admin") and user.role != "admin":
        raise HTTPException(status_code=403, detail="Only an admin can modify admin users")
    if body.manager_id == emp.id:
        raise HTTPException(status_code=400, detail="An employee cannot be their own manager")
    check_email_domain(body.email)
    clash = db.query(User).filter(User.email == body.email.lower(),
                                  User.id != emp.id).first()
    if clash:
        raise HTTPException(status_code=400, detail="Another account uses this email")

    emp.email = body.email.lower()
    emp.full_name = body.full_name
    if body.employee_code:
        emp.employee_code = body.employee_code
    _apply_employee_fields(emp, body)
    audit(db, user.id, "update_employee", "hr",
          f"Updated {emp.full_name} (#{emp.id})", client_info(request))
    db.commit()
    db.refresh(emp)
    return user_full(emp, include_sensitive=True)


@router.post("/employees/{employee_id}/deactivate")
def deactivate(employee_id: int, request: Request,
               user: User = Depends(require_hr), db: Session = Depends(get_db)):
    emp = db.get(User, employee_id)
    if emp is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    if emp.id == user.id:
        raise HTTPException(status_code=400, detail="You cannot deactivate your own account")
    if emp.role == "admin" and user.role != "admin":
        raise HTTPException(status_code=403, detail="Only an admin can deactivate admin users")
    emp.is_active = False
    audit(db, user.id, "deactivate_employee", "hr", f"{emp.full_name} (#{emp.id})",
          client_info(request))
    db.commit()
    return {"message": f"{emp.full_name} has been deactivated"}


@router.post("/employees/{employee_id}/activate")
def activate(employee_id: int, request: Request,
             user: User = Depends(require_hr), db: Session = Depends(get_db)):
    emp = db.get(User, employee_id)
    if emp is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    emp.is_active = True
    audit(db, user.id, "activate_employee", "hr", f"{emp.full_name} (#{emp.id})",
          client_info(request))
    db.commit()
    return {"message": f"{emp.full_name} has been reactivated"}


@router.post("/employees/{employee_id}/reset-password")
def reset_password(employee_id: int, body: ResetPasswordRequest, request: Request,
                   user: User = Depends(require_hr), db: Session = Depends(get_db)):
    emp = db.get(User, employee_id)
    if emp is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    if emp.role == "admin" and user.role != "admin":
        raise HTTPException(status_code=403, detail="Only an admin can reset an admin password")
    emp.password_hash = hash_password(body.new_password)
    emp.must_change_password = True  # force a fresh password on next login
    notify(db, emp.id, "Password reset", "Your password was reset by HR.", "info")
    audit(db, user.id, "reset_password", "hr", f"For {emp.full_name} (#{emp.id})",
          client_info(request))
    db.commit()
    return {"message": "Password has been reset"}


# ---------- employee documents ----------

@router.get("/employees/{employee_id}/documents")
def list_documents(employee_id: int, user: User = Depends(require_hr),
                   db: Session = Depends(get_db)):
    docs = db.query(EmployeeDocument).filter(
        EmployeeDocument.user_id == employee_id) \
        .order_by(EmployeeDocument.created_at.desc()).all()
    return [{"id": d.id, "name": d.name, "file_path": d.file_path,
             "created_at": d.created_at.isoformat()} for d in docs]


@router.post("/employees/{employee_id}/documents")
def upload_document(employee_id: int, request: Request, name: str = Form(...),
                    file: UploadFile = File(...),
                    user: User = Depends(require_hr), db: Session = Depends(get_db)):
    if db.get(User, employee_id) is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    path = save_upload(file, "employee_docs")
    doc = EmployeeDocument(user_id=employee_id, name=name, file_path=path,
                           uploaded_by_id=user.id)
    db.add(doc)
    audit(db, user.id, "upload_document", "hr",
          f"'{name}' for employee #{employee_id}", client_info(request))
    db.commit()
    return {"id": doc.id, "name": doc.name, "file_path": doc.file_path}


# ---------- leave policies ----------

@router.get("/policies")
def get_policies(user: User = Depends(require_hr), db: Session = Depends(get_db)):
    return {p.leave_type: p.annual_allocation for p in db.query(LeavePolicy).all()}


@router.put("/policies")
def update_policies(body: PolicyUpdateRequest, request: Request,
                    user: User = Depends(require_hr), db: Session = Depends(get_db)):
    for leave_type, allocation in body.allocations.items():
        if allocation < 0 or allocation > 365:
            raise HTTPException(status_code=400, detail="Allocation must be between 0 and 365")
        policy = db.query(LeavePolicy).filter(LeavePolicy.leave_type == leave_type).first()
        if policy:
            policy.annual_allocation = allocation
        else:
            db.add(LeavePolicy(leave_type=leave_type, annual_allocation=allocation))
    audit(db, user.id, "update_policies", "hr", str(body.allocations), client_info(request))
    db.commit()
    return {p.leave_type: p.annual_allocation for p in db.query(LeavePolicy).all()}


# ---------- holidays ----------

@router.get("/holidays")
def list_holidays(year: int | None = None, user: User = Depends(require_hr),
                  db: Session = Depends(get_db)):
    q = db.query(Holiday)
    if year:
        q = q.filter(Holiday.date >= date(year, 1, 1), Holiday.date <= date(year, 12, 31))
    return [holiday_out(h) for h in q.order_by(Holiday.date).all()]


@router.post("/holidays")
def add_holiday(body: HolidayRequest, request: Request,
                user: User = Depends(require_hr), db: Session = Depends(get_db)):
    h = Holiday(date=body.date, name=body.name, holiday_type=body.holiday_type)
    db.add(h)
    audit(db, user.id, "add_holiday", "hr", f"{body.name} on {body.date}",
          client_info(request))
    db.commit()
    return holiday_out(h)


@router.delete("/holidays/{holiday_id}")
def delete_holiday(holiday_id: int, request: Request,
                   user: User = Depends(require_hr), db: Session = Depends(get_db)):
    h = db.get(Holiday, holiday_id)
    if h is None:
        raise HTTPException(status_code=404, detail="Holiday not found")
    db.delete(h)
    audit(db, user.id, "delete_holiday", "hr", f"{h.name} on {h.date}",
          client_info(request))
    db.commit()
    return {"message": "Holiday removed"}


# ---------- reports ----------

def _csv_response(headers: list[str], rows: list[list], filename: str) -> StreamingResponse:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    writer.writerows(rows)
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f"attachment; filename={filename}"})


@router.get("/reports/attendance")
def attendance_report(year: int, month: int, department_id: int | None = None,
                      format: str = "json", user: User = Depends(require_hr),
                      db: Session = Depends(get_db)):
    import calendar as pycal
    first = date(year, month, 1)
    last = date(year, month, pycal.monthrange(year, month)[1])
    emp_q = db.query(User).filter(User.is_active.is_(True))
    if department_id:
        emp_q = emp_q.filter(User.department_id == department_id)
    employees = emp_q.all()

    atts = db.query(Attendance).filter(Attendance.date >= first,
                                       Attendance.date <= last).all()
    by_user: dict[int, list[Attendance]] = {}
    for a in atts:
        by_user.setdefault(a.user_id, []).append(a)

    rows = []
    for emp in employees:
        recs = by_user.get(emp.id, [])
        rows.append({
            "employee": emp.full_name, "employee_code": emp.employee_code,
            "department": emp.department.name if emp.department else "",
            "days_present": sum(1 for a in recs if a.status == "present"),
            "half_days": sum(1 for a in recs if a.status == "half_day"),
            "late_arrivals": sum(1 for a in recs if a.is_late),
            "total_hours": round(sum(a.work_hours for a in recs), 1),
            "overtime_hours": round(sum(a.overtime_hours for a in recs), 1),
        })

    if format == "csv":
        headers = list(rows[0].keys()) if rows else ["employee"]
        return _csv_response(headers, [list(r.values()) for r in rows],
                             f"attendance_{year}_{month:02d}.csv")
    return rows


@router.get("/reports/leaves")
def leave_report(year: int, format: str = "json", user: User = Depends(require_hr),
                 db: Session = Depends(get_db)):
    reqs = db.query(LeaveRequest).filter(
        LeaveRequest.start_date >= date(year, 1, 1),
        LeaveRequest.start_date <= date(year, 12, 31)).all()
    summary: dict[int, dict] = {}
    for r in reqs:
        s = summary.setdefault(r.user_id, {
            "employee": r.user.full_name, "employee_code": r.user.employee_code,
            "approved_days": 0.0, "rejected": 0, "pending": 0})
        if r.status == "approved":
            s["approved_days"] += r.days
        elif r.status == "rejected":
            s["rejected"] += 1
        elif r.status == "pending":
            s["pending"] += 1
    rows = sorted(summary.values(), key=lambda r: r["employee"])
    if format == "csv":
        headers = ["employee", "employee_code", "approved_days", "rejected", "pending"]
        return _csv_response(headers, [[r[h] for h in headers] for r in rows],
                             f"leaves_{year}.csv")
    return rows


@router.get("/reports/late-arrivals")
def late_report(year: int, month: int, format: str = "json",
                user: User = Depends(require_hr), db: Session = Depends(get_db)):
    import calendar as pycal
    first = date(year, month, 1)
    last = date(year, month, pycal.monthrange(year, month)[1])
    rows = [{"employee": a.user.full_name, "date": a.date.isoformat(),
             "check_in": a.check_in.strftime("%H:%M") if a.check_in else ""}
            for a in db.query(Attendance).filter(
                Attendance.date >= first, Attendance.date <= last,
                Attendance.is_late.is_(True)).order_by(Attendance.date).all()]
    if format == "csv":
        return _csv_response(["employee", "date", "check_in"],
                             [list(r.values()) for r in rows],
                             f"late_arrivals_{year}_{month:02d}.csv")
    return rows
