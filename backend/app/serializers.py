"""Compact dict serializers for API responses."""
from .models import (
    Attendance, Announcement, AuditLog, Holiday, LeaveRequest, Notification,
    RegularizationRequest, User, WFHRequest,
)


def user_brief(u: User | None) -> dict | None:
    if u is None:
        return None
    return {"id": u.id, "full_name": u.full_name, "employee_code": u.employee_code,
            "email": u.email, "role": u.role,
            "department": u.department.name if u.department else None,
            "designation": u.designation.title if u.designation else None}


def user_full(u: User, include_sensitive: bool = False) -> dict:
    data = {
        **user_brief(u),
        "phone": u.phone,
        "department_id": u.department_id,
        "designation_id": u.designation_id,
        "location_id": u.location_id,
        "shift_id": u.shift_id,
        "manager_id": u.manager_id,
        "manager_name": u.manager.full_name if u.manager else None,
        "joining_date": u.joining_date.isoformat() if u.joining_date else None,
        "date_of_birth": u.date_of_birth.isoformat() if u.date_of_birth else None,
        "emergency_contact_name": u.emergency_contact_name,
        "emergency_contact_phone": u.emergency_contact_phone,
        "address": u.address,
        "is_active": u.is_active,
    }
    if include_sensitive:
        data.update(pan_number=u.pan_number, aadhaar_number=u.aadhaar_number,
                    passport_number=u.passport_number, bank_account=u.bank_account,
                    ifsc_code=u.ifsc_code)
    else:
        # Masked view for the employee's own profile page.
        data.update(
            pan_number=_mask(u.pan_number), aadhaar_number=_mask(u.aadhaar_number),
            passport_number=_mask(u.passport_number), bank_account=_mask(u.bank_account),
            ifsc_code=u.ifsc_code)
    return data


def _mask(value: str | None) -> str | None:
    if not value:
        return None
    return "•" * max(len(value) - 4, 0) + value[-4:]


def attendance_out(a: Attendance, include_user: bool = False) -> dict:
    data = {
        "id": a.id, "date": a.date.isoformat(),
        "check_in": a.check_in.isoformat() if a.check_in else None,
        "check_out": a.check_out.isoformat() if a.check_out else None,
        "status": a.status, "work_hours": a.work_hours,
        "break_minutes": a.break_minutes, "overtime_hours": a.overtime_hours,
        "is_late": a.is_late, "notes": a.notes,
        "on_break": any(b.end_time is None for b in a.breaks),
        "breaks": [{"start": b.start_time.isoformat(),
                    "end": b.end_time.isoformat() if b.end_time else None} for b in a.breaks],
    }
    if include_user:
        data["user"] = user_brief(a.user)
    return data


def _request_common(r, include_user: bool) -> dict:
    data = {
        "id": r.id, "reason": r.reason, "status": r.status,
        "approver_comment": r.approver_comment,
        "approver_name": r.approver.full_name if r.approver else None,
        "created_at": r.created_at.isoformat(),
        "decided_at": r.decided_at.isoformat() if r.decided_at else None,
    }
    if include_user:
        data["user"] = user_brief(r.user)
    return data


def leave_out(r: LeaveRequest, include_user: bool = False) -> dict:
    return {**_request_common(r, include_user), "kind": "leave",
            "leave_type": r.leave_type, "start_date": r.start_date.isoformat(),
            "end_date": r.end_date.isoformat(), "days": r.days,
            "document_path": r.document_path}


def wfh_out(r: WFHRequest, include_user: bool = False) -> dict:
    return {**_request_common(r, include_user), "kind": "wfh",
            "date": r.date.isoformat(), "document_path": r.document_path}


def regularization_out(r: RegularizationRequest, include_user: bool = False) -> dict:
    return {**_request_common(r, include_user), "kind": "regularization",
            "date": r.date.isoformat(),
            "requested_check_in": r.requested_check_in.isoformat() if r.requested_check_in else None,
            "requested_check_out": r.requested_check_out.isoformat() if r.requested_check_out else None}


def holiday_out(h: Holiday) -> dict:
    return {"id": h.id, "date": h.date.isoformat(), "name": h.name,
            "holiday_type": h.holiday_type}


def announcement_out(a: Announcement) -> dict:
    return {"id": a.id, "title": a.title, "body": a.body,
            "created_by": a.created_by.full_name if a.created_by else None,
            "created_at": a.created_at.isoformat()}


def notification_out(n: Notification) -> dict:
    return {"id": n.id, "title": n.title, "body": n.body, "kind": n.kind,
            "is_read": n.is_read, "created_at": n.created_at.isoformat()}


def audit_out(l: AuditLog) -> dict:
    return {"id": l.id, "user": l.user.full_name if l.user else "System",
            "action": l.action, "module": l.module, "details": l.details,
            "ip_address": l.ip_address, "user_agent": l.user_agent,
            "created_at": l.created_at.isoformat()}
