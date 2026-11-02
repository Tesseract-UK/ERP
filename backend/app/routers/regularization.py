"""Attendance regularization requests (missed check-in / check-out)."""
from datetime import date
import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import client_info, get_current_user
from ..attendance_location import attendance_now
from ..models import RegularizationRequest, User
from ..schemas import RegularizationCreateRequest
from ..serializers import regularization_out
from ..utils import audit, notify, notify_first_approvers, parse_dt

router = APIRouter(prefix="/regularization", tags=["regularization"])


@router.get("/mention-options")
def mention_options(search: str = Query(default="", max_length=100),
                    user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Names/codes for active colleagues available to mention in a correction."""
    query = db.query(User).filter(
        User.is_active.is_(True), User.id != user.id
    )
    if search.strip():
        like = f"%{search.strip()}%"
        query = query.filter(
            User.full_name.ilike(like) | User.employee_code.ilike(like)
        )
    people = query.order_by(User.full_name).limit(30).all()
    return [{"id": person.id, "full_name": person.full_name,
             "employee_code": person.employee_code, "role": person.role}
            for person in people]


@router.get("")
def my_requests(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(RegularizationRequest) \
        .filter(RegularizationRequest.user_id == user.id) \
        .order_by(RegularizationRequest.created_at.desc()).limit(200).all()
    return [regularization_out(r) for r in rows]


@router.post("")
def create_request(body: RegularizationCreateRequest, request: Request,
                   user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if body.date > attendance_now().date():
        raise HTTPException(status_code=400, detail="Cannot regularize a future date")
    check_in = parse_dt(body.requested_check_in)
    check_out = parse_dt(body.requested_check_out)
    if check_in is None and check_out is None:
        raise HTTPException(status_code=400,
                            detail="Provide a corrected check-in and/or check-out time")
    if check_in and check_out and check_out <= check_in:
        raise HTTPException(status_code=400, detail="Check-out must be after check-in")

    pending = db.query(RegularizationRequest).filter(
        RegularizationRequest.user_id == user.id,
        RegularizationRequest.date == body.date,
        RegularizationRequest.status == "pending").count()
    if pending:
        raise HTTPException(status_code=400,
                            detail="A pending regularization already exists for this date")

    mentioned_ids = list(dict.fromkeys(body.mentioned_user_ids))
    if user.id in mentioned_ids:
        raise HTTPException(status_code=400, detail="You cannot mention yourself")
    mentioned_people = []
    if mentioned_ids:
        mentioned_people = db.query(User).filter(
            User.id.in_(mentioned_ids), User.is_active.is_(True)
        ).all()
        if len(mentioned_people) != len(mentioned_ids):
            raise HTTPException(status_code=400, detail="One or more mentioned colleagues are unavailable")

    req = RegularizationRequest(user_id=user.id, date=body.date,
                                requested_check_in=check_in,
                                requested_check_out=check_out, reason=body.reason,
                                mentions_json=json.dumps(mentioned_ids))
    db.add(req)
    db.flush()
    notify_first_approvers(
        db, user, "New regularization request",
        f"{user.full_name} requested attendance regularization for {body.date.isoformat()}",
        entity_type="regularization", entity_id=req.id,
    )
    approver_ids = {
        n.user_id for n in db.new if getattr(n, "kind", None) == "approval"
    }
    for person in mentioned_people:
        if person.id not in approver_ids:
            notify(
                db, person.id, "You were mentioned in a regularization request",
                f"{user.full_name} mentioned you in an attendance correction request for {body.date.isoformat()}",
                "mention", actor_id=user.id, entity_type="regularization", entity_id=req.id,
            )
    audit(db, user.id, "apply_regularization", "regularization",
          f"For {body.date}", client_info(request))
    db.commit()
    db.refresh(req)
    return regularization_out(req)
