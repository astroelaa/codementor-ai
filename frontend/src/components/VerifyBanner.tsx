import { useState } from "react";
import { MailWarning } from "lucide-react";
import { ApiError, api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useToast } from "../lib/toast";

/** Shown to signed-in users whose email is not verified yet. */
export function VerifyBanner() {
  const { user } = useAuth();
  const toast = useToast();
  const [busy, setBusy] = useState(false);

  if (!user || user.is_verified) return null;

  async function resend() {
    if (busy) return;
    setBusy(true);
    try {
      const r = await api.resendVerification();
      toast("success", r.message);
    } catch (err) {
      toast("error", err instanceof ApiError ? err.message : "Try again later.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card mt-5 flex flex-wrap items-center gap-3 px-5 py-3.5 text-sm" role="status">
      <MailWarning size={16} strokeWidth={1.5} className="text-(--warning)" />
      <span className="text-(--muted)">
        Your email is unverified. Everything works, but verify to protect your account.
      </span>
      <button type="button" onClick={() => void resend()} disabled={busy} className="btn btn-ghost btn-sm ml-auto">
        {busy ? "Sending…" : "Resend verification email"}
      </button>
    </div>
  );
}
