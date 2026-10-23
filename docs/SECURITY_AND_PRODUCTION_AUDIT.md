# CodeMentor AI — Security & Production Audit

> **Historical document (pre-Supabase migration).** JWT/bcrypt and email
> verification details below describe the previous system. See the root
> `README.md` for the current Supabase Auth + PostgreSQL + RLS architecture.

Audited 2026-10-14 against the code at `main` (74 backend tests green,
frontend build green). Updated 2026-10-17: production is live on Vercel
(frontend `codementor-ai.vercel.app`, backend `codementor-ai-api.vercel.app`,
Supabase Postgres, Gmail SMTP verification; **144 backend tests green**).
Severity: HIGH / MED / LOW / NOTE.

## 1. Authentication and accounts

- Passwords: bcrypt via `app/security.py`, never stored plain. **OK.**
- JWT: HS256, `sub` + `iat`/`exp`, 7-day expiry, dev secret refused at boot
  in production. Invalid/expired tokens → 401 (tested). **OK.**
- **MED — no server-side token revocation.** Logout only deletes the client
  token; a stolen token stays valid up to 7 days. **FIXED:** `token_version`
  counter on the user row (JWT carries `ver`; only the current version is
  accepted; password reset bumps the version). Integer comparison avoids the
  clock-resolution race that timestamps would introduce (proven by test).
- Email verification: **IMPLEMENTED** (hashed single-use tokens, 24h TTL,
  resend capped 3/hour, `#/verify?token=` + resend UI, unverified keep full
  access with banner — no lockouts).
- Password recovery: **IMPLEMENTED** (generic responses, 1h single-use
  tokens, old sessions revoked, `#/forgot` + `#/reset` pages).
- Logged-in password change: **IMPLEMENTED** (`POST /api/auth/change-password`
  requires the current password, rejects reusing the same password, bumps
  `token_version` to revoke other sessions, returns a fresh token for the
  current session; tested 2026-10-17 in production).
- Account deletion: `DELETE /api/auth/me` re-checks the password and
  cascades all rows (tested in production 2026-10-17: wrong password 401,
  correct password 204, post-delete login 401).
- Guest caps enforced server-side; ownership checks on all nested resources
  (tested, incl. cross-user 404s). **OK.**
- Login/signup rate-limited (10/min/IP); login error is generic, but signup
  409 reveals address existence — standard trade-off, documented here.
- No sessions table server-side (stateless JWT) — acceptable at this scale.

## 2. API and application security

- Pydantic validation + size caps on all free text (code 8000, messages 4000,
  docs 4000, titles 200). **OK.**
- CORS: explicit origin list, no credentials, no wildcard. **OK.**
- AI quota: 30 mentor calls/min/IP + 60-message session caps + 700-token
  output cap; failures → 502/503 envelope. In-memory limiter is correct for a
  single free instance (documented limitation for multi-instance).
- Errors: `{detail, code}` only; raw exceptions logged server-side;
  `X-Request-ID` echo for correlation. **OK.**
- Logs: no passwords, keys, tokens, or prompts (grep-verified). **OK.**
- Browser storage: JWT + guest token in `localStorage` (XSS trade-off,
  required for static hosting without same-site cookies; mitigated by expiry
  + logout + no token in logs).
- Dependencies (installed): FastAPI 0.121, SQLAlchemy 2.0.44, Pydantic 2.12,
  PyJWT 2.15, bcrypt 5.0, httpx 0.28, groq SDK 1.7, uvicorn 0.38 — current,
  no known critical advisories for this stack at audit time.
- Git history scanned (`gsk_`, `ghp_`): **no secrets committed**. `dist/`,
  `node_modules/`, `*.db`, `.env` untracked/ignored. Frontend bundle contains
  only the public `VITE_API_BASE_URL`.
- DB: FKs + unique constraints; cascades scoped by user FK; Alembic chain of
  4 verified on scratch DBs; no destructive ops at boot.

## 3. PWA and frontend

- Manifest + icons + SW generated; `/api/*` is `NetworkOnly` (no private data
  cached); update prompt + offline notice in UI. Device install test pending.
- No frontend unit-test runner (build + tsc + browser checks instead).

## 4. Implemented this session (all tested)

1. Email verification (hashed single-use tokens, resend limits, link compatible
   with `#/verify?token=`), unverified users keep full access + banner (no lockouts).
2. Password reset (hashed single-use tokens, generic responses, session
   invalidation via `token_version` counter).
3. SMTP/console email abstraction; all secrets server-side.
4. Persistent notifications (DB table, ownership, unread count, preferences).
5. Memory: session recap + project context injection + inspectable endpoint.
6. RAG/LangGraph: evaluated — deferred with reasons (see proposal doc).

## 5. Standing risks

- Old Groq key (exposed in chat) must be deleted on the Groq dashboard —
  production already runs on the rotated key.
- In-memory rate limiter is single-process correct; fine on one Vercel
  instance per request burst, but multi-instance scaling would need a shared
  store.
- Free-tier sleep/quotas on Vercel/Supabase/Groq.
- `codementor-ai.vercel.app` is a deployment alias rather than a project
  domain — cosmetic/ops issue only (documented in deployment-checklist).
