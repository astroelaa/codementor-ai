import { createClient, type SupabaseClient } from "@supabase/supabase-js";

const url = (import.meta.env.VITE_SUPABASE_URL || "").trim();
const anonKey = (import.meta.env.VITE_SUPABASE_ANON_KEY || "").trim();

export const AUTH_MISCONFIGURED_DETAIL =
  "Authentication is not configured. Set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY and rebuild.";

export const supabase: SupabaseClient | null =
  url && anonKey
    ? createClient(url, anonKey, {
        auth: {
          flowType: "pkce",
          detectSessionInUrl: false,
          persistSession: true,
          autoRefreshToken: true,
        },
      })
    : null;

const AUTH_QUERY_KEYS = ["code", "error", "error_description", "error_code"];

function readAuthCode(): string | null {
  const search = new URLSearchParams(window.location.search);
  const direct = search.get("code");
  if (direct) return direct;
  const hash = window.location.hash;
  const queryStart = hash.indexOf("?");
  if (queryStart === -1) return null;
  return new URLSearchParams(hash.slice(queryStart + 1)).get("code");
}

function clearAuthQuery(): void {
  const current = new URL(window.location.href);
  for (const key of AUTH_QUERY_KEYS) current.searchParams.delete(key);
  const [path, query = ""] = current.hash.split("?", 2);
  if (query) {
    const params = new URLSearchParams(query);
    for (const key of AUTH_QUERY_KEYS) params.delete(key);
    const remaining = params.toString();
    current.hash = remaining ? `${path}?${remaining}` : path;
  }
  window.history.replaceState(
    {},
    "",
    `${current.pathname}${current.search}${current.hash}`,
  );
}

let callback: Promise<void> | null = null;

export function consumeAuthCallback(): Promise<void> {
  if (!supabase) return Promise.resolve();
  if (!callback) {
    callback = (async () => {
      const code = readAuthCode();
      if (!code) {
        clearAuthQuery();
        return;
      }
      try {
        const { error } = await supabase.auth.exchangeCodeForSession(code);
        if (error) throw error;
      } finally {
        clearAuthQuery();
      }
    })();
  }
  return callback;
}
