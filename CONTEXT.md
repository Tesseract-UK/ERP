# Project Context (live — keep this updated)

Working notes for picking this project back up on any device/session. Static
architecture docs live in `README.md`; this file is the current state,
in-flight work, and things a fresh session can't infer from the code alone.

Last updated: 2026-08-06.

## What this is

Tesseract HRMS — React/Vite frontend + FastAPI backend, SQLite locally /
Postgres in production. See `README.md` for the full feature list and
architecture notes.

## Current auth architecture (recently replaced)

Auth was **migrated from a custom email+password JWT system to Clerk**
(adds Google sign-in). Key pieces:

- **Frontend**: `Login.jsx`/`Signup.jsx` render Clerk's `<SignIn/>`/`<SignUp/>`
  components (dark-themed via `clerkAppearance.js`). `api.js` reads the auth
  token from `window.Clerk.session.getToken()` on every request — no more
  localStorage JWT for normal users.
- **Backend**: `deps.py::get_current_user` verifies Clerk session tokens via
  JWKS (RS256). `app/clerk.py::sync_clerk_user` runs the first time a given
  Clerk identity is seen — fetches the Clerk profile, enforces the
  `@tesseractuk.in` domain restriction server-side, and either links the
  identity to an existing HR-provisioned employee (matched by email) or
  creates a new `role: employee` row.
- **Admin break-glass login**: the original password-based `/auth/login`
  still works, but **only for `role: admin` accounts** — it's a deliberate
  fallback if Clerk/Google is ever down, not a general bypass. Accessible via
  the "Admin emergency access" link below the Clerk widget on `/login`.
  Frontend stores this token separately (`localStorage: hrms_admin_token`,
  see `getLegacyToken`/`setLegacyToken` in `api.js`) and it takes priority
  over the Clerk token when present.
- **Assigning roles/managers to new sign-ups**: no special UI was built for
  this — it didn't need to be. Every Clerk sign-up auto-creates a normal
  `employee` row, which just shows up in Employees → Edit like any other
  employee, where HR/Admin sets their real role and reporting manager.

Clerk dev instance: `peaceful-reptile-39.clerk.accounts.dev` (test keys, see
`backend/.env` / `frontend/.env`, both gitignored — not in this file).

### Known Clerk + Vite/React-Router gotchas already solved here (don't reintroduce)

- **No `React.StrictMode`** in `main.jsx` — its dev-only double-invoked
  effects raced Clerk's local-dev session handshake into a reload loop.
- **No custom `navigate` prop** on `<ClerkProvider>` — routing Clerk's
  internal redirects through React Router's `navigate()` intercepted Clerk's
  own handshake redirect and re-triggered it, also causing a reload loop.
  Clerk manages its own navigation now (occasional full page load during the
  auth flow instead of client-side routing — acceptable tradeoff).
- **Sync failure must sign out of Clerk**, not just clear local state — if
  `/auth/me` fails after Clerk auth succeeds (wrong domain, deactivated
  account), `AuthContext.jsx` calls Clerk's `signOut()`. Skipping this leaves
  Clerk thinking you're signed in while the route guard bounces you to
  `/login`, and Clerk's `<SignIn/>` auto-redirects straight back since it
  sees an active session — an infinite loop between `/` and `/login`.

## Deployment status

- **GitHub**: `github.com/Tesseract-UK/ERP`, branch `main`, up to date with
  all Clerk work pushed.
- **Auto-deploy on push is NOT set up / not working** for the Vercel
  frontend — confirmed by pushing multiple times with no new deployment
  appearing. **Always deploy the frontend manually** after pushing (see
  below) until someone fixes the GitHub↔Vercel integration (there was a
  Vercel "Authorize App" GitHub permissions screen seen mid-session that may
  be related — worth checking Vercel project → Settings → Git if this needs
  a real fix).
