# CodeMentor AI — Product Feature Matrix

> **Historical document (pre-Supabase migration).** Auth endpoints, `is_verified`,
> and guest-token details below describe the previous system. See the root
> `README.md` for the current Supabase Auth + RLS architecture.

Living audit of every user-facing feature. How to read the columns:

- **Frontend** — real UI access on `https://codementor-ai.vercel.app`
  (verified in the deployed bundle across all 13 lazy chunks, 2026-10-17).
- **API** — backend endpoint that backs the feature.
- **Persisted** — data survives refresh, logout, and reload from the database.
- **Local** — covered by the pytest suite (fake LLM, no network).
- **Prod** — exercised against production **2026-10-17** with a disposable
  account (deleted after the audit; exact status codes recorded below).
- **Status** — `working` | `broken` (real defect found in prod) | `partial`.

Production run summary: **53 API checks — 43 OK.** Every `broken` status below
was reproduced with a real request/response against production, not inferred.
Script-side mistakes in the first audit pass (wrong field names, wrong key
names) were corrected and are NOT counted as product defects.

| Feature | Frontend | API | Persisted | Local | Prod | Status |
|---|---|---|---|---|---|---|
| Signup (creates account + welcome email path) | `/signup` | `POST /api/auth/signup` → 201 | users row + verified=false | ✅ | ✅ 201 | working |
| Login / logout / JWT session | `/login` | `POST /api/auth/login` → 200 | token_version revocation | ✅ | ✅ 200 | working |
| Profile data (+ preferred language / experience / learning goal) | `/profile` | `GET/PATCH /api/auth/me` → 200 | users columns | ✅ | ✅ 200 round-trip | working |
| Email verification state + resend (3/h cap) | banner + `/profile` | `POST /api/auth/resend-verification` → 200 | budget enforced | ✅ (budget) | ✅ 200 (send path live-delivered, user-confirmed 2026-10-16) | working |
| Verify-email with token | `/verify?token=` | `POST /api/auth/verify-email` | flips is_verified; bogus token → 400 | ✅ | ✅ 400 on bogus token (link-click delivery verified separately) | working |
| Forgot password (generic response, no account leak) | `/forgot` | `POST /api/auth/forgot-password` → 200 | single-use 1h token | ✅ | ✅ 200 | working |
| Reset password (revokes sessions) | `/reset?token=` | `POST /api/auth/reset-password` | new hash + token bump; bogus token → 400 | ✅ | ✅ 400 on bogus token | working |
| Change password while logged in (revokes other sessions) | `/profile` | `POST /api/auth/change-password` → 200 | token_version bump + notice email | ✅ | ✅ 200; earlier prod test proved old-token 401 | working |
| Delete account (password re-auth) | `/profile` danger zone | `DELETE /api/auth/me` | cascades ALL rows; wrong pw → 401; ok → 204 | ✅ | ✅ 401/204 + post-delete login 401 | working |
| Code snippets gallery | Workspace | `GET /api/snippets` | seeded | ✅ | ✅ 200 | working |
| Language registry / docs links | Workspace, Docs | `GET /api/languages` | seeded | ✅ | ✅ 200 | working |
| Resource library (links only) | Docs | `GET /api/resources` | seeded | ✅ | ✅ 200 | working |
| Create session (practice mode, language detect) | `/app` | `POST /api/sessions` → 201 | sessions row | ✅ | ✅ 201 | working |
| Create session (my code mode) | `/app` | `POST /api/sessions` `mode="mycode"` | mode column | ✅ (unit) | ✅ 201 (first-pass script used a wrong literal and got the expected 422) | working |
| Guest mode (1 free session, no account) | `/app` | guest token cookie/header | guest_token column | ✅ | limited by design (audit used a real account); covered by tests | working |
| Session list + resume/replay | `/app`, `/history` | `GET /api/sessions`, `GET /api/sessions/{id}` | messages live in DB | ✅ | ✅ 200, transcript + meta present | working |
| Mentor turn (normal): evaluates reply vs previous question, Socratic, no fixed code | `/app` chat | `POST /api/sessions/{id}/messages` → 200 | message + meta(evaluation, sources) | ✅ | ✅ 200 — real reply: "Your loop correctly sums… What will happen if you call average([])?" | working |
| **Mentor turn resilience: transient provider failure or non-JSON model reply** | — | same endpoint | n/a | ✅ resilience suite (retry-once, Retry-After honoured and capped at 8 s, busy-503 mapping, streaming busy event) | ✅ retried live (audit's 3× 502 + probe 503 no longer user-visible when a single retry recovers them; provider 429s/timeouts on every provider now come back as the friendly 503 "the mentor is busy", never a generic outage; double-blip still surfaces the error by contract) | working |
| Streaming mentor replies (SSE) | `/app` (getReader) | `POST /api/sessions/{id}/messages/stream` → 200 SSE | message + meta | ✅ 8 streaming regression tests | ✅ live 200: visible text clean (no JSON envelope), done event correct | working |
| Hint budget (3/session, decremented, 403 when exhausted) | hint button + dots | `POST /api/sessions/{id}/hints` | hints_used + Hint rows | ✅ | ✅ 200/200/403 pattern observed (one 502 inside the sequence — see resilience row) | working (budget) |
| Solve flow: explain fix in own words, weak fails, strong passes + badges | solve box | `POST /api/sessions/{id}/explain` → 200 | status solved + solved_at, badges | ✅ | ✅ weak → passed:false; strong → passed:true score 90; solved; badges [first-solve]; then 409 on new messages | working |
| Dashboard (totals, streak_days, weak spots, recent) | `/dashboard` | `GET /api/dashboard` | derived + daily_activity | ✅ | ✅ 200 with streak_days etc. after activity | working |
| Skill progress (per misconception type) | `/dashboard` | `GET /api/skills` | skill_progress rows | ✅ | ✅ 200 | working |
| Learning path (auto items, regenerate, mark done) | `/dashboard` | `GET /api/learning-path`, `POST …/regenerate`, `PATCH …/items/{id}` | learning_paths + path_items | ✅ | ✅ 200/200/200 | working |
| Project briefs (AI objective + milestones + tasks) | `/projects` | `POST /api/projects/{id}/brief` | objective, architecture, milestones, tasks | ✅ | ⚠️ 200 with 5 milestones in probe; **502 seen in audit run 1** (same resilience defect) | working (fragile) |
| Projects CRUD + milestones + tasks + next task | `/projects` | `POST/GET/PATCH /api/projects…` | projects, milestones, project_tasks | ✅ | ✅ 201/200/201/201/200 + next-task guidance | working |
| Docs simplifier (grounded explanation + question) | `/docs` | `POST /api/docs/simplify`, `GET /api/docs/history` | doc_simplifications | ✅ | ✅ 200 + history 200 | working |
| Misconception memory (list + forget) | Workspace/Dashboard | `GET /api/memory`, `DELETE /api/memory/misconceptions/{id}` | misconceptions rows | ✅ | ✅ 200 (no rows existed this run to delete; delete path unit-covered) | working |
| Notifications (solve event, unread count, mark read, read-all) | bell menu | `GET/POST/PATCH /api/notifications…` | notifications rows | ✅ | ✅ solve notification created; unread/read/read-all 200 | working |
| Anti-repetition (non-streaming retry-once) | invisible | internal (`is_repeat` + nudge) | — | ✅ | partial: repeat not reproduced live this run; unit-proven | working |
| **Anti-repetition (streaming)** | invisible | internal (pre-emit buffer + one retry) | — | ✅ | ✅ live: no verbatim repeats; model can still rephrase the same question under the similarity threshold | working |
| Theme (dark/light) persistence | navbar + profile | `PATCH /api/auth/me` theme | users.theme + localStorage | ✅ | ✅ (previous prod round) | working |

## Broken features found (fixed in phase 2, verified in production)

1. **Mentor reliability (normal, hints, brief).** Transient failures reached
   the user as 502/503 with no single retry:
   - audit run 1: `POST …/messages` → **502** `{"detail":"The mentor returned
     an unusable response. Try again."}`; 3rd hint → **502** same body;
     project brief → **502** same body (all parse/"unusable" paths);
   - audit run 2 (probe): one turn → **503** `{"code":503}` "no AI provider is
     configured or reachable" (transient provider miss).
   **Fixed** (`complete_with_retry`, one retry on transient provider errors
   and non-JSON/schema-invalid replies) and verified live 2026-10-17.
2. **Streaming raw-JSON leak.** In the STREAMING endpoint the model twice
   replied with the internal JSON envelope; the endpoint streamed it verbatim
   to the UI (visible `{"reply": "…"}` in the chat) and persisted it.
   **Fixed**: pre-emit buffering, envelope `reply` extraction, one bounded
   retry, and repeat detection before any token reaches the client. Verified
   live 2026-10-17 with clean streamed text.

Remaining honest limitation (documented, not fixable deterministically): the
model may occasionally rephrase the same guiding question in different words
that fall under the 0.82 similarity threshold — prompts demand fresh wording
and the forced `greeting`/`off_target` verdicts guarantee the assessment side.

Everything else audited: 43/53 checks OK, no functional regressions found.
