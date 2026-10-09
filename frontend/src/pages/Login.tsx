import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { LogIn } from "lucide-react";
import { useAuth } from "../lib/auth";
import { ApiError } from "../lib/api";
import { useToast } from "../lib/toast";
import { Reveal } from "../components/Reveal";
import { Logo } from "../components/Logo";

export function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const toast = useToast();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await login(email.trim(), password);
      toast("success", "Welcome back.");
      navigate("/app");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Login failed. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto w-[min(440px,92%)] py-16 md:py-24">
      <Reveal>
        <div className="card p-7 md:p-9">
          <Logo />
          <h1 className="mt-5 text-2xl font-extrabold tracking-tight">Log in</h1>
          <p className="mt-1 text-sm text-(--muted)">Pick up where your reasoning left off.</p>
          <form onSubmit={onSubmit} className="mt-6 flex flex-col gap-4">
            <div>
              <label className="label" htmlFor="login-email">Email</label>
              <input
                id="login-email"
                className="input"
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
              />
            </div>
            <div>
              <label className="label" htmlFor="login-password">Password</label>
              <input
                id="login-password"
                className="input"
                type="password"
                required
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Your password"
              />
            </div>
            {error && (
              <p role="alert" className="rounded-lg border border-(--danger) bg-(--danger)/10 px-3 py-2 text-sm">
                {error}
              </p>
            )}
            <button type="submit" className="btn btn-primary w-full" disabled={busy}>
              <LogIn size={16} strokeWidth={1.5} />
              {busy ? "Logging in…" : "Log in"}
            </button>
          </form>
          <p className="mt-5 text-center text-sm text-(--muted)">
            No account yet?{" "}
            <Link to="/signup" className="font-semibold text-(--accent-text)">Sign up free</Link>
          </p>
        </div>
      </Reveal>
    </main>
  );
}
