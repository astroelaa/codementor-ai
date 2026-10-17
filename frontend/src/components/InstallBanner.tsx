import { Download } from "lucide-react";
import { IOS_INSTALL_HINT, useInstall } from "../lib/install";
import { useToast } from "../lib/toast";

const MANUAL_HINT = 'Open your browser menu and choose "Install app" (or "Add to Home Screen").';

/**
 * Bottom banner that offers the real install prompt. It appears on every
 * page load until the app is installed; "Later" hides it for this page view
 * only. iOS gets short Share -> Add to Home Screen instructions because no
 * prompt event exists there.
 */
export function InstallBanner() {
  const { showBanner, isIOS, prompt, dismissBanner } = useInstall();
  const toast = useToast();

  if (!showBanner) return null;

  async function install() {
    if (isIOS) {
      toast("info", IOS_INSTALL_HINT);
      return;
    }
    const shown = await prompt();
    if (!shown) toast("info", MANUAL_HINT);
  }

  return (
    <div
      data-install-banner
      className="fixed inset-x-3 bottom-3 z-[95] mx-auto w-auto max-w-xl"
      role="status"
    >
      <div className="glass-pop flex items-center gap-3 px-4 py-3 shadow-xl">
        <span className="grid size-9 shrink-0 place-items-center rounded-[10px] accent-deep text-white" aria-hidden="true">
          <Download size={17} strokeWidth={1.5} />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-[13px] font-bold">Install CodeMentor AI</p>
          <p className="text-xs text-(--muted)">
            {isIOS
              ? IOS_INSTALL_HINT
              : "Opens full screen and starts offline. The mentor needs a connection."}
          </p>
        </div>
        {!isIOS && (
          <button type="button" onClick={() => void install()} className="btn btn-primary btn-sm shrink-0">
            Install
          </button>
        )}
        <button
          type="button"
          onClick={dismissBanner}
          className="btn btn-ghost btn-sm shrink-0 px-3"
          aria-label="Hide install banner for now"
        >
          {isIOS ? "Got it" : "Later"}
        </button>
      </div>
    </div>
  );
}
