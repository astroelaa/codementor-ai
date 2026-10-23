import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import {
  Award,
  Bot,
  Check,
  ChevronDown,
  CircleCheck,
  Flag,
  FlaskConical,
  GraduationCap,
  Languages,
  Lightbulb,
  Flame,
  Loader2,
  Play,
  RotateCcw,
  Send,
  Square,
  Tag,
  TriangleAlert,
  WifiOff,
  X,
} from "lucide-react";
import { CodeEditor } from "../components/CodeEditor";
import { EmptyState } from "../components/bits";
import { ThinkingOrb } from "thinking-orbs";
import { Reveal } from "../components/Reveal";
import { LANGUAGES, guessLanguage } from "../lib/detect";
import {
  ApiError,
  api,
  API_MISCONFIGURED,
  streamMessage,
  type Badge,
  type MentorTurn,
  type Misconception,
  type SourceRef,
} from "../lib/api";
import { useAuth } from "../lib/auth";
import { useToast } from "../lib/toast";

const OPENING =
  "Here is my code. Something is wrong with it. Start with your first guiding question.";

interface ChatMsg {
  id: string;
  role: "user" | "assistant";
  content: string;
  misconception?: Misconception | null;
  sources?: SourceRef[] | null;
}

const BADGE_ICONS: Record<string, typeof Flag> = {
  flag: Flag,
  check: Check,
  lightbulb: Lightbulb,
  flame: Flame,
  languages: Languages,
  "graduation-cap": GraduationCap,
};

function badgeIcon(slug: string) {
  return BADGE_ICONS[slug] ?? Award;
}

