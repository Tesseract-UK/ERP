# Brainstorm — Tesseract HRMS

> APPEND-ONLY working memory for non-trivial decisions.

---

## 2026-11-10 — How to model "onboarding pending"
**Options:** (a) new `onboarding_status` column set by HR; (b) derive from `manager_id IS NULL`
for non-admins; (c) reuse `profile_completed`.
**Edge cases:** admin demoted to employee (no manager) → must become pending; manager
deactivated with reports → blocked already; legacy rows without manager → become pending
on deploy (visible to HR on the dashboard list).
**Chosen:** (b). One source of truth; the rule "no one but admin without a manager" *is*
the onboarding gate. `profile_completed` is set true when a manager is assigned, for
compatibility only.

## 2026-11-10 — Who can be a manager?
If only role=manager can manage, the top manager has no valid manager (only Admins are
exempt) → contradiction. Allow Admins as managers. HR stays non-managing.

## 2026-11-10 — Email delivery semantics
Send inside the request = slow + emails for rolled-back work. Outbox table = durable but
needs a worker. Chosen: in-session outbox flushed on `after_commit` to a small thread
pool; at-most-once, in-app notification stays the source of truth. Revisit (outbox table
+ retry) if delivery reliability becomes a requirement.
