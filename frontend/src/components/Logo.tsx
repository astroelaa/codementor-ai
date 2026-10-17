import { useId } from "react";

/**
 * CodeMentor AI mark: a rounded violet glass tile with a white code bracket
 * pair and a central four-point spark. Original geometry, no copied marks.
 * The spark twinkles subtly unless `animated` is false; reduced-motion users
 * get the static version (see .logo-spark in index.css).
 */
export function LogoMark({
  size = 30,
  animated = true,
}: {
  size?: number;
  animated?: boolean;
}) {
  const uid = useId().replace(/[^a-zA-Z0-9_-]/g, "");
  const tile = `cm-tile-${uid}`;
  const sheen = `cm-sheen-${uid}`;
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true" className="shrink-0">
      <defs>
        <linearGradient id={tile} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#8B6DFF" />
          <stop offset="1" stopColor="#5B3DF5" />
        </linearGradient>
        <linearGradient id={sheen} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#FFFFFF" stopOpacity="0.5" />
          <stop offset="1" stopColor="#FFFFFF" stopOpacity="0" />
        </linearGradient>
      </defs>
      <rect x="1" y="1" width="30" height="30" rx="9" fill={`url(#${tile})`} />
      <ellipse cx="16" cy="8.5" rx="12.5" ry="6" fill={`url(#${sheen})`} opacity="0.55" />
      <rect
        x="1.4"
        y="1.4"
        width="29.2"
        height="29.2"
        rx="8.6"
        fill="none"
        stroke="rgba(255,255,255,0.5)"
        strokeWidth="0.8"
      />
      <path
        d="M10.4 12 6.9 16l3.5 4"
        fill="none"
        stroke="#FFFFFF"
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M21.6 12l3.5 4-3.5 4"
        fill="none"
        stroke="#FFFFFF"
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
        opacity="0.62"
      />
      <path
        className={animated ? "logo-spark" : undefined}
        d="M16 11.1l1.5 3.4 3.4 1.5-3.4 1.5L16 20.9l-1.5-3.4L11.1 16l3.4-1.5Z"
        fill="#FFFFFF"
      />
    </svg>
  );
}

export function Logo({ compact = false }: { compact?: boolean }) {
  return (
    <span className="inline-flex items-center gap-2.5">
      <LogoMark />
      {!compact && (
        <span className="text-[17px] font-bold tracking-tight">
          CodeMentor <span className="text-(--accent-text)">AI</span>
        </span>
      )}
    </span>
  );
}
