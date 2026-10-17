import {
  Component,
  useEffect,
  useState,
  type ErrorInfo,
  type ReactNode,
} from "react";
import { Link } from "react-router-dom";
import { RefreshCw, TriangleAlert, WifiOff } from "lucide-react";

interface Props {
  children: ReactNode;
  /** Rendered instead of the children once a child throws. */
  fallback: ReactNode;
  /** Optional hook for logging. Falls back to silence (decorative boundaries). */
  onError?: (error: unknown) => void;
}

interface State {
  failed: boolean;
}

/**
 * Minimal error boundary. Used twice:
 *  - around the lazy three.js Wave chunk, where a failed chunk load (offline,
 *    new deploy with rotated hashes) must fall back to the static gradient
 *    without a trace in the UI;
 *  - at route level, where the fallback is the friendly offline/reload screen.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { failed: false };

  static getDerivedStateFromError(): State {
    return { failed: true };
  }

  componentDidCatch(error: Error, _info: ErrorInfo) {
    this.props.onError?.(error);
  }

  render() {
    return this.state.failed ? this.props.fallback : this.props.children;
  }
}

/**
 * Route-level failure screen: one honest message for chunk/render errors and
 * a Reload button. When the device is offline it says so instead of blaming
 * the app; the connection is watched live so the text flips the moment the
 * network comes back. A Reload is always safe here — nothing in the app
 * shell is lost, and sessions live on the server.
 */
export function RouteErrorFallback() {
  const [offline, setOffline] = useState(
    typeof navigator === "undefined" ? false : !navigator.onLine,
  );

  useEffect(() => {
    const up = () => setOffline(false);
    const down = () => setOffline(true);
    window.addEventListener("online", up);
    window.addEventListener("offline", down);
    return () => {
      window.removeEventListener("online", up);
      window.removeEventListener("offline", down);
    };
  }, []);

  return (
    <div className="mx-auto flex min-h-[60vh] w-[min(560px,92%)] flex-col items-center justify-center py-20 text-center">
      <span className="pill">
        {offline ? (
          <WifiOff size={14} strokeWidth={1.5} aria-hidden="true" />
        ) : (
          <TriangleAlert size={14} strokeWidth={1.5} aria-hidden="true" />
        )}
        {offline ? "Offline" : "Load error"}
      </span>
      <h1 className="h2-serif mt-5 text-2xl">
        {offline ? "You\u2019re offline" : "This page didn\u2019t load"}
      </h1>
      <p className="mt-3 text-sm leading-relaxed text-(--muted)">
        {offline
          ? "The app shell is on your device, but this page hasn\u2019t been " +
            "saved for offline use yet. Reconnect and reload \u2014 your code " +
            "and sessions are safe."
          : "Something went wrong while loading this page. A reload usually " +
            "fixes it \u2014 your code and sessions are safe."}
      </p>
      <div className="mt-7 flex flex-wrap justify-center gap-3">
        <button
          type="button"
          onClick={() => window.location.reload()}
          className="btn btn-primary"
        >
          <RefreshCw size={16} strokeWidth={1.5} /> Reload
        </button>
        <Link to="/" className="btn btn-ghost">
          Back to home
        </Link>
      </div>
    </div>
  );
}
