# Architecture — Tesseract HRMS

**Stack:** React 18 + Vite (frontend, Vercel, `payroll.tesseractuk.in`) · FastAPI + SQLAlchemy
(backend, Render, `erp-gksp.onrender.com`) · PostgreSQL in production, SQLite locally.

## Identity & access
- Employees, Managers and HR sign in with **Google OAuth** (server-side code flow,
  callback `/auth/google/callback`), restricted to `@tesseractuk.in`. Admins sign in
  with a password at `/admin`. Sessions are HttpOnly cookies with rotating refresh tokens.
- Roles: `employee`, `manager`, `hr`, `admin`. `require_roles(...)` in `deps.py`; Admin
  passes every role check except where a route explicitly excludes Admins.

## Reporting tree (the core invariant)
- Everyone except an **Admin** reports to an active **Manager or Admin** (`users.manager_id`).
  Admins report to no one. Enforced in `routers/hr.py::_validate_reporting_line` for
  create, update and set-manager; role changes to Admin clear `manager_id`.
- A user with no manager is **onboarding pending** (`serializers.user_full` →
  `onboarding_pending`, `can_request`): zero balances, no ID/bank fields shown, and
  leave/WFH/regularization submissions return 403 (`utils.require_request_eligibility`).
  New Google sign-ups land here; HR/Admins are notified (in-app + email). Assigning a
  manager completes onboarding and notifies the joiner.

## Requests, approvals, conversations
- Leave, WFH and regularization requests (`routers/leaves.py`, `wfh.py`, `regularization.py`).
  Submitting notifies + emails the requester's manager; @-tagged colleagues become
  conversation participants and are notified + emailed.
- **Approver:** the requester's manager; an Admin can override. No HR stage
  (`routers/approvals.py`, `conversations.can_decide`). Decisions are posted into the thread.
- **Conversations** (`app/conversations.py`, `routers/conversations.py`): one thread per
  request (`request_comments`, `request_participants`). Visible to requester, their
  manager, tagged participants, and every Admin. Tagging in a reply adds the person.
- Admins never check in (`attendance.attendance_user`) and never submit requests.

## Company calendar
- Holidays (`/hr/holidays`, HR or Admin) and company-wide WFH days
  (`/company-calendar/wfh-days`, Admin only). Both auto-post an announcement. A company
  WFH day lets everyone check in from anywhere without using WFH balance.

## Email
- `app/mailer.py`: `queue_email()` stores messages on the DB session; they are sent on a
  background thread only after commit (discarded on rollback). `EMAIL_BACKEND` =
  `console` (log only, current default) | `smtp` | `disabled`. From
  `notifications@tesseractuk.in`.
- Sent: manager on every new request; tagged people; requester on decision; HR/Admin on
  a new sign-up; joiner when onboarding completes.

## Not supported (by decision)
- File/document uploads anywhere (removed 2026-11-10). Old upload columns/tables remain
  in the DB but nothing reads or writes them.

## Schema changes
- Applied at startup by `main.py` (`create_all` + additive `ALTER TABLE` checks); the
  Alembic folder is kept for reference. New tables: `company_wfh_days`,
  `request_participants`, `request_comments`.

## Tests
- `backend/tests/` (pytest, throwaway SQLite): RBAC matrix and all flows above.
  Run: `cd backend && .venv/bin/python -m pytest -q tests`.