export function Workspace() {
  const { user, ensureGuest } = useAuth();
  const toast = useToast();

  const [langSel, setLangSel] = useState<string>("auto");
  const [goal, setGoal] = useState("debug");
  const [mode, setMode] = useState<"practice" | "mycode">("practice");
  const [code, setCode] = useState("");
  const [starterCode, setStarterCode] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [status, setStatus] = useState<"active" | "solved" | null>(null);
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState("");
  const [busy, setBusy] = useState(false);
  const [starting, setStarting] = useState(false);
  const [provider, setProvider] = useState("");
  const [score, setScore] = useState(0);
  const [hintsLeft, setHintsLeft] = useState(3);
  const [topics, setTopics] = useState<string[]>([]);
  const [badges, setBadges] = useState<Badge[]>([]);
  const [explanation, setExplanation] = useState("");
  const [explainOpen, setExplainOpen] = useState(false);
  const [explaining, setExplaining] = useState(false);
  const [guestCapped, setGuestCapped] = useState(false);
  const [projectId, setProjectId] = useState<string | null>(null);
  const [turnNotice, setTurnNotice] = useState<{
    message: string;
    retry: (() => Promise<void>) | null;
  } | null>(null);
  // Mentor features need the backend; the editor itself does not. Track the
  // connection so the UI can say exactly what still works offline.
  const [online, setOnline] = useState(() =>
    typeof navigator === "undefined" ? true : navigator.onLine,
  );

  useEffect(() => {
    const up = () => setOnline(true);
    const down = () => setOnline(false);
    window.addEventListener("online", up);
    window.addEventListener("offline", down);
    return () => {
      window.removeEventListener("online", up);
      window.removeEventListener("offline", down);
    };
  }, []);

  const abortRef = useRef<AbortController | null>(null);
  const logRef = useRef<HTMLDivElement>(null);
  const [searchParams, setSearchParams] = useSearchParams();
  const [resuming, setResuming] = useState(() => searchParams.get("session") !== null);
  const {
    data: snippets,
    isError: serverUnreachable,
    refetch: retryServer,
  } = useQuery({
    queryKey: ["snippets"],
    queryFn: api.snippets,
    staleTime: 5 * 60 * 1000,
    retry: 1,
  });

  const snippetByLang = useMemo(() => {
    const map = new Map<string, string>();
    for (const s of snippets ?? []) map.set(s.language, s.code);
    return map;
  }, [snippets]);

  // Authoritative list comes from the backend registry; the local list is
  // only a fallback so the selector works while offline.
  const { data: registry } = useQuery({
    queryKey: ["languages"],
    queryFn: api.languages,
    staleTime: Infinity,
    retry: 1,
  });
  const langOptions = useMemo(
    () => registry?.map((l) => ({ value: l.key, label: l.label })) ?? LANGUAGES,
    [registry],
  );

  // Effective language for highlighting: manual choice wins, otherwise a
  // client-side guess (the backend re-detects authoritatively on create).
  const effectiveLanguage = useMemo(
    () =>
      langSel === "auto" ? (guessLanguage(code) ?? "python") : langSel,
    [langSel, code],
  );

  useEffect(() => {
    if (!code) {
      const py = snippetByLang.get("python");
      if (py) setCode(py);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [snippetByLang]);

  function loadExample(lang: string) {
    const sample = snippetByLang.get(lang);
    if (!sample) return;
    setLangSel(lang);
    setCode(sample);
  }

  useEffect(() => {
    const el = logRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, streaming, busy]);

  // Resume a persisted session (?session=<id>): survives refresh + login.
  // Depends on the param (not just mount): same-route navigations such as
  // History "Continue" links must also trigger hydration.
  const resumeId = searchParams.get("session");
  useEffect(() => {
    if (!resumeId || resumeId === sessionId) return;
    let cancelled = false;
    (async () => {
      try {
        const s = await api.getSession(resumeId);
        if (cancelled) return;
        setSessionId(s.id);
        setStatus(s.status);
        setCode(s.code);
        setStarterCode(s.code);
        setLangSel(s.language);
        setGoal(s.goal || "debug");
        setMode(s.mode === "mycode" ? "mycode" : "practice");
        setScore(s.understanding_score);
        setHintsLeft(s.hints_left);
        setTopics([]);
        setProjectId(s.project_id ?? null);
        setMessages(
          s.messages.map((m) => ({
            id: m.id,
            role: m.role,
            content: m.content,
            misconception:
              ((m.meta ?? {}) as { misconception?: Misconception | null })
                .misconception ?? null,
            sources:
              (Array.isArray(((m.meta ?? {}) as { sources?: unknown }).sources)
                ? (((m.meta ?? {}) as { sources?: SourceRef[] }).sources ?? [])
                : []
              ).filter(
                (src): src is SourceRef =>
                  !!src && typeof src.title === "string" && typeof src.url === "string",
              ),
          })),
        );
      } catch {
        if (!cancelled) {
          toast("error", "Could not reopen that session. Start a new one.");
          setSearchParams({});
        }
      } finally {
        if (!cancelled) setResuming(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [resumeId]);

  function handleApiError(err: unknown, retry?: () => Promise<void>) {
    if (err instanceof ApiError && err.status === 403 && err.message.includes("1 free session")) {
      setGuestCapped(true);
      return;
    }
    if (err instanceof ApiError && err.status === 503 && retry) {
      setTurnNotice({ message: err.message, retry });
      return;
    }
    // status 0 = never reached the API: network/CORS failure or timeout.
    // Both are recoverable, so offer the retry inline like a busy mentor.
    // (A misconfigured build is a deploy problem, not a retry problem.)
    if (!API_MISCONFIGURED && err instanceof ApiError && err.status === 0) {
      if (retry) setTurnNotice({ message: err.message, retry });
      else toast("error", err.message);
      return;
    }
    toast("error", err instanceof ApiError ? err.message : "Something went wrong. Try again.");
  }

  function applyTurn(turn: MentorTurn) {
    setTurnNotice(null);
    setScore(turn.understanding_score);
    setHintsLeft(turn.hints_left);
    setTopics(turn.next_topics);
    setMessages((m) => [
      ...m,
      {
        id: turn.message_id,
        role: "assistant",
        content: turn.reply,
        misconception: turn.misconception,
        sources: turn.sources ?? [],
      },
    ]);
  }

  function cancelStream() {
    abortRef.current?.abort();
  }

  async function runStream(id: string, content: string, snapshot: string) {
    setBusy(true);
    setProvider("");
    setTurnNotice(null);
    const controller = new AbortController();
    abortRef.current = controller;
    let acc = "";
    let finished = false;
    try {
      for await (const ev of streamMessage(id, content, snapshot, controller.signal)) {
        if (controller.signal.aborted) break;
        if (ev.kind === "provider") setProvider(ev.provider);
        else if (ev.kind === "token") {
          acc += ev.text;
          setStreaming(acc);
        } else if (ev.kind === "done") {
          applyTurn(ev.turn);
          finished = true;
        } else if (ev.kind === "error" && !finished) {
          finished = true;
          if (ev.transport) {
            // Never reached the server: one plain-JSON retry is safe.
            try {
              applyTurn(await api.postMessage(id, content, snapshot));
            } catch (err) {
              if (controller.signal.aborted) return;
              handleApiError(err, () => runStream(id, content, snapshot));
            }
          } else {
            // Server-side failure (e.g. the mentor is busy): recoverable —
            // surface it inline with a retry button instead of a raw toast.
            setTurnNotice({
              message: ev.detail,
              retry: () => runStream(id, content, snapshot),
            });
          }
        }
      }
    } catch (err) {
      if (!finished && !controller.signal.aborted) {
        handleApiError(err, () => runStream(id, content, snapshot));
      }
    } finally {
      if (abortRef.current === controller) abortRef.current = null;
      setBusy(false);
      setStreaming("");
    }
  }

  function offlineNotice() {
    toast("info", "You're offline — the mentor needs a connection. Your code stays here.");
  }

  async function start() {
    if (API_MISCONFIGURED) {
      toast("error", "The app is not connected to its backend (API URL is not configured).");
      return;
    }
    if (!online) {
      offlineNotice();
      return;
    }
    if (!code.trim()) {
      toast("info", "Paste your code first — or load a sample snippet.");
      return;
    }
    setStarting(true);
    setGuestCapped(false);
    try {
      if (!user) await ensureGuest();
      const projectParam = searchParams.get("project");
      const s = await api.createSession(langSel, code, goal, projectParam, mode);
      setProjectId(s.project_id);
      // Sync the selector to the server-stored language (authoritative).
      setLangSel(s.language);
      setMode(s.mode === "mycode" ? "mycode" : "practice");
      setStarterCode(s.code);
      setSessionId(s.id);
      setStatus("active");
      setMessages([]);
      setScore(0);
      setHintsLeft(s.hints_left);
      setTopics([]);
      setBadges(s.badges_earned);
      if (s.badges_earned.length > 0)
        toast("success", "First session started. Good luck.");
      await runStream(s.id, OPENING, s.code);
    } catch (err) {
      handleApiError(err);
    } finally {
      setStarting(false);
    }
  }

  async function send() {
    const content = input.trim();
    if (!content || busy || !sessionId || status !== "active") return;
    if (!online) {
      offlineNotice();
      return;
    }
    setInput("");
    setMessages((m) => [...m, { id: `u-${Date.now()}`, role: "user", content }]);
    await runStream(sessionId, content, code);
  }

  async function askHint(isRetry = false) {
    if (busy || !sessionId || status !== "active") return;
    if (!online && !isRetry) {
      offlineNotice();
      return;
    }
    if (!isRetry && hintsLeft <= 0) {
      toast("info", "No hints left in this session. Reason it out.");
      return;
    }
    setBusy(true);
    setTurnNotice(null);
    if (!isRetry) {
      setMessages((m) => [
        ...m,
        { id: `u-${Date.now()}`, role: "user", content: "I am stuck. Give me a hint, not the answer." },
      ]);
    }
    try {
      applyTurn(await api.requestHint(sessionId, code));
    } catch (err) {
      handleApiError(err, () => askHint(true));
    } finally {
      setBusy(false);
    }
  }

  async function submitExplanation() {
    const text = explanation.trim();
    if (!text || explaining || !sessionId || status !== "active") return;
    if (!online) {
      offlineNotice();
      return;
    }
    setExplaining(true);
    setMessages((m) => [...m, { id: `u-${Date.now()}`, role: "user", content: text }]);
    try {
      const r = await api.submitExplanation(sessionId, text, code);
      setScore(r.understanding_score);
      setHintsLeft(r.hints_left);
      setMessages((m) => [
        ...m,
        { id: `a-${Date.now()}`, role: "assistant", content: r.reply },
      ]);
      setExplanation("");
      setExplainOpen(false);
      if (r.passed) {
        setStatus("solved");
        setBadges(r.badges_earned);
        toast("success", "Session solved. You explained it yourself.");
      } else {
        toast("info", "Not quite — read the feedback and try again.");
      }
    } catch (err) {
      handleApiError(err);
    } finally {
      setExplaining(false);
    }
  }

  function reset() {
    setSessionId(null);
    setStatus(null);
    setProjectId(null);
    setStarterCode(null);
    setMessages([]);
    setInput("");
    setStreaming("");
    setScore(0);
    setHintsLeft(3);
    setTopics([]);
    setBadges([]);
    setProvider("");
    setExplanation("");
    setExplainOpen(false);
    setGuestCapped(false);
    setTurnNotice(null);
    setSearchParams({});
  }

  const sessionMisconceptions = useMemo(() => {
    const seen = new Map<string, Misconception>();
    for (const m of messages) {
      if (m.misconception && !seen.has(m.misconception.type))
        seen.set(m.misconception.type, m.misconception);
    }
    return [...seen.values()];
  }, [messages]);

  const inSession = sessionId !== null;

  return (
    <main className="mx-auto w-[min(1200px,94%)] py-8 md:py-12">
      <Reveal>
        <div className="flex flex-wrap items-center gap-3">
          <div>
            <p className="eyebrow">Mentor workspace</p>
            <h1 className="mt-1 text-2xl font-extrabold tracking-tight md:text-3xl">
              Debug with a mentor
            </h1>
          </div>
          <div className="ml-auto flex flex-wrap items-center gap-2">
            {status && (
              <span className={`tag ${status === "solved" ? "border-(--success)" : ""}`}>
                {status === "solved" ? <CircleCheck size={13} strokeWidth={1.5} /> : null}
                {status}
              </span>
            )}
            {status && <span className="tag">{goal}</span>}
            {status && <span className="tag">{effectiveLanguage}</span>}
            {status && (
              <span className="tag" title={mode === "practice" ? "Seeded challenge" : "Your own code"}>
                {mode === "practice" ? "practice" : "my code"}
              </span>
            )}
            {projectId && (
              <Link to="/projects" className="tag" title="Linked project">
                project
              </Link>
            )}
            {provider && <span className="tag">via {provider}</span>}
            {inSession && (
              <button type="button" onClick={reset} className="btn btn-ghost btn-sm" disabled={busy}>
                <RotateCcw size={14} strokeWidth={1.5} /> New session
              </button>
            )}
          </div>
        </div>
      </Reveal>

      {user?.is_anonymous && inSession && !guestCapped && (
        <Reveal delay={0.05}>
          <div className="card mt-5 flex flex-wrap items-center gap-3 px-5 py-3.5 text-sm">
            <FlaskConical size={16} strokeWidth={1.5} className="text-(--accent-text)" />
            <span className="text-(--muted)">
              Guest session — one free session, not linked to an account.
            </span>
            <Link to="/signup" className="ml-auto font-semibold text-(--accent-text)">
              Sign up free for unlimited sessions
            </Link>
          </div>
        </Reveal>
      )}

      {guestCapped && (
        <div className="card mt-5 p-8 text-center">
          <h2 className="text-xl font-extrabold">Guest session used</h2>
          <p className="mx-auto mt-2 max-w-md text-sm text-(--muted)">
            Guest mode includes one free session, and this guest session has
            used it. Create a free account for unlimited sessions, history, and
            badges.
          </p>
          <div className="mt-5 flex justify-center gap-3">
            <Link to="/signup" className="btn btn-primary">Sign up free</Link>
            <Link to="/login" className="btn btn-ghost">Log in</Link>
          </div>
        </div>
      )}

      {!guestCapped && (
        <div className="mt-6 grid items-start gap-5 lg:grid-cols-[1.1fr_1fr] xl:grid-cols-[1fr_1fr_280px]">
          {API_MISCONFIGURED && (
            <div className="card flex flex-wrap items-center gap-3 border-(--danger) px-5 py-3.5 text-sm lg:col-span-2 xl:col-span-3" role="alert">
              <span className="text-(--danger)">Backend not configured — the mentor cannot reach its API. Set <span className="font-mono">VITE_API_BASE_URL</span> and rebuild.</span>
            </div>
          )}
          {!online && (
            <div
              className="card flex flex-wrap items-center gap-3 border-(--warning) px-5 py-3.5 text-sm lg:col-span-2 xl:col-span-3"
              role="status"
            >
              <WifiOff size={16} strokeWidth={1.5} className="shrink-0 text-(--warning)" />
              <span className="text-(--muted)">
                You&rsquo;re offline — the editor and your code still work, but the
                mentor needs a connection for replies. Everything resumes when
                you&rsquo;re back online.
              </span>
            </div>
          )}
          {online && serverUnreachable && (
            <div className="card flex flex-wrap items-center gap-3 border-(--warning) px-5 py-3.5 text-sm lg:col-span-2 xl:col-span-3" role="status">
              <TriangleAlert size={16} strokeWidth={1.5} className="shrink-0 text-(--warning)" />
              <span className="text-(--muted)">
                Can&rsquo;t reach the mentor server. Check your connection — if
                you&rsquo;re online, the service may be briefly unavailable. Your
                code is safe here.
              </span>
              <button
                type="button"
                onClick={() => void retryServer()}
                className="btn btn-ghost btn-sm ml-auto"
              >
                Retry
              </button>
            </div>
          )}
          {/* ---------- editor ---------- */}
          <Reveal className="min-w-0">
            <div className="card overflow-hidden">
              <div className="flex flex-wrap items-center gap-2 border-b border-(--border) px-4 py-2.5">
                <label htmlFor="ws-lang" className="sr-only">Programming language</label>
                <select
                  id="ws-lang"
                  value={langSel}
                  disabled={inSession}
                  onChange={(e) => setLangSel(e.target.value)}
                  className="rounded-lg border border-(--border) bg-(--surface-2) px-2.5 py-1.5 font-mono text-xs font-semibold text-(--text) outline-none transition-colors focus:border-(--accent) disabled:opacity-60 [&>option]:bg-(--surface-2) [&>option]:text-(--text)"
                >
                  <option value="auto">
                    Auto{langSel === "auto" ? ` (${effectiveLanguage})` : ""}
                  </option>
                  {langOptions.map((l) => (
                    <option key={l.value} value={l.value}>
                      {l.label}
                    </option>
                  ))}
                </select>
                {!inSession && (
                  <>
                    <label htmlFor="ws-example" className="sr-only">Load example snippet</label>
                    <select
                      id="ws-example"
                      value=""
                      onChange={(e) => {
                        if (e.target.value) loadExample(e.target.value);
                        e.target.value = "";
                      }}
                      className="rounded-lg border border-(--border) bg-(--surface-2) px-2.5 py-1.5 text-xs font-semibold text-(--text) outline-none transition-colors hover:border-(--border-strong) focus:border-(--accent) [&>option]:bg-(--surface-2) [&>option]:text-(--text)"
                    >
                      <option value="">Load example…</option>
                      {(snippets ?? []).map((s) => (
                        <option key={s.language} value={s.language}>
                          {s.title} ({s.language})
                        </option>
                      ))}
                    </select>
                  </>
                )}
              </div>
              <CodeEditor
                language={effectiveLanguage}
                value={code}
                onChange={setCode}
                label="Your code"
              />
              <div className="flex flex-wrap items-center gap-3 border-t border-(--border) px-4 py-3">
                {!inSession ? (
                  resuming ? (
                    <span className="flex items-center gap-2 text-sm text-(--muted)">
                      <Loader2 size={16} strokeWidth={1.5} className="animate-spin" />
                      Reopening your session…
                    </span>
                  ) : (
                    <>
                      <div className="flex gap-1.5" role="radiogroup" aria-label="Session mode">
                        {(
                          [
                            ["practice", "Practice"],
                            ["mycode", "My Code"],
                          ] as const
                        ).map(([value, label]) => (
                          <button
                            key={value}
                            role="radio"
                            aria-checked={mode === value}
                            type="button"
                            onClick={() => {
                              setMode(value);
                              if (value === "mycode" && snippetByLang.get("python") === code) {
                                setCode("");
                              }
                              if (value === "practice" && !code) {
                                const py = snippetByLang.get("python");
                                if (py) setCode(py);
                              }
                            }}
                            title={
                              value === "practice"
                                ? "Work on a seeded challenge"
                                : "Paste or write your own code"
                            }
                            className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors ${
                              mode === value
                                ? "bg-(--accent-soft) text-(--accent-text)"
                                : "text-(--muted) hover:text-(--text)"
                            }`}
                          >
                            {label}
                          </button>
                        ))}
                      </div>
                      <div className="flex gap-1.5" role="radiogroup" aria-label="Session goal">
                        {(
                          [
                            ["debug", "Debug"],
                            ["review", "Review"],
                            ["explain", "Explain"],
                          ] as const
                        ).map(([value, label]) => (
                          <button
                            key={value}
                            role="radio"
                            aria-checked={goal === value}
                            type="button"
                            onClick={() => setGoal(value)}
                            title={
                              value === "debug"
                                ? "Find and fix a bug"
                                : value === "review"
                                  ? "Review quality and best practices"
                                  : "Understand how the code works"
                            }
                            className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors ${
                              goal === value
                                ? "bg-(--accent-soft) text-(--accent-text)"
                                : "text-(--muted) hover:text-(--text)"
                            }`}
                          >
                            {label}
                          </button>
                        ))}
                      </div>
                      <button type="button" onClick={start} className="btn btn-primary" disabled={starting}>
                        {starting ? <Loader2 size={16} strokeWidth={1.5} className="animate-spin" /> : <Play size={16} strokeWidth={1.5} />}
                        {starting ? "Starting…" : "Diagnose"}
                      </button>
                      <span className="text-xs text-(--faint)">No answer is ever shown — only questions.</span>
                    </>
                  )
                ) : (
                  <>
                    <span className="text-xs text-(--faint)">
                      Edits are sent with each message.
                    </span>
                    {mode === "practice" && starterCode && (
                      <button
                        type="button"
                        onClick={() => setCode(starterCode)}
                        className="btn btn-ghost btn-sm ml-auto"
                        disabled={busy || code === starterCode}
                        title="Restore the initial challenge code"
                      >
                        <RotateCcw size={14} strokeWidth={1.5} /> Restore starter code
                      </button>
                    )}
                  </>
                )}
              </div>
            </div>
          </Reveal>

          {/* ---------- chat ---------- */}
          <Reveal delay={0.06} className="min-w-0">
            <div className="glass-card flex min-h-[480px] flex-col overflow-hidden">
              <div className="border-b border-(--border) px-4 py-2.5 text-[13px] font-semibold text-(--muted)">
                Mentor session
              </div>
              <div ref={logRef} aria-live="polite" className="flex max-h-[460px] min-h-[300px] flex-1 flex-col gap-3 overflow-y-auto p-4">
                {!inSession && (
                  <EmptyState
                    title="No session yet"
                    body="Load a sample or paste your own code, then press Diagnose. The mentor will open with a single question."
                  />
                )}
                <AnimatePresence initial={false}>
                  {messages.map((m) => (
                    <motion.div
                      key={m.id}
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.25 }}
                      className={`flex gap-2 ${m.role === "user" ? "flex-row-reverse" : ""}`}
                    >
                      <span
                        className={`grid size-7 shrink-0 place-items-center rounded-full text-white ${
                          m.role === "user" ? "bg-(--surface-2) text-(--muted)" : "bg-(--accent)"
                        }`}
                        aria-hidden="true"
                      >
                        {m.role === "user" ? "Y" : <Bot size={14} strokeWidth={1.5} />}
                      </span>
                      <div className="max-w-[88%]">
                        <p
                          className={`rounded-2xl px-3.5 py-2.5 text-[14px] leading-relaxed ${
                            m.role === "user"
                              ? "rounded-tr-sm accent-deep text-white"
                              : "rounded-tl-sm border border-(--border) bg-(--surface-2)"
                          }`}
                        >
                          {m.content}
                        </p>
                        {m.misconception && (
                          <span className="tag mt-1.5" title={m.misconception.description}>
                            <Tag size={12} strokeWidth={1.5} />
                            {m.misconception.type}
                          </span>
                        )}
                        {m.role === "assistant" && m.sources && m.sources.length > 0 && (
                          <ul className="mt-1.5 flex flex-col gap-1" aria-label="References">
                            {m.sources.map((s) => (
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
                    </motion.div>
                  ))}
                </AnimatePresence>
                {busy && !streaming && (
                  <div className="flex gap-2">
                    <span className="grid size-7 place-items-center rounded-full bg-(--accent) text-white" aria-hidden="true">
                      <Bot size={14} strokeWidth={1.5} />
                    </span>
                    <div className="rounded-2xl rounded-tl-sm border border-(--border) bg-(--surface-2) px-4 py-3">
                      <div className="orb-halo">
                        <ThinkingOrb
                          state="working"
                          size={32}
                          theme="auto"
                          aria-label="Mentor is thinking"
                        />
                      </div>
                    </div>
                  </div>
                )}
                {streaming && (
                  <div className="flex gap-2">
                    <span className="grid size-7 place-items-center rounded-full bg-(--accent) text-white" aria-hidden="true">
                      <Bot size={14} strokeWidth={1.5} />
                    </span>
                    <p className="max-w-[88%] rounded-2xl rounded-tl-sm border border-(--border) bg-(--surface-2) px-3.5 py-2.5 text-[14px] leading-relaxed">
                      {streaming}
                      <span className="ml-0.5 inline-block h-4 w-[2px] animate-pulse bg-(--accent-text)" aria-hidden="true" />
                    </p>
                  </div>
                )}
              </div>
              {turnNotice && (
                <div className="flex flex-wrap items-center gap-2 border-t border-(--border) px-3 py-2.5 text-[13px]" role="alert">
                  <TriangleAlert size={15} strokeWidth={1.5} className="shrink-0 text-(--warning)" />
                  <span className="min-w-0 flex-1 text-(--muted)">{turnNotice.message}</span>
                  {turnNotice.retry && (
                    <button
                      type="button"
                      onClick={() => void turnNotice.retry?.()}
                      className="btn btn-ghost btn-sm"
                      disabled={busy}
                    >
                      <RotateCcw size={13} strokeWidth={1.5} /> Retry
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => setTurnNotice(null)}
                    className="btn btn-ghost btn-sm px-2.5"
                    aria-label="Dismiss"
                  >
                    <X size={13} strokeWidth={1.5} />
                  </button>
                </div>
              )}
              <div className="flex min-w-0 gap-2 border-t border-(--border) p-3">
                <input
                  className="input min-w-0"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") void send();
                  }}
                  placeholder={inSession ? "Type your reasoning…" : "Start a session first"}
                  disabled={!inSession || busy || status !== "active"}
                  aria-label="Your reasoning"
                />
                <button type="button" onClick={() => void send()} className="btn btn-primary btn-sm px-4" disabled={!inSession || busy || status !== "active" || !online} aria-label="Send">
                  <Send size={15} strokeWidth={1.5} />
                </button>
                {busy ? (
                  <button
                    type="button"
                    onClick={cancelStream}
                    className="btn btn-ghost btn-sm"
                    aria-label="Stop generating"
                    title="Stop generating"
                  >
                    <Square size={13} strokeWidth={2} />
                    <span className="hidden xl:inline">Stop</span>
                  </button>
                ) : (
                  <button type="button" onClick={() => void askHint()} className="btn btn-ghost btn-sm" disabled={!inSession || status !== "active" || !online} aria-label="Ask for a hint">
                    <Lightbulb size={15} strokeWidth={1.5} />
                    <span className="hidden xl:inline">Hint</span>
                  </button>
                )}
              </div>
              {inSession && status === "active" && (
                <div className="border-t border-(--border) px-3 py-2.5">
                  <button
                    type="button"
                    onClick={() => setExplainOpen((o) => !o)}
                    aria-expanded={explainOpen}
                    className="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-[13px] font-semibold text-(--muted) transition-colors hover:text-(--text)"
                  >
                    <ChevronDown size={15} strokeWidth={1.5} className={`transition-transform ${explainOpen ? "rotate-180" : ""}`} />
                    I fixed it — check my explanation
                  </button>
                  <AnimatePresence initial={false}>
                    {explainOpen && (
                      <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: "auto", opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.22, ease: "easeOut" }}
                        className="overflow-hidden"
                      >
                        <div className="flex flex-col gap-2 px-1 pb-1 pt-2">
                          <textarea
                            className="input min-h-20 resize-y"
                            value={explanation}
                            onChange={(e) => setExplanation(e.target.value)}
                            placeholder="Explain the root cause and why your fix works, in your own words…"
                            aria-label="Your explanation of the fix"
                          />
                          <button type="button" onClick={() => void submitExplanation()} className="btn btn-primary btn-sm self-end" disabled={explaining || !explanation.trim()}>
                            {explaining ? <Loader2 size={14} strokeWidth={1.5} className="animate-spin" /> : <Check size={14} strokeWidth={1.5} />}
                            {explaining ? "Judging…" : "Check my explanation"}
                          </button>
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              )}
            </div>
          </Reveal>

          {/* ---------- side panel ---------- */}
          <Reveal delay={0.12} className="min-w-0">
            <aside className="glass-card flex flex-col divide-y divide-(--border) lg:sticky lg:top-24">
              <div className="p-4">
                <p className="label">Hint budget</p>
                <div className="flex gap-1.5" aria-label={`${hintsLeft} hints left`}>
                  {[0, 1, 2].map((i) => (
                    <span
                      key={i}
                      className={`grid h-8 w-10 place-items-center rounded-lg border transition-all ${
                        i < hintsLeft
                          ? "border-(--border-strong) bg-(--accent-soft) text-(--accent-text)"
                          : "border-(--border) opacity-30 grayscale"
                      }`}
                    >
                      <Lightbulb size={14} strokeWidth={1.5} />
                    </span>
                  ))}
                </div>
                <p className="mt-2 text-xs text-(--muted)">
                  {hintsLeft === 0 ? "No hints left — reason it out." : `${hintsLeft} left — only if you ask.`}
                </p>
              </div>
              <div className="p-4">
                <p className="label">Understanding</p>
                <div className="meter" role="progressbar" aria-valuenow={score} aria-valuemin={0} aria-valuemax={100} aria-label="Understanding score">
                  <div style={{ width: `${score}%` }} />
                </div>
                <p className="mt-2 text-xs text-(--muted)">{score}/100 — grows when your reasoning is sound.</p>
              </div>
              {topics.length > 0 && (
                <div className="p-4">
                  <p className="label">Recommended next</p>
                  <ul className="flex flex-col gap-1.5">
                    {topics.map((t) => (
                      <li key={t} className="rounded-lg border border-(--border) bg-(--bg-soft) px-2.5 py-1.5 text-[13px] text-(--muted)">
                        {t}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {sessionMisconceptions.length > 0 && (
                <div className="p-4">
                  <p className="label">Spotted misconceptions</p>
                  <div className="flex flex-wrap gap-1.5">
                    {sessionMisconceptions.map((m) => (
                      <span key={m.type} className="tag" title={m.description}>
                        <Tag size={12} strokeWidth={1.5} />{m.type}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {status === "solved" && (
                <div className="p-4">
                  <p className="flex items-center gap-1.5 text-sm font-bold text-(--success)">
                    <CircleCheck size={15} strokeWidth={1.5} /> Solved
                  </p>
                  {badges.length > 0 && (
                    <ul className="mt-2 flex flex-col gap-1.5">
                      {badges.map((b) => {
                        const Icon = badgeIcon(b.icon);
                        return (
                          <li key={b.slug} className="flex items-center gap-2 text-[13px] text-(--muted)" title={b.description}>
                            <Icon size={14} strokeWidth={1.5} className="text-(--accent-text)" />
                            {b.name}
                          </li>
                        );
                      })}
                    </ul>
                  )}
                </div>
              )}
            </aside>
          </Reveal>
        </div>
      )}
    </main>
  );
}
