"""Shared helpers: audit logging, notifications, request eligibility, attendance math."""
import json
from datetime import date, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from .config import HALF_DAY_THRESHOLD_HOURS, LATE_ARRIVAL_TIME, STANDARD_WORK_HOURS
from .mailer import queue_email
from .models import Announcement, Attendance, AuditLog, Holiday, Notification, User


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


def notify_and_email(
    db: Session, recipient: User, title: str, body: str, kind: str, *,
    email_subject: str, email_body: str, actor_id: int | None = None,
    entity_type: str | None = None, entity_id: int | None = None,
) -> None:
    """In-app notification plus an email that is sent after commit."""
    notify(db, recipient.id, title, body, kind, actor_id=actor_id,
           entity_type=entity_type, entity_id=entity_id)
    queue_email(db, recipient.email, email_subject, email_body)


def publish_announcement(db: Session, author: User, title: str, body: str) -> Announcement:
    """Create an announcement and notify every other active user in-app."""
    ann = Announcement(title=title, body=body, created_by_id=author.id)
    db.add(ann)
    db.flush()
    for (user_id,) in db.query(User.id).filter(User.is_active.is_(True), User.id != author.id).all():
        notify(db, user_id, f"📢 {title}", body[:300], "announcement",
               actor_id=author.id, entity_type="announcement", entity_id=ann.id)
    return ann


NO_MANAGER_MESSAGE = (
    "You haven't been assigned a manager yet. The HR team has been asked to "
    "complete your joining formalities; you can submit requests once a "
    "manager is assigned."
)


def is_onboarding_pending(user: User) -> bool:
    """Everyone except an Admin must report to a manager before they can
    request leave, WFH or regularization. Admins never report to anyone."""
    return user.role != "admin" and user.manager_id is None


def require_request_eligibility(user: User) -> None:
    """Gate every leave/WFH/regularization submission."""
    if user.role == "admin":
        raise HTTPException(status_code=403,
                            detail="Administrators do not submit leave, WFH or regularization requests")
    if user.manager_id is None:
        raise HTTPException(status_code=403, detail=NO_MANAGER_MESSAGE)


def parse_mention_ids(raw_ids: str | list | None) -> list[int]:
    """Accept a JSON string (multipart forms) or a list (JSON bodies)."""
    if isinstance(raw_ids, list):
        parsed = raw_ids
    else:
        try:
            parsed = json.loads(raw_ids or "[]")
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="Mention list is invalid")
    if not isinstance(parsed, list) or len(parsed) > 20 or any(
        isinstance(value, bool) or not isinstance(value, int) or value < 1
        for value in parsed
    ):
        raise HTTPException(status_code=400, detail="Mention list is invalid")
    return list(dict.fromkeys(parsed))


def validate_mentions(db: Session, author: User, raw_ids: str | list | None) -> tuple[list[int], list[User]]:
    """Validate tagged colleague IDs: any active colleague except the author."""
    ids = parse_mention_ids(raw_ids)
    if author.id in ids:
        raise HTTPException(status_code=400, detail="You cannot mention yourself")
    people = db.query(User).filter(User.id.in_(ids), User.is_active.is_(True)).all() if ids else []
    if len(people) != len(ids):
        raise HTTPException(status_code=400, detail="One or more mentioned colleagues are unavailable")
    by_id = {person.id: person for person in people}
    return ids, [by_id[i] for i in ids]


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


def parse_dt(value: str | None) -> datetime | None:
    """Parse an ISO datetime string (from the frontend) into a naive datetime."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.replace(tzinfo=None)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid datetime: {value}")
