"""Admin module: org structure, announcements, audit logs, settings."""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import client_info, get_current_user, require_admin, require_hr
from ..models import (
    Announcement, AuditLog, CompanySetting, Department, Designation, Location,
    Shift, User,
)
from ..schemas import (
    AnnouncementRequest, LocationRequest, NamedItemRequest, SettingsRequest, ShiftRequest,
)
from ..serializers import announcement_out, audit_out
from ..utils import audit, notify

router = APIRouter(prefix="/admin", tags=["admin"])


# ---------- reference data (read open to all authenticated users for dropdowns) ----------

@router.get("/org-data")
def org_data(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {
        "departments": [{"id": d.id, "name": d.name, "is_active": d.is_active}
                        for d in db.query(Department).order_by(Department.name).all()],
        "designations": [{"id": d.id, "title": d.title, "is_active": d.is_active}
                         for d in db.query(Designation).order_by(Designation.title).all()],
        "locations": [{"id": l.id, "name": l.name, "address": l.address,
                       "is_active": l.is_active}
                      for l in db.query(Location).order_by(Location.name).all()],
        "shifts": [{"id": s.id, "name": s.name, "start_time": s.start_time,
                    "end_time": s.end_time, "is_active": s.is_active}
                   for s in db.query(Shift).order_by(Shift.name).all()],
        "managers": [{"id": u.id, "full_name": u.full_name}
                     for u in db.query(User).filter(
                         User.role.in_(["manager", "hr", "admin"]),
                         User.is_active.is_(True)).order_by(User.full_name).all()],
    }


def _crud_named(db, model, body_name: str, request, user, label: str):
    item = model(**({"name": body_name} if model is not Designation else {"title": body_name}))
    db.add(item)
    audit(db, user.id, f"create_{label}", "admin", body_name, client_info(request))
    db.commit()
    return {"id": item.id}


@router.post("/departments")
def create_department(body: NamedItemRequest, request: Request,
                      user: User = Depends(require_hr), db: Session = Depends(get_db)):
    if db.query(Department).filter(Department.name == body.name).first():
        raise HTTPException(status_code=400, detail="Department already exists")
    return _crud_named(db, Department, body.name, request, user, "department")


@router.post("/designations")
def create_designation(body: NamedItemRequest, request: Request,
                       user: User = Depends(require_hr), db: Session = Depends(get_db)):
    if db.query(Designation).filter(Designation.title == body.name).first():
        raise HTTPException(status_code=400, detail="Designation already exists")
    return _crud_named(db, Designation, body.name, request, user, "designation")


@router.post("/locations")
def create_location(body: LocationRequest, request: Request,
                    user: User = Depends(require_admin), db: Session = Depends(get_db)):
    item = Location(name=body.name, address=body.address)
    db.add(item)
    audit(db, user.id, "create_location", "admin", body.name, client_info(request))
    db.commit()
    return {"id": item.id}


@router.post("/shifts")
def create_shift(body: ShiftRequest, request: Request,
                 user: User = Depends(require_admin), db: Session = Depends(get_db)):
    item = Shift(name=body.name, start_time=body.start_time, end_time=body.end_time)
    db.add(item)
    audit(db, user.id, "create_shift", "admin", body.name, client_info(request))
    db.commit()
    return {"id": item.id}


@router.post("/{kind}/{item_id}/toggle")
def toggle_active(kind: str, item_id: int, request: Request,
                  user: User = Depends(require_admin), db: Session = Depends(get_db)):
    models = {"departments": Department, "designations": Designation,
              "locations": Location, "shifts": Shift}
    if kind not in models:
        raise HTTPException(status_code=404, detail="Unknown item type")
    item = db.get(models[kind], item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    item.is_active = not item.is_active
    audit(db, user.id, f"toggle_{kind}", "admin", f"#{item_id} → {item.is_active}",
          client_info(request))
    db.commit()
    return {"id": item.id, "is_active": item.is_active}


# ---------- announcements ----------

@router.get("/announcements")
def list_announcements(user: User = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    rows = db.query(Announcement).order_by(Announcement.created_at.desc()).limit(50).all()
    return [announcement_out(a) for a in rows]


@router.post("/announcements")
def create_announcement(body: AnnouncementRequest, request: Request,
                        user: User = Depends(require_hr), db: Session = Depends(get_db)):
    ann = Announcement(title=body.title, body=body.body, created_by_id=user.id)
    db.add(ann)
    for u in db.query(User).filter(User.is_active.is_(True), User.id != user.id).all():
        notify(db, u.id, f"📢 {body.title}", body.body[:300], "announcement")
    audit(db, user.id, "create_announcement", "admin", body.title, client_info(request))
    db.commit()
    return announcement_out(ann)


@router.delete("/announcements/{ann_id}")
def delete_announcement(ann_id: int, request: Request,
                        user: User = Depends(require_hr), db: Session = Depends(get_db)):
    ann = db.get(Announcement, ann_id)
    if ann is None:
        raise HTTPException(status_code=404, detail="Announcement not found")
    db.delete(ann)
    audit(db, user.id, "delete_announcement", "admin", ann.title, client_info(request))
    db.commit()
    return {"message": "Announcement deleted"}


# ---------- audit logs ----------

@router.get("/audit-logs")
def audit_logs(user: User = Depends(require_admin), db: Session = Depends(get_db),
               module: str | None = None, user_id: int | None = None,
               page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200)):
    q = db.query(AuditLog)
    if module:
        q = q.filter(AuditLog.module == module)
    if user_id:
        q = q.filter(AuditLog.user_id == user_id)
    total = q.count()
    rows = q.order_by(AuditLog.created_at.desc()) \
        .offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size,
            "items": [audit_out(l) for l in rows]}


# ---------- company settings ----------

@router.get("/settings")
def get_settings(user: User = Depends(require_hr), db: Session = Depends(get_db)):
    return {s.key: s.value for s in db.query(CompanySetting).all()}


@router.put("/settings")
def update_settings(body: SettingsRequest, request: Request,
                    user: User = Depends(require_admin), db: Session = Depends(get_db)):
    for key, value in body.settings.items():
        setting = db.query(CompanySetting).filter(CompanySetting.key == key).first()
        if setting:
            setting.value = value
        else:
            db.add(CompanySetting(key=key, value=value))
    audit(db, user.id, "update_settings", "admin", str(list(body.settings)),
          client_info(request))
    db.commit()
    return {s.key: s.value for s in db.query(CompanySetting).all()}
