import { useEffect, useRef } from "react";

/**
 * Pointer-reactive aurora for the landing hero.
 *
 * The two drifting washes stay pure CSS; this component only nudges the
 * container (--ax/--ay in -1..1) toward the pointer for a subtle parallax.
 * It sits behind content, never captures input, keeps everything static
 * under prefers-reduced-motion, and removes its listener on unmount.
 */
export function Aurora() {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el || typeof window.matchMedia !== "function") return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    let raf = 0;
    let targetX = 0;
    let targetY = 0;
    let x = 0;
    let y = 0;

    const tick = () => {
      raf = 0;
      x += (targetX - x) * 0.12;
      y += (targetY - y) * 0.12;
      el.style.setProperty("--ax", x.toFixed(4));
      el.style.setProperty("--ay", y.toFixed(4));
      if (Math.abs(targetX - x) > 0.001 || Math.abs(targetY - y) > 0.001) {
        raf = requestAnimationFrame(tick);
      }
    };

    const onMove = (event: PointerEvent) => {
      targetX = (event.clientX / window.innerWidth - 0.5) * 2;
      targetY = (event.clientY / window.innerHeight - 0.5) * 2;
      if (!raf) raf = requestAnimationFrame(tick);
    };

    window.addEventListener("pointermove", onMove, { passive: true });
    return () => {
      window.removeEventListener("pointermove", onMove);
      if (raf) cancelAnimationFrame(raf);
      el.style.removeProperty("--ax");
      el.style.removeProperty("--ay");
    };
  }, []);

  return (
    <div
      ref={ref}
      className="aurora pointer-events-none absolute inset-0"
      aria-hidden="true"
    />
  );
}
