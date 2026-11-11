# Tasks — Tesseract HRMS

## Open
- [x] Email token for mitaly@ (sends as notifications@) — in `.env.production`.
- [ ] Fill DATABASE_URL + INITIAL_ADMIN_EMAIL in `.env.production`, paste into Render; VITE_API_URL into Vercel.
- [ ] Google Console: add `https://erp-gksp.onrender.com/auth/google/callback` as a redirect URI.
- [ ] Render env: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`,
      `FRONTEND_URL`, `CORS_ORIGINS`; remove old Clerk vars.
- [x] Assign managers to existing users without one — local DB done 2026-11-10 (dev2@, unnayan.m@ → Admin). Production still needs the same check after deploy.
- [ ] Click-through UI test in a browser (automated browser was unavailable; API flow verified).
- [ ] Push `main` and deploy backend + frontend (frontend deploys manually — see CONTEXT.md).
- [ ] After deploy: HR must enter leave/WFH allocations for every existing employee (balances are 0 until set).
- [ ] Delete stray `client_secret_*.json` from the repo root (gitignored).

## Done (2026-11-10)
- Manager-gated onboarding, manager-only approvals + admin override, conversations with
  @-tagging, email layer, company WFH days, combined Leave & WFH screen, reject confirmation,
  uploads removed, Clerk removed, pytest suite.
