"""HR module: employee management, leave policies, holidays, reports."""
import csv
import io
import secrets
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import client_info, require_admin, require_hr
from ..attendance_location import attendance_now
from ..models import (
    Attendance, Department, Designation, EmployeeLeavePolicy,
    Holiday, LEAVE_TYPES, LeavePolicy, LeaveRequest, Location,
    RegularizationRequest, ROLES, Shift, User, WFHRequest,
)
from ..schemas import (
    AttendanceCorrectionRequest, EmployeeLeaveOverrideRequest, EmployeeRoleChangeRequest,
    EmployeeUpsertRequest, HolidayRequest,
    PolicyUpdateRequest, ResetPasswordRequest, SetManagerRequest,
)
from ..security import hash_password
from ..session_service import revoke_user_sessions
from ..serializers import (
    attendance_out, holiday_out, leave_out, regularization_out, user_brief,
    user_full, wfh_out,
)
from ..mailer import app_link
from ..utils import audit, check_email_domain, notify, notify_and_email, publish_announcement
from .leaves import compute_balances

router = APIRouter(prefix="/hr", tags=["hr"])


# ---------- employees ----------

MANAGER_ROLES = {"manager", "admin"}


def _validate_reporting_line(db: Session, role: str, manager_id: int | None,
                             employee_id: int | None = None) -> User | None:
    """Everyone except an Admin reports to an active Manager or Admin; Admins
    report to no one. Rejects self-assignment and reporting cycles."""
    if role == "admin":
        if manager_id is not None:
            raise HTTPException(status_code=400, detail="Admins do not report to a manager")
        return None
    if manager_id is None:
        raise HTTPException(status_code=400,
                            detail="Assign a reporting manager — everyone except an Admin must have one")
    if employee_id is not None and manager_id == employee_id:
        raise HTTPException(status_code=400, detail="An employee cannot be their own manager")
    manager = db.get(User, manager_id)
    if manager is None or not manager.is_active or manager.role not in MANAGER_ROLES:
        raise HTTPException(status_code=400,
                            detail="Choose an active Manager or Admin as reporting manager")
    if employee_id is not None:
        ancestor_id, seen = manager.manager_id, {manager.id}
        while ancestor_id is not None and ancestor_id not in seen:
            if ancestor_id == employee_id:
                raise HTTPException(status_code=400, detail="This assignment would create a reporting cycle")
            seen.add(ancestor_id)
            ancestor = db.get(User, ancestor_id)
            ancestor_id = ancestor.manager_id if ancestor else None
    return manager


def _active_report_count(db: Session, manager_id: int) -> int:
    return db.query(User.id).filter(User.manager_id == manager_id, User.is_active.is_(True)).count()


def _announce_manager_assigned(db: Session, emp: User, manager: User, was_pending: bool) -> None:
    title = "Your onboarding is complete" if was_pending else "Your reporting manager changed"
    notify_and_email(
        db, emp, title, f"{manager.full_name} is now your reporting manager. "
        "You can now apply for leave, WFH and regularization.", "info",
        actor_id=manager.id,
        email_subject=f"Tesseract HRMS — {title}",
        email_body=(f"Hi {emp.full_name},\n\n{manager.full_name} is now your reporting manager. "
                    f"You can now apply for leave, work from home and regularization:\n"
                    f"{app_link('/')}\n\n— Tesseract HRMS"),
    )
    notify(db, manager.id, "New direct report", f"{emp.full_name} now reports to you.",
           "info", actor_id=emp.id)


@router.get("/employees")
def list_employees(
    user: User = Depends(require_hr), db: Session = Depends(get_db),
    search: str | None = None, department_id: int | None = None,
    include_inactive: bool = False,
    manager_id: int | None = None,  # direct reports of this manager
    role: str | None = None,
    unassigned: bool = False,       # active employees with no manager set
    page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100),
):
    q = db.query(User)
    if role is not None:
        if role not in ROLES:
            raise HTTPException(status_code=400, detail="Invalid role filter")
        q = q.filter(User.role == role)
    if not include_inactive:
        q = q.filter(User.is_active.is_(True))
    if search:
        like = f"%{search}%"
        q = q.filter(or_(User.full_name.ilike(like), User.email.ilike(like),
                         User.employee_code.ilike(like)))
    if department_id:
        q = q.filter(User.department_id == department_id)
    if manager_id:
        q = q.filter(User.manager_id == manager_id)
    if unassigned:
        # Admins never have a manager, so they are never "unassigned".
        q = q.filter(User.manager_id.is_(None), User.role != "admin")
    total = q.count()
    rows = q.order_by(User.full_name).offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size,
            "items": [{**user_brief(u), "is_active": u.is_active,
                       "manager_name": u.manager.full_name if u.manager else None,
                       "onboarding_pending": u.role != "admin" and u.manager_id is None}
                      for u in rows]}


