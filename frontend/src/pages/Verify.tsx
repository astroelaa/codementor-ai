import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { CheckCircle2, Loader2, XCircle } from "lucide-react";
import { ApiError, api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { Reveal } from "../components/Reveal";
import { Logo } from "../components/Logo";

export function Verify() {
  const [params] = useSearchParams();
  const { refresh } = useAuth();
  const [state, setState] = useState<"working" | "ok" | "fail">("working");
  const [message, setMessage] = useState("");
  const ran = useRef(false);

  useEffect(() => {
    if (ran.current) return;
    ran.current = true;
    const token = params.get("token") ?? "";
    if (!token) {
      setState("fail");
      setMessage("This link is missing its token. Request a new verification email.");
      return;
    }
    api
      .verifyEmail(token)
      .then((r) => {
        setState("ok");
        setMessage(r.message);
        void refresh();
      })
      .catch((err) => {
        setState("fail");
        setMessage(err instanceof ApiError ? err.message : "Verification failed.");
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <main className="mx-auto w-[min(440px,92%)] py-16 md:py-24">
      <Reveal>
        <div className="card p-7 text-center md:p-9">
          <div className="flex justify-center"><Logo compact /></div>
          <h1 className="mt-4 text-2xl font-extrabold tracking-tight">Email verification</h1>
          <div className="mt-5" aria-live="polite">
            {state === "working" && (
              <p className="flex items-center justify-center gap-2 text-(--muted)">
                <Loader2 size={17} strokeWidth={1.5} className="animate-spin" />
                Checking your link…
              </p>
            )}
            {state === "ok" && (
              <>
                <p className="flex items-center justify-center gap-2 font-semibold text-(--success)">
                  <CheckCircle2 size={18} strokeWidth={1.5} /> {message}
                </p>
                <Link to="/app" className="btn btn-primary mt-5 w-full">Start debugging</Link>
              </>
            )}
            {state === "fail" && (
              <>
                <p className="flex items-center justify-center gap-2 font-semibold text-(--danger)">
                  <XCircle size={18} strokeWidth={1.5} /> {message}
                </p>
                <p className="mt-3 text-sm text-(--muted)">
                  Links expire after 24 hours and work only once. Log in to request a fresh one.
                </p>
                <Link to="/login" className="btn btn-ghost mt-5 w-full">Back to log in</Link>
              </>
            )}
          </div>
        </div>
      </Reveal>
    </main>
  );
}
