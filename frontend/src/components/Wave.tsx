import { useEffect, useRef } from "react";
import * as THREE from "three";

/**
 * Decorative wireframe wave + sparse starfield for the landing hero.
 *
 * Loaded through React.lazy (its own chunk; three.js never reaches the main
 * bundle). Rules it lives by:
 *  - pointer-transparent: renders behind content and never captures input;
 *  - devicePixelRatio capped, pauses when the tab is hidden or the hero
 *    leaves the viewport;
 *  - all geometries, materials, listeners and the renderer are disposed on
 *    unmount;
 *  - never mounted at all under prefers-reduced-motion, without WebGL, or on
 *    low-power devices (the Landing gates it via useWaveEligible, which has a
 *    static-gradient fallback).
 */
export default function Wave() {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const host = ref.current;
    if (!host) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    const FIELD_W = 9.2;
    const FIELD_D = 5.6;
    const SEG_X = 76;
    const SEG_Z = 34;
    const AMP_1 = 0.42;
    const AMP_2 = 0.15;

    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({
        alpha: true,
        antialias: true,
        powerPreference: "low-power",
      });
    } catch {
      return;
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.75));
    renderer.setClearAlpha(0);
    const canvas = renderer.domElement;
    canvas.style.position = "absolute";
    canvas.style.inset = "0";
    canvas.style.width = "100%";
    canvas.style.height = "100%";
    canvas.style.pointerEvents = "none";
    host.appendChild(canvas);

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(46, 1, 0.1, 60);
    const camBase = new THREE.Vector3(0, 2.05, 4.55);
    camera.position.copy(camBase);
    camera.lookAt(0, -0.35, 0);

    // ---- wireframe grid: line segments sampled from a live wave field ----
    const vertexCount = (SEG_X * (SEG_Z + 1) + SEG_Z * (SEG_X + 1)) * 2;
    const positions = new Float32Array(vertexCount * 3);
    const colors = new Float32Array(vertexCount * 3);
    const xs = new Float32Array(vertexCount);
    const zs = new Float32Array(vertexCount);

    // violet (near) -> magenta (far), dimmed with distance
    const NEAR: [number, number, number] = [0.66, 0.44, 1.0];
    const FAR: [number, number, number] = [0.86, 0.34, 0.95];
    let v = 0;
    const push = (x: number, z: number) => {
      xs[v] = x;
      zs[v] = z;
      const t = (z + FIELD_D / 2) / FIELD_D; // 0 far .. 1 near
      const b = 0.4 + 0.6 * t;
      positions[v * 3] = x;
      positions[v * 3 + 2] = z;
      colors[v * 3] = (FAR[0] + (NEAR[0] - FAR[0]) * t) * b;
      colors[v * 3 + 1] = (FAR[1] + (NEAR[1] - FAR[1]) * t) * b;
      colors[v * 3 + 2] = (FAR[2] + (NEAR[2] - FAR[2]) * t) * b;
      v += 1;
    };
    for (let r = 0; r <= SEG_Z; r += 1) {
      const z = -FIELD_D / 2 + (r / SEG_Z) * FIELD_D;
      for (let c = 0; c < SEG_X; c += 1) {
        push(-FIELD_W / 2 + (c / SEG_X) * FIELD_W, z);
        push(-FIELD_W / 2 + ((c + 1) / SEG_X) * FIELD_W, z);
      }
    }
    for (let c = 0; c <= SEG_X; c += 1) {
      const x = -FIELD_W / 2 + (c / SEG_X) * FIELD_W;
      for (let r = 0; r < SEG_Z; r += 1) {
        push(x, -FIELD_D / 2 + (r / SEG_Z) * FIELD_D);
        push(x, -FIELD_D / 2 + ((r + 1) / SEG_Z) * FIELD_D);
      }
    }

    const waveGeo = new THREE.BufferGeometry();
    waveGeo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    waveGeo.setAttribute("color", new THREE.BufferAttribute(colors, 3));
    const waveMat = new THREE.LineBasicMaterial({
      vertexColors: true,
      transparent: true,
      opacity: 0.62,
    });
    const wave = new THREE.LineSegments(waveGeo, waveMat);
    scene.add(wave);

    // ---- sparse starfield ----
    const STAR_COUNT = 240;
    const starPos = new Float32Array(STAR_COUNT * 3);
    for (let s = 0; s < STAR_COUNT; s += 1) {
      starPos[s * 3] = (Math.random() - 0.5) * 14;
      starPos[s * 3 + 1] = Math.random() * 4.2 - 0.3;
      starPos[s * 3 + 2] = -5.2 + Math.random() * 6.4;
    }
    const starGeo = new THREE.BufferGeometry();
    starGeo.setAttribute("position", new THREE.BufferAttribute(starPos, 3));
    const starMat = new THREE.PointsMaterial({
      color: 0xcdc4ff,
      size: 0.045,
      sizeAttenuation: true,
      transparent: true,
      opacity: 0.85,
      depthWrite: false,
    });
    const stars = new THREE.Points(starGeo, starMat);
    scene.add(stars);

    // ---- sizing ----
    const resize = () => {
      const w = host.clientWidth || 1;
      const h = host.clientHeight || 1;
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(host);

    // ---- mild pointer parallax (passive; never intercepts input) ----
    let targetX = 0;
    let targetY = 0;
    let px = 0;
    let py = 0;
    const onPointer = (event: PointerEvent) => {
      targetX = (event.clientX / window.innerWidth - 0.5) * 2;
      targetY = (event.clientY / window.innerHeight - 0.5) * 2;
    };
    window.addEventListener("pointermove", onPointer, { passive: true });

    // ---- frame loop with visibility + viewport pauses ----
    const clock = new THREE.Clock();
    let raf = 0;
    let inView = true;

    const frame = () => {
      raf = 0;
      if (!inView || document.hidden) return;
      const t = clock.getElapsedTime();
      px += (targetX - px) * 0.05;
      py += (targetY - py) * 0.05;
      camera.position.x = camBase.x + px * 0.55;
      camera.position.y = camBase.y - py * 0.25;
      camera.lookAt(0, -0.35, 0);
      for (let i = 0; i < vertexCount; i += 1) {
        const x = xs[i];
        const z = zs[i];
        positions[i * 3 + 1] =
          AMP_1 * Math.sin(x * 0.85 + t * 0.55) * Math.cos(z * 1.05 - t * 0.42) +
          AMP_2 * Math.sin((x + z) * 1.35 + t * 0.8);
      }
      waveGeo.attributes.position.needsUpdate = true;
      stars.rotation.y = t * 0.012;
      renderer.render(scene, camera);
      raf = requestAnimationFrame(frame);
    };
    const wake = () => {
      if (!raf && inView && !document.hidden) raf = requestAnimationFrame(frame);
    };
    const onVisibility = () => {
      if (document.hidden) {
        if (raf) cancelAnimationFrame(raf);
        raf = 0;
      } else {
        clock.getDelta(); // discard the pause gap
        wake();
      }
    };
    document.addEventListener("visibilitychange", onVisibility);
    const io = new IntersectionObserver(
      ([entry]) => {
        inView = entry.isIntersecting;
        if (inView) wake();
        else if (raf) {
          cancelAnimationFrame(raf);
          raf = 0;
        }
      },
      { rootMargin: "80px" },
    );
    io.observe(host);
    wake();

    return () => {
      if (raf) cancelAnimationFrame(raf);
      io.disconnect();
      ro.disconnect();
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener("pointermove", onPointer);
      waveGeo.dispose();
      waveMat.dispose();
      starGeo.dispose();
      starMat.dispose();
      scene.clear();
      renderer.dispose();
      renderer.forceContextLoss();
      canvas.remove();
    };
  }, []);

  return <div ref={ref} className="absolute inset-0 overflow-hidden" />;
}
