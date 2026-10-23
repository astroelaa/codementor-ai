# CodeMentor AI — Deployment Checklist

**Status: Supabase migration complete; production deployment follows the
`main` branch.**

## Done (verified in the repository)

- ✅ **Supabase Postgres**: schema, RLS policies, Auth-user trigger, and seed
  data are applied with `alembic upgrade head`.
- ✅ **Supabase Auth**: PKCE frontend, anonymous guests, password-reset email,
  JWKS verification, and service-role account deletion.
- ✅ **Backend deploy (Vercel)**: project `codementor-ai-api`,
  <https://codementor-ai-api.vercel.app>. Root Directory `backend`,
  `backend/vercel.json` (300s timeout, `iad1`). Migration runs in the build
  step (`backend/scripts/migrate.py`) and is no-op-safe per deploy.
- ✅ **Frontend deploy (Vercel)**: project `codementor-ai`,
  <https://codementor-ai.vercel.app>, connected to `astroelaa/codementor-ai`
  branch `main`, Root Directory `frontend`. GitHub Pages remains live as a
  public mirror: <https://astroelaa.github.io/codementor-ai/>.
- ✅ **CI**: backend pytest (180 tests) + frontend typecheck/build green on
  every push to `main`. The backend job uses the Supabase repository secrets.
- ✅ **Solve-notification email (optional)**: `EMAIL_PROVIDER`,
  `EMAIL_SMTP_*`, or `RESEND_API_KEY`. Supabase Auth sends signup and password
  reset email; this optional mail is only for session-solved notifications.

## Required platform configuration

### Backend (Vercel)

Set these names in Vercel → Settings → Environment Variables:

`DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`,
`SUPABASE_SERVICE_ROLE_KEY`, `ENVIRONMENT=production`, `ALLOWED_ORIGINS`,
`GROQ_API_KEY`, and any optional fallback provider keys.

`SUPABASE_SERVICE_ROLE_KEY` is server-only. `DATABASE_URL` must be the Supabase
session-pooler PostgreSQL URL with `sslmode=require`.

### Frontend (Vercel)

Set `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`, and `VITE_API_BASE_URL`.

### GitHub Pages

Set repository variables `VITE_API_BASE_URL`, `VITE_SUPABASE_URL`, and
`VITE_SUPABASE_ANON_KEY` (Settings → Secrets and variables → Actions →
Variables). These are public browser values.

### GitHub Actions CI

Set repository secrets `SUPABASE_URL`, `SUPABASE_ANON_KEY`, and
`SUPABASE_SERVICE_ROLE_KEY` for the live identity/RLS tests.

### Supabase Auth

- Site URL = production frontend URL.
- Redirect URLs include local Vite, Vercel, and GitHub Pages origins.
- Anonymous sign-ins enabled.
- Email provider configured for password reset.

## Standing user actions (outside the repo)

- Rotate/delete any API key that was ever exposed publicly.
- Keep the Supabase Auth URL configuration current if the frontend domain
  changes.
- Review Supabase backups / point-in-time recovery before high-risk migrations.

## Documented alternatives (NOT used in production; configs kept in repo)

- **Render Blueprint** (`render.yaml`, repo root): rootDir `backend`,
  pip install, `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0
  --port $PORT`, `/health` check. Requires a credit card on Render.
- **Hugging Face Spaces Docker** (`backend/Dockerfile`): same start command,
  `${PORT:-7860}`. Import as a new Space if Vercel is ever replaced.
