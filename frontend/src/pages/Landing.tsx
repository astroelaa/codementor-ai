import { Link } from "react-router-dom";
import {
  ArrowRight,
  Check,
  Flame,
  Lightbulb,
  MessagesSquare,
  Route,
  ScanEye,
  ScrollText,
  Sparkles,
} from "lucide-react";
import { AnchorLink } from "../components/AnchorLink";
import { Counter } from "../components/Counter";
import { Faq } from "../components/Faq";
import { Reveal } from "../components/Reveal";
import { LogoMark } from "../components/Logo";

/* ---------- hero product mockup (static, representative) ---------- */
function HeroMockup() {
  return (
    <div className="card relative overflow-hidden shadow-2xl" aria-hidden="true">
      <div className="glow-accent pointer-events-none absolute -top-24 left-1/2 h-64 w-[130%] -translate-x-1/2" />
      <div className="flex items-center gap-2 border-b border-(--border) px-4 py-3">
        <span className="size-2.5 rounded-full bg-(--faint)" />
        <span className="size-2.5 rounded-full bg-(--faint)" />
        <span className="size-2.5 rounded-full bg-(--faint)" />
        <span className="ml-2 font-mono text-xs text-(--muted)">average.py</span>
        <span className="tag ml-auto">1 question at a time</span>
      </div>
      <div className="grid md:grid-cols-2">
        <div className="border-b border-(--border) p-4 font-mono text-[12.5px] leading-6 md:border-r md:border-b-0">
          <p><span className="text-(--faint)">1</span> <span className="text-(--accent-text)">def</span> <span className="text-(--text)">average(numbers):</span></p>
          <p><span className="text-(--faint)">2</span>     total = <span className="text-(--accent-text)">0</span></p>
          <p><span className="text-(--faint)">3</span>     <span className="text-(--accent-text)">for</span> n <span className="text-(--accent-text)">in</span> numbers:</p>
          <p><span className="text-(--faint)">4</span>         total += n</p>
          <p><span className="text-(--faint)">5</span>     <span className="text-(--accent-text)">return</span> total / len(numbers)</p>
        </div>
        <div className="flex flex-col gap-3 p-4 text-[13px]">
          <div className="flex gap-2.5">
            <span className="grid size-7 shrink-0 place-items-center rounded-full bg-(--accent) text-xs font-bold text-white">M</span>
            <p className="rounded-xl rounded-tl-sm border border-(--border) bg-(--surface-2) px-3.5 py-2.5 text-(--text)">
              Run this in your head with an empty list. What is{" "}
              <span className="font-mono text-[12px]">len(numbers)</span> at that moment?
            </p>
          </div>
          <div className="flex justify-end">
            <p className="rounded-xl rounded-tr-sm bg-(--accent) px-3.5 py-2.5 text-white">
              It would be 0… and then we divide by zero.
            </p>
          </div>
          <div className="flex items-center gap-2 text-(--muted)">
            <span className="typing-dot" /><span className="typing-dot" /><span className="typing-dot" />
          </div>
        </div>
      </div>
    </div>
  );
}

