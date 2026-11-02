"""Company office geofence and authoritative attendance clock helpers."""

from datetime import datetime, timedelta, timezone
from math import asin, cos, isfinite, radians, sin, sqrt

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .config import (
    MAX_GPS_ACCURACY_METERS,
    OFFICE_GEOFENCE_RADIUS_METERS,
    OFFICE_LATITUDE,
    OFFICE_LONGITUDE,
)
from .models import CompanySetting


GEOFENCE_SETTINGS = {
    "office_latitude": (OFFICE_LATITUDE, -90.0, 90.0),
    "office_longitude": (OFFICE_LONGITUDE, -180.0, 180.0),
    "office_radius_meters": (OFFICE_GEOFENCE_RADIUS_METERS, 50.0, 5000.0),
    "max_gps_accuracy_meters": (MAX_GPS_ACCURACY_METERS, 10.0, 500.0),
}


def attendance_now() -> datetime:
    """Return the company's current wall-clock time for attendance records."""
    india_time = timezone(timedelta(hours=5, minutes=30))
    return datetime.now(india_time).replace(tzinfo=None)


def default_geofence_settings() -> dict[str, str]:
    return {key: str(default) for key, (default, _, _) in GEOFENCE_SETTINGS.items()}


def get_geofence_settings(db: Session) -> dict[str, float]:
    values = default_geofence_settings()
    for setting in db.query(CompanySetting).filter(
        CompanySetting.key.in_(GEOFENCE_SETTINGS)
    ).all():
        values[setting.key] = setting.value

    parsed: dict[str, float] = {}
    for key, value in values.items():
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=503,
                detail="Office attendance location settings are invalid. Contact an administrator.",
            ) from exc
        _, minimum, maximum = GEOFENCE_SETTINGS[key]
        if not isfinite(number) or not minimum <= number <= maximum:
            raise HTTPException(
                status_code=503,
                detail="Office attendance location settings are invalid. Contact an administrator.",
            )
        parsed[key] = number
    return parsed


def validate_geofence_settings(values: dict[str, str]) -> None:
    """Reject invalid admin changes before they can affect attendance checks."""
    if not values:
        raise HTTPException(status_code=400, detail="Provide at least one attendance setting")
    for key, value in values.items():
        if key not in GEOFENCE_SETTINGS:
            raise HTTPException(status_code=400, detail=f"Unknown attendance setting: {key}")
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=f"{key} must be a number") from exc
        _, minimum, maximum = GEOFENCE_SETTINGS[key]
        if not isfinite(number) or not minimum <= number <= maximum:
            raise HTTPException(
                status_code=400,
                detail=f"{key} must be between {minimum:g} and {maximum:g}",
            )


def distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance between two GPS points."""
    earth_radius = 6_371_000
    phi1, phi2 = radians(lat1), radians(lat2)
    delta_phi = radians(lat2 - lat1)
    delta_lambda = radians(lon2 - lon1)
    haversine = (
        sin(delta_phi / 2) ** 2
        + cos(phi1) * cos(phi2) * sin(delta_lambda / 2) ** 2
    )
    return 2 * earth_radius * asin(sqrt(min(1.0, haversine)))


def validate_attendance_location(
    db: Session,
    latitude: float,
    longitude: float,
    accuracy_meters: float,
    *,
    allow_outside_office: bool,
) -> float:
    """Require a usable browser fix and enforce the office radius when needed."""
    settings = get_geofence_settings(db)
    if accuracy_meters <= 0 or accuracy_meters > settings["max_gps_accuracy_meters"]:
        raise HTTPException(
            status_code=400,
            detail=(
                "Your location is too imprecise to record attendance. "
                "Move near a window or try again outdoors."
            ),
        )

    distance = distance_meters(
        latitude,
        longitude,
        settings["office_latitude"],
        settings["office_longitude"],
    )
    # The 500 m office rule uses the browser-reported point. GPS uncertainty has
    # its own separately configurable cap above; it does not shrink the radius.
    # WFH removes only the office-distance restriction; location is still captured.
    if not allow_outside_office and distance > settings["office_radius_meters"]:
        raise HTTPException(
            status_code=403,
            detail=(
                f"You are about {round(distance)} metres from the office. "
                f"Check-in and check-out are allowed within "
                f"{round(settings['office_radius_meters'])} metres, unless your "
                "work-from-home request is approved for today."
            ),
        )
    return round(distance, 1)
