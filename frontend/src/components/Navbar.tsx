import { Link, NavLink, useNavigate } from "react-router-dom";
import { useState } from "react";
import { LogOut, Menu, Moon, Sun, X } from "lucide-react";
import { AnchorLink } from "./AnchorLink";
import { Logo } from "./Logo";
import { useAuth } from "../lib/auth";
import { useTheme } from "../lib/theme";

const LINKS = [
  { to: "/app", label: "Demo", anchor: false },
  { to: "/#method", label: "Method", anchor: true },
  { to: "/#features", label: "Features", anchor: true },
  { to: "/#faq", label: "FAQ", anchor: true },
];

export function Navbar() {
  const { user, logout } = useAuth();
  const { theme, toggle } = useTheme();
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();

  return (
    <header className="glass sticky top-0 z-50 border-b border-(--border)">
      <div className="mx-auto flex h-16 w-[min(1200px,92%)] items-center gap-4">
        <Link to="/" aria-label="CodeMentor AI home">
          <Logo />
        </Link>
        <nav className="ml-6 hidden items-center gap-6 md:flex" aria-label="Primary">
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
              <span className="hidden max-w-36 truncate text-sm text-(--muted) sm:block">
                {user.display_name || user.email}
              </span>
              <button
                type="button"
                onClick={() => {
                  logout();
                  navigate("/");
                }}
                className="btn btn-ghost btn-sm"
                aria-label="Log out"
              >
                <LogOut size={15} strokeWidth={1.5} />
                <span className="hidden sm:inline">Log out</span>
              </button>
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
            className="grid size-9 place-items-center rounded-[10px] border border-(--border) md:hidden"
          >
            {open ? <X size={17} strokeWidth={1.5} /> : <Menu size={17} strokeWidth={1.5} />}
          </button>
        </div>
      </div>
        {open && (
        <nav className="border-t border-(--border) px-[4%] py-3 md:hidden" aria-label="Mobile">
          <NavLink
            to="/app"
            onClick={() => setOpen(false)}
            className="block py-2.5 text-[15px] text-(--muted)"
          >
            Demo
          </NavLink>
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
          {!user && (
            <Link to="/login" onClick={() => setOpen(false)} className="block py-2.5 text-[15px]">
              Log in
            </Link>
          )}
        </nav>
      )}
    </header>
  );
}
