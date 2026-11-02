
"""Database models for the HRMS.

Leave and WFH balances are computed (policy allocation minus approved usage)
rather than stored, which avoids balance-sync bugs.
"""
from datetime import datetime, date

from sqlalchemy import (
    Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base

# ---- enums kept as plain strings for cross-database portability ----
ROLES = ("employee", "manager", "hr", "admin")
ATTENDANCE_STATUSES = ("present", "absent", "leave", "wfh", "holiday", "half_day")
REQUEST_STATUSES = ("pending", "approved", "rejected", "cancelled")
LEAVE_TYPES = (
    "casual", "sick", "earned", "unpaid", "maternity", "paternity", "optional_holiday",
)
HOLIDAY_TYPES = ("national", "state", "company", "optional")


class Department(Base):
    __tablename__ = "departments"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Designation(Base):
    __tablename__ = "designations"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(100), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Location(Base):
    __tablename__ = "locations"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    address: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Shift(Base):
    __tablename__ = "shifts"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    start_time: Mapped[str] = mapped_column(String(5), default="09:00")  # HH:MM
    end_time: Mapped[str] = mapped_column(String(5), default="18:00")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_code: Mapped[str] = mapped_column(String(20), unique=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))

    # Legacy Clerk identity; retained temporarily during migration.
    clerk_user_id: Mapped[str | None] = mapped_column(
        String(64), unique=True, index=True
    )

    # Stable Google identity used by Google OAuth.
    google_sub: Mapped[str | None] = mapped_column(
        String(255), unique=True, index=True
    )

    full_name: Mapped[str] = mapped_column(String(150))
    role: Mapped[str] = mapped_column(String(20), default="employee")
    phone: Mapped[str | None] = mapped_column(String(20))
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"))
    designation_id: Mapped[int | None] = mapped_column(ForeignKey("designations.id"))
    location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"))
    shift_id: Mapped[int | None] = mapped_column(ForeignKey("shifts.id"))
    manager_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    joining_date: Mapped[date | None] = mapped_column(Date)
    date_of_birth: Mapped[date | None] = mapped_column(Date)

    # Sensitive fields — editable by HR/Admin only.
    pan_number: Mapped[str | None] = mapped_column(String(20))
    aadhaar_number: Mapped[str | None] = mapped_column(String(20))
    passport_number: Mapped[str | None] = mapped_column(String(30))
    bank_account: Mapped[str | None] = mapped_column(String(30))
    ifsc_code: Mapped[str | None] = mapped_column(String(15))

    # Employee-editable fields.
    emergency_contact_name: Mapped[str | None] = mapped_column(String(150))
    emergency_contact_phone: Mapped[str | None] = mapped_column(String(20))
    address: Mapped[str | None] = mapped_column(Text)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # First-login onboarding: force a password change, then a one-time
    # personal-details submission before the app unlocks.
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    profile_completed: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    department = relationship("Department", lazy="joined")
    designation = relationship("Designation", lazy="joined")
    manager = relationship("User", remote_side=[id], lazy="joined", join_depth=1)


