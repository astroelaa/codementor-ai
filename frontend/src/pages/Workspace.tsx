import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
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
  Tag,
} from "lucide-react";
import { CodeEditor } from "../components/CodeEditor";
import { EmptyState } from "../components/bits";
import { TypingDots } from "../components/bits";
import { Reveal } from "../components/Reveal";
import {
  ApiError,
  api,
  streamMessage,
  tokenStore,
  type Badge,
  type MentorTurn,
  type Misconception,
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
  const { user } = useAuth();
  const toast = useToast();

  const [language, setLanguage] = useState("python");
  const [code, setCode] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [status, setStatus] = useState<"active" | "solved" | null>(null);
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState("");
  const [thinking, setThinking] = useState(false);
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

  const logRef = useRef<HTMLDivElement>(null);
  const { data: snippets } = useQuery({
    queryKey: ["snippets"],
    queryFn: api.snippets,
    staleTime: 5 * 60 * 1000,
  });

  const snippetFor = useMemo(
    () => (snippets ?? []).find((s) => s.language === language),
    [snippets, language],
  );

  useEffect(() => {
    if (!code && snippetFor) setCode(snippetFor.code);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [snippetFor]);

  useEffect(() => {
    const el = logRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, streaming, thinking]);

  function handleApiError(err: unknown) {
    if (err instanceof ApiError && err.status === 403 && err.message.includes("1 free session")) {
      setGuestCapped(true);
      return;
    }
    toast("error", err instanceof ApiError ? err.message : "Something went wrong. Try again.");
  }

  function applyTurn(turn: MentorTurn) {
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
      },
    ]);
  }

  async function runStream(id: string, content: string) {
    setBusy(true);
    setThinking(true);
    setProvider("");
    let acc = "";
    let finished = false;
    try {
      for await (const ev of streamMessage(id, content)) {
        if (ev.kind === "provider") setProvider(ev.provider);
        else if (ev.kind === "token") {
          acc += ev.text;
          setStreaming(acc);
          setThinking(false);
        } else if (ev.kind === "done") {
          applyTurn(ev.turn);
          finished = true;
        } else if (ev.kind === "error" && !finished) {
          finished = true;
          if (ev.transport) {
            // Never reached the server: one plain-JSON retry is safe.
            try {
              applyTurn(await api.postMessage(id, content));
            } catch (err) {
              handleApiError(err);
            }
          } else {
            toast("error", ev.detail);
          }
        }
      }
    } catch (err) {
      if (!finished) handleApiError(err);
    } finally {
      setBusy(false);
      setThinking(false);
      setStreaming("");
    }
  }

  async function start() {
    if (!code.trim()) {
      toast("info", "Paste your code first — or load a sample snippet.");
      return;
    }
    setStarting(true);
    setGuestCapped(false);
    try {
      const s = await api.createSession(language, code);
      if (s.guest_token) tokenStore.guest = s.guest_token;
      setSessionId(s.id);
      setStatus("active");
      setMessages([]);
      setScore(0);
      setHintsLeft(s.hints_left);
      setTopics([]);
      setBadges(s.badges_earned);
      if (s.badges_earned.length > 0)
        toast("success", "First session started. Good luck.");
      await runStream(s.id, OPENING);
    } catch (err) {
      handleApiError(err);
    } finally {
      setStarting(false);
    }
  }

  async function send() {
    const content = input.trim();
    if (!content || busy || !sessionId || status !== "active") return;
    setInput("");
    setMessages((m) => [...m, { id: `u-${Date.now()}`, role: "user", content }]);
    await runStream(sessionId, content);
  }

  async function askHint() {
    if (busy || !sessionId || status !== "active") return;
    if (hintsLeft <= 0) {
      toast("info", "No hints left in this session. Reason it out.");
      return;
    }
    setBusy(true);
    setMessages((m) => [
      ...m,
      { id: `u-${Date.now()}`, role: "user", content: "I am stuck. Give me a hint, not the answer." },
    ]);
    try {
      applyTurn(await api.requestHint(sessionId));
    } catch (err) {
      handleApiError(err);
    } finally {
      setBusy(false);
    }
  }

  async function submitExplanation() {
    const text = explanation.trim();
    if (!text || explaining || !sessionId || status !== "active") return;
    setExplaining(true);
    setMessages((m) => [...m, { id: `u-${Date.now()}`, role: "user", content: text }]);
    try {
      const r = await api.submitExplanation(sessionId, text);
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
          <div className="ml-auto flex items-center gap-2">
            {status && (
              <span className={`tag ${status === "solved" ? "border-(--success)" : ""}`}>
                {status === "solved" ? <CircleCheck size={13} strokeWidth={1.5} /> : null}
                {status}
              </span>
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

      {!user && inSession && !guestCapped && (
        <Reveal delay={0.05}>
          <div className="card mt-5 flex flex-wrap items-center gap-3 px-5 py-3.5 text-sm">
            <FlaskConical size={16} strokeWidth={1.5} className="text-(--accent-text)" />
            <span className="text-(--muted)">
              Guest session — your progress is not saved.
            </span>
            <Link to="/signup" className="ml-auto font-semibold text-(--accent-text)">
              Sign up free to keep it
            </Link>
          </div>
        </Reveal>
      )}

      {guestCapped && (
        <div className="card mt-5 p-8 text-center">
          <h2 className="text-xl font-extrabold">Guest session used</h2>
          <p className="mx-auto mt-2 max-w-md text-sm text-(--muted)">
            Guest mode includes one free session, and this device has used it.
            Create a free account for unlimited sessions, history, and badges.
          </p>
          <div className="mt-5 flex justify-center gap-3">
            <Link to="/signup" className="btn btn-primary">Sign up free</Link>
            <Link to="/login" className="btn btn-ghost">Log in</Link>
          </div>
        </div>
      )}

      {!guestCapped && (
        <div className="mt-6 grid items-start gap-5 lg:grid-cols-[1fr_1fr_280px]">
          {/* ---------- editor ---------- */}
          <Reveal className="min-w-0">
            <div className="card overflow-hidden">
              <div className="flex items-center gap-2 border-b border-(--border) px-4 py-2.5">
                <div className="flex gap-1" role="tablist" aria-label="Language">
                  {(["python", "javascript"] as const).map((l) => (
                    <button
                      key={l}
                      role="tab"
                      aria-selected={language === l}
                      type="button"
                      disabled={inSession}
                      onClick={() => {
                        setLanguage(l);
                        const s = (snippets ?? []).find((x) => x.language === l);
                        if (s) setCode(s.code);
                      }}
                      className={`rounded-lg px-3 py-1.5 font-mono text-xs font-semibold transition-colors ${
                        language === l
                          ? "bg-(--accent-soft) text-(--accent-text)"
                          : "text-(--muted) hover:text-(--text)"
                      } disabled:opacity-60`}
                    >
                      {l === "python" ? "average.py" : "average.js"}
                    </button>
                  ))}
                </div>
                {snippetFor && !inSession && (
                  <button
                    type="button"
                    onClick={() => setCode(snippetFor.code)}
                    className="ml-auto text-xs font-semibold text-(--muted) transition-colors hover:text-(--text)"
                  >
                    Load sample: {snippetFor.title}
                  </button>
                )}
              </div>
              <CodeEditor
                language={language}
                value={code}
                onChange={inSession ? () => {} : setCode}
                label="Your code"
              />
              <div className="flex flex-wrap items-center gap-3 border-t border-(--border) px-4 py-3">
                {!inSession ? (
                  <>
                    <button type="button" onClick={start} className="btn btn-primary" disabled={starting}>
                      {starting ? <Loader2 size={16} strokeWidth={1.5} className="animate-spin" /> : <Play size={16} strokeWidth={1.5} />}
                      {starting ? "Starting…" : "Diagnose"}
                    </button>
                    <span className="text-xs text-(--faint)">No answer is ever shown — only questions.</span>
                  </>
                ) : (
                  <span className="text-xs text-(--faint)">
                    Code is locked while the session runs. Start a new session to change it.
                  </span>
                )}
              </div>
            </div>
          </Reveal>

          {/* ---------- chat ---------- */}
          <Reveal delay={0.06} className="min-w-0">
            <div className="card flex min-h-[480px] flex-col overflow-hidden">
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
                              ? "rounded-tr-sm bg-(--accent) text-white"
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
                      </div>
                    </motion.div>
                  ))}
                </AnimatePresence>
                {thinking && (
                  <div className="flex gap-2">
                    <span className="grid size-7 place-items-center rounded-full bg-(--accent) text-white" aria-hidden="true">
                      <Bot size={14} strokeWidth={1.5} />
                    </span>
                    <div className="rounded-2xl rounded-tl-sm border border-(--border) bg-(--surface-2) px-4 py-3">
                      <TypingDots />
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
              <div className="flex gap-2 border-t border-(--border) p-3">
                <input
                  className="input"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") void send();
                  }}
                  placeholder={inSession ? "Type your reasoning…" : "Start a session first"}
                  disabled={!inSession || busy || status !== "active"}
                  aria-label="Your reasoning"
                />
                <button type="button" onClick={() => void send()} className="btn btn-primary btn-sm px-4" disabled={!inSession || busy || status !== "active"} aria-label="Send">
                  <Send size={15} strokeWidth={1.5} />
                </button>
                <button type="button" onClick={() => void askHint()} className="btn btn-ghost btn-sm" disabled={!inSession || busy || status !== "active"} aria-label="Ask for a hint">
                  <Lightbulb size={15} strokeWidth={1.5} />
                  <span className="hidden xl:inline">Hint</span>
                </button>
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
                  {explainOpen && (
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
                  )}
                </div>
              )}
            </div>
          </Reveal>

          {/* ---------- side panel ---------- */}
          <Reveal delay={0.12} className="min-w-0">
            <aside className="card flex flex-col divide-y divide-(--border) lg:sticky lg:top-24">
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
