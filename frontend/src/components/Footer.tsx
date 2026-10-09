import { Link } from "react-router-dom";
import { AnchorLink } from "./AnchorLink";
import { Logo } from "./Logo";

const COLUMNS: { title: string; links: { label: string; to: string; anchor?: boolean }[] }[] = [
  {
    title: "Product",
    links: [
      { label: "Demo", to: "/app" },
      { label: "Features", to: "/#features", anchor: true },
      { label: "FAQ", to: "/#faq", anchor: true },
    ],
  },
  {
    title: "Account",
    links: [
      { label: "Sign up", to: "/signup" },
      { label: "Log in", to: "/login" },
      { label: "Method", to: "/#method", anchor: true },
    ],
  },
  {
    title: "Legal",
    links: [
      { label: "Privacy", to: "/privacy" },
      { label: "Terms", to: "/terms" },
    ],
  },
];

export function Footer() {
  const year = new Date().getFullYear();
  return (
    <footer className="border-t border-(--border) bg-(--bg-soft)">
      <div className="mx-auto w-[min(1200px,92%)] py-14">
        <div className="grid gap-10 md:grid-cols-[1.4fr_1fr_1fr_1fr]">
          <div>
            <Logo />
            <p className="mt-4 max-w-xs text-sm leading-relaxed text-(--muted)">
              Code generators give you answers. CodeMentor AI builds your understanding.
            </p>
          </div>
          {COLUMNS.map((col) => (
            <nav key={col.title} aria-label={`Footer — ${col.title}`}>
              <p className="text-[13px] font-bold">{col.title}</p>
              <ul className="mt-4 flex flex-col gap-2.5">
                {col.links.map((l) => (
                  <li key={l.label}>
                    {l.anchor ? (
                      <AnchorLink to={l.to} className="text-sm text-(--muted) transition-colors hover:text-(--text)">
                        {l.label}
                      </AnchorLink>
                    ) : (
                      <Link to={l.to} className="text-sm text-(--muted) transition-colors hover:text-(--text)">
                        {l.label}
                      </Link>
                    )}
                  </li>
                ))}
              </ul>
            </nav>
          ))}
        </div>
        <div className="mt-12 flex flex-wrap items-center justify-between gap-3 border-t border-(--border) pt-6 text-[13px] text-(--faint)">
          <span>© {year} CodeMentor AI</span>
          <span>Learn to understand code.</span>
        </div>
      </div>
    </footer>
  );
}
