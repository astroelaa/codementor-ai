import type { MouseEvent, ReactNode } from "react";
import { useLocation, useNavigate } from "react-router-dom";

/**
 * In-page anchor that works with HashRouter: navigates home first when
 * needed, then smooth-scrolls to the element id.
 */
export function AnchorLink({
  to,
  children,
  className,
  onDone,
}: {
  to: string;
  children: ReactNode;
  className?: string;
  onDone?: () => void;
}) {
  const navigate = useNavigate();
  const location = useLocation();

  function onClick(e: MouseEvent) {
    const [path, hash] = to.split("#");
    if (!hash) return; // plain route: let the router handle it
    e.preventDefault();
    const go = () => {
      document
        .getElementById(hash)
        ?.scrollIntoView({ behavior: "smooth", block: "start" });
    };
    if (location.pathname !== path) {
      navigate(path);
      window.setTimeout(go, 120);
    } else {
      go();
    }
    onDone?.();
  }

  return (
    <a href={to} onClick={onClick} className={className}>
      {children}
    </a>
  );
}
