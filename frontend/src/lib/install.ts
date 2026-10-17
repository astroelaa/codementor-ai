/* PWA install experience.
 *
 * Captures the one-shot `beforeinstallprompt` event (fired by Chromium when
 * the app is installable), tracks whether the app already runs as an
 * installed app, and exposes the real prompt to any component. Nothing here
 * fakes an install: when the browser has no prompt (Firefox, desktop Safari)
 * the UI falls back to honest guidance, and on iOS — which never fires the
 * event — it shows "Share -> Add to Home Screen" instructions.
 *
 * Dismissal semantics: "Later" hides the banner for the current page view
 * only (module-level in-memory flag, reset by every reload). The app being
 * installed is the only permanent state, and it is recorded so a browser tab
 * visit after installing does not ask again.
 */
import { useEffect, useState } from "react";

type PromptEvent = Event & {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
};

const INSTALLED_KEY = "cm-installed";

const listeners = new Set<() => void>();
let deferred: PromptEvent | null = null;
let bannerDismissed = false; // in-memory: reset on every page load
let installedFlag = readInstalledFlag();

function readInstalledFlag(): boolean {
  try {
    return localStorage.getItem(INSTALLED_KEY) === "1";
  } catch {
    return false;
  }
}

function markInstalled() {
  installedFlag = true;
  try {
    localStorage.setItem(INSTALLED_KEY, "1");
  } catch {
    /* private mode: fall back to the runtime flag only */
  }
}

function emit() {
  for (const l of listeners) l();
}

function standaloneNow(): boolean {
  if (typeof window === "undefined") return false;
  const media = window.matchMedia?.("(display-mode: standalone)");
  if (media?.matches) return true;
  return (navigator as Navigator & { standalone?: boolean }).standalone === true;
}

if (typeof window !== "undefined") {
  window.addEventListener("beforeinstallprompt", (event) => {
    // Suppress Chromium's own mini-infobar so the app presents one clear,
    // dismissible offer instead of two competing ones.
    event.preventDefault();
    deferred = event as PromptEvent;
    emit();
  });
  window.addEventListener("appinstalled", () => {
    deferred = null;
    markInstalled();
    emit();
  });
}

export const IOS_INSTALL_HINT = 'Tap Share, then "Add to Home Screen".';

export function isIOSDevice(): boolean {
  if (typeof navigator === "undefined") return false;
  const ua = navigator.userAgent;
  return (
    /iphone|ipad|ipod/i.test(ua) ||
    // iPadOS 13+ reports itself as a Mac; touch points give it away.
    (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1)
  );
}

export interface InstallApi {
  /** The app runs as an installed app (standalone, iOS, or appinstalled). */
  installed: boolean;
  /** The browser handed us a real install prompt we can still trigger. */
  canPrompt: boolean;
  /** Banner visibility: not installed, not dismissed this page view, useful. */
  showBanner: boolean;
  isIOS: boolean;
  /** Trigger the real browser prompt. Returns false when none is available. */
  prompt: () => Promise<boolean>;
  /** Hide the banner until the next page load. */
  dismissBanner: () => void;
}

export function useInstall(): InstallApi {
  const [, force] = useState(0);

  useEffect(() => {
    const listener = () => force((n) => n + 1);
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
    };
  }, []);

  const installed = installedFlag || standaloneNow();
  const canPrompt = !installed && deferred !== null;

  return {
    installed,
    canPrompt,
    isIOS: !installed && isIOSDevice(),
    showBanner: !installed && !bannerDismissed && (canPrompt || isIOSDevice()),
    async prompt() {
      if (!deferred) return false;
      const event = deferred;
      // One-shot: the event cannot be reused, and Chromium decides when (or
      // whether) to fire a fresh one after the user chooses.
      deferred = null;
      try {
        await event.prompt();
        const choice = await event.userChoice;
        if (choice.outcome === "accepted") markInstalled();
      } catch {
        /* some engines throw when the prompt is ignored; offer guidance */
      }
      emit();
      return true;
    },
    dismissBanner() {
      bannerDismissed = true;
      emit();
    },
  };
}
