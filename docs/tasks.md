# Tasks — Tesseract HRMS

## Open
- [ ] Choose email provider and set `EMAIL_BACKEND=smtp` + `SMTP_USERNAME`/`SMTP_PASSWORD`
      on Render (Google Workspace App Password for notifications@tesseractuk.in, or a
      transactional provider). Check Render plan allows outbound SMTP.
- [ ] Google Console: add `https://erp-gksp.onrender.com/auth/google/callback` as a redirect URI.
- [ ] Render env: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`,
      `FRONTEND_URL`, `CORS_ORIGINS`; remove old Clerk vars.
- [x] Assign managers to existing users without one — local DB done 2026-11-10 (dev2@, unnayan.m@ → Admin). Production still needs the same check after deploy.
- [ ] Click-through UI test in a browser (automated browser was unavailable; API flow verified).
- [ ] Push `main` and deploy backend + frontend (frontend deploys manually — see CONTEXT.md).
- [ ] Delete stray `client_secret_*.json` from the repo root (gitignored).

## Done (2026-11-10)
- Manager-gated onboarding, manager-only approvals + admin override, conversations with
  @-tagging, email layer, company WFH days, combined Leave & WFH screen, reject confirmation,
  uploads removed, Clerk removed, pytest suite.
