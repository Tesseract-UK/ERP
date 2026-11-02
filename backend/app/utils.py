"""Shared helpers: audit logging, notifications, attendance math, file uploads."""
import os
import re
import json
import uuid
from datetime import date, datetime, timedelta

from fastapi import HTTPException, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session

from .config import (
    HALF_DAY_THRESHOLD_HOURS, LATE_ARRIVAL_TIME, MAX_UPLOAD_SIZE,
    STANDARD_WORK_HOURS, UPLOAD_DIR,
)
from .models import Attendance, AuditLog, Holiday, Notification, User

ALLOWED_UPLOAD_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".doc", ".docx"}


def check_email_domain(email: str) -> None:
    """Accept only an explicitly configured company email domain.

    A wildcard is deliberately not supported: this is an organization-only HRMS.
    Mailbox ownership is verified separately by the identity provider.
    """
    from .config import ALLOWED_EMAIL_DOMAINS

    normalized = email.strip().lower()
    local_part, separator, domain = normalized.rpartition("@")
    allowed_domains = {item for item in ALLOWED_EMAIL_DOMAINS if item and item != "*"}
    if not separator or not local_part or domain not in allowed_domains:
        allowed = ", ".join(f"@{d}" for d in sorted(allowed_domains)) or "the company domain"
        raise HTTPException(status_code=403,
                            detail=f"Only {allowed} accounts can be used")


def generate_employee_code(db: Session) -> str:
    count = db.query(func.count(User.id)).scalar() or 0
    return f"EMP{count + 1:04d}"


def audit(db: Session, user_id: int | None, action: str, module: str,
          details: str = "", client: dict | None = None) -> None:
    db.add(AuditLog(
        user_id=user_id, action=action, module=module, details=details[:2000],
        ip_address=(client or {}).get("ip"), user_agent=(client or {}).get("user_agent"),
    ))


def notify(
    db: Session,
    user_id: int,
    title: str,
    body: str = "",
    kind: str = "info",
    *,
    actor_id: int | None = None,
    entity_type: str | None = None,
    entity_id: int | None = None,
) -> None:
    db.add(Notification(
        user_id=user_id, title=title, body=body, kind=kind,
        actor_id=actor_id, entity_type=entity_type, entity_id=entity_id,
    ))


def notify_first_approvers(
    db: Session, requester: User, title: str, body: str, *,
    entity_type: str | None = None, entity_id: int | None = None,
) -> None:
    """Notify the first active reviewer in the configured approval chain."""
    manager = db.get(User, requester.manager_id) if requester.manager_id else None
    if manager is not None and manager.is_active and manager.role == "manager":
        notify(db, manager.id, title, body, "approval", actor_id=requester.id,
               entity_type=entity_type, entity_id=entity_id)
        return

    reviewers = db.query(User).filter(
        User.role == "hr", User.is_active.is_(True)
    ).all()
    if not reviewers:
        reviewers = db.query(User).filter(
            User.role == "admin", User.is_active.is_(True)
        ).all()
    for reviewer in reviewers:
        notify(db, reviewer.id, title, body, "approval", actor_id=requester.id,
               entity_type=entity_type, entity_id=entity_id)


def validate_mentions(db: Session, requester: User, raw_ids: str | None) -> tuple[list[int], list[User]]:
    """Validate the selected colleague IDs submitted by a mention control."""
    try:
        parsed = json.loads(raw_ids or "[]")
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Mention list is invalid")
    if not isinstance(parsed, list) or len(parsed) > 20 or any(
        isinstance(value, bool) or not isinstance(value, int) or value < 1
        for value in parsed
    ):
        raise HTTPException(status_code=400, detail="Mention list is invalid")
    ids = list(dict.fromkeys(parsed))
    if requester.id in ids:
        raise HTTPException(status_code=400, detail="You cannot mention yourself")
    people = db.query(User).filter(User.id.in_(ids), User.is_active.is_(True)).all() if ids else []
    if len(people) != len(ids):
        raise HTTPException(status_code=400, detail="One or more mentioned colleagues are unavailable")
    return ids, people


def notify_mentions(db: Session, requester: User, people: list[User], *,
                    entity_type: str, entity_id: int, message: str,
                    already_notified_ids: set[int] | None = None) -> None:
    """Notify tagged colleagues without duplicating their approval notification."""
    skip_ids = already_notified_ids or set()
    for person in people:
        if person.id in skip_ids:
            continue
        notify(db, person.id, "You were mentioned in a request", message,
               "mention", actor_id=requester.id,
               entity_type=entity_type, entity_id=entity_id)


def holiday_dates(db: Session, start: date, end: date) -> set[date]:
    rows = db.query(Holiday.date).filter(Holiday.date >= start, Holiday.date <= end,
                                         Holiday.holiday_type != "optional").all()
    return {r[0] for r in rows}


def working_days_between(db: Session, start: date, end: date) -> float:
    """Count days excluding weekends and non-optional holidays."""
    holidays = holiday_dates(db, start, end)
    days, d = 0, start
    while d <= end:
        if d.weekday() < 5 and d not in holidays:
            days += 1
        d += timedelta(days=1)
    return float(days)


def recompute_attendance(att: Attendance) -> None:
    """Recalculate work hours, break duration, overtime and status."""
    total_break_min = 0.0
    for br in att.breaks:
        if br.end_time:
            total_break_min += (br.end_time - br.start_time).total_seconds() / 60

    att.break_minutes = round(total_break_min, 1)

    if att.check_in and att.check_out:
        gross_hours = (att.check_out - att.check_in).total_seconds() / 3600
        att.work_hours = round(max(gross_hours - total_break_min / 60, 0), 2)
        att.overtime_hours = round(max(att.work_hours - STANDARD_WORK_HOURS, 0), 2)
        if att.status in ("present", "half_day"):
            att.status = "half_day" if att.work_hours < HALF_DAY_THRESHOLD_HOURS else "present"
    if att.check_in:
        late_h, late_m = (int(x) for x in LATE_ARRIVAL_TIME.split(":"))
        att.is_late = (att.check_in.hour, att.check_in.minute) > (late_h, late_m)
    if att.status_override in {"present", "absent"}:
        # The Admin correction is the reviewed final status. Recompute punch
        # durations, but do not replace that decision with an inferred status.
        att.status = att.status_override


def save_upload(file: UploadFile | None, subdir: str) -> str | None:
    """Persist an uploaded document; returns the stored relative path."""
    if file is None or not file.filename:
        return None
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"File type {ext} is not allowed")
    # Bound memory use before loading the full upload. Reading exactly one byte
    # beyond the limit is enough to reject an oversized file safely.
    content = file.file.read(MAX_UPLOAD_SIZE + 1)
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=400, detail="File exceeds the 5 MB size limit")
    safe_base = re.sub(r"[^A-Za-z0-9_.-]", "_", os.path.splitext(file.filename)[0])[:40]
    rel_path = os.path.join(subdir, f"{safe_base}_{uuid.uuid4().hex[:8]}{ext}")
    abs_path = os.path.join(UPLOAD_DIR, rel_path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    with open(abs_path, "wb") as f:
        f.write(content)
    return rel_path


def parse_dt(value: str | None) -> datetime | None:
    """Parse an ISO datetime string (from the frontend) into a naive datetime."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.replace(tzinfo=None)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid datetime: {value}")
