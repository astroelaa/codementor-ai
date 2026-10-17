import { useEffect, useState } from "react";

/**
 * Gates the decorative hero wave. It stays off when motion is reduced, when
 * WebGL is unavailable (or only software-rendered), on low-core / low-memory
 * devices and when the user asked for reduced data usage. The three.js chunk
 * is only imported after the first idle moment so it never competes with the
 * first paint. Landing renders a static gradient instead whenever this is
 * false.
 */
export function useWaveEligible(): boolean {
  const [eligible, setEligible] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let timer = 0;
    let idleId = 0;

    try {
      if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
      const nav = navigator as Navigator & {
        deviceMemory?: number;
        connection?: { saveData?: boolean };
      };
      const cores = nav.hardwareConcurrency ?? 8;
      const memory = nav.deviceMemory ?? 8;
      if (cores <= 3 || memory <= 2 || nav.connection?.saveData === true) return;
      const probe = document.createElement("canvas");
      const opts = { failIfMajorPerformanceCaveat: true } as WebGLContextAttributes;
      const gl = probe.getContext("webgl2", opts) ?? probe.getContext("webgl", opts);
      if (!gl) return;
    } catch {
      return;
    }

    const show = () => {
      if (!cancelled) setEligible(true);
    };
    if (typeof window.requestIdleCallback === "function") {
      idleId = window.requestIdleCallback(show, { timeout: 1400 });
    } else {
      timer = window.setTimeout(show, 700);
    }
    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
      if (idleId && typeof window.cancelIdleCallback === "function") {
        window.cancelIdleCallback(idleId);
      }
    };
  }, []);

  return eligible;
}
