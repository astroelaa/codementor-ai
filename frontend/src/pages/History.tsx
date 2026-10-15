import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Bot, Play, RefreshCw } from "lucide-react";
import { ApiError, api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { Reveal } from "../components/Reveal";
import { EmptyState } from "../components/bits";

export function History() {
  const { user } = useAuth();
  const [params] = useSearchParams();
  const [openId, setOpenId] = useState<string | null>(params.get("s"));

  const list = useQuery({
    queryKey: ["sessions"],
    queryFn: api.listSessions,
    enabled: !!user,
    retry: 1,
  });
  const detail = useQuery({
    queryKey: ["session", openId],
    queryFn: () => api.getSession(openId!),
    enabled: !!user && !!openId,
    retry: 1,
  });

  const openSession = useMemo(
    () => (list.data ?? []).find((s) => s.id === openId) ?? null,
    [list.data, openId],
  );

  if (!user) {
    return (
      <main className="mx-auto w-[min(760px,92%)] py-16">
        <EmptyState
          title="Sign in to see your history"
          body="Past sessions, replays, and continue-where-you-left-off live here."
        />
        <div className="mt-5 flex justify-center gap-3">
          <Link to="/login" className="btn btn-ghost">Log in</Link>
          <Link to="/signup" className="btn btn-primary">Sign up free</Link>
        </div>
      </main>
    );
  }

  return (
    <main className="mx-auto w-[min(1200px,92%)] py-8 md:py-12">
      <Reveal>
        <p className="eyebrow">History</p>
        <h1 className="h2-serif mt-2 text-3xl md:text-4xl">Past sessions</h1>
      </Reveal>

      {list.isPending ? (
        <div className="mt-6 flex flex-col gap-2" aria-label="Loading history">
          <div className="skeleton h-14" />
          <div className="skeleton h-14" />
          <div className="skeleton h-14" />
        </div>
      ) : list.isError ? (
        <div className="mt-6">
          <EmptyState
            title="Could not load history"
            body={list.error instanceof ApiError ? list.error.message : "Try again in a moment."}
          />
          <div className="mt-5 text-center">
            <button type="button" onClick={() => void list.refetch()} className="btn btn-ghost">
              <RefreshCw size={15} strokeWidth={1.5} /> Retry
            </button>
          </div>
        </div>
      ) : (list.data ?? []).length === 0 ? (
        <div className="mt-6">
          <EmptyState
            title="No sessions yet"
            body="Your debugging history will appear here — every session you start, with its full replay."
          />
          <div className="mt-5 text-center">
            <Link to="/app" className="btn btn-primary">Start your first session</Link>
          </div>
        </div>
      ) : (
        <div className="mt-6 grid items-start gap-5 lg:grid-cols-[340px_1fr]">
          <ul className="flex max-h-[60vh] flex-col gap-2 overflow-y-auto pr-1">
            {(list.data ?? []).map((s) => (
              <li key={s.id}>
                <button
                  type="button"
                  onClick={() => setOpenId(openId === s.id ? null : s.id)}
                  aria-expanded={openId === s.id}
                  className={`w-full rounded-xl border px-4 py-3 text-left transition-colors ${
                    openId === s.id
                      ? "border-(--accent) bg-(--accent-soft)"
                      : "border-(--border) bg-(--surface) hover:border-(--border-strong)"
                  }`}
                >
                  <span className="flex items-center gap-2 text-sm font-semibold">
                    <span className="font-mono text-[13px]">{s.language}</span>
                    <span className="text-(--muted)">·</span>
                    <span className="text-(--muted)">{s.goal}</span>
                    <span className={`tag ml-auto ${s.status === "solved" ? "border-(--success)" : ""}`}>
                      {s.status}
                    </span>
                  </span>
                  <span className="mt-1 block truncate font-mono text-xs text-(--faint)">
                    {s.code.split("\n")[0].slice(0, 60)}
                  </span>
                  <span className="mt-1 block text-xs text-(--muted)">
                    {s.message_count} messages · {s.understanding_score}/100 ·{" "}
                    {new Date(s.updated_at).toLocaleDateString()}
                  </span>
                </button>
              </li>
            ))}
          </ul>

          <div className="card min-h-[300px] p-5 md:p-6">
            {!openId || !openSession ? (
              <EmptyState
                title="Select a session"
                body="Pick a session on the left to replay every message exactly as it happened."
              />
            ) : detail.isPending ? (
              <div className="flex flex-col gap-2" aria-label="Loading replay">
                <div className="skeleton h-4 w-11/12" />
                <div className="skeleton h-4 w-3/4" />
                <div className="skeleton h-4 w-5/6" />
              </div>
            ) : detail.isError ? (
              <EmptyState
                title="Could not load this session"
                body={detail.error instanceof ApiError ? detail.error.message : "Try again."}
              />
            ) : (
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-mono text-[13px]">{openSession.language}</span>
                  <span className="text-(--muted)">·</span>
                  <span className="text-[13px] text-(--muted)">{openSession.goal}</span>
                  <span className={`tag ${openSession.status === "solved" ? "border-(--success)" : ""}`}>
                    {openSession.status}
                  </span>
                  {openSession.status === "active" && (
                    <Link to={`/app?session=${openSession.id}`} className="btn btn-primary btn-sm ml-auto">
                      <Play size={14} strokeWidth={1.5} /> Continue
                    </Link>
                  )}
                </div>
                <pre className="mt-4 overflow-x-auto rounded-xl border border-(--border) bg-(--bg-soft) p-4 font-mono text-[12.5px] leading-relaxed">
                  {openSession.code}
                </pre>
                <div className="mt-4 flex flex-col gap-3" aria-label="Session replay">
                  {detail.data.messages.map((m) => (
                    <div key={m.id} className={`flex gap-2 ${m.role === "user" ? "flex-row-reverse" : ""}`}>
                      <span
                        className={`grid size-7 shrink-0 place-items-center rounded-full ${
                          m.role === "user" ? "bg-(--surface-2) text-(--muted)" : "bg-(--accent) text-white"
                        }`}
                        aria-hidden="true"
                      >
                        {m.role === "user" ? "Y" : <Bot size={14} strokeWidth={1.5} />}
                      </span>
                      <div className="max-w-[88%]">
                        <p
                          className={`rounded-2xl px-3.5 py-2.5 text-[14px] leading-relaxed ${
                            m.role === "user"
                              ? "rounded-tr-sm bg-(--accent) text-white"
                              : "rounded-tl-sm border border-(--border) bg-(--surface-2)"
                          }`}
                        >
                          {m.content}
                        </p>
                        {m.role === "assistant" &&
                          Array.isArray(
                            ((m.meta ?? {}) as { sources?: unknown }).sources,
                          ) &&
                          (
                            ((m.meta ?? {}) as { sources?: { title?: unknown; url?: unknown }[] })
                              .sources ?? []
                          ).length > 0 && (
                            <ul className="mt-1.5 flex flex-col gap-1" aria-label="References">
                              {(
                                ((m.meta ?? {}) as { sources?: { title?: unknown; url?: unknown }[] })
                                  .sources ?? []
                              )
                                .filter(
                                  (s): s is { title: string; url: string } =>
                                    !!s && typeof s.title === "string" && typeof s.url === "string",
                                )
                                .map((s) => (
                                  <li key={s.url} className="text-xs text-(--muted)">
                                    <a
                                      href={s.url}
                                      target="_blank"
                                      rel="noreferrer"
                                      className="underline decoration-dotted underline-offset-2 hover:text-(--text)"
                                    >
                                      {s.title}
                                    </a>
                                  </li>
                                ))}
                            </ul>
                          )}
                      </div>
                    </div>
                  ))}
                </div>
                {openSession.status === "active" && (
                  <p className="mt-4 text-[13px] text-(--muted)">
                    Continue in the workspace to keep reasoning — history stays in sync.{" "}
                    <Link to={`/app?session=${openSession.id}`} className="font-semibold text-(--accent-text)">
                      Open in workspace <ArrowRight size={13} strokeWidth={1.5} className="inline" />
                    </Link>
                  </p>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </main>
  );
}
