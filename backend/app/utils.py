"""Shared helpers: audit logging, notifications, attendance math, file uploads."""
import os
import re
import uuid
from datetime import date, datetime, timedelta

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from .config import (
    HALF_DAY_THRESHOLD_HOURS, LATE_ARRIVAL_TIME, MAX_UPLOAD_SIZE,
    STANDARD_WORK_HOURS, UPLOAD_DIR,
)
from .models import Attendance, AuditLog, Holiday, Notification

ALLOWED_UPLOAD_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".doc", ".docx"}


def audit(db: Session, user_id: int | None, action: str, module: str,
          details: str = "", client: dict | None = None) -> None:
    db.add(AuditLog(
        user_id=user_id, action=action, module=module, details=details[:2000],
        ip_address=(client or {}).get("ip"), user_agent=(client or {}).get("user_agent"),
    ))


def notify(db: Session, user_id: int, title: str, body: str = "", kind: str = "info") -> None:
    db.add(Notification(user_id=user_id, title=title, body=body, kind=kind))


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


def save_upload(file: UploadFile | None, subdir: str) -> str | None:
    """Persist an uploaded document; returns the stored relative path."""
    if file is None or not file.filename:
        return None
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"File type {ext} is not allowed")
    content = file.file.read()
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
