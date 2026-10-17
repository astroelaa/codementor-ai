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
      // Offline starts use the static gradient immediately: the wave chunk
      // is intentionally not precached, so fetching it would only fail.
      if (!navigator.onLine) return;
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
      // Reject software rasterizers (SwiftShader / llvmpipe / VMs): the wave
      // would run, but it would burn the main thread on CPUs, not GPUs.
      const debug = gl.getExtension("WEBGL_debug_renderer_info");
      if (debug) {
        const renderer = String(gl.getParameter(debug.UNMASKED_RENDERER_WEBGL) ?? "");
        if (/swiftshader|llvmpipe|software|basic render/i.test(renderer)) return;
      }
    } catch {
      return;
    }

    const show = () => {
      if (!cancelled) setEligible(true);
    };
    if (typeof window.requestIdleCallback === "function") {
      idleId = window.requestIdleCallback(show, { timeout: 1800 });
    } else {
      timer = window.setTimeout(show, 900);
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
