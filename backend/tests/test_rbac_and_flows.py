"""RBAC and end-to-end flow checks for onboarding, requests, approvals,
conversations, company calendar and email."""
from app.models import Announcement, Notification, RequestComment, RequestParticipant

from conftest import next_weekday


def _leave(client, mentions=(), days=1):
    start = next_weekday(10)
    return client.post("/leaves", json={
        "leave_type": "casual", "start_date": start.isoformat(),
        "end_date": start.isoformat(), "reason": "Family function",
        "mentioned_user_ids": list(mentions)})


# ---------- onboarding gate ----------

def test_pending_joiner_is_blocked_and_sees_nothing(org):
    c = org.client(org.pending)
    me = c.get("/profile").json()
    assert me["onboarding_pending"] is True and me["can_request"] is False
    assert me["pan_number"] is None and me["bank_account"] is None
    balance = c.get("/leaves/balance").json()
    assert balance["casual"]["allocated"] == 0 and balance["wfh"]["remaining"] == 0
    for r in (_leave(c),
              c.post("/wfh", json={"date": next_weekday().isoformat(), "reason": "Plumber"}),
              c.post("/regularization", json={"date": "2026-01-05", "requested_check_in": "2026-01-05T09:00",
                                              "reason": "Forgot"})):
        assert r.status_code == 403
        assert "manager" in r.json()["detail"]


def test_hr_assigning_manager_completes_onboarding(org, sent_emails):
    hr = org.client(org.hr)
    r = hr.post(f"/hr/employees/{org.pending.id}/set-manager", json={"manager_id": org.manager.id})
    assert r.status_code == 200, r.text
    me = org.client(org.pending).get("/profile").json()
    assert me["can_request"] is True
    # Balances stay 0 until HR enters them — the company policy is not applied.
    assert org.client(org.pending).get("/leaves/balance").json()["casual"]["allocated"] == 0
    r = hr.put(f"/hr/employees/{org.pending.id}/leave-overrides", json={"allocations": {"casual": 12}})
    assert r.status_code == 200, r.text
    assert org.client(org.pending).get("/leaves/balance").json()["casual"]["allocated"] == 12
    assert any(to == "pending@tesseractuk.in" for to, _s, _b in sent_emails)


def test_nobody_but_admin_can_be_left_without_manager(org):
    hr = org.client(org.hr)
    assert hr.post(f"/hr/employees/{org.alice.id}/set-manager", json={"manager_id": None}).status_code == 400
    # HR may not edit HR/Admin reporting lines.
    assert hr.post(f"/hr/employees/{org.hr.id}/set-manager", json={"manager_id": org.manager.id}).status_code == 403
    admin = org.client(org.admin)
    assert admin.post(f"/hr/employees/{org.admin2.id}/set-manager",
                      json={"manager_id": org.manager.id}).status_code == 400
    # Creating an employee requires a manager.
    r = hr.post("/hr/employees", json={"email": "new@tesseractuk.in", "full_name": "New", "role": "employee"})
    assert r.status_code == 400
    r = hr.post("/hr/employees", json={"email": "new@tesseractuk.in", "full_name": "New",
                                       "role": "employee", "manager_id": org.manager.id})
    assert r.status_code == 200, r.text
    # An employee is not a valid manager.
    assert hr.post(f"/hr/employees/{org.bob.id}/set-manager", json={"manager_id": org.alice.id}).status_code == 400


# ---------- admin ----------

def test_admin_never_requests_or_checks_in(org):
    admin = org.client(org.admin)
    assert _leave(admin).status_code == 403
    r = admin.post("/attendance/check-in", json={"latitude": 22.7, "longitude": 75.9, "accuracy_meters": 10})
    assert r.status_code == 403
    assert admin.get("/profile").json()["onboarding_pending"] is False


def test_admin_can_make_another_admin_and_hr_cannot(org):
    hr = org.client(org.hr)
    assert hr.post(f"/hr/employees/{org.alice.id}/role", json={"role": "admin"}).status_code == 403
    admin = org.client(org.admin)
    r = admin.post(f"/hr/employees/{org.bob.id}/role", json={"role": "admin"})
    assert r.status_code == 200, r.text
    org.db.expire_all()
    assert org.bob.role == "admin" and org.bob.manager_id is None
    # A manager with reports cannot be demoted to employee.
    assert admin.post(f"/hr/employees/{org.manager.id}/role", json={"role": "employee"}).status_code == 409


# ---------- requests, approvals, conversations ----------

def test_leave_emails_manager_and_tags_colleague(org, sent_emails):
    alice = org.client(org.alice)
    r = _leave(alice, mentions=[org.carol.id])
    assert r.status_code == 200, r.text
    leave_id = r.json()["id"]
    recipients = {to for to, _s, _b in sent_emails}
    assert {"manager@tesseractuk.in", "carol@tesseractuk.in"} <= recipients
    assert org.db.query(RequestParticipant).filter_by(kind="leave", request_id=leave_id,
                                                      user_id=org.carol.id).count() == 1
    # Visibility: owner, manager, tagged, admin yes; others no.
    for user, ok in ((org.alice, True), (org.manager, True), (org.carol, True), (org.admin, True),
                     (org.bob, False), (org.hr, False), (org.other_manager, False)):
        code = org.client(user).get(f"/conversations/leave/{leave_id}").status_code
        assert code == (200 if ok else 404), (user.full_name, code)


