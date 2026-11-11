# Context Log — Tesseract HRMS

> APPEND-ONLY. Never edit or delete a past entry — only add new ones below the last
> entry. decisions.md is the curated summary; this file is the diary.
> (Earlier history lives in /CONTEXT.md.)

---

## 2026-11-10
**Goal:** Merge the Google-OAuth/ERP PRs, then implement the owner's correction list:
manager-gated onboarding, manager-only approvals, conversations with @-tags + email,
company WFH days, combined Leave/WFH screen, reject confirmation, admin rules, no uploads,
full RBAC verification.
**What happened:** PRs #1/#2 came from fork `UnnayanMishra` (not visible as branches);
fetched via `pull/N/head` and merged into local `main` with local WIP (3 trivial
conflicts). Google login failed with `redirect_uri_mismatch` until the callback URI was
added to "Authorised redirect URIs" (it had been put in JS origins). Backend rewritten
per decisions D-002…D-007; frontend updated (Conversations page/modal, Leave & WFH page,
Approvals with 2-step reject, Policies company calendar, onboarding notices, admin views).
**What went well:** pytest suite (15) caught a real mailer bug: `after_rollback` does not
fire when no DB transaction began, so a queued email could leak to the next commit — fixed
with `after_soft_rollback` + ensuring a transaction in `queue_email`. API end-to-end run (22
steps) on a copy of the dev DB passed.
**What went wrong:** DB backup file was briefly included in a local commit (amended out
before any push). Browser automation unavailable, so UI was build-checked but not clicked.
**Outcome / decision:** See decisions D-001…D-007. Not pushed yet.

---

## 2026-11-10 (afternoon) — feedback from first local click-test
- Help-request recipient box looked pre-filled and listed the Admin twice (manager + admin). Replaced with server-side type-to-search picker (scales to any headcount), each person listed once.
- Added shifts 10:00–19:00, 13:30–22:30, 16:30–01:30, 17:30–02:30. Found shifts were labels only: lateness used a global 09:30 and overnight checkout would fail after midnight. Made attendance shift-aware (D-009).
- Leave balances now 0 until HR enters them; HR cannot edit their own (D-008). Fixed NumberInput not reflecting programmatic changes.
- User thought "HR Mitaly" was HR, but role was still employee (role field locked in Edit form). Promoted via admin API; added "Change role…" button inside the Edit form.
- Tests: 24 passing (9 new).

## 2026-11-10 (evening) — production readiness for Supabase + Render + Vercel
- User chose Supabase (DB), Render (API), Vercel (web).
- Ran the suite against Postgres 15 in Docker: 2 failures SQLite hid — `SELECT … FOR UPDATE` with joined eager loads is rejected by Postgres. Would have broken every approve/reject and admin attendance correction in production. Fixed with `with_for_update(of=Model)`; added a regression test (verified it fails without the fix).
- Empty DB had no way to get an Admin (seed creates demo users with a known password; Render free has no shell). Added `app/bootstrap.py`: INITIAL_ADMIN_* env creates the first Admin once; also ensures the leave-policy template.
- render.yaml no longer provisions a Render DB; DATABASE_URL is a dashboard secret (Supabase session pooler).
- Tests: 25 pass on SQLite and Postgres. `TEST_DATABASE_URL` lets the suite run on a scratch Postgres.

## 2026-11-11 — Gmail API mail backend
- User asked for a GCP email option because SMTP is blocked on Render free tier.
- Added `app/gmail_api.py` (service-account JWT → token, cached; Gmail `messages.send`, one retry on 401),
  `EMAIL_BACKEND=gmail_api` with `GMAIL_SERVICE_ACCOUNT_JSON` (raw or base64) + `GMAIL_SENDER`; config fails fast on a bad key.
- Tests: `tests/test_gmail_api.py` against a mocked Google (token claims, caching, delegation error, mailer swallows failures). 28 pass.
- Service-account key creation was blocked by org policy and the user lacks org IAM rights. Added
  refresh-token mode to `gmail_api.py` + `backend/scripts/gmail_token.py` (local loopback on the
  local GOOGLE_REDIRECT_URI, verifies signed-in email and granted scope). Service-account mode kept.
- User wants sending only, no mailbox. Switched to Resend (`mailer._send_resend`), removed Gmail API code
  and script, render.yaml now has RESEND_API_KEY instead of SMTP creds. 27 tests pass.
- Restored Gmail API backend (user: no third party, needs >100/day); removed Resend.
- 2026-11-11: Gmail token obtained for mitaly@ (sends as notifications@ alias); verified with Google (200, gmail.send).
  Created gitignored root `.env.production` = every Render var + VITE_API_URL (generated SECRET_KEY and
  INITIAL_ADMIN_PASSWORD; DATABASE_URL and INITIAL_ADMIN_EMAIL left to fill). Hardened .gitignore (.env.*, keys,
  *.db); removed unused CLERK_* from local backend/.env; history scan found no committed secrets.
