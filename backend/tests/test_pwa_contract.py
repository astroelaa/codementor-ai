"""PWA contract tests.

These guard the invariants the deployed GitHub Pages build depends on:
the service worker never precaches the heavy three.js wave chunk, offline
starts fall back to the static gradient instead of crashing, navigation
fallbacks never swallow auth/API paths, install prompts are wired to the
real browser events, and the service worker only registers in production.

They read the frontend sources as text: the frontend has no test runner of
its own, and these are build-time contracts, not runtime behaviour.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND = REPO_ROOT / "frontend"


def _read(*parts: str) -> str:
    path = FRONTEND.joinpath(*parts)
    assert path.is_file(), f"missing frontend file: {path}"
    return path.read_text(encoding="utf-8")


def test_wave_chunk_is_excluded_from_precache():
    cfg = _read("vite.config.ts")
    assert "globIgnores" in cfg
    assert '"**/Wave-*.js"' in cfg


def test_manifest_scope_and_start_url_follow_the_pages_base():
    cfg = _read("vite.config.ts")
    assert "scope: BASE" in cfg
    assert "start_url: `${BASE}#/`" in cfg


def test_navigation_fallback_denylist_covers_api_and_auth():
    cfg = _read("vite.config.ts")
    assert "navigateFallbackDenylist" in cfg
    for pattern in (r"/^\/api\//", r"/\/auth\//", r"/\/oauth/"):
        assert pattern in cfg, f"denylist missing {pattern}"


def test_service_worker_registers_in_production_only():
    main = _read("src", "main.tsx")
    assert "import.meta.env.PROD && <PwaStatus />" in main


def test_lazy_wave_falls_back_to_the_static_gradient():
    landing = _read("src", "pages", "Landing.tsx")
    # A failed chunk fetch resolves to the static gradient, not a crash...
    assert 'import("../components/Wave").catch(' in landing
    # ...and render-time failures are caught by the boundary around it.
    assert (
        '<ErrorBoundary fallback={<div className="hero-wave-static" />}>' in landing
    )
    wave = _read("src", "components", "Wave.tsx")
    assert 'from "three"' in wave


def test_route_level_error_boundary_has_reload_and_offline_copy():
    main = _read("src", "main.tsx")
    assert "<ErrorBoundary" in main
    assert "fallback={<RouteErrorFallback />}" in main
    boundary = _read("src", "components", "ErrorBoundary.tsx")
    assert "window.location.reload()" in boundary


def test_no_sleeping_host_copy_in_user_facing_sources():
    for path in ("src/pages/Workspace.tsx", "src/components/ErrorBoundary.tsx"):
        text = FRONTEND.joinpath(*path.split("/")).read_text(encoding="utf-8")
        lowered = text.lower()
        assert "sleep" not in lowered, f"stale sleeping copy in {path}"
        assert "wake" not in lowered, f"stale wake-up copy in {path}"


def test_install_flow_captures_the_real_browser_prompt():
    install = _read("src", "lib", "install.ts")
    assert "beforeinstallprompt" in install
    assert "appinstalled" in install
    assert "display-mode: standalone" in install
    assert "standalone" in install  # navigator.standalone (iOS)
    assert "Add to Home Screen" in install
    # Dismissal is per page view only: no persistence of "dismissed".
    assert "bannerDismissed = false" in install


def test_about_route_is_public_and_linked():
    main = _read("src", "main.tsx")
    assert '<Route path="/about" element={<About />} />' in main
    about = _read("src", "pages", "About.tsx")
    assert "FAQ" in about
    footer = _read("src", "components", "Footer.tsx")
    assert 'to: "/about"' in footer
