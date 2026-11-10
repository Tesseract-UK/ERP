"""Private employee requests shared only with their named participants."""

import json
from datetime import datetime

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import client_info, get_current_user
from ..models import (
    EmployeeRequest,
    EmployeeRequestMessage,
    EmployeeRequestParticipant,
    Notification,
    User,
)
from ..schemas import (
    EmployeeRequestCommentRequest,
    EmployeeRequestForwardRequest,
    EmployeeRequestStatusRequest,
)
from ..utils import audit, notify


router = APIRouter(prefix="/requests", tags=["employee requests"])
REQUEST_PRIORITIES = {"low", "normal", "high"}
ACTIVE_STATUSES = {"open", "in_progress"}


def _allowed_contacts(db: Session, requester: User) -> list[dict]:
    contacts: list[dict] = []
    if requester.manager_id:
        manager = db.get(User, requester.manager_id)
        if manager is not None and manager.is_active:
            contacts.append({"id": manager.id, "name": manager.full_name, "role": "manager"})

    for role in ("hr", "admin"):
        users = db.query(User).filter(
            User.role == role,
            User.is_active.is_(True),
            User.id != requester.id,
        ).order_by(User.full_name).all()
        contacts.extend(
            {"id": user.id, "name": user.full_name, "role": role}
            for user in users
        )
    return contacts


def _validate_contact_ids(
    db: Session, requester: User, recipient_ids: list[int]
) -> list[User]:
    if not recipient_ids or len(recipient_ids) > 3 or len(set(recipient_ids)) != len(recipient_ids):
        raise HTTPException(status_code=400, detail="Mention one to three different people")

    allowed = {item["id"]: item["role"] for item in _allowed_contacts(db, requester)}
    if any(recipient_id not in allowed for recipient_id in recipient_ids):
        raise HTTPException(
            status_code=400,
            detail="You can mention only your manager, HR, or an admin",
        )
    roles = [allowed[recipient_id] for recipient_id in recipient_ids]
    if len(set(roles)) != len(roles):
        raise HTTPException(
            status_code=400,
            detail="Mention no more than one person for each role",
        )
    users = db.query(User).filter(
        User.id.in_(recipient_ids), User.is_active.is_(True)
    ).all()
    by_id = {user.id: user for user in users}
    if len(by_id) != len(recipient_ids):
        raise HTTPException(status_code=400, detail="A selected contact is no longer active")
    return [by_id[recipient_id] for recipient_id in recipient_ids]


def _is_participant(db: Session, request_id: int, user_id: int) -> bool:
    return db.query(EmployeeRequestParticipant.id).filter(
        EmployeeRequestParticipant.request_id == request_id,
        EmployeeRequestParticipant.user_id == user_id,
    ).first() is not None


