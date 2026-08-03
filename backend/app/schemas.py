"""Pydantic request models. Responses are serialized via serializers.py."""
from datetime import date

from pydantic import BaseModel, EmailStr, Field, field_validator

from .models import HOLIDAY_TYPES, LEAVE_TYPES, ROLES


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class CheckInRequest(BaseModel):
    local_time: str  # ISO datetime from the client's clock
    latitude: float | None = None
    longitude: float | None = None


class CheckOutRequest(BaseModel):
    local_time: str


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
    employee_code: str | None = None
    password: str | None = Field(default=None, min_length=8)
    role: str = "employee"
    phone: str | None = None
    department_id: int | None = None
    designation_id: int | None = None
    location_id: int | None = None
    shift_id: int | None = None
    manager_id: int | None = None
    joining_date: date | None = None
    date_of_birth: date | None = None
    pan_number: str | None = None
    aadhaar_number: str | None = None
    passport_number: str | None = None
    bank_account: str | None = None
    ifsc_code: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None
    address: str | None = None

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


class AnnouncementRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=5000)


class NamedItemRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class ShiftRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    start_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    end_time: str = Field(pattern=r"^\d{2}:\d{2}$")


class LocationRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    address: str | None = None


class SettingsRequest(BaseModel):
    settings: dict[str, str]


class ResetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=8, max_length=128)
