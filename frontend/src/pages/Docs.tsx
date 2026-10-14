import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { BookOpenText, Loader2, RefreshCw, Sparkles } from "lucide-react";
import { ApiError, api, type DocHistoryItem, type DocResult } from "../lib/api";
import { useAuth } from "../lib/auth";
import { Reveal } from "../components/Reveal";
import { EmptyState } from "../components/bits";
import { LANGUAGES } from "../lib/detect";

const MAX_LEN = 4000;

export function Docs() {
  const { user } = useAuth();
  const [text, setText] = useState("");
  const [language, setLanguage] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<DocResult | null>(null);

  const history = useQuery({
    queryKey: ["docs-history"],
    queryFn: api.docHistory,
    enabled: !!user,
    retry: 1,
  });

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!text.trim() || busy) return;
    setBusy(true);
    setError("");
    setResult(null);
    try {
      const r = await api.simplifyDocs(text.trim(), language);
      setResult(r);
      void history.refetch();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Simplification failed. Try again.");
    } finally {
      setBusy(false);
    }
  }

  if (!user) {
    return (
      <main className="mx-auto w-[min(760px,92%)] py-16">
        <EmptyState
          title="Sign in to simplify docs"
          body="Paste documentation or technical text and get a plain-language explanation, saved to your history."
        />
        <div className="mt-5 flex justify-center gap-3">
          <Link to="/login" className="btn btn-ghost">Log in</Link>
          <Link to="/signup" className="btn btn-primary">Sign up free</Link>
        </div>
      </main>
    );
  }

  const renderRecord = (r: DocResult | DocHistoryItem, input?: string) => (
    <div className="card p-5 md:p-6">
      {input && (
        <details className="mb-4">
          <summary className="cursor-pointer text-[13px] font-semibold text-(--muted)">
            Source text
          </summary>
          <p className="mt-2 max-h-40 overflow-y-auto rounded-xl bg-(--bg-soft) p-3 font-mono text-xs leading-relaxed text-(--muted)">
            {input}
          </p>
        </details>
      )}
      <div className="flex items-start gap-2.5">
        <BookOpenText size={17} strokeWidth={1.5} className="mt-0.5 shrink-0 text-(--accent-text)" />
        <p className="serif-body text-(--text)">{r.explanation}</p>
      </div>
      {r.example && (
        <div className="mt-4">
          <p className="label">Example</p>
          <pre className="overflow-x-auto rounded-xl border border-(--border) bg-(--bg-soft) p-3.5 font-mono text-[13px] leading-relaxed">
            {r.example}
          </pre>
        </div>
      )}
      {r.question && (
        <div className="mt-4 rounded-xl border border-(--border-strong) bg-(--accent-soft) p-3.5 text-sm">
          <span className="font-semibold">Check yourself: </span>
          {r.question}
        </div>
      )}
    </div>
  );

  return (
    <main className="mx-auto w-[min(900px,92%)] py-8 md:py-12">
      <Reveal>
        <p className="eyebrow">Documentation simplifier</p>
        <h1 className="h2-serif mt-2 text-3xl md:text-4xl">Understand any docs</h1>
        <p className="mt-2 max-w-xl text-[15px] text-(--muted)">
          Paste documentation or technical text. You get a plain-language explanation
          grounded in your source — never invented facts.
        </p>
      </Reveal>

      <Reveal delay={0.05}>
        <form onSubmit={onSubmit} className="card mt-6 p-5 md:p-6">
          <div className="flex flex-wrap items-end gap-3">
            <div>
              <label className="label" htmlFor="docs-lang">Language (optional)</label>
              <select
                id="docs-lang"
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
                className="rounded-lg border border-(--border) bg-(--surface-2) px-2.5 py-2 text-sm font-semibold outline-none focus:border-(--accent) [&>option]:bg-(--surface-2) [&>option]:text-(--text)"
              >
                <option value="">General</option>
                {LANGUAGES.map((l) => (
                  <option key={l.value} value={l.value}>{l.label}</option>
                ))}
              </select>
            </div>
            <span className="ml-auto font-mono text-xs text-(--faint)">
              {text.length}/{MAX_LEN}
            </span>
          </div>
          <label className="label mt-4" htmlFor="docs-text">Documentation or technical text</label>
          <textarea
            id="docs-text"
            className="input min-h-36 resize-y font-mono text-[13px]"
            value={text}
            maxLength={MAX_LEN}
            onChange={(e) => setText(e.target.value)}
            placeholder="Paste the docs, error message, or function reference you want explained…"
          />
          {error && (
            <p role="alert" className="mt-3 rounded-lg border border-(--danger) bg-(--danger)/10 px-3 py-2 text-sm">
              {error}
            </p>
          )}
          <button type="submit" className="btn btn-primary mt-4" disabled={busy || !text.trim()}>
            {busy ? <Loader2 size={16} strokeWidth={1.5} className="animate-spin" /> : <Sparkles size={16} strokeWidth={1.5} />}
            {busy ? "Simplifying…" : "Simplify"}
          </button>
        </form>
      </Reveal>

      {result && (
        <Reveal>
          <div className="mt-5">{renderRecord(result)}</div>
        </Reveal>
      )}

      <div className="mt-8">
        <h2 className="font-bold">History</h2>
        {history.isPending ? (
          <div className="mt-3 flex flex-col gap-2" aria-label="Loading doc history">
            <div className="skeleton h-20" />
            <div className="skeleton h-20" />
          </div>
        ) : history.isError ? (
          <div className="mt-3 flex items-center gap-3">
            <p className="text-sm text-(--muted)">Could not load history.</p>
            <button type="button" onClick={() => void history.refetch()} className="btn btn-ghost btn-sm">
              <RefreshCw size={14} strokeWidth={1.5} /> Retry
            </button>
          </div>
        ) : (history.data ?? []).length === 0 && !result ? (
          <p className="mt-3 text-sm text-(--muted)">Nothing simplified yet — your past explanations will appear here.</p>
        ) : (
          <div className="mt-3 flex flex-col gap-4">
            {(history.data ?? []).map((h) => (
              <div key={h.id}>{renderRecord(h, h.input_text)}</div>
            ))}
          </div>
        )}
      </div>
    </main>
  );
}