def _get_accessible_request(db: Session, request_id: int, user: User) -> EmployeeRequest:
    item = db.get(EmployeeRequest, request_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Request not found")
    if (
        user.role != "admin"
        and item.requester_id != user.id
        and not _is_participant(db, item.id, user.id)
    ):
        raise HTTPException(status_code=404, detail="Request not found")
    return item


def _serialize(item: EmployeeRequest, user: User, *, include_messages: bool = False) -> dict:
    participants = [
        {"id": participant.user.id, "name": participant.user.full_name,
         "role": participant.user.role}
        for participant in item.participants
    ]
    result = {
        "id": item.id,
        "requester_id": item.requester_id,
        "requester_name": item.requester.full_name,
        "title": item.title,
        "category": item.category,
        "priority": item.priority,
        "description": item.description,
        "status": item.status,
        "participants": participants,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
        "can_withdraw": item.requester_id == user.id and item.status in ACTIVE_STATUSES,
        "can_reply": (user.role == "admin" or item.requester_id == user.id or _is_participant_for_item(item, user.id))
        and item.status in ACTIVE_STATUSES,
        "can_forward": item.requester_id != user.id
        and (user.role == "admin" or _is_participant_for_item(item, user.id))
        and item.status in ACTIVE_STATUSES,
        "can_update_status": item.requester_id != user.id
        and (user.role == "admin" or _is_participant_for_item(item, user.id))
        and item.status in ACTIVE_STATUSES,
    }
    if include_messages:
        result["messages"] = [
            {"id": message.id, "user_id": message.user_id,
             "user_name": message.user.full_name,
             "type": message.message_type, "body": message.body,
             "created_at": message.created_at.isoformat()}
            for message in item.messages
        ]
    return result


def _is_participant_for_item(item: EmployeeRequest, user_id: int) -> bool:
    return any(participant.user_id == user_id for participant in item.participants)


def _add_participants(
    db: Session,
    item: EmployeeRequest,
    users: list[User],
    added_by: User,
) -> list[User]:
    added = []
    existing_ids = {participant.user_id for participant in item.participants}
    for contact in users:
        if contact.id == item.requester_id or contact.id in existing_ids:
            continue
        item.participants.append(EmployeeRequestParticipant(
            user=contact,
            added_by_id=added_by.id,
        ))
        added.append(contact)
        existing_ids.add(contact.id)
    return added


def _notify_people(
    db: Session, user_ids: list[int], title: str, body: str, kind: str,
    *, actor_id: int | None = None, request_id: int | None = None,
) -> None:
    for user_id in set(user_ids):
        notify(db, user_id, title, body[:300], kind, actor_id=actor_id,
               entity_type="employee_request" if request_id else None,
               entity_id=request_id)


def _parse_recipient_ids(raw: str) -> list[int]:
    try:
        values = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Mention list is invalid") from exc
    if (
        not isinstance(values, list)
        or any(isinstance(value, bool) or not isinstance(value, int) for value in values)
    ):
        raise HTTPException(status_code=400, detail="Mention list is invalid")
    return values


@router.get("/recipients")
def request_recipients(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Return only the employee's manager and active HR/admin contacts."""
    return _allowed_contacts(db, user)


@router.get("")
def list_requests(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    status: str | None = None,
):
    if user.role == "admin":
        query = db.query(EmployeeRequest)
        allowed_statuses = {"open", "in_progress", "resolved", "rejected", "withdrawn"}
        if status:
            if status not in allowed_statuses:
                raise HTTPException(status_code=400, detail="Invalid employee request status filter")
            query = query.filter(EmployeeRequest.status == status)
        total = query.count()
        items = query.order_by(
            EmployeeRequest.updated_at.desc(), EmployeeRequest.id.desc()
        ).offset((page - 1) * page_size).limit(page_size).all()
        audit(db, user.id, "view_all_employee_requests", "requests",
              f"Viewed organization requests page {page} ({len(items)}/{total} rows)", client_info(request))
        db.commit()
        return {
            "items": [_serialize(item, user) for item in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    else:
        participant_ids = select(EmployeeRequestParticipant.request_id).where(
            EmployeeRequestParticipant.user_id == user.id
        )
        query = db.query(EmployeeRequest).filter(or_(
            EmployeeRequest.requester_id == user.id,
            EmployeeRequest.id.in_(participant_ids),
        ))
    items = query.order_by(EmployeeRequest.updated_at.desc(), EmployeeRequest.id.desc()).limit(200).all()
    return [_serialize(item, user) for item in items]


@router.post("")
def create_request(
    request: Request,
    title: str = Form(..., min_length=2, max_length=200),
    category: str = Form(..., min_length=1, max_length=80),
    priority: str = Form("normal"),
    description: str = Form(..., min_length=3, max_length=10000),
    recipient_ids: str = Form(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if priority not in REQUEST_PRIORITIES:
        raise HTTPException(status_code=400, detail="Choose low, normal, or high priority")
    contacts = _validate_contact_ids(db, user, _parse_recipient_ids(recipient_ids))
    item = EmployeeRequest(
        requester_id=user.id,
        title=title.strip(),
        category=category.strip(),
        priority=priority,
        description=description.strip(),
        status="open",
    )
    db.add(item)
    db.flush()
    _add_participants(db, item, contacts, user)
    _notify_people(
        db,
        [contact.id for contact in contacts],
        f"New employee request: {item.title}",
        f"{user.full_name} mentioned you in a {item.category} request.",
        "request",
        actor_id=user.id, request_id=item.id,
    )
    audit(db, user.id, "create_employee_request", "requests",
          f"Request #{item.id}: {item.title}", client_info(request))
    db.commit()
    db.refresh(item)
    return _serialize(item, user, include_messages=True)


@router.get("/{request_id}")
def get_request(
    request_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = _get_accessible_request(db, request_id, user)
    if user.role == "admin":
        audit(db, user.id, "view_employee_request", "requests",
              f"Viewed employee request #{item.id}", client_info(request))
        db.commit()
    return _serialize(item, user, include_messages=True)


@router.post("/{request_id}/comments")
def add_comment(
    request_id: int,
    body: EmployeeRequestCommentRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = _get_accessible_request(db, request_id, user)
    if item.status not in ACTIVE_STATUSES:
        raise HTTPException(status_code=400, detail="This request is no longer open")
    contacts = _validate_contact_ids(db, item.requester, body.recipient_ids)
    _add_participants(db, item, contacts, user)
    db.add(EmployeeRequestMessage(
        request_id=item.id,
        user_id=user.id,
        message_type="comment",
        body=body.body.strip(),
    ))
    item.updated_at = datetime.utcnow()
    targets = {contact.id for contact in contacts}
    targets.update(
        participant.user_id for participant in item.participants
        if participant.user_id != user.id
    )
    _notify_people(
        db,
        list(targets),
        f"Reply on employee request: {item.title}",
        f"{user.full_name} added a comment.",
        "request",
        actor_id=user.id, request_id=item.id,
    )
    audit(db, user.id, "comment_employee_request", "requests",
          f"Request #{item.id}", client_info(request))
    db.commit()
    db.refresh(item)
    return _serialize(item, user, include_messages=True)


@router.post("/{request_id}/forward")
def forward_request(
    request_id: int,
    body: EmployeeRequestForwardRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = _get_accessible_request(db, request_id, user)
    if item.status not in ACTIVE_STATUSES:
        raise HTTPException(status_code=400, detail="This request is no longer open")
    if user.role != "admin" and (item.requester_id == user.id or not _is_participant(db, item.id, user.id)):
        raise HTTPException(status_code=403, detail="Only a mentioned person can forward this request")
    contacts = _validate_contact_ids(db, item.requester, [body.recipient_id])
    target = contacts[0]
    added = _add_participants(db, item, [target], user)
    if not added:
        raise HTTPException(status_code=400, detail="That person is already part of this request")
    note = body.note.strip()
    text = f"Forwarded this request to {target.full_name}."
    if note:
        text += f" Note: {note}"
    db.add(EmployeeRequestMessage(
        request_id=item.id,
        user_id=user.id,
        message_type="forward",
        body=text,
    ))
    item.updated_at = datetime.utcnow()
    _notify_people(
        db,
        [target.id, item.requester_id],
        f"Employee request forwarded: {item.title}",
        text,
        "request",
        actor_id=user.id, request_id=item.id,
    )
    audit(db, user.id, "forward_employee_request", "requests",
          f"Request #{item.id} to employee #{target.id}", client_info(request))
    db.commit()
    db.refresh(item)
    return _serialize(item, user, include_messages=True)


@router.post("/{request_id}/status")
def update_request_status(
    request_id: int,
    body: EmployeeRequestStatusRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = _get_accessible_request(db, request_id, user)
    if user.role != "admin" and (item.requester_id == user.id or not _is_participant(db, item.id, user.id)):
        raise HTTPException(status_code=403, detail="Only a mentioned person can update this request")
    if item.status not in ACTIVE_STATUSES:
        raise HTTPException(status_code=400, detail="This request is no longer open")
    item.status = body.status
    item.updated_at = datetime.utcnow()
    label = body.status.replace("_", " ").title()
    message = f"{user.full_name} marked this request {label}."
    if body.comment.strip():
        message += f" Comment: {body.comment.strip()}"
    db.add(EmployeeRequestMessage(
        request_id=item.id,
        user_id=user.id,
        message_type="status",
        body=message,
    ))
    notify(db, item.requester_id, f"Request {label.lower()}: {item.title}", message, "request",
           actor_id=user.id, entity_type="employee_request", entity_id=item.id)
    audit(db, user.id, "update_employee_request_status", "requests",
          f"Request #{item.id}: {body.status}", client_info(request))
    db.commit()
    db.refresh(item)
    return _serialize(item, user, include_messages=True)


@router.post("/{request_id}/withdraw")
def withdraw_request(
    request_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = _get_accessible_request(db, request_id, user)
    if item.requester_id != user.id:
        raise HTTPException(status_code=403, detail="Only the requester can withdraw this request")
    if item.status not in ACTIVE_STATUSES:
        raise HTTPException(status_code=400, detail="This request is already closed")
    item.status = "withdrawn"
    item.updated_at = datetime.utcnow()
    db.add(EmployeeRequestMessage(
        request_id=item.id,
        user_id=user.id,
        message_type="status",
        body=f"{user.full_name} withdrew this request.",
    ))
    _notify_people(
        db,
        [participant.user_id for participant in item.participants],
        f"Employee request withdrawn: {item.title}",
        f"{user.full_name} withdrew this request.",
        "request",
        actor_id=user.id, request_id=item.id,
    )
    audit(db, user.id, "withdraw_employee_request", "requests",
          f"Request #{item.id}", client_info(request))
    db.commit()
    db.refresh(item)
    return _serialize(item, user, include_messages=True)