class AuthSession(Base):
    """Server-tracked login session, allowing immediate revocation."""
    __tablename__ = "auth_sessions"

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AuthRefreshToken(Base):
    """Hash-only, single-use refresh credentials for rotating sessions."""
    __tablename__ = "auth_refresh_tokens"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("auth_sessions.session_id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime)


class Attendance(Base):
    __tablename__ = "attendance"
    __table_args__ = (
        UniqueConstraint("user_id", "date", name="uq_attendance_user_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    check_in: Mapped[datetime | None] = mapped_column(DateTime)
    check_out: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(20), default="present")
    work_hours: Mapped[float] = mapped_column(Float, default=0)
    break_minutes: Mapped[float] = mapped_column(Float, default=0)
    overtime_hours: Mapped[float] = mapped_column(Float, default=0)
    is_late: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text)
    # Admin corrections are stored separately from punch data so later work-hour
    # recomputation cannot silently undo the reviewed attendance status.
    status_override: Mapped[str | None] = mapped_column(String(20))
    status_override_reason: Mapped[str | None] = mapped_column(Text)
    status_override_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    status_override_at: Mapped[datetime | None] = mapped_column(DateTime)

    # Device/location capture at check-in for fraud reduction.
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    location_accuracy_meters: Mapped[float | None] = mapped_column(Float)
    distance_from_office_meters: Mapped[float | None] = mapped_column(Float)
    checkout_latitude: Mapped[float | None] = mapped_column(Float)
    checkout_longitude: Mapped[float | None] = mapped_column(Float)
    checkout_accuracy_meters: Mapped[float | None] = mapped_column(Float)
    checkout_distance_from_office_meters: Mapped[float | None] = mapped_column(Float)
    ip_address: Mapped[str | None] = mapped_column(String(45))
    browser: Mapped[str | None] = mapped_column(String(100))
    os: Mapped[str | None] = mapped_column(String(100))
    device: Mapped[str | None] = mapped_column(String(100))

    user = relationship("User", foreign_keys=[user_id], lazy="joined")
    status_override_by = relationship("User", foreign_keys=[status_override_by_id], lazy="joined")
    breaks = relationship(
        "AttendanceBreak",
        back_populates="attendance",
        cascade="all, delete-orphan",
        order_by="AttendanceBreak.start_time",
    )


class AttendanceBreak(Base):
    __tablename__ = "attendance_breaks"

    id: Mapped[int] = mapped_column(primary_key=True)
    attendance_id: Mapped[int] = mapped_column(ForeignKey("attendance.id"), index=True)
    start_time: Mapped[datetime] = mapped_column(DateTime)
    end_time: Mapped[datetime | None] = mapped_column(DateTime)

    attendance = relationship("Attendance", back_populates="breaks")


class LeavePolicy(Base):
    """Company-wide annual allocation per leave type; wfh row holds the WFH
    allowance. Applies to every employee unless overridden below."""
    __tablename__ = "leave_policies"

    id: Mapped[int] = mapped_column(primary_key=True)
    leave_type: Mapped[str] = mapped_column(String(30), unique=True)
    annual_allocation: Mapped[float] = mapped_column(Float, default=0)


class EmployeeLeavePolicy(Base):
    """Per-employee override of the annual allocation for one leave type
    (or "wfh"). Absent = that employee just uses the company-wide policy."""
    __tablename__ = "employee_leave_policies"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    leave_type: Mapped[str] = mapped_column(String(30))
    annual_allocation: Mapped[float] = mapped_column(Float, default=0)

    __table_args__ = (
        UniqueConstraint("user_id", "leave_type", name="uq_employee_leave_policy"),
    )


class LeaveRequest(Base):
    __tablename__ = "leave_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    leave_type: Mapped[str] = mapped_column(String(30))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    days: Mapped[float] = mapped_column(Float)
    reason: Mapped[str] = mapped_column(Text)
    mentions_json: Mapped[str] = mapped_column(Text, default="[]")
    document_path: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    approver_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    approver_comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime)
    approval_stage: Mapped[str] = mapped_column(String(20), default="pending_manager", index=True)
    manager_decided_at: Mapped[datetime | None] = mapped_column(DateTime)
    manager_decided_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    manager_comment: Mapped[str | None] = mapped_column(Text)
    hr_decided_at: Mapped[datetime | None] = mapped_column(DateTime)
    hr_comment: Mapped[str | None] = mapped_column(Text)

    user = relationship("User", foreign_keys=[user_id], lazy="joined")
    approver = relationship("User", foreign_keys=[approver_id], lazy="joined")
    manager_decided_by = relationship("User", foreign_keys=[manager_decided_by_id], lazy="joined")


