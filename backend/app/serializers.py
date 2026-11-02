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
        "must_change_password": u.must_change_password,
        "profile_completed": u.profile_completed,
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


def attendance_out(
    a: Attendance,
    include_user: bool = False,
    include_location: bool | None = None,
    include_admin_audit: bool = False,
) -> dict:
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
    # Exact GPS data is returned only in the employee's own attendance view.
    # Team summaries do not disclose a person's precise location to colleagues.
    if include_location is None:
        include_location = not include_user
    if include_location:
        data.update(
            latitude=a.latitude,
            longitude=a.longitude,
            location_accuracy_meters=a.location_accuracy_meters,
            distance_from_office_meters=a.distance_from_office_meters,
            checkout_latitude=a.checkout_latitude,
            checkout_longitude=a.checkout_longitude,
            checkout_accuracy_meters=a.checkout_accuracy_meters,
            checkout_distance_from_office_meters=a.checkout_distance_from_office_meters,
        )
    if include_user:
        data["user"] = user_brief(a.user)
    if include_admin_audit:
        data.update(
            status_override=a.status_override,
            status_override_reason=a.status_override_reason,
            status_override_by=(a.status_override_by.full_name if a.status_override_by else None),
            status_override_at=(a.status_override_at.isoformat() if a.status_override_at else None),
        )
    return data


def _request_common(r, include_user: bool) -> dict:
    import json
    try:
        mentioned_user_ids = json.loads(getattr(r, "mentions_json", "[]") or "[]")
    except (TypeError, ValueError):
        mentioned_user_ids = []
    data = {
        "id": r.id, "reason": r.reason, "status": r.status,
        "approver_comment": r.approver_comment,
        "approval_stage": getattr(r, "approval_stage", "pending_manager"),
        "manager_decided_at": r.manager_decided_at.isoformat() if getattr(r, "manager_decided_at", None) else None,
        "manager_comment": getattr(r, "manager_comment", None),
        "manager_approver_name": (
            r.manager_decided_by.full_name if getattr(r, "manager_decided_by", None)
            else r.user.manager.full_name if (
                getattr(r, "manager_decided_at", None) and r.user.manager
            ) else None
        ),
        "hr_decided_at": r.hr_decided_at.isoformat() if getattr(r, "hr_decided_at", None) else None,
        "hr_comment": getattr(r, "hr_comment", None),
        "approver_name": r.approver.full_name if r.approver else None,
        "created_at": r.created_at.isoformat(),
        "decided_at": r.decided_at.isoformat() if r.decided_at else None,
        "mentioned_user_ids": mentioned_user_ids,
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
    import json
    try:
        mentioned_user_ids = json.loads(r.mentions_json or "[]")
    except (TypeError, ValueError):
        mentioned_user_ids = []
    return {**_request_common(r, include_user), "kind": "regularization",
            "date": r.date.isoformat(),
            "requested_check_in": r.requested_check_in.isoformat() if r.requested_check_in else None,
            "requested_check_out": r.requested_check_out.isoformat() if r.requested_check_out else None,
            "mentioned_user_ids": mentioned_user_ids}


def holiday_out(h: Holiday) -> dict:
    return {"id": h.id, "date": h.date.isoformat(), "name": h.name,
            "holiday_type": h.holiday_type}


def announcement_out(a: Announcement) -> dict:
    return {"id": a.id, "title": a.title, "body": a.body,
            "created_by": a.created_by.full_name if a.created_by else None,
            "created_at": a.created_at.isoformat()}


def notification_out(n: Notification) -> dict:
    return {"id": n.id, "title": n.title, "body": n.body, "kind": n.kind,
            "is_read": n.is_read, "created_at": n.created_at.isoformat(),
            "actor_id": n.actor_id,
            "actor_name": n.actor.full_name if n.actor else None,
            "entity_type": n.entity_type, "entity_id": n.entity_id}


def audit_out(l: AuditLog) -> dict:
    return {"id": l.id, "user": l.user.full_name if l.user else "System",
            "action": l.action, "module": l.module, "details": l.details,
            "ip_address": l.ip_address, "user_agent": l.user_agent,
            "created_at": l.created_at.isoformat()}