/* ---------- bento features ---------- */
const BENTO = [
  {
    icon: MessagesSquare,
    title: "Socratic debugging",
    body: "The mentor diagnoses your bug privately, then leads you to it with one question at a time. The answer is always yours.",
    span: "md:col-span-2",
    mock: (
      <div className="mt-4 rounded-xl border border-(--border) bg-(--bg-soft) p-4 text-sm">
        <p className="text-(--muted)">Mentor</p>
        <p className="mt-1 font-medium">“What does the divisor equal on the last line?”</p>
      </div>
    ),
  },
  {
    icon: Lightbulb,
    title: "Hint budget",
    body: "Three hints per session, only on request. Scarcity makes you think first — the way real debugging feels.",
    span: "",
    mock: (
      <div className="mt-4 flex gap-2" aria-hidden="true">
        {[0, 1, 2].map((i) => (
          <span key={i} className={`grid h-8 w-10 place-items-center rounded-lg border ${i < 2 ? "border-(--border-strong) bg-(--accent-soft)" : "border-(--border) opacity-30"}`}>
            <Lightbulb size={15} strokeWidth={1.5} />
          </span>
        ))}
      </div>
    ),
  },
  {
    icon: ScanEye,
    title: "Misconception detection",
    body: "Wrong beliefs are named the moment you express them, stored, and turned into your personal learning path.",
    span: "",
    mock: (
      <div className="mt-4" aria-hidden="true">
        <span className="tag">empty-input · assumes len() is never zero</span>
      </div>
    ),
  },
  {
    icon: ScrollText,
    title: "Explanation check",
    body: "A session only counts as solved when you explain the fix in your own words. No explanation, no closure.",
    span: "",
    mock: null,
  },
  {
    icon: Route,
    title: "Learning path",
    body: "Your weak spots become a prioritised path with progress tracking — generated from real sessions, not guesses.",
    span: "md:col-span-2",
    mock: (
      <div className="mt-4 flex flex-col gap-2 text-[13px]" aria-hidden="true">
        {["Guard clauses", "Edge cases: empty input", "Writing your own test cases"].map((t, i) => (
          <div key={t} className="flex items-center gap-3 rounded-lg border border-(--border) bg-(--bg-soft) px-3 py-2">
            <span className={`grid size-5 place-items-center rounded-full text-[11px] font-bold ${i === 0 ? "bg-(--success) text-black" : "border border-(--border-strong) text-(--muted)"}`}>
              {i === 0 ? <Check size={12} strokeWidth={2.5} /> : i + 1}
            </span>
            <span className={i === 0 ? "text-(--muted) line-through" : ""}>{t}</span>
          </div>
        ))}
      </div>
    ),
  },
];

const STEPS = [
  { title: "Paste the broken code", body: "Pick Python or JavaScript, or try a sample bug." },
  { title: "Answer one question", body: "The mentor asks a single guiding question. You reason out loud." },
  { title: "Get challenged", body: "Weak assumptions are named as misconceptions to fix." },
  { title: "Explain the fix", body: "Describe the change in your own words. Session solved." },
];

const FAQS = [
  {
    q: "Does the mentor ever just give me the answer?",
    a: "No. It diagnoses the bug internally but only ever responds with questions, challenges, and at most three hints per session that you must explicitly request. The fix — and the understanding — stays yours.",
  },
  {
    q: "Which languages are supported?",
    a: "Python and JavaScript today, each with sample buggy snippets to practise on. The Socratic method itself is language-agnostic, so more languages will follow.",
  },
  {
    q: "What does the free guest mode include?",
    a: "One full debugging session with no account: the same Socratic turns, hint budget, and explanation check. Sign up to keep history, streaks, badges, and a personal learning path.",
  },
  {
    q: "How is this different from a code generator?",
    a: "Generators optimise for the fastest correct output, which skips learning. CodeMentor AI optimises for your understanding score: reasoning evaluated each turn, misconceptions stored, and progress measured over time.",
  },
  {
    q: "What happens to my code and data?",
    a: "Sessions belong to your account. You can delete your account and all associated data at any time from settings. API keys and secrets are never stored in the database or logs.",
  },
];

