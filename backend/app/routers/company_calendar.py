"""Company calendar: holidays plus Admin-declared company-wide WFH days.

Everyone can read it (it drives every calendar view). Only an Admin declares
or removes a company WFH day; each one is announced to the whole company.
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import client_info, get_current_user, require_admin
from ..models import CompanyWFHDay, Holiday, User
from ..schemas import CompanyWFHDayRequest
from ..serializers import holiday_out
from ..utils import audit, publish_announcement

router = APIRouter(prefix="/company-calendar", tags=["company calendar"])


def wfh_day_out(day: CompanyWFHDay) -> dict:
    return {"id": day.id, "date": day.date.isoformat(), "note": day.note,
            "created_by": day.created_by.full_name if day.created_by else None}


@router.get("")
def company_calendar(year: int = Query(..., ge=2000, le=2100),
                     user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    start, end = date(year, 1, 1), date(year, 12, 31)
    holidays = db.query(Holiday).filter(Holiday.date >= start, Holiday.date <= end) \
        .order_by(Holiday.date).all()
    wfh_days = db.query(CompanyWFHDay).filter(CompanyWFHDay.date >= start,
                                              CompanyWFHDay.date <= end) \
        .order_by(CompanyWFHDay.date).all()
    return {"holidays": [holiday_out(h) for h in holidays],
            "wfh_days": [wfh_day_out(d) for d in wfh_days]}


@router.post("/wfh-days")
def declare_wfh_day(body: CompanyWFHDayRequest, request: Request,
                    user: User = Depends(require_admin), db: Session = Depends(get_db)):
    if body.date.weekday() >= 5:
        raise HTTPException(status_code=400, detail="Choose a working day, not a weekend")
    if db.query(Holiday.id).filter(Holiday.date == body.date,
                                   Holiday.holiday_type != "optional").first():
        raise HTTPException(status_code=400, detail="This date is already a holiday")
    if db.query(CompanyWFHDay.id).filter(CompanyWFHDay.date == body.date).first():
        raise HTTPException(status_code=409, detail="This date is already a company WFH day")
    day = CompanyWFHDay(date=body.date, note=body.note.strip(), created_by_id=user.id)
    db.add(day)
    publish_announcement(
        db, user, f"Company-wide work from home on {body.date:%d %b %Y}",
        f"Everyone works from home on {body.date:%A, %d %B %Y}. {body.note.strip()}\n"
        "No WFH request is needed and it does not use your WFH balance.",
    )
    audit(db, user.id, "declare_company_wfh", "calendar", f"{body.date}: {body.note}",
          client_info(request))
    db.commit()
    db.refresh(day)
    return wfh_day_out(day)


@router.delete("/wfh-days/{day_id}")
def remove_wfh_day(day_id: int, request: Request,
                   user: User = Depends(require_admin), db: Session = Depends(get_db)):
    day = db.get(CompanyWFHDay, day_id)
    if day is None:
        raise HTTPException(status_code=404, detail="Company WFH day not found")
    publish_announcement(db, user, f"Company WFH cancelled for {day.date:%d %b %Y}",
                         f"{day.date:%A, %d %B %Y} is a normal office day again.")
    db.delete(day)
    audit(db, user.id, "remove_company_wfh", "calendar", str(day.date), client_info(request))
    db.commit()
    return {"message": "Company WFH day removed"}
