# Decisions Log — Tesseract HRMS

> Curated ADR-style summary — one entry per meaningful decision. For the full
> blow-by-blow trail (including false starts), see context.md.

---

## D-001: Replace Clerk with direct Google OAuth
**Date:** 2026-11-09
**Decision:** Merged PR #1/#2 (fork `UnnayanMishra`): server-side Google OAuth code flow,
own session JWT + refresh cookies; Clerk code and config removed 2026-11-10.
**Why:** Owner wanted Clerk gone; company-only Google accounts.
**Alternatives considered:** Google Identity Services button (ID-token flow, no redirect URI) — PR chose the code flow.
**Status:** active

## D-002: Everyone except Admin must have a manager; no manager = onboarding pending
**Date:** 2026-11-10
**Decision:** Manager may be a Manager or an Admin. Users without one cannot request
anything and see zero balances; assigning a manager completes onboarding.
**Why:** Owner requirement: "No person in ERP should exist without a manager"; new
sign-ups wait for HR formalities.
**Alternatives considered:** separate `onboarding_status` column — rejected; manager
presence is the real gate and avoids two sources of truth.
**Status:** active

## D-003: Manager-only approvals with Admin override; HR stage removed
**Date:** 2026-11-10
**Decision:** The requester's manager approves/rejects; Admin may decide any request.
**Why:** Owner chose "Manager only + Admin override".
**Status:** active

## D-004: Conversation thread per request with @-tagging
**Date:** 2026-11-10
**Decision:** Generic `request_comments` / `request_participants` keyed by (kind, request_id).
Tagged people can read the full thread (including the reason). Admins see all.
**Why:** Owner wants tagged people to be part of the conversation and admins to enter any.
**Status:** active

## D-005: Remove all document uploads
**Date:** 2026-11-10
**Decision:** No uploads anywhere; endpoints removed, DB columns left in place.
**Why:** Owner's choice.
**Status:** active

## D-006: Email sent after commit, console backend until SMTP is configured
**Date:** 2026-11-10
**Decision:** `queue_email` + SQLAlchemy `after_commit` / `after_soft_rollback` hooks; thread pool sender.
**Why:** Never email about a rolled-back action; never block requests on SMTP. Owner chose "decide later" for provider.
**Alternatives considered:** Google Workspace SMTP (App Password), Resend/SendGrid.
**Status:** active — provider pending

## D-007: Company-wide WFH days are Admin-declared and announced
**Date:** 2026-11-10
**Decision:** `company_wfh_days` table; doesn't use WFH balance; holidays and WFH days auto-announce.
**Status:** active

## D-008: Leave balances are 0 until HR sets them per employee
**Date:** 2026-11-10
**Decision:** `compute_balances` uses only `employee_leave_policies`; the company policy is a template HR copies via "Fill from company policy". Nobody (incl. HR) may set their own allocation — an Admin or another HR does.
**Why:** User request; avoids new joiners silently getting full-year balances.
**Consequence:** existing employees in production show 0 after deploy until HR fills them.
**Status:** active

## D-009: Attendance follows the employee's shift
**Date:** 2026-11-10
**Decision:** Late = after own shift start + `LATE_GRACE_MINUTES` (30); no shift → old `LATE_ARRIVAL_TIME`. Shifts with end <= start are overnight: the record belongs to the start date; punches until 20h after check-in close it. Standard shifts are created at startup, matched on times.
**Why:** New 13:30/16:30/17:30 shifts would otherwise be "late" daily and fail checkout after midnight.
**Status:** active

## D-010: Supabase Postgres via the session pooler; first Admin from env
**Date:** 2026-11-10
**Decision:** Render connects to Supabase's Session pooler (IPv4) with sslmode=require. A fresh DB gets its first Admin from INITIAL_ADMIN_* at startup (only while no Admin exists). Demo seed is dev-only.
**Status:** active

## D-011 — Email via Gmail API (service account), not SMTP (2026-11-11)
Render's free tier blocks outbound SMTP ports, so Gmail SMTP + App Password cannot send.
Chose `EMAIL_BACKEND=gmail_api`: a Google Cloud service account with domain-wide
delegation limited to `gmail.send`, impersonating `notifications@tesseractuk.in`, sending over
HTTPS. No new dependencies (PyJWT + cryptography + httpx). SMTP remains supported for paid hosts.
