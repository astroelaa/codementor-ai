# CodeMentor AI — Deployment Checklist

**Status: production deployment complete (verified 2026-10-16).**
Everything below reflects the live system. Render and Hugging Face remain
documented ALTERNATIVES only — they are not used and not configured in
production.

## Done (verified, no action needed)

- ✅ **Neon Postgres**: production database live; `/ready` returns
  `{"status":"ready","database":"ok"}`; schema current through
  migration `3a1c9d47b802` (user learning preferences).
- ✅ **Backend deploy (Vercel)**: project `codementor-ai-api`,
  <https://codementor-ai-api.vercel.app>. Root Directory `backend`,
  `backend/vercel.json` (300s timeout, `iad1`). Migration runs in the
  build step (`backend/scripts/migrate.py`) and is no-op-safe per deploy.
- ✅ **Frontend deploy (Vercel)**: project `codementor-ai`,
  <https://codementor-ai.vercel.app>, connected to `astroelaa/codementor-ai`
  branch `main`, Root Directory `frontend`. GitHub Pages remains live as a
  public mirror: <https://astroelaa.github.io/codementor-ai/> (repo variable
  `VITE_API_BASE_URL`).
- ✅ **Transactional email (SMTP/Gmail)**: `EMAIL_PROVIDER=smtp`,
  `EMAIL_SMTP_HOST=smtp.gmail.com`, `EMAIL_SMTP_PORT=465`
  (TLS-on-connect — 587 STARTTLS sessions are dropped by Vercel egress),
  `EMAIL_SMTP_USER` / `EMAIL_SMTP_PASSWORD` / `EMAIL_SENDER` set as secrets.
  Real delivery proven: verification email submitted by Gmail and received
  in a real inbox (user-confirmed 2026-10-16).
- ✅ **Backend secrets**: set with hidden values only (`DATABASE_URL`,
  `JWT_SECRET`, `GROQ_API_KEY`, `EMAIL_SMTP_PASSWORD`). `/health` returns
  provider names only; no key material ever shipped in the repo.
- ✅ **CI**: backend pytest (144 tests) + frontend typecheck/build green on
  every push to `main`.

## Standing user actions (outside the repo)

- Rotate/delete the old Groq key on the Groq dashboard if a key was ever
  exposed anywhere public (production already uses the rotated key).
- Keep the platform dashboard current (e.g. attach the canonical frontend
  domain as a project domain from the Vercel dashboard if it was added as a
  one-off alias).

## Documented alternatives (NOT used in production; configs kept in repo)

- **Render Blueprint** (`render.yaml`, repo root): rootDir `backend`,
  pip install, `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0
  --port $PORT`, `/health` check. Requires a credit card on Render.
- **Hugging Face Spaces Docker** (`backend/Dockerfile`): same start command,
  `${PORT:-7860}`. Import as a new Space if Vercel is ever replaced.

## Historical blockers — resolved

| formerly blocked | resolution (2026-10-16) |
|---|---|
| Neon Postgres | provisioned; pooled `postgresql+psycopg2://` URL stored only as a Vercel secret |
| Backend host | Vercel (Render card requirement documented as alternative) |
| Transactional email | Gmail SMTP on port 465; real inbox delivery confirmed |
| Frontend API URL | repo variable `VITE_API_BASE_URL` = canonical backend URL |
| Groq key rotation | rotated key in production; old key in chat history — verify deletion on the Groq dashboard |