- **Backend (Render)**: `CLERK_SECRET_KEY` / `CLERK_PUBLISHABLE_KEY` env vars
  added manually in the Render dashboard by the user. Backend is confirmed
  live and responding at `https://erp-gksp.onrender.com` (this is the real
  production API URL — baked into the frontend build as `VITE_API_URL`).
  Unknown whether Render auto-deploys on push either — not yet stress-tested
  the way the frontend was.
- **Frontend (Vercel) — RESOLVED, now deployed with Clerk.** The right
  project was `tesseract5` team → `frontend` project all along (this is
  what owns `payroll.tesseractuk.in`) — an earlier check with
  `vercel domains ls --scope tesseract5` misleadingly returned 0 domains
  (that command only lists domains *registered through* Vercel, not custom
  domains *attached* to a project — check the project's dashboard "Domains"
  section instead, or `vercel inspect <deployment>`, not `vercel domains ls`).
  Deployed via `cd frontend && vercel link --yes --project frontend --scope
  tesseract5 && vercel --prod --yes`. Also added
  `VITE_CLERK_PUBLISHABLE_KEY` as a production env var via
  `vercel env add VITE_CLERK_PUBLISHABLE_KEY production` (it was missing —
  the build would otherwise throw, since `main.jsx` hard-fails without it).
  Verified: live bundle hash changed and now contains "Clerk".
  Other Vercel accounts checked and ruled out along the way — leave alone:
  - `vaishnavitesseractuk-milk` — only project is an unrelated
    `vaishnavimilk.com`. **Not part of this app, do not touch.**

**To redeploy the frontend after future pushes** (until auto-deploy is
fixed):
```bash
cd frontend
vercel link --yes --project frontend --scope tesseract5   # if not already linked
vercel --prod --yes
```
Verify: `curl -s https://payroll.tesseractuk.in/ | grep -o 'assets/index-[^"]*\.js'`
then `curl -s https://payroll.tesseractuk.in/<that path> | grep -o Clerk` —
non-empty output confirms the current build is live.

## Design system

Dark, Razorpay-inspired theme — see `frontend/src/styles.css` (`:root` CSS
variables) and the memory note `dark-theme-design.md`. All icons are
`lucide-react` (see `frontend/src/components/icons.jsx`) — no emoji anywhere
in the app, intentionally.

## Local dev quick start

See `README.md` for full setup. Both dev servers are commonly left running
in the background during a session:

```bash
cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000
cd frontend && npm run dev   # localhost:5173
```

Test accounts (password `Password@123`, but note: password login now only
works for `role: admin` — `admin@tesseractuk.in`. Other seeded accounts
(`hr@`, `manager@`, `employee@`, `dev2@tesseractuk.in`) need to sign in via
Clerk using that exact email to link to their existing HR-provisioned
record, since their password login is now blocked by the admin-only
break-glass restriction).

## Open items / next steps

1. Do a real end-to-end test on production: Google sign-in at
   `payroll.tesseractuk.in`, confirm domain restriction error text, confirm
   a fresh sign-up shows up in Employees for role/manager assignment.
2. Fix Vercel auto-deploy-on-push (currently must deploy manually — see
   Deployment status above), and check whether Render has the same problem.
3. Production Clerk keys: currently using `pk_test_.../sk_test_...` (Clerk
   dev instance) in both local dev AND production. Before real users depend
   on this, switch production to a Clerk **Production** instance and its
   `pk_live_.../sk_live_...` keys instead.
4. Production Postgres has no seed data (the admin break-glass login
   returned "Invalid email or password" for `admin@tesseractuk.in` there) —
   decide how the first production admin account gets created: run
   `python -m app.seed` via a Render shell, or create one by hand.
5. The old password-management UI (Employees → "Reset PW" / "Allow PW
   Change", Profile → change password) is now vestigial for non-admin users
   since Clerk owns credentials for everyone else — flagged to the user,
   not yet removed/hidden (their call whether to clean it up).
