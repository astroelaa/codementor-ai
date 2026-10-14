# CodeMentor AI — Product Evolution Proposal (Phase 0)

Read-only audit of the repository at `main`, verified 2026-10-14 by
inspecting code, running the test suite (58 passed), the production build,
and one live Groq mentor turn (HTTP 200). No application code was changed
for this document.

## 1. Feature matrix: verified vs gaps

| Capability | Status | Evidence |
|---|---|---|
| Register / login / logout (JWT + bcrypt) | VERIFIED | pytest + live signup/login |
| Guest mode, 1 free session, server-enforced | VERIFIED | pytest (403 on 2nd), live |
| Mentor sessions (debug/review/explain goals) | VERIFIED | live turn, grounded prompt |
| Socratic turns, JSON + SSE streaming | VERIFIED | tests + live SSE events |
| Hint budget (3, server-side), explanation check → solved | VERIFIED | pytest |
| Misconception tags, skills, streaks, badges | VERIFIED | pytest + live dashboard data |
| Dashboard / history + replay / resume / docs simplifier / learning paths | VERIFIED | pytest + in-browser, real rows |
| Language auto-detect + manual override | VERIFIED | unit tests (incl. ties/empty) |
| Token usage recording (measured only) | VERIFIED | unit tests; `null` when unreported |
| Authz: ownership, cross-user 403/404, rate limits, secret-free errors | VERIFIED | pytest |
| PWA shell (manifest/SW/safe caching) | PARTIAL | registered locally; device test pending |
| Account deletion UI | VERIFIED | Dashboard → Account (API-tested) |
| Project briefs / milestones / tasks | MISSING | no models, no endpoints |
| Line-by-line explain mode content | PARTIAL | goal exists; no step-through UI |
| Guided practice / challenges | MISSING | — |
| Curated docs / citations / retrieval | MISSING | simplifier is pure-model, no sources |
| Code execution / sandbox | MISSING (by design) | no executor anywhere in repo |
| Linters / formatters / static analysis | MISSING | none in repo |
| Settings page | PARTIAL | theme in navbar; delete on Dashboard |

## 2. Language support matrix (per layer)

| Language | UI list | Backend detect | Editor highlight | Snippet | Prompts | Linter | Execution |
|---|---|---|---|---|---|---|---|
| Python | yes | yes | full | yes | generic+name | no | no |
| JavaScript | yes | yes | full | yes | generic+name | no | no |
| TypeScript | yes | yes | full (TS mode) | yes | generic+name | no | no |
| Java | yes | yes | full | yes | generic+name | no | no |
| C++ | yes | yes | full | yes | generic+name | no | no |
| C# | yes | yes | **fallback to Java** | yes | generic+name | no | no |
| Go | yes | yes | full | yes | generic+name | no | no |
| SQL | yes | yes | full | yes | generic+name | no | no |
| C / Rust / HTML-CSS | **no** | no | no | no | no | no | no |

Notes: detector is regex heuristics (frontend mirror is best-effort; backend
is authoritative). Prompts carry the language name but no per-language concept
guidance yet. Lists are duplicated in 3 places (`detect.py`, `detect.ts`,
`schemas.py` literal) — centralize before widening coverage.

## 3. Persistence inventory

Stored: users, sessions (language/goal/code/status/score/hints), messages
(+meta incl. usage), hints, misconceptions, skills + progress, learning paths
+ items, badges, daily activity, doc simplifications. Missing: project briefs,
milestones/tasks, learning goals as first-class objects, resource metadata.
SQLite locally; Postgres via `DATABASE_URL`; migrations `64bf→f4c926f→8f967aef`.

## 4. Integration audit (existing only)

- **Groq (primary, official SDK, `openai/gpt-oss-20b`)**: live-verified.
  Free-tier quotas apply; model IDs rot — re-check on any 4xx.
- **Gemini/OpenAI/Anthropic adapters**: code-complete, never live-tested.
  Keep disabled until one is verified; do NOT add more providers.
- **Neon Postgres**: chosen, not yet provisioned (account action).
- **Render/HF**: configs committed, not yet deployed (card wall on Render).
- **Judge0**: not integrated — evaluate only if execution becomes required.
- **GitHub repo integration**: none — defer unless a milestone needs it.

## 5. Limits affecting the plan

Security: JWT in localStorage (accepted for Pages), guest caps server-side,
no code execution anywhere (keep it that way until a sandbox exists).
Cost: Groq free tier is the only confirmed-free inference; streaming doubles
calls per turn (reply + scoring) by design. Licensing: no LICENSE file yet —
add MIT before public release; Exercism content is CC-BY-SA-friendly but verify
per-track; MDN is CC-BY-SA 2.5 (attribute + link); never scrape wholesale.
Deploy: Pages static only; backend needs a host + Neon; free tiers sleep.

## 6. Product direction (mapped to existing components)

- **Learn With Me** = extend `goal=explain` + new `practice` session kind reusing
  messages/scoring; misconception → skill → path loop already exists.
- **Build With Me** = new `projects` + `milestones`/`tasks` tables, brief
  generator prompt, per-task mentor sessions linked by `project_id`; resume
  uses stored context (same pattern as `?session=` resume).
- **Improve My Code** = today's debug/review goals + severity-tagged findings
  inside the existing `MentorFeedback` reply contract (no schema break).

## 7. Phased roadmap

1. **Language registry** — one `LANGUAGES` source of truth (backend module +
   generated TS), aliases/extensions, per-language prompt notes + official doc
   links; acceptance: no duplicated lists, C# honest labeling.
2. **Mentor workflows** — findings/severity structure in replies, step-through
   explain UI, practice sessions; acceptance: pytest + live turns per goal.
3. **Projects + milestones** — models, migration, brief/task endpoints, UI;
   acceptance: project survives refresh/login, tasks drive sessions.
4. **Resources + citations** — curated link metadata (no scraping), mentor cites
   sources in replies; acceptance: every citation resolves, licenses recorded.
5. **Retrieval/execution evaluation** — spike only: keyword doc lookup first;
   Judge0 costing + isolation review; acceptance: decision doc, no sandbox yet
   unless justified.
6. **Harden + deploy** — MIT license, backup runbook test, prod smoke, docs.

## 8. Risks / open questions

- Groq free-tier longevity; single-provider risk until a fallback is verified.
- Regex detection quality for C-family languages (tree-sitter later?).
- Practice/exercise licensing per source (verify before storing).
- Free-host sleep vs UX promises; Postgres provisioning still pending.