class WFHRequest(Base):
    __tablename__ = "wfh_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    date: Mapped[date] = mapped_column(Date)
    reason: Mapped[str] = mapped_column(Text)
    mentions_json: Mapped[str] = mapped_column(Text, default="[]")
    document_path: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    approver_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    approver_comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime)
    approval_stage: Mapped[str] = mapped_column(String(20), default="pending_manager", index=True)
    manager_decided_at: Mapped[datetime | None] = mapped_column(DateTime)
    manager_decided_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    manager_comment: Mapped[str | None] = mapped_column(Text)
    hr_decided_at: Mapped[datetime | None] = mapped_column(DateTime)
    hr_comment: Mapped[str | None] = mapped_column(Text)

    user = relationship("User", foreign_keys=[user_id], lazy="joined")
    approver = relationship("User", foreign_keys=[approver_id], lazy="joined")
    manager_decided_by = relationship("User", foreign_keys=[manager_decided_by_id], lazy="joined")


class RegularizationRequest(Base):
    __tablename__ = "regularization_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    date: Mapped[date] = mapped_column(Date)
    requested_check_in: Mapped[datetime | None] = mapped_column(DateTime)
    requested_check_out: Mapped[datetime | None] = mapped_column(DateTime)
    reason: Mapped[str] = mapped_column(Text)
    mentions_json: Mapped[str] = mapped_column(Text, default="[]")
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    approver_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    approver_comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime)
    approval_stage: Mapped[str] = mapped_column(String(20), default="pending_manager", index=True)
    manager_decided_at: Mapped[datetime | None] = mapped_column(DateTime)
    manager_decided_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    manager_comment: Mapped[str | None] = mapped_column(Text)
    hr_decided_at: Mapped[datetime | None] = mapped_column(DateTime)
    hr_comment: Mapped[str | None] = mapped_column(Text)

    user = relationship("User", foreign_keys=[user_id], lazy="joined")
    approver = relationship("User", foreign_keys=[approver_id], lazy="joined")
    manager_decided_by = relationship("User", foreign_keys=[manager_decided_by_id], lazy="joined")


class Holiday(Base):
    __tablename__ = "holidays"

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    name: Mapped[str] = mapped_column(String(150))
    holiday_type: Mapped[str] = mapped_column(String(20), default="company")


class Announcement(Base):
    __tablename__ = "announcements"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    created_by = relationship("User", lazy="joined")


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str | None] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(40), default="info")
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    entity_type: Mapped[str | None] = mapped_column(String(40))
    entity_id: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    actor = relationship("User", foreign_keys=[actor_id], lazy="joined")


class EmployeeRequest(Base):
    """A private employee help request shared only with named participants."""
    __tablename__ = "employee_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    requester_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(80))
    priority: Mapped[str] = mapped_column(String(20), default="normal")
    description: Mapped[str] = mapped_column(Text)
    attachment_path: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    requester = relationship("User", foreign_keys=[requester_id], lazy="joined")
    participants = relationship(
        "EmployeeRequestParticipant",
        back_populates="request",
        cascade="all, delete-orphan",
    )
    messages = relationship(
        "EmployeeRequestMessage",
        back_populates="request",
        cascade="all, delete-orphan",
        order_by="EmployeeRequestMessage.created_at",
    )


class EmployeeRequestParticipant(Base):
    __tablename__ = "employee_request_participants"
    __table_args__ = (
        UniqueConstraint("request_id", "user_id", name="uq_request_participant"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("employee_requests.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    added_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    request = relationship("EmployeeRequest", back_populates="participants")
    user = relationship("User", foreign_keys=[user_id], lazy="joined")


class EmployeeRequestMessage(Base):
    __tablename__ = "employee_request_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("employee_requests.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    message_type: Mapped[str] = mapped_column(String(20), default="comment")
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    request = relationship("EmployeeRequest", back_populates="messages")
    user = relationship("User", foreign_keys=[user_id], lazy="joined")


class EmployeeDocument(Base):
    __tablename__ = "employee_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(150))
    file_path: Mapped[str] = mapped_column(String(255))
    uploaded_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(100))
    module: Mapped[str] = mapped_column(String(50))
    details: Mapped[str | None] = mapped_column(Text)
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    user = relationship("User", lazy="joined")


class CompanySetting(Base):
    __tablename__ = "company_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(80), unique=True)
    value: Mapped[str] = mapped_column(Text)