@router.get("/employees/{employee_id}")
def get_employee(employee_id: int, request: Request, user: User = Depends(require_hr),
                 db: Session = Depends(get_db)):
    emp = db.get(User, employee_id)
    if emp is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    if user.role == "admin":
        audit(db, user.id, "view_employee_record", "admin",
              f"Viewed sensitive employee record #{emp.id}", client_info(request))
        db.commit()
    return user_full(emp, include_sensitive=True)


@router.post("/employees/{employee_id}/set-manager")
def set_manager(employee_id: int, body: SetManagerRequest, request: Request,
                user: User = Depends(require_hr), db: Session = Depends(get_db)):
    """Assign or change a reporting manager — this is also the step that
    completes a new joiner's onboarding and unlocks their requests."""
    emp = db.get(User, employee_id)
    if emp is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    if emp.role in {"hr", "admin"} and user.role != "admin":
        raise HTTPException(status_code=403, detail="Only Admin can modify HR or Admin reporting lines")
    manager = _validate_reporting_line(db, emp.role, body.manager_id, emp.id)
    was_pending = emp.manager_id is None
    changed = emp.manager_id != body.manager_id
    emp.manager_id = body.manager_id
    if manager is not None:
        emp.profile_completed = True
        if changed:
            _announce_manager_assigned(db, emp, manager, was_pending)
    audit(db, user.id, "set_manager", "hr",
          f"{emp.full_name} (#{emp.id}) manager -> {body.manager_id or 'none'}",
          client_info(request))
    db.commit()
    db.refresh(emp)
    return {**user_brief(emp), "manager_name": emp.manager.full_name if emp.manager else None}


@router.get("/employees/{employee_id}/requests")
def employee_requests(employee_id: int, request: Request, user: User = Depends(require_hr),
                      db: Session = Depends(get_db)):
    """Combined leave/WFH/regularization history for one employee, most
    recent first — powers the employee detail page's requests panel."""
    if db.get(User, employee_id) is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    items = [leave_out(r) for r in db.query(LeaveRequest).filter(
                LeaveRequest.user_id == employee_id).all()]
    items += [wfh_out(r) for r in db.query(WFHRequest).filter(
                WFHRequest.user_id == employee_id).all()]
    items += [regularization_out(r) for r in db.query(RegularizationRequest).filter(
                RegularizationRequest.user_id == employee_id).all()]
    items.sort(key=lambda r: r["created_at"], reverse=True)
    if user.role == "admin":
        audit(db, user.id, "view_employee_hr_requests", "admin",
              f"Viewed HR request history for employee #{employee_id}", client_info(request))
        db.commit()
    return items


