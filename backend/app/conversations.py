"""Conversation threads on leave, WFH and regularization requests.

Who can see a request's conversation:
  * the requester,
  * the requester's current manager (the approver),
  * anyone @-tagged into it (a RequestParticipant row),
  * every Admin (Admins can open and join any conversation).

Tagging someone in the request or in a later comment adds them as a
participant, notifies them in-app and emails them.
"""
import json
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from .mailer import app_link  # re-exported for routers
from .models import (
    CONVERSATION_KINDS, LeaveRequest, RegularizationRequest, RequestComment,
    RequestParticipant, User, WFHRequest,
)
from .serializers import leave_out, regularization_out, user_brief, wfh_out
from .utils import notify, notify_and_email, validate_mentions

KIND_MODELS = {
    "leave": (LeaveRequest, leave_out),
    "wfh": (WFHRequest, wfh_out),
    "regularization": (RegularizationRequest, regularization_out),
}
KIND_LABEL = {"leave": "Leave request", "wfh": "WFH request",
              "regularization": "Regularization request"}
KIND_PHRASE = {"leave": "leave request", "wfh": "WFH request",
               "regularization": "regularization request"}


def load_request(db: Session, kind: str, request_id: int, *, for_update: bool = False):
    if kind not in KIND_MODELS:
        raise HTTPException(status_code=404, detail="Unknown request type")
    model = KIND_MODELS[kind][0]
    query = db.query(model).filter(model.id == request_id)
    if for_update:
        query = query.with_for_update()
    record = query.first()
    if record is None:
        raise HTTPException(status_code=404, detail="Request not found")
    return record


def heading(kind: str, req, *, with_name: bool = True) -> str:
    """Short human title, e.g. 'Leave · Casual · 12 Nov 2026 → 14 Nov 2026 — Asha'."""
    fmt = "%d %b %Y"
    if kind == "leave":
        detail = (f"Leave · {req.leave_type.replace('_', ' ').title()} · "
                  f"{req.start_date:{fmt}} → {req.end_date:{fmt}}")
    elif kind == "wfh":
        detail = f"Work from home · {req.date:{fmt}}"
    else:
        detail = f"Regularization · {req.date:{fmt}}"
    return f"{detail} — {req.user.full_name}" if with_name else detail


def participant_ids(db: Session, kind: str, request_id: int) -> set[int]:
    return {row[0] for row in db.query(RequestParticipant.user_id).filter(
        RequestParticipant.kind == kind, RequestParticipant.request_id == request_id
    ).all()}


def can_view(db: Session, user: User, kind: str, req) -> bool:
    if user.role == "admin" or req.user_id == user.id:
        return True
    if req.user.manager_id == user.id:
        return True
    return user.id in participant_ids(db, kind, req.id)


def can_decide(user: User, req) -> bool:
    """Only the requester's manager decides; an Admin may override."""
    if req.status != "pending" or req.user_id == user.id:
        return False
    return user.role == "admin" or req.user.manager_id == user.id


def audience(db: Session, kind: str, req) -> set[int]:
    """Everyone who should hear about activity on this conversation."""
    ids = {req.user_id} | participant_ids(db, kind, req.id)
    if req.user.manager_id:
        ids.add(req.user.manager_id)
    return ids


def add_participants(db: Session, kind: str, req, people: list[User], added_by: User) -> list[User]:
    """Add tagged people who are not already in the thread; returns the newly added."""
    existing = audience(db, kind, req)
    added = []
    for person in people:
        if person.id in existing:
            continue
        db.add(RequestParticipant(kind=kind, request_id=req.id,
                                  user_id=person.id, added_by_id=added_by.id))
        existing.add(person.id)
        added.append(person)
    return added


def notify_tagged(db: Session, actor: User, kind: str, req, people: list[User], text: str) -> None:
    title = heading(kind, req)
    link = app_link(f"/conversations?open={kind}:{req.id}")
    for person in people:
        if person.id == actor.id:
            continue
        notify_and_email(
            db, person, f"You were tagged: {title}",
            f"{actor.full_name} tagged you in this conversation: “{text[:200]}”",
            "mention", actor_id=actor.id, entity_type=kind, entity_id=req.id,
            email_subject=f"{actor.full_name} tagged you: {title}",
            email_body=(
                f"Hi {person.full_name},\n\n"
                f"{actor.full_name} tagged you in a conversation on Tesseract HRMS.\n\n"
                f"{title}\n\n“{text}”\n\n"
                f"You are now part of this conversation. Open it to read the full thread "
                f"and reply:\n{link}\n\n— Tesseract HRMS"
            ),
        )


