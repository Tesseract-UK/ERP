# Tesseract HRMS

A lightweight, production-ready Employee Management System (HRMS) covering attendance,
leave management, work-from-home requests, approvals, employee profiles and
role-based access control.

**Stack:** React 18 + Vite (frontend, Vercel) · FastAPI + SQLAlchemy (backend, Render) · PostgreSQL

## Features by role

| Role | Capabilities |
|---|---|
| **Employee** | Check-in/out with geolocation + device capture, breaks, color-coded attendance calendar, leave & WFH requests with document upload, attendance regularization, profile self-service, notifications |
| **Manager** | Everything above + team dashboard, approve/reject leave, WFH and regularization requests with comments, team attendance with filters, per-employee team calendar |
| **HR** | Everything above (org-wide) + employee CRUD, deactivate/reactivate, password resets, document management, leave policy & holiday configuration, CSV-exportable reports, announcements |
| **Admin** | Unrestricted: departments, designations, locations, shifts, company settings, full audit log |

Attendance is computed automatically: working hours, break duration, overtime,
late arrivals, and Present / Half Day statuses. Leave and WFH balances are derived
from HR-configured policies minus approved usage — no balance-sync bugs.
Every significant action lands in the audit log with user, IP, and browser info.

## Local development

Backend (Python 3.11+; uses SQLite locally, PostgreSQL in production):

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m app.seed          # seeds a blank local SQLite database only
# To replace the local demo data with the 25-person sample:
python -m app.seed --reset-local
uvicorn app.main:app --reload --port 8000
```

Frontend (Node 18+):

```bash
cd frontend
npm install
npm run dev                 # http://localhost:5173
```

The local demo seed creates 25 synthetic accounts, including `demo.admin@tesseractuk.in`,
`demo.hr1@tesseractuk.in`, `demo.manager1@tesseractuk.in`, and 18 `demo.<name>@tesseractuk.in`
employee accounts. All use password `DemoOnly@123` when local password login is enabled.
These are fictional local test accounts; never copy the demo seed into production.

API docs: http://localhost:8000/docs

## Deployment

### Backend → Render

1. Push this repo to GitHub and create a **Blueprint** on Render pointing at
   `render.yaml` — it provisions the web service and a PostgreSQL database.
2. Do **not** run the demo seed on the deployed database. Create the initial
   production administrator with `python -m app.create_admin` in the Render shell;
   employees then join through the configured company Google sign-in flow.
3. Set `CORS_ORIGINS` to your Vercel URL.
4. Set `APP_ENV=production`, `ALLOWED_EMAIL_DOMAINS=tesseractuk.in`, and
   `FRONTEND_URL` to the deployed frontend origin. Configure
   `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `GOOGLE_REDIRECT_URI` in the
   Render dashboard, then register that exact HTTPS callback URI in Google
   Cloud. Production startup rejects missing secrets, SQLite, and local HTTP
   origins. For the cross-site Render API session cookie use
   `COOKIE_SECURE=true` and `COOKIE_SAMESITE=none` as in `render.yaml`.

Manual alternative: create a Web Service with root dir `backend`, build
`pip install -r requirements.txt`, start
`uvicorn app.main:app --host 0.0.0.0 --port $PORT`, and set `DATABASE_URL`,
`SECRET_KEY`, `CORS_ORIGINS`.

> **Note:** uploaded documents are stored on local disk (`UPLOAD_DIR`). On Render,
> attach a persistent disk to `/opt/render/project/src/backend/uploads`, or swap
> `app/utils.py::save_upload` for S3 later — it is the single integration point.

### Frontend → Vercel

1. Import the repo in Vercel with **root directory `frontend`** (framework: Vite).
2. Set env var `VITE_API_URL` to your deployed Render API HTTPS URL (e.g.
   `https://tesseract-hrms-api.onrender.com`) before the production build.
3. `vercel.json` already handles SPA rewrites for client-side routing.

## Architecture notes

- **JWT auth** (PyJWT + bcrypt), role checks via FastAPI dependencies; the admin
  role passes every role gate.
- **Single dashboard endpoint** returns everything the home page needs in one call.
- **Statuses merge at read time**: the calendar overlays attendance rows, approved
  leave/WFH, holidays and weekends — approving a leave never has to write future
  attendance rows.
- **Notifications** are in-app rows created alongside each event; an email channel
  can subscribe to the same `notify()` helper without touching business logic.
- Pool sizing, pagination and `lazy="joined"` relationships keep it comfortable on
  free-tier Render + Vercel.

## Extending

Each domain is one router + one model section + one page. To add Payroll,
Assets, Recruitment etc., follow the same pattern: model → schema → router
(with `require_roles`) → page + nav entry.