export function Landing() {
  return (
    <main>
      {/* ---------- hero ---------- */}
      <section className="relative overflow-hidden">
        <div className="bg-grid pointer-events-none absolute inset-0" aria-hidden="true" />
        <div className="relative mx-auto grid w-[min(1200px,92%)] items-center gap-12 py-20 md:grid-cols-[1.05fr_1fr] md:py-28">
          <div>
            <Reveal>
              <p className="eyebrow">Socratic debugging mentor</p>
            </Reveal>
            <Reveal delay={0.05}>
              <h1 className="mt-4 text-[clamp(2.4rem,5.5vw,4rem)] font-extrabold leading-[1.05] tracking-tight">
                Stop copying fixes.
                <br />
                <span className="text-(--accent-text)">Start understanding bugs.</span>
              </h1>
            </Reveal>
            <Reveal delay={0.1}>
              <p className="mt-5 max-w-lg text-[17px] leading-relaxed text-(--muted)">
                Code generators give you answers. CodeMentor AI builds your
                understanding — one guiding question at a time, until you can
                explain the fix yourself.
              </p>
            </Reveal>
            <Reveal delay={0.15}>
              <div className="mt-8 flex flex-wrap gap-3">
                <Link to="/app" className="btn btn-primary px-7 py-3.5 text-base">
                  Start debugging free <ArrowRight size={17} strokeWidth={1.5} />
                </Link>
                <AnchorLink to="/#how" className="btn btn-ghost px-7 py-3.5 text-base">
                  See how it works
                </AnchorLink>
              </div>
            </Reveal>
            <Reveal delay={0.2}>
              <div className="mt-10 flex gap-10">
                {[
                  { v: 1, s: "", label: "question at a time" },
                  { v: 3, s: "", label: "hints per session" },
                  { v: 0, s: "", label: "answers handed out" },
                ].map((s) => (
                  <div key={s.label}>
                    <p className="text-3xl font-extrabold text-(--accent-text)">
                      <Counter to={s.v} suffix={s.s} />
                    </p>
                    <p className="mt-1 text-[13px] text-(--muted)">{s.label}</p>
                  </div>
                ))}
              </div>
            </Reveal>
          </div>
          <Reveal delay={0.1} y={28}>
            <div className="relative">
              <div className="glow-accent pointer-events-none absolute -inset-8" aria-hidden="true" />
              <HeroMockup />
            </div>
          </Reveal>
        </div>
      </section>

      {/* ---------- how it works ---------- */}
      <section id="how" className="border-t border-(--border) bg-(--bg-soft)">
        <div className="mx-auto w-[min(1200px,92%)] py-20 md:py-24">
          <Reveal>
            <p className="eyebrow">How it works</p>
            <h2 className="mt-3 max-w-xl text-3xl font-extrabold tracking-tight md:text-4xl">
              From “it’s broken” to “I know exactly why”
            </h2>
          </Reveal>
          <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {STEPS.map((step, i) => (
              <Reveal key={step.title} delay={i * 0.06}>
                <div className="card card-hover h-full p-6">
                  <span className="grid size-10 place-items-center rounded-xl bg-(--accent) text-base font-extrabold text-white">
                    {i + 1}
                  </span>
                  <h3 className="mt-4 font-bold">{step.title}</h3>
                  <p className="mt-1.5 text-sm leading-relaxed text-(--muted)">{step.body}</p>
                </div>
              </Reveal>
            ))}
          </div>
          <Reveal delay={0.1}>
            <div className="mt-8 text-center">
              <Link to="/app" className="btn btn-primary">
                Try the live demo <ArrowRight size={16} strokeWidth={1.5} />
              </Link>
            </div>
          </Reveal>
        </div>
      </section>

      {/* ---------- bento features ---------- */}
      <section id="features" className="border-t border-(--border)">
        <div className="mx-auto w-[min(1200px,92%)] py-20 md:py-24">
          <Reveal>
            <p className="eyebrow">Features</p>
            <h2 className="mt-3 max-w-xl text-3xl font-extrabold tracking-tight md:text-4xl">
              Teaching mechanics, not a chat wrapper
            </h2>
          </Reveal>
          <div className="mt-10 grid gap-4 md:grid-cols-3">
            {BENTO.map((f, i) => (
              <Reveal key={f.title} delay={(i % 3) * 0.06} className={f.span}>
                <article className="card card-hover h-full p-6">
                  <span className="grid size-11 place-items-center rounded-xl border border-(--border-strong) bg-(--accent-soft)">
                    <f.icon size={20} strokeWidth={1.5} className="text-(--accent-text)" />
                  </span>
                  <h3 className="mt-4 text-lg font-bold">{f.title}</h3>
                  <p className="mt-1.5 text-sm leading-relaxed text-(--muted)">{f.body}</p>
                  {f.mock}
                </article>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ---------- method ---------- */}
      <section id="method" className="border-t border-(--border) bg-(--bg-soft)">
        <div className="mx-auto grid w-[min(1200px,92%)] items-center gap-12 py-20 md:grid-cols-2 md:py-24">
          <Reveal>
            <p className="eyebrow">The learning method</p>
            <h2 className="mt-3 text-3xl font-extrabold tracking-tight md:text-4xl">
              Being handed an answer is not understanding
            </h2>
            <div className="mt-6 flex flex-col gap-5">
              {[
                { icon: ScanEye, t: "Diagnose silently", b: "The mentor works out what is broken, then keeps the diagnosis to itself." },
                { icon: MessagesSquare, t: "Question, not lecture", b: "Small sharp questions force you to read your own code — where debugging skill is built." },
                { icon: Flame, t: "Reasoning is graded", b: "Your understanding meter moves when your explanation is sound, not when code happens to run." },
                { icon: Sparkles, t: "Explain it back", b: "The session closes only when you describe the fix in your own words." },
              ].map((row) => (
                <div key={row.t} className="flex gap-4">
                  <span className="grid size-10 shrink-0 place-items-center rounded-xl border border-(--border-strong)">
                    <row.icon size={18} strokeWidth={1.5} className="text-(--accent-text)" />
                  </span>
                  <div>
                    <h3 className="font-bold">{row.t}</h3>
                    <p className="mt-0.5 text-sm text-(--muted)">{row.b}</p>
                  </div>
                </div>
              ))}
            </div>
          </Reveal>
          <Reveal delay={0.1}>
            <div className="card p-6 md:p-8">
              <div className="flex items-center gap-3">
                <LogoMark size={36} />
                <div>
                  <p className="font-bold">Session complete</p>
                  <p className="text-sm text-(--muted)">average.py · Python</p>
                </div>
                <span className="tag ml-auto">Solved</span>
              </div>
              <div className="mt-5">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-(--muted)">Understanding</span>
                  <span className="font-mono font-semibold">88/100</span>
                </div>
                <div className="meter mt-2"><div style={{ width: "88%" }} /></div>
              </div>
              <div className="mt-5 border-t border-(--border) pt-5">
                <p className="label">Your explanation</p>
                <p className="rounded-xl bg-(--bg-soft) p-4 text-sm leading-relaxed">
                  “len of an empty list is 0, so the division crashes. Checking for
                  empty input first keeps both calls correct.”
                </p>
              </div>
            </div>
          </Reveal>
        </div>
      </section>

      {/* ---------- faq ---------- */}
      <section id="faq" className="border-t border-(--border)">
        <div className="mx-auto w-[min(820px,92%)] py-20 md:py-24">
          <Reveal>
            <p className="eyebrow">FAQ</p>
            <h2 className="mt-3 text-3xl font-extrabold tracking-tight md:text-4xl">
              Questions, answered
            </h2>
          </Reveal>
          <Reveal delay={0.08}>
            <div className="mt-8">
              <Faq items={FAQS} />
            </div>
          </Reveal>
        </div>
      </section>

      {/* ---------- final CTA ---------- */}
      <section className="border-t border-(--border) bg-(--bg-soft)">
        <div className="mx-auto w-[min(820px,92%)] py-20 text-center md:py-24">
          <Reveal>
            <h2 className="text-3xl font-extrabold tracking-tight md:text-4xl">
              Your next bug is a lesson.
              <br />
              <span className="text-(--accent-text)">Learn it properly.</span>
            </h2>
            <p className="mx-auto mt-4 max-w-md text-(--muted)">
              One free guest session, no account needed. The mentor is waiting with
              exactly one question.
            </p>
            <div className="mt-8 flex flex-wrap justify-center gap-3">
              <Link to="/app" className="btn btn-primary px-7 py-3.5 text-base">
                Start debugging free <ArrowRight size={17} strokeWidth={1.5} />
              </Link>
              <Link to="/signup" className="btn btn-ghost px-7 py-3.5 text-base">
                Create an account
              </Link>
            </div>
          </Reveal>
        </div>
      </section>
    </main>
  );
}
