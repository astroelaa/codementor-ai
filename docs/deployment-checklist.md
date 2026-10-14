# CodeMentor AI — Deployment Checklist

Code and configuration in this repo are deploy-ready. The remaining steps
need account access and are listed as blockers below.

## Blocker list

| Blocked action | Reason | Your exact steps | Verification | Meanwhile |
|---|---|---|---|---|
| Neon Postgres database | Needs your Neon account | 1. Sign up at neon.tech (GitHub login, no card). 2. New Project named `codementor-ai`. 3. Copy the connection string from the dashboard. 4. Change its start to `postgresql+psycopg2://` and keep it in your own Notepad — never in chat. | String starts with `postgresql+psycopg2://` and contains `@` + password | All code/config below is finished locally |
| Backend host deploy | Render demands a credit card; needs your clicks | **Option A (card):** Render → New + → Blueprint → connect `astroelaa/codementor-ai` → Apply, then fill env table. **Option B (no card):** huggingface.co → New Space → Docker SDK, name `codementor-ai-api`, Dockerfile path `backend/Dockerfile`, port 7860 → add env table in Settings → rebuild. | `GET /ready` returns `{"status":"ready","database":"ok"}` | Dockerfile + render.yaml already committed |
| Transactional email delivery | Needs SMTP credentials or a sender domain | In the host dashboard set `EMAIL_PROVIDER=smtp`, `EMAIL_SMTP_HOST/PORT/USER/PASSWORD`, `EMAIL_SENDER` (a real address you own), `FRONTEND_URL` = backend origin is separate — frontend links use the Pages URL. Until then, `console` provider logs recipient+subject only. | Sign up → server log shows recipient line; real inbox message after SMTP | Console backend + mocked tests work without credentials |
| Backend env secrets | Only you hold them | Paste into the host dashboard (Environment/Variables tab): `DATABASE_URL`, `GROQ_API_KEY`, `JWT_SECRET` (click Generate, ≥32 chars), `ALLOWED_ORIGINS=https://astroelaa.github.io`. Leave `LLM_PROVIDER=groq`, `ENVIRONMENT=production`. | `/health` shows `providers_configured: ["groq"]`, no key material in body | `.env.example` documents every var |
| Frontend API URL | Needs the live backend URL | GitHub repo → Settings → Secrets and variables → Actions → **Variables** tab → New variable `VITE_API_BASE_URL` = backend URL (https, no trailing slash). Pages rebuilds automatically. | Live workspace no longer shows the waking-up banner | Variable name matches `api.ts` + workflow |
| Groq key rotation | Current key was pasted in chat | After deploy works: Groq dashboard → delete the exposed key → create new → paste into `backend/.env` locally and the host env → restart/rebuild. | New mentor turn returns HTTP 200 | Current key still works for local dev |

## What is already done (no action needed)

- `render.yaml` at repo root (auto-detected Blueprint): rootDir `backend`,
  `pip install -r requirements.txt`, `alembic upgrade head && uvicorn
  app.main:app --host 0.0.0.0 --port $PORT`, `/health` check, free plan.
- `backend/Dockerfile` (repo-root build context): same start command,
  `${PORT:-7860}` for HF Spaces.
- Pages workflow builds `frontend/` with `vars.VITE_API_BASE_URL`, deploys
  `dist/`; HashRouter + base `/codementor-ai/` verified live.
- CI workflow runs backend pytest + frontend typecheck/build.
- Production boot refuses dev JWT secret / non-Postgres DB; `/ready` checks
  the real database without spending AI calls.
