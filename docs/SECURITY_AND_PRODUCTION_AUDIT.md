# CodeMentor AI — Security & Production Audit

Audited 2026-10-14 against the code at `main` (74 backend tests green,
frontend build green). Severity: HIGH / MED / LOW / NOTE.

## 1. Authentication and accounts

- Passwords: bcrypt via `app/security.py`, never stored plain. **OK.**
- JWT: HS256, `sub` + `iat`/`exp`, 7-day expiry, dev secret refused at boot
  in production. Invalid/expired tokens → 401 (tested). **OK.**
- **MED — no server-side token revocation.** Logout only deletes the client
  token; a stolen token stays valid up to 7 days. Fix planned: `token_valid_after`
  on the user row, enforced at auth, bumped on password reset.
- Email verification: **MISSING** (no columns, no endpoints). Planned Phase 2.
- Password recovery: **MISSING**. Planned Phase 2 with revocation above.
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

## 4. Gaps being implemented next (in order)

1. Email verification (hashed single-use tokens, resend limits, link compatible
   with `#/verify?token=`), unverified users keep full access + banner (no lockouts).
2. Password reset (hashed single-use tokens, generic responses, session
   invalidation via `token_valid_after`).
3. SMTP/console email abstraction; all secrets server-side.
4. Persistent notifications (DB table, ownership, unread count, preferences).
5. Memory: session recap + project context injection + inspectable endpoint.
6. RAG/LangGraph: evaluated — deferred with reasons (see proposal doc).

## 5. Standing risks

- Chat-exposed Groq key + tokens must be rotated/deleted (user action).
- Production Postgres + host deploy unverified (account actions pending).
- Free-tier sleep/quotas; single-process limiter; regex detector heuristics.