def test_comment_tagging_adds_participant_and_notifies(org, sent_emails):
    leave_id = _leave(org.client(org.alice)).json()["id"]
    mgr = org.client(org.manager)
    r = mgr.post(f"/conversations/leave/{leave_id}/comments",
                 json={"body": "@Hr please check the balance", "mentioned_user_ids": [org.hr.id]})
    assert r.status_code == 200, r.text
    hr = org.client(org.hr)
    convo = hr.get(f"/conversations/leave/{leave_id}").json()
    assert convo["comments"][-1]["body"].startswith("@Hr")
    assert hr.post(f"/conversations/leave/{leave_id}/comments", json={"body": "Balance is fine"}).status_code == 200
    assert "hr@tesseractuk.in" in {to for to, _s, _b in sent_emails}
    # Requester gets an in-app note about the new message.
    assert org.db.query(Notification).filter_by(user_id=org.alice.id, kind="comment").count() >= 1
    # HR can now find it in their conversation list.
    assert any(c["id"] == leave_id and c["tagged"] for c in hr.get("/conversations").json())


def test_only_manager_or_admin_decides(org):
    leave_id = _leave(org.client(org.alice)).json()["id"]
    for user in (org.hr, org.bob, org.other_manager, org.alice):
        code = org.client(user).post(f"/approvals/leave/{leave_id}/approve", json={}).status_code
        assert code == 403, (user.full_name, code)
    r = org.client(org.manager).post(f"/approvals/leave/{leave_id}/reject", json={"comment": "Busy week"})
    assert r.status_code == 200 and r.json()["status"] == "rejected"
    assert org.client(org.manager).post(f"/approvals/leave/{leave_id}/approve", json={}).status_code == 400
    decision = org.db.query(RequestComment).filter_by(kind="leave", request_id=leave_id,
                                                      message_type="decision").one()
    assert "Busy week" in decision.body


def test_admin_override_and_pending_scopes(org):
    org.client(org.alice).post("/wfh", json={"date": next_weekday().isoformat(), "reason": "Internet install"})
    org.client(org.carol).post("/wfh", json={"date": next_weekday().isoformat(), "reason": "Courier"})
    mgr_pending = org.client(org.manager).get("/approvals/pending").json()
    assert {i["user"]["id"] for i in mgr_pending} == {org.alice.id}
    admin = org.client(org.admin)
    admin_pending = admin.get("/approvals/pending").json()
    assert {i["user"]["id"] for i in admin_pending} >= {org.alice.id, org.carol.id}
    carol_req = next(i for i in admin_pending if i["user"]["id"] == org.carol.id)
    r = admin.post(f"/approvals/wfh/{carol_req['id']}/approve", json={})
    assert r.status_code == 200 and r.json()["status"] == "approved"
    assert org.client(org.hr).get("/approvals/pending").status_code == 403
    assert org.client(org.alice).get("/approvals/pending").status_code == 403


def test_admin_sees_every_conversation(org):
    _leave(org.client(org.alice))
    assert org.client(org.alice).get("/conversations?scope=all").status_code == 403
    assert org.client(org.hr).get("/conversations?scope=all").status_code == 403
    all_items = org.client(org.admin).get("/conversations?scope=all").json()
    assert len(all_items) == 1
    # Manager sees it as a direct report's request; an unrelated employee does not.
    assert len(org.client(org.manager).get("/conversations").json()) == 1
    assert org.client(org.bob).get("/conversations").json() == []


# ---------- company calendar ----------

def test_company_wfh_day_is_admin_only_and_announced(org):
    day = next_weekday(20)
    assert org.client(org.hr).post("/company-calendar/wfh-days", json={"date": day.isoformat()}).status_code == 403
    r = org.client(org.admin).post("/company-calendar/wfh-days", json={"date": day.isoformat(), "note": "Office maintenance"})
    assert r.status_code == 200, r.text
    assert org.db.query(Announcement).filter(Announcement.title.like("Company-wide work from home%")).count() == 1
    cal = org.client(org.alice).get(f"/company-calendar?year={day.year}").json()
    assert cal["wfh_days"][0]["date"] == day.isoformat()
    r = org.client(org.alice).post("/wfh", json={"date": day.isoformat(), "reason": "Already WFH"})
    assert r.status_code == 400


def test_holiday_creation_announces(org):
    day = next_weekday(30)
    r = org.client(org.hr).post("/hr/holidays", json={"date": day.isoformat(), "name": "Founders Day"})
    assert r.status_code == 200, r.text
    assert org.db.query(Announcement).filter(Announcement.title == "Holiday: Founders Day").count() == 1
    assert org.client(org.alice).post("/hr/holidays", json={"date": day.isoformat(), "name": "X"}).status_code == 403


# ---------- removed features and role guards ----------

def test_document_uploads_are_gone(org):
    admin = org.client(org.admin)
    assert admin.get("/files/leave_docs/x.pdf").status_code == 404
    assert admin.get(f"/hr/employees/{org.alice.id}/documents").status_code in (404, 405)
    assert org.client(org.pending).post("/profile/onboarding", json={}).status_code in (404, 405)


def test_role_guards_on_admin_and_hr_endpoints(org):
    employee = org.client(org.alice)
    manager = org.client(org.manager)
    hr = org.client(org.hr)
    for path in ("/hr/employees", "/hr/policies", "/hr/holidays"):
        assert employee.get(path).status_code == 403
        assert manager.get(path).status_code == 403
        assert hr.get(path).status_code == 200
    assert hr.get("/admin/audit-logs").status_code == 403
    assert org.client(org.admin).get("/admin/audit-logs").status_code == 200
    assert employee.put("/hr/policies", json={"allocations": {"casual": 99}}).status_code == 403


def test_email_is_not_sent_when_transaction_rolls_back(db, sent_emails):
    from app.mailer import queue_email
    queue_email(db, "x@tesseractuk.in", "s", "b")
    db.rollback()
    queue_email(db, "y@tesseractuk.in", "s", "b")
    db.commit()
    assert [to for to, _s, _b in sent_emails] == ["y@tesseractuk.in"]
