import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { CheckCircle2, KeyRound, Mail } from "lucide-react";
import { ApiError } from "../lib/api";
import { useAuth } from "../lib/auth";
import { Reveal } from "../components/Reveal";
import { Logo } from "../components/Logo";

export function Forgot() {
  const { sendPasswordReset } = useAuth();
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState("");

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!email.trim() || busy) return;
    setBusy(true);
    try {
      await sendPasswordReset(email.trim());
      setSent(
        "If an account exists for that email, a reset link is on its way.",
      );
    } catch (err) {
      setSent(err instanceof ApiError ? err.message : "Try again in a moment.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto w-[min(440px,92%)] py-16 md:py-24">
      <Reveal>
        <div className="card p-7 md:p-9">
          <Logo />
          <h1 className="mt-5 text-2xl font-extrabold tracking-tight">Forgot password</h1>
          <p className="mt-1 text-sm text-(--muted)">We never email passwords — only a one-time reset link.</p>
          {sent ? (
            <p role="status" className="mt-6 rounded-xl border border-(--border) bg-(--bg-soft) p-4 text-sm">
              {sent}
            </p>
          ) : (
            <form onSubmit={onSubmit} className="mt-6 flex flex-col gap-4">
              <div>
                <label className="label" htmlFor="forgot-email">Email</label>
                <input
                  id="forgot-email"
                  className="input"
                  type="email"
                  required
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                />
              </div>
              <button type="submit" className="btn btn-primary w-full" disabled={busy}>
                <Mail size={16} strokeWidth={1.5} />
                {busy ? "Sending…" : "Send reset link"}
              </button>
            </form>
          )}
          <p className="mt-5 text-center text-sm text-(--muted)">
            <Link to="/login" className="font-semibold text-(--accent-text)">Back to log in</Link>
          </p>
        </div>
      </Reveal>
    </main>
  );
}

export function Reset() {
  const { user, loading, resetPassword, logout } = useAuth();
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!password || busy) return;
    setBusy(true);
    setError("");
    try {
      await resetPassword(password);
      await logout();
      setDone(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Reset failed. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto w-[min(440px,92%)] py-16 md:py-24">
      <Reveal>
        <div className="card p-7 md:p-9">
          <Logo />
          <h1 className="mt-5 text-2xl font-extrabold tracking-tight">Choose a new password</h1>
          {done ? (
            <p role="status" className="mt-4 flex items-center gap-2 font-semibold text-(--success)">
              <CheckCircle2 size={18} strokeWidth={1.5} /> Password updated. Log in with your new password.
            </p>
          ) : loading ? (
            <p role="status" className="mt-4 text-sm text-(--muted)">
              Checking your reset link…
            </p>
          ) : !user ? (
            <p role="alert" className="mt-4 text-sm text-(--muted)">
              This reset link is invalid or has expired. Request a fresh reset
              link from the log-in page.
            </p>
          ) : (
            <form onSubmit={onSubmit} className="mt-6 flex flex-col gap-4">
              <div>
                <label className="label" htmlFor="reset-password">New password</label>
                <input
                  id="reset-password"
                  className="input"
                  type="password"
                  required
                  minLength={8}
                  autoComplete="new-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="At least 8 characters"
                />
              </div>
              {error && (
                <p role="alert" className="rounded-lg border border-(--danger) bg-(--danger)/10 px-3 py-2 text-sm">
                  {error}
                </p>
              )}
              <button type="submit" className="btn btn-primary w-full" disabled={busy}>
                <KeyRound size={16} strokeWidth={1.5} />
                {busy ? "Saving…" : "Reset password"}
              </button>
            </form>
          )}
          {done && (
            <Link to="/login" className="btn btn-ghost mt-5 w-full">Back to log in</Link>
          )}
        </div>
      </Reveal>
    </main>
  );
}
