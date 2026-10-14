# CodeMentor AI — Production Readiness Audit

Date: 2026-10-14. Source of truth: this repository at `main`.
Baseline checks (re-ran): backend pytest **38 passed**; frontend `tsc + vite build` **pass**.

## 1. Current architecture

- **Frontend** (`frontend/`): React 18 + TypeScript + Vite, Tailwind v4,
  HashRouter, TanStack Query, Framer Motion, lucide-react, CodeMirror
  (python/javascript/typescript/java/cpp/go(sql). `VITE_API_BASE_URL`
  (fallback `VITE_API_URL`, then localhost). Base path `/codementor-ai/`.
  Pages: Landing, Login, Signup, Workspace, Privacy/Terms. Live on GitHub Pages.
- **Backend** (`backend/app/`): FastAPI (sync SQLAlchemy 2), JWT (PyJWT, bcrypt),
  per-IP sliding-window rate limits, CORS allow-list, Pydantic v2 schemas.
  Routers: auth, mentor (sessions/turns/SSE/hints/explain), meta (health/snippets).
  LLM manager: groq (official SDK) → gemini → openai → anthropic fallback chain;
  only providers with keys are tried. SQLite locally, `DATABASE_URL` for Postgres.
  One Alembic revision on `main`.
- **Deploy**: Pages via `.github/workflows/pages.yml`; backend via `render.yaml`
  (Blueprint) or `backend/Dockerfile` (HF Spaces, no card). DB: Neon (pending).

## 2. Verified working (executed, not assumed)

Auth signup/login/me, guest 1-free-session cap, session ownership (403/404),
Socratic turns (JSON + SSE `token`/`done` events), 3-hint budget server-side,
explanation check → solved + badges + streak + skills, misconception storage,
8-language detection + snippets, structured `{detail, code}` errors, 429 with
`Retry-After`, secret-free responses (tested), secret-free git history (scanned).
Live Groq turn verified 2026-10-09 (HTTP 200, Socratic reply, no code leaked).

## 3. Bugs / weaknesses found

1. **(HIGH)** Production starts happily with the dev JWT secret and silently
   uses SQLite when `DATABASE_URL` is missing. Fix: startup validation.
2. **(MED)** `/health` is liveness-only; nothing checks DB/provider readiness.
   Fix: `/ready` with cheap DB + provider-config checks (no AI call).
3. **(MED)** No CI test workflow — only the Pages build runs in Actions.
   Fix: add backend pytest + frontend typecheck/build job.
4. **(LOW)** Rate limiter is in-memory (correct for one free instance; note it).
5. **(LOW)** No request IDs in logs; provider errors sanitized (good) but terse.
6. Tokens in `localStorage`: accepted for Pages (cross-site cookies won't work);
   mitigations are short-ish expiry, no token logging, logout clears state.

## 4. Missing production capabilities

- Dashboard / history-replay / doc-simplifier / learning-path **frontend pages**
  (backend endpoints exist in shelved stash, unverified).
- Review goals (review/debug/explain modes) — designed, not implemented.
- Token-usage recording (in stash, unverified).
- PWA (no manifest/service worker/icons).
- Backup/restore docs; privacy data-flow doc (Legal pages are generic).
- Production smoke test against Neon (blocked on account access + backend URL).

## 5. Fixes applied during this mission

- Restored + adapted shelved endpoints: `GET /api/dashboard`, `GET /api/skills`,
  `GET/POST /api/learning-path` (+ item status PATCH), `POST /api/docs/simplify`,
  `GET /api/docs/history` — all real DB rows, auth-enforced, tested.
- Added `LearningPath.source` (`weak-spots`|`starter`) via Alembic revision
  `f4c926f88e02`; `alembic upgrade head` in tests proves a fresh DB migrates.
- Production startup validation: `ENVIRONMENT=production` now refuses the dev
  JWT secret (<32 chars) and non-PostgreSQL `DATABASE_URL` at boot.
- New `/ready` endpoint checks the database with `SELECT 1` and reports
  provider configuration (no AI call); `/health` stays liveness-only.
- Suite grew 38 → 55 tests (progress, docs, ops, detection, prompts).
- Review goals: `goal` (debug/review/explain) stored per session, goal-specific
  prompt preambles, same stable response schema; tested.
- Frontend pages: Dashboard (real stats/weak-spots/badges/path), History
  (replay + continue via `?session=` resume, which also fixes refresh
  persistence), Docs simplifier + history. Verified in-browser with live data.
- Navbar collapses to hamburger below 1024px (7 links no longer crowd).
- Lesson: dev `codementor.db` needed `alembic upgrade head` after the goal
  migration; tests use isolated migrated DBs and were unaffected.
- Measured token usage end to end (`Completion` value object, per-provider
  extractors, stored in message `meta`, returned on turns/explain/simplify;
  `null` when the provider reports nothing — never invented).
- Review-goal prompt preambles verified by unit tests, not by live spend.
- PWA: manifest + generated icons + service worker ship in `dist/`; API
  traffic is `NetworkOnly` (no private data cached); SW registration and
  scope verified in-browser; full airplane-mode test still needs a real device.
- CI workflow runs backend pytest + frontend typecheck/build on code pushes.
- Central language registry (`services/languages.py`, 10 languages) drives
  detection, snippets, prompt guidance, and `/api/languages`; C and Rust
  added; C# fallback honestly flagged; schemas/snippets/registry consistency
  tested (suite: 73).
- Projects/milestones/tasks with AI brief generation, next-task guidance,
  and session linking (ownership-enforced, migration-tested).
- Curated `/api/resources` link catalog (links + licenses only, no scraping).
- Request-ID middleware: every response carries `X-Request-ID` (echoed when
  sent); error diagnosis without secret exposure.
- Fixed a real resume bug found by log forensics: `?session=` hydration only
  ran on mount, so same-route Continue links silently failed. It now depends
  on the param; verified with a logged-in replay (code + messages + status).

## 6. Outstanding deployment blockers (account actions)

- Neon project + `DATABASE_URL` (user).
- Backend host deploy (Render card-wall vs HF Spaces) + env vars (user pastes).
- `VITE_API_BASE_URL` repo variable → Pages rebuild (user or agent with access).
- Fresh Groq key rotation after chat exposure (user; current key works).