def post_comment(db: Session, actor: User, kind: str, req, body: str,
                 mention_ids: list[int] | str | None = None, *,
                 message_type: str = "comment") -> RequestComment:
    body = (body or "").strip()
    if not body:
        raise HTTPException(status_code=400, detail="Write a message first")
    if len(body) > 4000:
        raise HTTPException(status_code=400, detail="Message is too long (4000 characters max)")
    ids, people = validate_mentions(db, actor, mention_ids)
    comment = RequestComment(kind=kind, request_id=req.id, user_id=actor.id, body=body,
                             message_type=message_type, mentions_json=json.dumps(ids))
    db.add(comment)
    previous_audience = audience(db, kind, req)
    add_participants(db, kind, req, people, actor)
    db.flush()

    tagged_ids = {person.id for person in people}
    notify_tagged(db, actor, kind, req, people, body)
    if message_type == "comment":
        title = heading(kind, req)
        for user_id in previous_audience - tagged_ids - {actor.id}:
            notify(db, user_id, f"New message: {title}",
                   f"{actor.full_name}: {body[:200]}", "comment",
                   actor_id=actor.id, entity_type=kind, entity_id=req.id)
    return comment


def comment_out(comment: RequestComment) -> dict:
    try:
        mentions = json.loads(comment.mentions_json or "[]")
    except (TypeError, ValueError):
        mentions = []
    return {
        "id": comment.id, "body": comment.body, "message_type": comment.message_type,
        "created_at": comment.created_at.isoformat(),
        "user": user_brief(comment.user), "mentioned_user_ids": mentions,
    }


def conversation_out(db: Session, user: User, kind: str, req) -> dict:
    serialize = KIND_MODELS[kind][1]
    comments = db.query(RequestComment).filter(
        RequestComment.kind == kind, RequestComment.request_id == req.id
    ).order_by(RequestComment.created_at.asc(), RequestComment.id.asc()).all()
    participants = db.query(RequestParticipant).filter(
        RequestParticipant.kind == kind, RequestParticipant.request_id == req.id
    ).all()
    manager = req.user.manager
    return {
        "kind": kind, "id": req.id, "heading": heading(kind, req),
        "request": serialize(req, include_user=True),
        "requester": user_brief(req.user),
        "manager": user_brief(manager),
        "participants": [user_brief(p.user) for p in participants],
        "comments": [comment_out(c) for c in comments],
        "can_comment": True,
        "can_decide": can_decide(user, req),
    }


def conversation_summaries(db: Session, user: User, *, include_all: bool = False) -> list[dict]:
    """Conversations this user belongs to (or every one, for an Admin)."""
    tagged: dict[str, set[int]] = {kind: set() for kind in CONVERSATION_KINDS}
    for kind, request_id in db.query(RequestParticipant.kind, RequestParticipant.request_id).filter(
        RequestParticipant.user_id == user.id
    ).all():
        tagged.setdefault(kind, set()).add(request_id)

    items = []
    for kind, (model, _serialize) in KIND_MODELS.items():
        query = db.query(model)
        if not include_all:
            report_ids = [row[0] for row in db.query(User.id).filter(User.manager_id == user.id).all()]
            conditions = [model.user_id == user.id]
            if report_ids:
                conditions.append(model.user_id.in_(report_ids))
            if tagged[kind]:
                conditions.append(model.id.in_(tagged[kind]))
            query = query.filter(or_(*conditions))
        rows = query.order_by(model.created_at.desc()).limit(300).all()
        if not rows:
            continue
        ids = [r.id for r in rows]
        last_by_request: dict[int, RequestComment] = {}
        counts: dict[int, int] = {}
        for comment in db.query(RequestComment).filter(
            RequestComment.kind == kind, RequestComment.request_id.in_(ids)
        ).order_by(RequestComment.created_at.asc()).all():
            last_by_request[comment.request_id] = comment
            counts[comment.request_id] = counts.get(comment.request_id, 0) + 1
        for r in rows:
            last = last_by_request.get(r.id)
            last_at = last.created_at if last else r.created_at
            items.append({
                "kind": kind, "id": r.id, "heading": heading(kind, r),
                "status": r.status, "requester": user_brief(r.user),
                "message_count": counts.get(r.id, 0),
                "last_message": (f"{last.user.full_name}: {last.body[:160]}" if last
                                 else f"{r.user.full_name}: {r.reason[:160]}"),
                "last_activity": last_at.isoformat(),
                "tagged": r.id in tagged[kind],
                "_sort": last_at,
            })
    items.sort(key=lambda item: item["_sort"] or datetime.min, reverse=True)
    for item in items:
        item.pop("_sort")
    return items[:300]


def announce_new_request(db: Session, requester: User, kind: str, req,
                         tagged: list[User], summary: str) -> None:
    """Tell the manager (in-app + email) and bring tagged colleagues in."""
    title = heading(kind, req)
    manager = requester.manager
    if manager is not None and manager.is_active:
        notify_and_email(
            db, manager, f"New {KIND_PHRASE[kind]}: {requester.full_name}",
            summary, "approval", actor_id=requester.id, entity_type=kind, entity_id=req.id,
            email_subject=f"{requester.full_name} applied — {heading(kind, req, with_name=False)}",
            email_body=(
                f"Hi {manager.full_name},\n\n"
                f"{requester.full_name} has applied for the following and is waiting for "
                f"your review:\n\n{title}\nReason: {req.reason}\n\n"
                f"Kindly review and approve or reject it:\n{app_link('/approvals')}\n\n"
                f"— Tesseract HRMS"
            ),
        )
    added = add_participants(db, kind, req, tagged, requester)
    notify_tagged(db, requester, kind, req, added, req.reason)
