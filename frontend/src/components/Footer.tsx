import { Link } from "react-router-dom";
import { AnchorLink } from "./AnchorLink";
import { Logo } from "./Logo";

export function Footer() {
  const year = new Date().getFullYear();
  return (
    <footer className="border-t border-(--border) bg-(--bg-soft)">
      <div className="mx-auto flex w-[min(1200px,92%)] flex-col items-center gap-6 py-12 text-center">
        <Logo />
        <p className="max-w-md text-sm text-(--muted)">
          Code generators give you answers. CodeMentor AI builds your understanding.
        </p>
        <nav className="flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-sm text-(--muted)" aria-label="Footer">
          <Link to="/app" className="transition-colors hover:text-(--text)">Demo</Link>
          <AnchorLink to="/#features" className="transition-colors hover:text-(--text)">Features</AnchorLink>
          <AnchorLink to="/#faq" className="transition-colors hover:text-(--text)">FAQ</AnchorLink>
          <Link to="/privacy" className="transition-colors hover:text-(--text)">Privacy</Link>
          <Link to="/terms" className="transition-colors hover:text-(--text)">Terms</Link>
        </nav>
        <p className="text-xs text-(--faint)">© {year} CodeMentor AI. Learn to understand code.</p>
      </div>
    </footer>
  );
}
