import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  Award,
  Check,
  Flame,
  Layers,
  RefreshCw,
  Target,
  Trash2,
} from "lucide-react";
import { ApiError, api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useToast } from "../lib/toast";
import { Reveal } from "../components/Reveal";
import { EmptyState } from "../components/bits";

const BADGE_ICONS: Record<string, typeof Award> = {
  flag: Award,
  check: Check,
  lightbulb: Target,
  flame: Flame,
  languages: Layers,
  "graduation-cap": Award,
};

export function Dashboard() {
  const { user, logout, refresh } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [showDelete, setShowDelete] = useState(false);
  const [confirmWord, setConfirmWord] = useState("");

  const dash = useQuery({
    queryKey: ["dashboard"],
    queryFn: api.dashboard,
    enabled: !!user,
    retry: 1,
  });
  const path = useQuery({
    queryKey: ["learning-path"],
    queryFn: api.learningPath,
    enabled: !!user,
    retry: 1,
  });
  const memory = useQuery({
    queryKey: ["memory"],
    queryFn: api.readMemory,
    enabled: !!user,
    retry: 1,
  });

  const regen = useMutation({    mutationFn: api.regeneratePath,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["learning-path"] });
      toast("success", "Learning path regenerated from your weak spots.");
    },
    onError: (e) =>
      toast("error", e instanceof ApiError ? e.message : "Could not regenerate."),
  });
  const removeAccount = useMutation({
    mutationFn: () => api.deleteAccount(),
    onSuccess: async () => {
      await logout();
      navigate("/");
      toast("success", "Account and all data deleted.");
    },
    onError: (e) =>
      toast("error", e instanceof ApiError ? e.message : "Could not delete."),
  });
  const forget = useMutation({
    mutationFn: (id: string) => api.deleteMisconception(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["memory"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      toast("success", "Memory entry deleted.");
    },
    onError: (e) =>
      toast("error", e instanceof ApiError ? e.message : "Could not delete."),
  });
  const prefs = useMutation({
    mutationFn: (patch: { notify_security_emails?: boolean; notify_progress_emails?: boolean }) =>
      api.updatePreferences(patch),
    onSuccess: () => {
      void refresh();
      toast("success", "Email preferences saved.");
    },
    onError: (e) =>
      toast("error", e instanceof ApiError ? e.message : "Could not save."),
  });
  const setItem = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      api.updatePathItem(id, status),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["learning-path"] }),
    onError: (e) =>
      toast("error", e instanceof ApiError ? e.message : "Could not update."),
  });

  if (!user) {
    return (
      <main className="mx-auto w-[min(760px,92%)] py-16">
        <EmptyState
          title="Sign in to see your dashboard"
          body="Your sessions, streak, badges, and learning path live here once you have an account."
        />
        <div className="mt-5 flex justify-center gap-3">
          <Link to="/login" className="btn btn-ghost">Log in</Link>
          <Link to="/signup" className="btn btn-primary">Sign up free</Link>
        </div>
      </main>
    );
  }

  if (dash.isPending) {
    return (
      <main className="mx-auto flex w-[min(1200px,92%)] flex-col gap-3 py-12" aria-label="Loading dashboard">
        <div className="skeleton h-8 w-1/3" />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="skeleton h-24" />
          ))}
        </div>
      </main>
    );
  }

  if (dash.isError) {
    return (
      <main className="mx-auto w-[min(760px,92%)] py-16">
        <EmptyState
          title="Could not load the dashboard"
          body={dash.error instanceof ApiError ? dash.error.message : "Try again in a moment."}
        />
        <div className="mt-5 text-center">
          <button type="button" onClick={() => void dash.refetch()} className="btn btn-ghost">
            <RefreshCw size={15} strokeWidth={1.5} /> Retry
          </button>
        </div>
      </main>
    );
  }

  const d = dash.data;
  const isNew = d.total_sessions === 0;

  return (
    <main className="mx-auto w-[min(1200px,92%)] py-8 md:py-12">
      <Reveal>
        <p className="eyebrow">Dashboard</p>
        <h1 className="h2-serif mt-2 text-3xl md:text-4xl">Your progress</h1>
      </Reveal>

      {isNew ? (
        <Reveal delay={0.05}>
          <div className="mt-6">
            <EmptyState
              title="No sessions yet"
              body="Start your first debugging session and your stats, weak spots, badges, and learning path will appear here — computed from real sessions only."
            />
            <div className="mt-5 text-center">
              <Link to="/app" className="btn btn-primary">
                Start debugging <ArrowRight size={16} strokeWidth={1.5} />
              </Link>
            </div>
          </div>
        </Reveal>
      ) : (
        <>
          <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {[
              { label: "Sessions", value: d.total_sessions },
              { label: "Solved", value: d.solved_sessions },
              { label: "Day streak", value: d.streak_days },
              { label: "Avg. understanding", value: `${d.avg_understanding}/100` },
            ].map((s, i) => (
              <Reveal key={s.label} delay={i * 0.05}>
                <div className="card p-5">
                  <p className="text-3xl font-extrabold text-(--accent-text)">{s.value}</p>
                  <p className="mt-1 text-[13px] text-(--muted)">{s.label}</p>
                </div>
              </Reveal>
            ))}
          </div>

          <div className="mt-5 grid items-start gap-5 lg:grid-cols-2">
            <Reveal>
              <div className="card p-6">
                <h2 className="font-bold">Weak spots</h2>
                <p className="mt-0.5 text-[13px] text-(--muted)">From misconceptions you actually expressed.</p>
                {d.weak_spots.length === 0 ? (
                  <p className="mt-4 text-sm text-(--muted)">None recorded yet — good sign.</p>
                ) : (
                  <ul className="mt-4 flex flex-col gap-3">
                    {d.weak_spots.map((w) => {
                      const max = d.weak_spots[0].count || 1;
                      return (
                        <li key={w.type}>
                          <div className="flex items-center justify-between text-sm">
                            <span className="font-mono text-[13px]">{w.type}</span>
                            <span className="text-(--muted)">×{w.count}</span>
                          </div>
                          <div className="meter mt-1.5">
                            <div style={{ width: `${Math.round((w.count / max) * 100)}%` }} />
                          </div>
                        </li>
                      );
                    })}
                  </ul>
                )}
                {d.languages.length > 0 && (
                  <div className="mt-5 flex flex-wrap gap-1.5 border-t border-(--border) pt-4">
                    {d.languages.map((l) => (
                      <span key={l.language} className="tag">
                        {l.language} · {l.sessions}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </Reveal>

            <Reveal delay={0.06}>
              <div className="card p-6">
                <h2 className="font-bold">Badges</h2>
                <p className="mt-0.5 text-[13px] text-(--muted)">Earned from recorded events, never invented.</p>
                {d.badges.length === 0 ? (
                  <p className="mt-4 text-sm text-(--muted)">No badges yet. Solve a session to earn the first one.</p>
                ) : (
                  <ul className="mt-4 grid gap-2 sm:grid-cols-2">
                    {d.badges.map((b) => {
                      const Icon = BADGE_ICONS[b.icon] ?? Award;
                      return (
                        <li key={b.slug} className="flex items-center gap-2.5 rounded-xl border border-(--border) bg-(--bg-soft) px-3 py-2.5" title={b.description}>
                          <Icon size={16} strokeWidth={1.5} className="shrink-0 text-(--accent-text)" />
                          <span className="text-[13px] font-semibold">{b.name}</span>
                        </li>
                      );
                    })}
                  </ul>
                )}
              </div>
            </Reveal>
          </div>

          <Reveal delay={0.08}>
            <div className="card mt-5 p-6">
              <h2 className="font-bold">Learning memory</h2>
              <p className="mt-0.5 text-[13px] text-(--muted)">
                What the mentor remembers about your mistakes. Delete anything
                you don't want kept — counters stay cumulative.
              </p>
              {!memory.data || memory.data.misconceptions.length === 0 ? (
                <p className="mt-4 text-sm text-(--muted)">
                  {memory.isPending ? "Loading…" : "No stored misconceptions yet."}
                </p>
              ) : (
                <ul className="mt-4 flex flex-col gap-2">
                  {memory.data.misconceptions.map((m) => (
                    <li
                      key={m.id}
                      className="flex items-start gap-2.5 rounded-xl border border-(--border) bg-(--bg-soft) px-3 py-2.5"
                    >
                      <div className="min-w-0 flex-1">
                        <p className="font-mono text-[13px] font-semibold">{m.type}</p>
                        <p className="text-[13px] text-(--muted)">{m.description}</p>
                      </div>
                      <button
                        type="button"
                        onClick={() => forget.mutate(m.id)}
                        disabled={forget.isPending}
                        aria-label={`Delete memory: ${m.type}`}
                        title="Delete this memory"
                        className="grid size-7 shrink-0 place-items-center rounded-lg border border-(--border) text-(--muted) transition-colors hover:border-(--danger) hover:text-(--danger)"
                      >
                        <Trash2 size={14} strokeWidth={1.5} />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </Reveal>

          <Reveal delay={0.08}>
            <div className="card mt-5 p-6">
              <div className="flex flex-wrap items-center gap-3">
                <div>
                  <h2 className="font-bold">Learning path</h2>
                  <p className="mt-0.5 text-[13px] text-(--muted)">
                    {path.data
                      ? `Generated from: ${path.data.source === "weak-spots" ? "your weak spots" : "starter picks"} — progress is measured separately.`
                      : "Built from your weak spots when you generate it."}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => regen.mutate()}
                  disabled={regen.isPending}
                  className="btn btn-ghost btn-sm ml-auto"
                >
                  <RefreshCw size={14} strokeWidth={1.5} />
                  {regen.isPending ? "Building…" : path.data ? "Regenerate" : "Generate"}
                </button>
              </div>
              {!path.data ? (
                <p className="mt-4 text-sm text-(--muted)">No active path. Generate one to get focused next steps.</p>
              ) : (
                <ul className="mt-4 flex flex-col gap-2">
                  {path.data.items.map((item) => (
                    <li key={item.id} className="flex items-start gap-3 rounded-xl border border-(--border) bg-(--bg-soft) px-3.5 py-2.5">
                      <select
                        aria-label={`Status of ${item.title}`}
                        value={item.status}
                        disabled={setItem.isPending}
                        onChange={(e) => setItem.mutate({ id: item.id, status: e.target.value })}
                        className="mt-0.5 rounded-lg border border-(--border) bg-(--surface-2) px-1.5 py-1 text-xs font-semibold"
                      >
                        <option value="todo">Todo</option>
                        <option value="doing">Doing</option>
                        <option value="done">Done</option>
                      </select>
                      <div>
                        <p className={`text-sm font-semibold ${item.status === "done" ? "text-(--muted) line-through" : ""}`}>
                          {item.title}
                        </p>
                        <p className="text-[13px] text-(--muted)">{item.detail}</p>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </Reveal>

          <Reveal delay={0.1}>
            <div className="card mt-5 p-6">
              <div className="flex items-center gap-3">
                <h2 className="font-bold">Recent sessions</h2>
                <Link to="/history" className="ml-auto text-sm font-semibold text-(--accent-text)">
                  All history <ArrowRight size={14} strokeWidth={1.5} className="inline" />
                </Link>
              </div>
              {d.recent_sessions.length === 0 ? (
                <p className="mt-4 text-sm text-(--muted)">Nothing here yet.</p>
              ) : (
                <ul className="mt-4 flex flex-col gap-2">
                  {d.recent_sessions.map((s) => (
                    <li key={s.id}>
                      <Link
                        to={`/history?s=${s.id}`}
                        className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-xl border border-(--border) bg-(--bg-soft) px-3.5 py-2.5 text-sm transition-colors hover:border-(--border-strong)"
                      >
                        <span className="font-mono text-[13px]">{s.language}</span>
                        <span className={`tag ${s.status === "solved" ? "border-(--success)" : ""}`}>{s.status}</span>
                        <span className="text-(--muted)">{s.message_count} messages</span>
                        <span className="ml-auto font-mono text-[13px] text-(--muted)">{s.understanding_score}/100</span>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </Reveal>

          <Reveal delay={0.12}>
            <div className="card mt-5 p-6">
              <h2 className="font-bold">Account</h2>
              {user.is_anonymous ? (
                <p className="mt-1 text-sm text-(--muted)">
                  You are using a guest session.{" "}
                  <Link to="/signup" className="font-semibold text-(--accent-text)">
                    Create a free account
                  </Link>{" "}
                  for unlimited sessions and a permanent history.
                </p>
              ) : (
                <p className="mt-1 text-sm text-(--muted)">
                  Signed in as{" "}
                  <span className="font-semibold text-(--text)">{user.email}</span>
                  {user.display_name ? ` (${user.display_name})` : ""}.
                </p>
              )}
              {!user.is_anonymous && (
                <div className="mt-4 flex flex-col gap-2.5 border-t border-(--border) pt-4">
                  <p className="label">Email preferences</p>
                  <label className="flex cursor-pointer items-start gap-2.5 text-sm">
                    <input
                      type="checkbox"
                      className="mt-1 size-4 accent-[#7C5CFF]"
                      checked={user.notify_security_emails}
                      onChange={(e) => prefs.mutate({ notify_security_emails: e.target.checked })}
                    />
                    <span>
                      <span className="font-semibold">Security emails</span>
                      <span className="block text-[13px] text-(--muted)">Password changes and important account notices. Recommended on.</span>
                    </span>
                  </label>
                  <label className="flex cursor-pointer items-start gap-2.5 text-sm">
                    <input
                      type="checkbox"
                      className="mt-1 size-4 accent-[#7C5CFF]"
                      checked={user.notify_progress_emails}
                      onChange={(e) => prefs.mutate({ notify_progress_emails: e.target.checked })}
                    />
                    <span>
                      <span className="font-semibold">Progress emails</span>
                      <span className="block text-[13px] text-(--muted)">A note when you solve a session. Off by default — no spam, ever.</span>
                    </span>
                  </label>
                </div>
              )}
              {!showDelete ? (
                <button
                  type="button"
                  onClick={() => setShowDelete(true)}
                  className="btn btn-ghost btn-sm mt-4 border-(--danger) text-(--danger)"
                >
                  Delete account and all data…
                </button>
              ) : (
                <form
                  className="mt-4 flex max-w-sm flex-col gap-2"
                  onSubmit={(e) => {
                    e.preventDefault();
                    if (confirmWord === "DELETE") removeAccount.mutate();
                  }}
                >
                  <p className="text-sm text-(--muted)">
                    This permanently deletes your account, sessions, messages,
                    and progress. This cannot be undone.
                  </p>
                  <label className="label" htmlFor="delete-confirm">
                    Type <strong>DELETE</strong> to confirm
                  </label>
                  <input
                    id="delete-confirm"
                    className="input"
                    value={confirmWord}
                    onChange={(e) => setConfirmWord(e.target.value)}
                    autoComplete="off"
                    placeholder="DELETE"
                  />
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => {
                        setShowDelete(false);
                        setConfirmWord("");
                      }}
                      className="btn btn-ghost btn-sm"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={removeAccount.isPending || confirmWord !== "DELETE"}
                      className="btn btn-sm border-(--danger) bg-(--danger) text-white"
                    >
                      {removeAccount.isPending ? "Deleting…" : "Yes, delete everything"}
                    </button>
                  </div>
                </form>
              )}
            </div>
          </Reveal>
        </>
      )}
    </main>
  );
}
