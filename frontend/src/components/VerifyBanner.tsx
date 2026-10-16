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
      // 200 here means the backend's email provider accepted the message.
      // Anything else (502 send failure, 429 rate limit) throws ApiError.
      await api.resendVerification();
      toast("success", "Verification email sent. Check your inbox.");
    } catch (err) {
      if (err instanceof ApiError && err.status === 429) {
        toast("error", "Too many requests. Try again later.");
      } else if (err instanceof ApiError && err.status === 502) {
        toast("error", "Could not send the email. Try again later.");
      } else {
        toast("error", err instanceof ApiError ? err.message : "Try again later.");
      }
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
