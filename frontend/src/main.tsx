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
import { AuthProvider } from "./lib/auth";
import { ThemeProvider } from "./lib/theme";
import { ToastProvider, useToast } from "./lib/toast";
import { Navbar } from "./components/Navbar";
import { Footer } from "./components/Footer";
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
const LegalPrivacy = lazy(() =>
  import("./pages/Legal").then((m) => ({ default: m.Privacy })),
);
const LegalTerms = lazy(() =>
  import("./pages/Legal").then((m) => ({ default: m.Terms })),
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
  return (
    <div className="flex min-h-screen flex-col">
      <Navbar />
      <div className="flex-1">
        <Suspense
          fallback={
            <div className="mx-auto flex w-[min(1200px,92%)] flex-col gap-3 py-20" aria-label="Loading page">
              <div className="skeleton h-8 w-1/3" />
              <div className="skeleton h-4 w-2/3" />
              <div className="skeleton h-4 w-1/2" />
            </div>
          }
        >
          <Routes>
            <Route path="/" element={<Landing />} />
            <Route path="/app" element={<Workspace />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/history" element={<History />} />
            <Route path="/docs" element={<Docs />} />
            <Route path="/login" element={<Login />} />
            <Route path="/signup" element={<Signup />} />
            <Route path="/privacy" element={<LegalPrivacy />} />
            <Route path="/terms" element={<LegalTerms />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
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
            <HashRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
              <ScrollToTop />
              <PwaStatus />
              <Shell />
            </HashRouter>
          </ToastProvider>
        </AuthProvider>
      </ThemeProvider>
    </QueryClientProvider>
  </StrictMode>,
);
