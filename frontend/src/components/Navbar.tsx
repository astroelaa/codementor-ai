import { Link, NavLink, useNavigate } from "react-router-dom";
import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import {
  Bell,
  CheckCheck,
  ChevronDown,
  Menu,
  Moon,
  Sun,
  User as UserIcon,
  X,
} from "lucide-react";
import { AnchorLink } from "./AnchorLink";
import { Logo } from "./Logo";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useTheme } from "../lib/theme";

const LINKS = [
  { to: "/app", label: "Demo", anchor: false },
  { to: "/projects", label: "Projects", anchor: false },
  { to: "/dashboard", label: "Dashboard", anchor: false },
  { to: "/history", label: "History", anchor: false },
  { to: "/docs", label: "Docs", anchor: false },
  { to: "/#method", label: "Method", anchor: true },
  { to: "/#features", label: "Features", anchor: true },
  { to: "/#faq", label: "FAQ", anchor: true },
];

export function Navbar() {
  const { user, logout } = useAuth();
  const { theme, toggle } = useTheme();
  const [open, setOpen] = useState(false);
  const [bellOpen, setBellOpen] = useState(false);
  const [accountOpen, setAccountOpen] = useState(false);
  const accountRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!accountOpen) return;
    function onDocClick(e: MouseEvent) {
      if (accountRef.current && !accountRef.current.contains(e.target as Node)) {
        setAccountOpen(false);
      }
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setAccountOpen(false);
    }
    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [accountOpen]);

  const unread = useQuery({
    queryKey: ["notifications-unread"],
    queryFn: api.unreadCount,
    enabled: !!user,
    staleTime: 30_000,
    retry: 1,
  });
  const notes = useQuery({
    queryKey: ["notifications"],
    queryFn: api.notifications,
    enabled: !!user && bellOpen,
    staleTime: 30_000,
    retry: 1,
  });
  const unreadN = unread.data?.count ?? 0;

  async function openBell() {
    const next = !bellOpen;
    setBellOpen(next);
    if (next) void notes.refetch();
  }

  async function readOne(id: string) {
    await api.markNotificationRead(id);
    void queryClient.invalidateQueries({ queryKey: ["notifications"] });
    void queryClient.invalidateQueries({ queryKey: ["notifications-unread"] });
  }

  async function readAll() {
    await api.markAllNotificationsRead();
    void queryClient.invalidateQueries({ queryKey: ["notifications"] });
    void queryClient.invalidateQueries({ queryKey: ["notifications-unread"] });
  }

  return (
    <header className="glass sticky top-0 z-50 border-b border-(--border)">
      <div className="mx-auto flex h-16 w-[min(1200px,92%)] items-center gap-4">
        <Link to="/" aria-label="CodeMentor AI home">
          <Logo />
        </Link>
        <nav className="ml-6 hidden items-center gap-5 lg:flex" aria-label="Primary">
          {LINKS.map((l) =>
            l.anchor ? (
              <AnchorLink
                key={l.label}
                to={l.to}
                className="text-sm text-(--muted) transition-colors hover:text-(--text)"
              >
                {l.label}
              </AnchorLink>
            ) : (
              <NavLink
                key={l.label}
                to={l.to}
                className="text-sm text-(--muted) transition-colors hover:text-(--text)"
              >
                {l.label}
              </NavLink>
            ),
          )}
        </nav>
        <div className="ml-auto flex items-center gap-2">
          <button
            type="button"
            onClick={toggle}
            aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
            className="grid size-9 place-items-center rounded-[10px] border border-(--border) text-(--muted) transition-colors hover:text-(--text)"
          >
            {theme === "dark" ? <Sun size={17} strokeWidth={1.5} /> : <Moon size={17} strokeWidth={1.5} />}
          </button>
          {user ? (
            <>
              <div className="relative">
                <button
                  type="button"
                  onClick={() => void openBell()}
                  aria-label={unreadN > 0 ? `${unreadN} unread notifications` : "Notifications"}
                  aria-expanded={bellOpen}
                  className="relative grid size-9 place-items-center rounded-[10px] border border-(--border) text-(--muted) transition-colors hover:text-(--text)"
                >
                  <Bell size={17} strokeWidth={1.5} />
                  {unreadN > 0 && (
                    <span className="absolute -right-1.5 -top-1.5 grid h-5 min-w-5 place-items-center rounded-full bg-(--accent) px-1 text-[10px] font-bold text-white">
                      {unreadN > 9 ? "9+" : unreadN}
                    </span>
                  )}
                </button>
                <AnimatePresence>
                  {bellOpen && (
                    <motion.div
                      initial={{ opacity: 0, y: -4, scale: 0.98 }}
                      animate={{ opacity: 1, y: 0, scale: 1 }}
                      exit={{ opacity: 0, y: -4, scale: 0.98 }}
                      transition={{ duration: 0.16, ease: "easeOut" }}
                      className="card absolute right-0 top-11 z-[90] max-h-80 w-80 overflow-y-auto p-2"
                      role="dialog"
                      aria-label="Notifications"
                    >
                      <div className="flex items-center justify-between px-2 py-1.5">
                        <span className="text-[13px] font-bold">Notifications</span>
                        <button type="button" onClick={() => void readAll()} className="flex items-center gap-1 text-xs font-semibold text-(--muted) hover:text-(--text)">
                          <CheckCheck size={13} strokeWidth={1.5} /> Mark all read
                        </button>
                      </div>
                      {(notes.data ?? []).length === 0 ? (
                        <p className="px-2 py-4 text-center text-[13px] text-(--muted)">
                          {notes.isPending ? "Loading…" : "All caught up."}
                        </p>
                      ) : (
                        (notes.data ?? []).slice(0, 8).map((n) => (
                          <button
                            key={n.id}
                            type="button"
                            onClick={() => void readOne(n.id)}
                            className={`block w-full rounded-lg px-2.5 py-2 text-left transition-colors hover:bg-(--surface-2) ${n.read ? "opacity-60" : ""}`}
                          >
                            <span className="block text-[13px] font-semibold">{n.title}</span>
                            {n.body && <span className="block text-xs text-(--muted)">{n.body}</span>}
                          </button>
                        ))
                      )}
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
              <div className="relative" ref={accountRef}>
                <button
                  type="button"
                  onClick={() => setAccountOpen((o) => !o)}
                  aria-label="Account menu"
                  aria-expanded={accountOpen}
                  className="flex max-w-40 items-center gap-1 rounded-[10px] border border-(--border) px-2.5 py-2 text-sm text-(--muted) transition-colors hover:text-(--text)"
                >
                  <UserIcon size={15} strokeWidth={1.5} aria-hidden />
                  <span className="hidden max-w-24 truncate sm:inline">
                    {user.display_name || user.email}
                  </span>
                  <ChevronDown
                    size={13}
                    strokeWidth={1.5}
                    className={`shrink-0 transition-transform ${accountOpen ? "rotate-180" : ""}`}
                    aria-hidden
                  />
                </button>
                <AnimatePresence>
                  {accountOpen && (
                    <motion.div
                      initial={{ opacity: 0, y: -4, scale: 0.98 }}
                      animate={{ opacity: 1, y: 0, scale: 1 }}
                      exit={{ opacity: 0, y: -4, scale: 0.98 }}
                      transition={{ duration: 0.16, ease: "easeOut" }}
                      className="card absolute right-0 top-11 z-[90] w-56 p-2"
                      role="dialog"
                      aria-label="Account"
                    >
                      <NavLink
                        to="/profile"
                        onClick={() => setAccountOpen(false)}
                        className="block rounded-lg px-2.5 py-2 text-[13px] font-semibold transition-colors hover:bg-(--surface-2)"
                      >
                        Profile & settings
                      </NavLink>
                      <NavLink
                        to="/dashboard"
                        onClick={() => setAccountOpen(false)}
                        className="block rounded-lg px-2.5 py-2 text-[13px] font-semibold transition-colors hover:bg-(--surface-2)"
                      >
                        Dashboard
                      </NavLink>
                      <button
                        type="button"
                        onClick={() => {
                          setAccountOpen(false);
                          logout();
                          navigate("/");
                        }}
                        className="block w-full rounded-lg px-2.5 py-2 text-left text-[13px] font-semibold text-(--muted) transition-colors hover:bg-(--surface-2)"
                      >
                        Log out
                      </button>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </>
          ) : (
            <>
              <Link to="/login" className="btn btn-ghost btn-sm hidden sm:inline-flex">
                Log in
              </Link>
              <Link to="/app" className="btn btn-primary btn-sm max-[420px]:hidden">
                Try it free
              </Link>
            </>
          )}
          <button
            type="button"
            onClick={() => setOpen((o) => !o)}
            aria-label={open ? "Close menu" : "Open menu"}
            aria-expanded={open}
            className="grid size-9 place-items-center rounded-[10px] border border-(--border) lg:hidden"
          >
            {open ? <X size={17} strokeWidth={1.5} /> : <Menu size={17} strokeWidth={1.5} />}
          </button>
        </div>
      </div>
        <AnimatePresence>
          {open && (
            <motion.nav
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.2, ease: "easeOut" }}
              className="overflow-hidden lg:hidden"
              aria-label="Mobile"
            >
              <div className="border-t border-(--border) px-[4%] py-3">
                {LINKS.filter((l) => !l.anchor).map((l) => (
                  <NavLink
                    key={l.label}
                    to={l.to}
                    onClick={() => setOpen(false)}
                    className="block py-2.5 text-[15px] text-(--muted)"
                  >
                    {l.label}
                  </NavLink>
                ))}
                {LINKS.filter((l) => l.anchor).map((l) => (
                  <AnchorLink
                    key={l.label}
                    to={l.to}
                    onDone={() => setOpen(false)}
                    className="block py-2.5 text-[15px] text-(--muted)"
                  >
                    {l.label}
                  </AnchorLink>
                ))}
                {user && (
                  <>
                    <NavLink
                      to="/profile"
                      onClick={() => setOpen(false)}
                      className="block py-2.5 text-[15px]"
                    >
                      Profile & settings
                    </NavLink>
                    <button
                      type="button"
                      onClick={() => {
                        setOpen(false);
                        logout();
                        navigate("/");
                      }}
                      className="block w-full py-2.5 text-left text-[15px] text-(--muted)"
                    >
                      Log out
                    </button>
                  </>
                )}
                {!user && (
                  <Link to="/login" onClick={() => setOpen(false)} className="block py-2.5 text-[15px]">
                    Log in
                  </Link>
                )}
              </div>
            </motion.nav>
          )}
        </AnimatePresence>
    </header>
  );
}