@router.put("/employees/{employee_id}/attendance/{attendance_date}/correction")
def correct_employee_attendance(
    employee_id: int,
    attendance_date: date,
    body: AttendanceCorrectionRequest,
    request: Request,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Record a reviewed attendance status correction without fabricating punches."""
    employee = db.get(User, employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found")

    # Only closed days may be corrected. This avoids changing a workday while
    # the employee may still be checking in, taking breaks, or checking out.
    if attendance_date >= attendance_now().date():
        raise HTTPException(status_code=400, detail="Attendance can be corrected only after the workday has ended")
    holiday = db.query(Holiday.id).filter(
        Holiday.date == attendance_date,
        Holiday.holiday_type != "optional",
    ).first()
    if holiday:
        raise HTTPException(status_code=409, detail="Company holiday attendance cannot be changed here")
    approved_leave = db.query(LeaveRequest.id).filter(
        LeaveRequest.user_id == employee_id,
        LeaveRequest.status == "approved",
        LeaveRequest.start_date <= attendance_date,
        LeaveRequest.end_date >= attendance_date,
    ).first()
    approved_wfh = db.query(WFHRequest.id).filter(
        WFHRequest.user_id == employee_id,
        WFHRequest.status == "approved",
        WFHRequest.date == attendance_date,
    ).first()
    if approved_leave or approved_wfh:
        raise HTTPException(status_code=409, detail="Approved leave or WFH controls this date; correct its request instead")

    attendance = db.query(Attendance).filter(
        Attendance.user_id == employee_id,
        Attendance.date == attendance_date,
    ).with_for_update().first()
    if attendance is None:
        attendance = Attendance(
            user_id=employee_id,
            date=attendance_date,
            status=body.status,
        )
        db.add(attendance)
    elif any(item.end_time is None for item in attendance.breaks):
        raise HTTPException(status_code=409, detail="An open break prevents this attendance correction")

    previous_status = attendance.status
    attendance.status = body.status
    attendance.status_override = body.status
    attendance.status_override_reason = body.reason
    attendance.status_override_by_id = user.id
    attendance.status_override_at = attendance_now()
    audit(
        db,
        user.id,
        "correct_employee_attendance",
        "admin",
        f"Employee #{employee.id} on {attendance_date}: {previous_status} -> {body.status}; reason: {body.reason}",
        client_info(request),
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Attendance changed at the same time; reload and try again") from exc
    db.refresh(attendance)
    return attendance_out(attendance, include_admin_audit=True)


@router.post("/employees")
def create_employee(body: EmployeeUpsertRequest, request: Request,
                    user: User = Depends(require_hr), db: Session = Depends(get_db)):
    allowed_roles = {"employee", "manager", "hr", "admin"} if user.role == "admin" else {"employee"}
    if body.role not in allowed_roles:
        raise HTTPException(status_code=403, detail="Only Admin can create Manager, HR, or Admin accounts; HR can create Employee accounts")
    check_email_domain(body.email)
    email = str(body.email).strip().lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="An account with this email already exists")
    if body.role == "admin" and not body.password:
        raise HTTPException(status_code=400, detail="An Admin password is required")
    if body.role != "admin" and body.password:
        raise HTTPException(status_code=400, detail="Only Admin accounts can have an application password")

    employee_code = body.employee_code.strip() if body.employee_code else None
    if employee_code and db.query(User.id).filter(User.employee_code == employee_code).first():
        raise HTTPException(status_code=409, detail="Employee code is already in use")
    _validate_reporting_line(db, body.role, body.manager_id)
    _validate_employee_references(db, body)

    emp = User(email=email, full_name=body.full_name.strip(),
               employee_code=employee_code or f"NEW{secrets.token_hex(8).upper()}",
               password_hash=hash_password(body.password) if body.role == "admin"
               else hash_password(secrets.token_urlsafe(48)),
               must_change_password=False, profile_completed=False)
    _apply_employee_fields(emp, body)
    db.add(emp)
    try:
        db.flush()
        if not employee_code:
            emp.employee_code = f"EMP{emp.id:06d}"
            if db.query(User.id).filter(User.employee_code == emp.employee_code, User.id != emp.id).first():
                emp.employee_code = f"EMP{emp.id:06d}-{secrets.token_hex(3).upper()}"
        audit(db, user.id, "create_employee", "hr",
              f"Created {emp.full_name} ({email}) role={emp.role}", client_info(request))
        db.commit()
        db.refresh(emp)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Employee email or code is already in use") from exc
    return user_full(emp, include_sensitive=True)


def _apply_employee_fields(emp: User, body: EmployeeUpsertRequest) -> None:
    for field in ("role", "phone", "department_id", "designation_id", "location_id",
                  "shift_id", "manager_id", "joining_date", "date_of_birth",
                  "pan_number", "aadhaar_number", "passport_number", "bank_account",
                  "ifsc_code", "emergency_contact_name", "emergency_contact_phone",
                  "address"):
        setattr(emp, field, getattr(body, field))


def _validate_employee_references(
    db: Session, body: EmployeeUpsertRequest, existing: User | None = None
) -> None:
    references = (
        (Department, body.department_id, existing.department_id if existing else None, "department"),
        (Designation, body.designation_id, existing.designation_id if existing else None, "designation"),
        (Location, body.location_id, existing.location_id if existing else None, "office location"),
        (Shift, body.shift_id, existing.shift_id if existing else None, "shift"),
    )
    for model, item_id, existing_id, label in references:
        if item_id is None:
            continue
        item = db.get(model, item_id)
        if item is None:
            raise HTTPException(status_code=400, detail=f"Selected {label} does not exist")
        if not item.is_active and item_id != existing_id:
            raise HTTPException(status_code=400, detail=f"Selected {label} is inactive")


@router.put("/employees/{employee_id}")
def update_employee(employee_id: int, body: EmployeeUpsertRequest, request: Request,
                    user: User = Depends(require_hr), db: Session = Depends(get_db)):
    emp = db.get(User, employee_id)
    if emp is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    if body.password is not None:
        raise HTTPException(
            status_code=400,
            detail="Password updates are available only through Admin password controls.",
        )
    if body.role != emp.role:
        raise HTTPException(status_code=400, detail="Change employee roles through the dedicated role-change action")
    if emp.role in {"hr", "admin"} and user.role != "admin":
        raise HTTPException(status_code=403, detail="Only Admin can edit HR or Admin accounts")
    check_email_domain(body.email)
    clash = db.query(User).filter(User.email == body.email.lower(),
                                  User.id != emp.id).first()
    if clash:
        raise HTTPException(status_code=400, detail="Another account uses this email")
    new_manager = _validate_reporting_line(db, emp.role, body.manager_id, emp.id)
    was_pending, manager_changed = emp.manager_id is None, emp.manager_id != body.manager_id
    _validate_employee_references(db, body, emp)
    employee_code = body.employee_code.strip() if body.employee_code else None
    if employee_code and db.query(User.id).filter(
        User.employee_code == employee_code, User.id != emp.id
    ).first():
        raise HTTPException(status_code=409, detail="Employee code is already in use")

    emp.email = str(body.email).strip().lower()
    emp.full_name = body.full_name.strip()
    if employee_code:
        emp.employee_code = employee_code
    _apply_employee_fields(emp, body)
    if new_manager is not None:
        emp.profile_completed = True
        if manager_changed:
            _announce_manager_assigned(db, emp, new_manager, was_pending)
    audit(db, user.id, "update_employee", "hr",
          f"Updated {emp.full_name} (#{emp.id})", client_info(request))
    try:
        db.commit()
        db.refresh(emp)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Employee email or code is already in use") from exc
    return user_full(emp, include_sensitive=True)


@router.post("/employees/{employee_id}/role")
def change_employee_role(employee_id: int, body: EmployeeRoleChangeRequest,
                         request: Request, user: User = Depends(require_hr),
                         db: Session = Depends(get_db)):
    """Apply the explicit Admin/HR role transition matrix and revoke sessions."""
    employee = db.get(User, employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    old_role, new_role = employee.role, body.role
    if user.role == "hr":
        if old_role != "employee" or new_role != "manager":
            raise HTTPException(status_code=403, detail="HR may promote an Employee to Manager only")
    elif user.role == "admin":
        if employee.id == user.id:
            raise HTTPException(status_code=403, detail="Ask another Admin to change your role")
        if old_role == "admin" and new_role != "admin":
            active_admins = db.query(User.id).filter(
                User.role == "admin", User.is_active.is_(True)
            ).count()
            if active_admins <= 1:
                raise HTTPException(status_code=409, detail="The last active Admin cannot be demoted")
    else:
        raise HTTPException(status_code=403, detail="Only HR or Admin can change roles")

    if old_role == new_role:
        return {"id": employee.id, "role": employee.role, "message": "Role is unchanged"}

    if old_role in MANAGER_ROLES and new_role not in MANAGER_ROLES and _active_report_count(db, employee.id):
        raise HTTPException(status_code=409, detail="Reassign this person’s active direct reports before changing the role")

    employee.role = new_role
    if new_role == "admin":
        # Admins sit outside the reporting tree.
        employee.manager_id = None
    # Someone demoted from Admin has no manager yet: their requests stay
    # locked (onboarding pending) until HR/Admin assigns one.
    revoke_user_sessions(db, employee.id)
    audit(db, user.id, "change_employee_role", "hr",
          f"{employee.full_name} (#{employee.id}): {old_role} -> {new_role}",
          client_info(request))
    db.commit()
    return {"id": employee.id, "role": new_role, "previous_role": old_role,
            "message": f"Role changed from {old_role} to {new_role}; active sessions revoked"}


@router.post("/employees/{employee_id}/deactivate")
def deactivate(employee_id: int, request: Request,
               user: User = Depends(require_hr), db: Session = Depends(get_db)):
    emp = db.get(User, employee_id)
    if emp is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    if emp.id == user.id:
        raise HTTPException(status_code=400, detail="You cannot deactivate your own account")
    if emp.role in {"hr", "admin"} and user.role != "admin":
        raise HTTPException(status_code=403, detail="Only Admin can deactivate HR or Admin accounts")
    if emp.role == "admin" and emp.is_active:
        active_admins = db.query(User.id).filter(
            User.role == "admin", User.is_active.is_(True)
        ).count()
        if active_admins <= 1:
            raise HTTPException(status_code=409, detail="The last active Admin cannot be deactivated")
    if _active_report_count(db, emp.id):
        raise HTTPException(status_code=409, detail="Reassign this person’s active direct reports before deactivation")
    emp.is_active = False
    revoke_user_sessions(db, emp.id)
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
    if emp.role in {"hr", "admin"} and user.role != "admin":
        raise HTTPException(status_code=403, detail="Only Admin can reactivate HR or Admin accounts")
    emp.is_active = True
    audit(db, user.id, "activate_employee", "hr", f"{emp.full_name} (#{emp.id})",
          client_info(request))
    db.commit()
    return {"message": f"{emp.full_name} has been reactivated"}


@router.post("/employees/{employee_id}/reset-password")
def reset_password(employee_id: int, body: ResetPasswordRequest, request: Request,
                   user: User = Depends(require_admin), db: Session = Depends(get_db)):
    emp = db.get(User, employee_id)
    if emp is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    if emp.role != "admin":
        raise HTTPException(status_code=403, detail="Passwords are available only for Admin accounts")
    if emp.id == user.id:
        raise HTTPException(status_code=400, detail="Use your Profile to update your own Admin password")
    emp.password_hash = hash_password(body.new_password)
    emp.must_change_password = False
    revoke_user_sessions(db, emp.id)
    audit(db, user.id, "reset_admin_password", "hr", f"For {emp.full_name} (#{emp.id})",
          client_info(request))
    db.commit()
    return {"message": "Password has been reset"}


# ---------- per-employee leave/WFH allocation overrides ----------

def _leave_override_payload(db: Session, employee_id: int) -> dict:
    company = {p.leave_type: p.annual_allocation for p in db.query(LeavePolicy).all()}
    overrides = {o.leave_type: o.annual_allocation for o in db.query(EmployeeLeavePolicy)
                 .filter(EmployeeLeavePolicy.user_id == employee_id).all()}
    types = list(LEAVE_TYPES) + ["wfh"]
    return {lt: {"company_default": company.get(lt, 0), "override": overrides.get(lt)} for lt in types}


@router.get("/employees/{employee_id}/leave-overrides")
def get_leave_overrides(employee_id: int, user: User = Depends(require_hr),
                        db: Session = Depends(get_db)):
    if db.get(User, employee_id) is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    return _leave_override_payload(db, employee_id)


@router.get("/employees/{employee_id}/balance")
def get_employee_balance(employee_id: int, user: User = Depends(require_hr),
                         db: Session = Depends(get_db)):
    """The employee's live computed leave/WFH balance — same numbers they
    see themselves, viewable by HR/Admin from the employee detail page."""
    if db.get(User, employee_id) is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    return compute_balances(db, employee_id)


@router.put("/employees/{employee_id}/leave-overrides")
def set_leave_overrides(employee_id: int, body: EmployeeLeaveOverrideRequest, request: Request,
                        user: User = Depends(require_hr), db: Session = Depends(get_db)):
    """Set (or clear, with a null value) this employee's personal leave/WFH
    allocation — otherwise they use the company-wide policy."""
    emp = db.get(User, employee_id)
    if emp is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    valid_types = set(LEAVE_TYPES) | {"wfh"}
    for leave_type, value in body.allocations.items():
        if leave_type not in valid_types:
            raise HTTPException(status_code=400, detail=f"Unknown leave type: {leave_type}")
        existing = db.query(EmployeeLeavePolicy).filter(
            EmployeeLeavePolicy.user_id == employee_id,
            EmployeeLeavePolicy.leave_type == leave_type).first()
        if value is None:
            if existing:
                db.delete(existing)
        else:
            if value < 0 or value > 365:
                raise HTTPException(status_code=400, detail="Allocation must be between 0 and 365")
            if existing:
                existing.annual_allocation = value
            else:
                db.add(EmployeeLeavePolicy(user_id=employee_id, leave_type=leave_type,
                                           annual_allocation=value))
    audit(db, user.id, "set_leave_overrides", "hr", f"For {emp.full_name} (#{emp.id})",
          client_info(request))
    db.commit()
    return _leave_override_payload(db, employee_id)


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
    if db.query(Holiday.id).filter(Holiday.date == body.date).first():
        raise HTTPException(status_code=409, detail="A holiday already exists on this date")
    h = Holiday(date=body.date, name=body.name, holiday_type=body.holiday_type)
    db.add(h)
    kind = "optional holiday" if body.holiday_type == "optional" else "holiday"
    publish_announcement(db, user, f"Holiday: {body.name}",
                         f"{body.date:%A, %d %B %Y} is a {kind}: {body.name}.")
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

def _csv_text(headers: list[str], rows: list[list]) -> str:
    def safe_cell(value):
        if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")):
            return "'" + value
        return value
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    writer.writerows([[safe_cell(value) for value in row] for row in rows])
    return buf.getvalue()


def _csv_response(headers: list[str], rows: list[list], filename: str) -> StreamingResponse:
    return StreamingResponse(iter([_csv_text(headers, rows)]), media_type="text/csv",
                             headers={"Content-Disposition": f"attachment; filename={filename}"})


@router.get("/reports/attendance")
def attendance_report(year: int = Query(..., ge=1900, le=2100),
                      month: int = Query(..., ge=1, le=12),
                      department_id: int | None = None,
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


@router.get("/reports/attendance-detail")
def attendance_detail_report(
    request: Request,
    date_from: date,
    date_to: date,
    employee_id: int | None = None,
    user: User = Depends(require_hr),
    db: Session = Depends(get_db),
):
    """Daily attendance detail plus per-employee totals, for one employee or all staff."""
    if date_from > date_to:
        raise HTTPException(status_code=400, detail="Start date must be on or before end date")
    if (date_to - date_from).days > 366:
        raise HTTPException(status_code=400, detail="Choose a date range of 367 days or less")

    employee_query = db.query(User)
    if employee_id is not None:
        employee_query = employee_query.filter(User.id == employee_id)
    else:
        employee_query = employee_query.filter(User.is_active.is_(True))
    employee_rows = employee_query.order_by(User.full_name).all()
    if employee_id is not None and not employee_rows:
        raise HTTPException(status_code=404, detail="Employee not found")

    # StreamingResponse iterates after this endpoint returns and FastAPI closes
    # the request-scoped DB session. Snapshot scalar values (including the
    # joined department name) now; never dereference ORM instances in the CSV
    # generator after the session has closed or the audit commit expires them.
    employees = [
        {
            "id": employee.id,
            "full_name": employee.full_name,
            "employee_code": employee.employee_code,
            "department_name": employee.department.name if employee.department else "",
        }
        for employee in employee_rows
    ]

    employee_ids = [employee["id"] for employee in employees]
    attendance_by_day = {}
    if employee_ids:
        attendance_rows = db.query(
            Attendance.user_id, Attendance.date, Attendance.status,
            Attendance.check_in, Attendance.check_out, Attendance.work_hours,
            Attendance.break_minutes, Attendance.overtime_hours, Attendance.is_late,
        ).filter(
            Attendance.user_id.in_(employee_ids),
            Attendance.date >= date_from, Attendance.date <= date_to,
        ).all()
        attendance_by_day = {(row.user_id, row.date): row for row in attendance_rows}

    holidays = {
        day: name for day, name in db.query(Holiday.date, Holiday.name).filter(
            Holiday.date >= date_from, Holiday.date <= date_to,
            Holiday.holiday_type != "optional",
        ).all()
    }
    leave_by_day = {}
    if employee_ids:
        approved_leaves = db.query(
            LeaveRequest.user_id, LeaveRequest.leave_type,
            LeaveRequest.start_date, LeaveRequest.end_date,
        ).filter(
            LeaveRequest.user_id.in_(employee_ids),
            LeaveRequest.status == "approved",
            LeaveRequest.start_date <= date_to,
            LeaveRequest.end_date >= date_from,
        ).all()
        for leave in approved_leaves:
            day = max(leave.start_date, date_from)
            end = min(leave.end_date, date_to)
            while day <= end:
                if day.weekday() < 5 and day not in holidays:
                    leave_by_day[(leave.user_id, day)] = leave.leave_type
                day += timedelta(days=1)

    wfh_days = set()
    if employee_ids:
        wfh_days = set(db.query(WFHRequest.user_id, WFHRequest.date).filter(
            WFHRequest.user_id.in_(employee_ids),
            WFHRequest.status == "approved",
            WFHRequest.date >= date_from, WFHRequest.date <= date_to,
        ).all())

    headers = [
        "row_type", "employee_name", "employee_code", "department", "date", "day",
        "attendance_status", "leave_type", "check_in", "check_out", "work_hours",
        "break_minutes", "overtime_hours", "late_arrival", "holiday",
        "worked_days", "present_days", "wfh_days", "half_days", "leave_days",
        "absent_workdays", "total_work_hours", "total_overtime_hours",
    ]

    def stream_csv():
        buffer = io.StringIO()
        writer = csv.writer(buffer)

        def emit(row):
            writer.writerow([
                "'" + value if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")) else value
                for value in row
            ])
            value = buffer.getvalue()
            buffer.seek(0)
            buffer.truncate(0)
            return value

        yield "\ufeff" + emit(headers)
        for employee in employees:
            totals = {"present": 0, "wfh": 0, "half": 0, "leave": 0, "absent": 0,
                      "hours": 0.0, "overtime": 0.0}
            day = date_from
            while day <= date_to:
                attendance = attendance_by_day.get((employee["id"], day))
                leave_type = leave_by_day.get((employee["id"], day))
                has_wfh = (employee["id"], day) in wfh_days
                is_weekday = day.weekday() < 5
                holiday_name = holidays.get(day, "")

                if attendance:
                    status = attendance.status
                elif leave_type:
                    status = "leave"
                elif has_wfh:
                    status = "wfh"
                elif holiday_name:
                    status = "holiday"
                elif not is_weekday:
                    status = "weekend"
                else:
                    status = "absent"

                if is_weekday and not holiday_name:
                    if status == "present":
                        totals["present"] += 1
                    if status == "wfh" or has_wfh:
                        totals["wfh"] += 1
                    if status == "half_day":
                        totals["half"] += 1
                    if leave_type:
                        totals["leave"] += 1
                    if status == "absent":
                        totals["absent"] += 1
                work_hours = float(attendance.work_hours or 0) if attendance else 0.0
                overtime = float(attendance.overtime_hours or 0) if attendance else 0.0
                totals["hours"] += work_hours
                totals["overtime"] += overtime
                yield emit([
                    "Daily", employee["full_name"], employee["employee_code"],
                    employee["department_name"],
                    day.isoformat(), day.strftime("%A"), status,
                    leave_type or "", attendance.check_in.strftime("%H:%M") if attendance and attendance.check_in else "",
                    attendance.check_out.strftime("%H:%M") if attendance and attendance.check_out else "",
                    round(work_hours, 2), round(float(attendance.break_minutes or 0), 1) if attendance else 0,
                    round(overtime, 2), bool(attendance.is_late) if attendance else False,
                    holiday_name, "", "", "", "", "", "", "", "",
                ])
                day += timedelta(days=1)

            # A half-day is half a worked day in the overall total while it
            # remains visible in its own summary column.
            worked = totals["present"] + totals["wfh"] + (totals["half"] * 0.5)
            yield emit([
                "Summary", employee["full_name"], employee["employee_code"],
                employee["department_name"],
                "", "", "", "", "", "", "", "", "", "", "",
                worked, totals["present"], totals["wfh"], totals["half"], totals["leave"],
                totals["absent"], round(totals["hours"], 2), round(totals["overtime"], 2),
            ])

    scope = f"employee_{employee_id}" if employee_id else "all_staff"
    filename = f"attendance_{scope}_{date_from.isoformat()}_{date_to.isoformat()}.csv"
    audit(db, user.id, "export_attendance_detail", "hr",
          f"Attendance detail {date_from} to {date_to}; employee={employee_id or 'all'}",
          client_info(request))
    db.commit()
    return StreamingResponse(
        stream_csv(), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/reports/leaves")
def leave_report(year: int = Query(..., ge=1900, le=2100),
                 format: str = "json", user: User = Depends(require_hr),
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
def late_report(year: int = Query(..., ge=1900, le=2100),
                month: int = Query(..., ge=1, le=12), format: str = "json",
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
