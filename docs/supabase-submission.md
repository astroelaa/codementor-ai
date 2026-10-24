# CodeMentor AI Supabase submission

## Project and function

CodeMentor AI is a web platform that helps programmers learn and improve through an AI Socratic programming mentor. Authenticated users keep private debugging sessions, messages, projects, milestones, tasks, learning progress, and notifications. Supabase Auth manages registered and anonymous identities, Supabase Postgres stores application data, and Row Level Security prevents users from reading or changing another user's private data.

## Links

- Repository: https://github.com/astroelaa/codementor-ai
- Vercel frontend: https://codementor-ai.vercel.app
- Vercel backend: https://codementor-ai-api.vercel.app
- GitHub Pages frontend: https://astroelaa.github.io/codementor-ai/

## Tables and RLS status

RLS is enabled and forced on every application table:

| Table | RLS |
|---|---|
| users | Enabled and forced |
| sessions | Enabled and forced |
| messages | Enabled and forced |
| hints | Enabled and forced |
| misconceptions | Enabled and forced |
| projects | Enabled and forced |
| milestones | Enabled and forced |
| project_tasks | Enabled and forced |
| notifications | Enabled and forced |
| learning_paths | Enabled and forced |
| path_items | Enabled and forced |
| skill_progress | Enabled and forced |
| user_badges | Enabled and forced |
| daily_activity | Enabled and forced |
| doc_simplifications | Enabled and forced |
| skills | Enabled and forced |
| badges | Enabled and forced |

## RLS policy pattern

Owner tables use `auth.uid() = user_id` for select, insert, update, and delete. The profile table uses `auth.uid() = id`. Child tables use an `EXISTS` policy that checks ownership of the related parent row. Reference tables are readable only by authenticated users. The backend also applies explicit ownership filters and executes requests with the authenticated database role and JWT claims as defense in depth.

## Isolation testing

Isolation was tested through the backend API and Supabase PostgREST using real Supabase access tokens. The automated test creates two registered users and an anonymous guest, creates sessions, messages, a project hierarchy, and notifications, then verifies that each identity sees only its own rows. Cross-user reads return no rows or an ownership error, cross-user updates and deletes do not change the owner's rows, unauthenticated requests return no protected rows, and guest access cannot expose registered-user data. Test identities are removed and cleanup is verified.

The live two-user experiment was also run on both production frontends. Account A created a project named `Private A Project`. Account B logged in separately and saw an empty Projects list on both Vercel and GitHub Pages. Opening Account A's project URL while authenticated as B redirected to the public app and did not expose the project. Account A and Account B were deleted after the experiment.
