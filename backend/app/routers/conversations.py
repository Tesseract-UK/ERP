"""Request conversations: list, read and reply (with @-tagging)."""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from ..conversations import (
    can_view, conversation_out, conversation_summaries, load_request, post_comment,
)
from ..database import get_db
from ..deps import client_info, get_current_user
from ..models import User
from ..schemas import ConversationCommentRequest
from ..utils import audit

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("/people")
def mention_options(search: str = Query(default="", max_length=100),
                    user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Active colleagues that can be @-tagged in a conversation."""
    query = db.query(User).filter(User.is_active.is_(True), User.id != user.id)
    term = search.strip()
    if term:
        like = f"%{term}%"
        query = query.filter(User.full_name.ilike(like) | User.employee_code.ilike(like)
                             | User.email.ilike(like))
    people = query.order_by(User.full_name).limit(30).all()
    return [{"id": p.id, "full_name": p.full_name, "employee_code": p.employee_code,
             "role": p.role} for p in people]


@router.get("")
def list_conversations(scope: str = Query(default="mine", pattern="^(mine|all)$"),
                       user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if scope == "all" and user.role != "admin":
        raise HTTPException(status_code=403, detail="Only Admins can view every conversation")
    return conversation_summaries(db, user, include_all=scope == "all")


@router.get("/{kind}/{request_id}")
def get_conversation(kind: str, request_id: int, request: Request,
                     user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    req = load_request(db, kind, request_id)
    if not can_view(db, user, kind, req):
        raise HTTPException(status_code=404, detail="Request not found")
    return conversation_out(db, user, kind, req)


@router.post("/{kind}/{request_id}/comments")
def add_comment(kind: str, request_id: int, body: ConversationCommentRequest, request: Request,
                user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    req = load_request(db, kind, request_id)
    if not can_view(db, user, kind, req):
        raise HTTPException(status_code=404, detail="Request not found")
    post_comment(db, user, kind, req, body.body, body.mentioned_user_ids)
    audit(db, user.id, "comment_request", "conversations",
          f"{kind} #{request_id}", client_info(request))
    db.commit()
    return conversation_out(db, user, kind, req)
