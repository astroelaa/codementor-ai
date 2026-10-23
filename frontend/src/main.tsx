import { StrictMode, Suspense, lazy, useEffect } from "react";
import { createRoot } from "react-dom/client";
import { useRegisterSW } from "virtual:pwa-register/react";
import {
  HashRouter,
  Navigate,
  Route,
  Routes,
  useLocation,
} from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AnimatePresence, MotionConfig, motion } from "framer-motion";
import { AuthProvider } from "./lib/auth";
import { ThemeProvider } from "./lib/theme";
import { ToastProvider, useToast } from "./lib/toast";
import { Navbar } from "./components/Navbar";
import { Footer } from "./components/Footer";
import { InstallBanner } from "./components/InstallBanner";
import { ErrorBoundary, RouteErrorFallback } from "./components/ErrorBoundary";
import "./index.css";

const Landing = lazy(() =>
  import("./pages/Landing").then((m) => ({ default: m.Landing })),
);
const Login = lazy(() =>
  import("./pages/Login").then((m) => ({ default: m.Login })),
);
const Signup = lazy(() =>
  import("./pages/Signup").then((m) => ({ default: m.Signup })),
);
const Workspace = lazy(() =>
  import("./pages/Workspace").then((m) => ({ default: m.Workspace })),
);
const Dashboard = lazy(() =>
  import("./pages/Dashboard").then((m) => ({ default: m.Dashboard })),
);
const History = lazy(() =>
  import("./pages/History").then((m) => ({ default: m.History })),
);
const Docs = lazy(() =>
  import("./pages/Docs").then((m) => ({ default: m.Docs })),
);
const Forgot = lazy(() =>
  import("./pages/Password").then((m) => ({ default: m.Forgot })),
);
const Reset = lazy(() =>
  import("./pages/Password").then((m) => ({ default: m.Reset })),
);
const Projects = lazy(() =>
  import("./pages/Projects").then((m) => ({ default: m.Projects })),
);
const Profile = lazy(() =>
  import("./pages/Profile").then((m) => ({ default: m.Profile })),
);
const LegalPrivacy = lazy(() =>
  import("./pages/Legal").then((m) => ({ default: m.Privacy })),
);
const LegalTerms = lazy(() =>
  import("./pages/Legal").then((m) => ({ default: m.Terms })),
);
const About = lazy(() =>
  import("./pages/About").then((m) => ({ default: m.About })),
);

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, staleTime: 60_000, refetchOnWindowFocus: false },
  },
});

function ScrollToTop() {
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);
  return null;
}

function PwaStatus() {
  const toast = useToast();
  // Explicit registration (injectRegister is off): updates and offline state
  // surface as UI instead of silent swaps. AI mentoring always needs the
  // network — only the app shell is cached, never API data.
  const {
    offlineReady: [offlineReady],
    needRefresh: [needRefresh],
    updateServiceWorker,
  } = useRegisterSW();
  useEffect(() => {
    if (offlineReady)
      toast("info", "App shell cached for offline starts. The mentor needs a connection.");
  }, [offlineReady, toast]);
  if (!needRefresh) return null;
  return (
    <div className="fixed bottom-20 left-1/2 z-[100] -translate-x-1/2">
      <button
        type="button"
        onClick={() => void updateServiceWorker(true)}
        className="btn btn-primary btn-sm shadow-xl"
      >
        Update available — reload
      </button>
    </div>
  );
}

function Shell() {
  const { pathname } = useLocation();
  return (
    <div className="flex min-h-screen flex-col">
      <Navbar />
      <div className="flex-1">
        {/* Restrained page transition: a short fade with a couple of pixels
            of travel, keyed by pathname so anchor scrolls do not remount.
            MotionConfig reducedMotion="user" turns all of this into a
            plain fade for reduced-motion users. */}
        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={pathname}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.18, ease: "easeOut" }}
          >
            <ErrorBoundary
              key={pathname}
              fallback={<RouteErrorFallback />}
              onError={(error) => console.error("route render failed:", error)}
            >
              <Suspense
                fallback={
                  <div className="mx-auto flex min-h-screen w-[min(1200px,92%)] flex-col gap-3 py-20" aria-label="Loading page">
                    <div className="skeleton h-8 w-1/3" />
                    <div className="skeleton h-4 w-2/3" />
                    <div className="skeleton h-4 w-1/2" />
                  </div>
                }
              >
                <Routes>
                  <Route path="/" element={<Landing />} />
                  <Route path="/app" element={<Workspace />} />
                  <Route path="/projects" element={<Projects />} />
                  <Route path="/dashboard" element={<Dashboard />} />
                  <Route path="/history" element={<History />} />
                  <Route path="/docs" element={<Docs />} />
                  <Route path="/login" element={<Login />} />
                  <Route path="/signup" element={<Signup />} />
                  <Route path="/profile" element={<Profile />} />
                  <Route path="/forgot" element={<Forgot />} />
                  <Route path="/reset" element={<Reset />} />
                  <Route path="/privacy" element={<LegalPrivacy />} />
                  <Route path="/terms" element={<LegalTerms />} />
                  <Route path="/about" element={<About />} />
                  <Route path="*" element={<Navigate to="/" replace />} />
                </Routes>
              </Suspense>
            </ErrorBoundary>
          </motion.div>
        </AnimatePresence>
      </div>
      <Footer />
    </div>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <AuthProvider>
          <ToastProvider>
            <MotionConfig reducedMotion="user">
              <HashRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
                <ScrollToTop />
                {/* Service worker registration is production-only: in dev the
                    register hook is a no-op and this component is not even
                    mounted, so no worker is registered or checked. */}
                {import.meta.env.PROD && <PwaStatus />}
                <InstallBanner />
                <Shell />
              </HashRouter>
            </MotionConfig>
          </ToastProvider>
        </AuthProvider>
      </ThemeProvider>
    </QueryClientProvider>
  </StrictMode>,
);
