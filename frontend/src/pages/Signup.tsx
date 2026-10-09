import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { UserPlus } from "lucide-react";
import { useAuth } from "../lib/auth";
import { ApiError } from "../lib/api";
import { useToast } from "../lib/toast";
import { Reveal } from "../components/Reveal";
import { Logo } from "../components/Logo";

export function Signup() {
  const { signup } = useAuth();
  const navigate = useNavigate();
  const toast = useToast();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await signup(email.trim(), password, name.trim());
      toast("success", "Account created. Let us debug something.");
      navigate("/app");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Signup failed. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto w-[min(440px,92%)] py-16 md:py-24">
      <Reveal>
        <div className="card p-7 md:p-9">
          <Logo />
          <h1 className="mt-5 text-2xl font-extrabold tracking-tight">Create your account</h1>
          <p className="mt-1 text-sm text-(--muted)">Free. Unlimited sessions. Your progress, saved.</p>
          <form onSubmit={onSubmit} className="mt-6 flex flex-col gap-4">
            <div>
              <label className="label" htmlFor="signup-name">Display name</label>
              <input
                id="signup-name"
                className="input"
                type="text"
                autoComplete="nickname"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Ada"
              />
            </div>
            <div>
              <label className="label" htmlFor="signup-email">Email</label>
              <input
                id="signup-email"
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
              <label className="label" htmlFor="signup-password">Password</label>
              <input
                id="signup-password"
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
              <UserPlus size={16} strokeWidth={1.5} />
              {busy ? "Creating…" : "Sign up free"}
            </button>
          </form>
          <p className="mt-5 text-center text-sm text-(--muted)">
            Already have an account?{" "}
            <Link to="/login" className="font-semibold text-(--accent-text)">Log in</Link>
          </p>
        </div>
      </Reveal>
    </main>
  );
}
