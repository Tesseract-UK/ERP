"""Pydantic request models. Responses are serialized via serializers.py."""
from datetime import date, time
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

from .models import HOLIDAY_TYPES, LEAVE_TYPES, ROLES


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class SignupRequest(BaseModel):
    """Self-service account creation, restricted to allowed email domains."""
    full_name: str = Field(min_length=1, max_length=150)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)

    @field_validator("password")
    @classmethod
    def password_fits_bcrypt(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be 72 UTF-8 bytes or fewer")
        return value


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class SetPasswordRequest(BaseModel):
    """Forced first-login password change (no current password needed)."""
    new_password: str = Field(min_length=8, max_length=128)


class OnboardingRequest(BaseModel):
    """One-time personal-details submission by a new employee."""
    phone: str = Field(min_length=7, max_length=20)
    address: str = Field(min_length=5, max_length=1000)
    emergency_contact_name: str = Field(min_length=2, max_length=150)
    emergency_contact_phone: str = Field(min_length=7, max_length=20)
    date_of_birth: date | None = None
    pan_number: str | None = Field(default=None, max_length=20)
    aadhaar_number: str | None = Field(default=None, max_length=20)
    passport_number: str | None = Field(default=None, max_length=30)
    bank_account: str | None = Field(default=None, max_length=30)
    ifsc_code: str | None = Field(default=None, max_length=15)


class CheckInRequest(BaseModel):
    # local_time is accepted temporarily for older frontend builds, but ignored.
    local_time: str | None = None
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    accuracy_meters: float = Field(gt=0, le=10000)


class CheckOutRequest(BaseModel):
    # Break endpoints still use this schema but do not require location.
    local_time: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    accuracy_meters: float | None = Field(default=None, gt=0, le=10000)


class AttendanceCorrectionRequest(BaseModel):
    status: Literal["present", "absent"]
    reason: str = Field(min_length=10, max_length=1000)

    @field_validator("reason")
    @classmethod
    def correction_reason_not_blank(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 10:
            raise ValueError("Explain the attendance correction in at least 10 characters")
        return value


class LeaveCreateRequest(BaseModel):
    leave_type: str
    start_date: date
    end_date: date
    reason: str = Field(min_length=3, max_length=2000)

    @field_validator("leave_type")
    @classmethod
    def valid_type(cls, v):
        if v not in LEAVE_TYPES:
            raise ValueError("Invalid leave type")
        return v

    @field_validator("end_date")
    @classmethod
    def valid_range(cls, v, info):
        start = info.data.get("start_date")
        if start and v < start:
            raise ValueError("End date cannot be before start date")
        return v


class WFHCreateRequest(BaseModel):
    date: date
    reason: str = Field(min_length=3, max_length=2000)


class RegularizationCreateRequest(BaseModel):
    date: date
    requested_check_in: str | None = None
    requested_check_out: str | None = None
    reason: str = Field(min_length=3, max_length=2000)
    mentioned_user_ids: list[int] = Field(default_factory=list, max_length=20)


class DecisionRequest(BaseModel):
    comment: str | None = Field(default=None, max_length=2000)


class ProfileUpdateRequest(BaseModel):
    """Fields an employee may edit on their own profile."""
    phone: str | None = Field(default=None, max_length=20)
    address: str | None = Field(default=None, max_length=1000)
    emergency_contact_name: str | None = Field(default=None, max_length=150)
    emergency_contact_phone: str | None = Field(default=None, max_length=20)


class EmployeeUpsertRequest(BaseModel):
    """HR/Admin employee create or update."""
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=150)
    employee_code: str | None = Field(default=None, max_length=20)
    password: str | None = Field(default=None, min_length=8, max_length=72)
    role: Literal["employee", "manager", "hr", "admin"] = "employee"
    phone: str | None = Field(default=None, max_length=20)
    department_id: int | None = None
    designation_id: int | None = None
    location_id: int | None = None
    shift_id: int | None = None
    manager_id: int | None = None
    joining_date: date | None = None
    date_of_birth: date | None = None
    pan_number: str | None = Field(default=None, max_length=20)
    aadhaar_number: str | None = Field(default=None, max_length=20)
    passport_number: str | None = Field(default=None, max_length=30)
    bank_account: str | None = Field(default=None, max_length=30)
    ifsc_code: str | None = Field(default=None, max_length=15)
    emergency_contact_name: str | None = Field(default=None, max_length=150)
    emergency_contact_phone: str | None = Field(default=None, max_length=20)
    address: str | None = Field(default=None, max_length=1000)

    @field_validator("full_name")
    @classmethod
    def non_blank_full_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Full name cannot be blank")
        return value

    @field_validator("employee_code")
    @classmethod
    def normalize_employee_code(cls, value: str | None) -> str | None:
        value = value.strip() if value else None
        return value or None

    @field_validator("password")
    @classmethod
    def password_fits_bcrypt(cls, value: str | None) -> str | None:
        if value is not None and len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be 72 UTF-8 bytes or fewer")
        return value


class EmployeeRoleChangeRequest(BaseModel):
    role: Literal["employee", "manager", "hr", "admin"]

    @field_validator("role")
    @classmethod
    def valid_role(cls, v):
        if v not in ROLES:
            raise ValueError("Invalid role")
        return v


class HolidayRequest(BaseModel):
    date: date
    name: str = Field(min_length=1, max_length=150)
    holiday_type: str = "company"

    @field_validator("holiday_type")
    @classmethod
    def valid_type(cls, v):
        if v not in HOLIDAY_TYPES:
            raise ValueError("Invalid holiday type")
        return v


class PolicyUpdateRequest(BaseModel):
    allocations: dict[str, float]  # leave_type -> annual allocation


class EmployeeLeaveOverrideRequest(BaseModel):
    # leave_type -> allocation, or null to remove the override (revert to
    # the company-wide policy for that type).
    allocations: dict[str, float | None]


class AnnouncementRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=5000)

    @field_validator("title", "body")
    @classmethod
    def strip_announcement_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be blank")
        return value


class NamedItemRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def nonblank_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name cannot be blank")
        return value


class ShiftRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    start_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    end_time: str = Field(pattern=r"^\d{2}:\d{2}$")

    @field_validator("name")
    @classmethod
    def nonblank_shift_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Shift name cannot be blank")
        return value

    @field_validator("start_time", "end_time")
    @classmethod
    def valid_clock_time(cls, value: str) -> str:
        try:
            time.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("Time must be a valid 24-hour HH:MM value") from exc
        return value


class LocationRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    address: str | None = Field(default=None, max_length=500)

    @field_validator("name")
    @classmethod
    def nonblank_location_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Location name cannot be blank")
        return value

    @field_validator("address")
    @classmethod
    def normalize_address(cls, value: str | None) -> str | None:
        value = value.strip() if value else None
        return value or None


class SettingsRequest(BaseModel):
    settings: dict[str, str] = Field(min_length=1, max_length=4)

    @field_validator("settings")
    @classmethod
    def normalize_setting_values(cls, values: dict[str, str]) -> dict[str, str]:
        normalized = {}
        for key, value in values.items():
            key = key.strip()
            value = value.strip()
            if not key or not value or len(value) > 40:
                raise ValueError("Setting keys and values must be nonblank and values at most 40 characters")
            normalized[key] = value
        return normalized


class EmployeeRequestCommentRequest(BaseModel):
    body: str = Field(min_length=1, max_length=5000)
    recipient_ids: list[int] = Field(min_length=1, max_length=3)


class EmployeeRequestForwardRequest(BaseModel):
    recipient_id: int
    note: str = Field(default="", max_length=2000)


class EmployeeRequestStatusRequest(BaseModel):
    status: str
    comment: str = Field(default="", max_length=2000)

    @field_validator("status")
    @classmethod
    def valid_status(cls, value):
        if value not in {"in_progress", "resolved", "rejected"}:
            raise ValueError("Status must be in_progress, resolved, or rejected")
        return value


class ResetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=8, max_length=128)


class SetManagerRequest(BaseModel):
    manager_id: int | None = None
