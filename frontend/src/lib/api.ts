/* Typed client for the CodeMentor AI backend. */

export const API_BASE =
  (import.meta.env.VITE_API_URL || "").trim().replace(/\/$/, "") ||
  "http://127.0.0.1:8000";

const TOKEN_KEY = "cm_token";
const GUEST_KEY = "cm_guest";

export const tokenStore = {
  get token() {
    return localStorage.getItem(TOKEN_KEY);
  },
  set token(v: string | null) {
    if (v) localStorage.setItem(TOKEN_KEY, v);
    else localStorage.removeItem(TOKEN_KEY);
  },
  get guest() {
    return localStorage.getItem(GUEST_KEY);
  },
  set guest(v: string | null) {
    if (v) localStorage.setItem(GUEST_KEY, v);
    else localStorage.removeItem(GUEST_KEY);
  },
};

export interface Badge {
  slug: string;
  name: string;
  description: string;
  icon: string;
}
export interface Misconception {
  type: string;
  description: string;
}
export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
  meta?: Record<string, unknown> | null;
}
export interface SessionDetail {
  id: string;
  language: string;
  code: string;
  status: "active" | "solved";
  understanding_score: number;
  hints_left: number;
  created_at: string;
  updated_at: string;
  solved_at: string | null;
  guest_token: string | null;
  badges_earned: Badge[];
  messages: ChatMessage[];
}
export interface MentorTurn {
  reply: string;
  understanding_score: number;
  hints_left: number;
  misconception: Misconception | null;
  next_topics: string[];
  message_id: string;
  provider: string;
}
export interface ExplainResult {
  passed: boolean;
  score: number;
  feedback: string;
  reply: string;
  understanding_score: number;
  hints_left: number;
  badges_earned: Badge[];
}
export interface Snippet {
  language: string;
  title: string;
  description: string;
  code: string;
}
export interface User {
  id: string;
  email: string;
  display_name: string;
  theme: string;
  created_at: string;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
  }
}

function headers(extra: Record<string, string> = {}): Record<string, string> {
  const h: Record<string, string> = { "Content-Type": "application/json", ...extra };
  if (tokenStore.token) h["Authorization"] = `Bearer ${tokenStore.token}`;
  else if (tokenStore.guest) h["X-Guest-Token"] = tokenStore.guest;
  return h;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: headers(init.headers as Record<string, string> | undefined),
  });
  if (res.status === 204) return undefined as T;
  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    body = null;
  }
  if (!res.ok) {
    const detail =
      body && typeof body === "object" && "detail" in body
        ? String((body as { detail: unknown }).detail)
        : `Request failed (${res.status}).`;
    throw new ApiError(res.status, detail);
  }
  return body as T;
}

/* ---------- auth ---------- */
export const api = {
  signup(email: string, password: string, display_name: string): Promise<User> {
    return request<User>("/api/auth/signup", {
      method: "POST",
      body: JSON.stringify({ email, password, display_name }),
    });
  },
  async login(email: string, password: string): Promise<string> {
    const data = await request<{ access_token: string }>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    tokenStore.token = data.access_token;
    return data.access_token;
  },
  me(): Promise<User> {
    return request<User>("/api/auth/me");
  },
  updateProfile(patch: { display_name?: string; theme?: string }): Promise<User> {
    return request<User>("/api/auth/me", {
      method: "PATCH",
      body: JSON.stringify(patch),
    });
  },
  deleteAccount(password: string): Promise<void> {
    return request<void>("/api/auth/me", {
      method: "DELETE",
      body: JSON.stringify({ password }),
    });
  },

  /* ---------- mentor ---------- */
  createSession(language: string, code: string): Promise<SessionDetail> {
    return request<SessionDetail>("/api/sessions", {
      method: "POST",
      body: JSON.stringify({ language, code }),
    });
  },
  getSession(id: string): Promise<SessionDetail> {
    return request<SessionDetail>(`/api/sessions/${id}`);
  },
  postMessage(sessionId: string, content: string): Promise<MentorTurn> {
    return request<MentorTurn>(`/api/sessions/${sessionId}/messages`, {
      method: "POST",
      body: JSON.stringify({ content }),
    });
  },
  requestHint(sessionId: string): Promise<MentorTurn> {
    return request<MentorTurn>(`/api/sessions/${sessionId}/hints`, { method: "POST" });
  },
  submitExplanation(sessionId: string, explanation: string): Promise<ExplainResult> {
    return request<ExplainResult>(`/api/sessions/${sessionId}/explain`, {
      method: "POST",
      body: JSON.stringify({ explanation }),
    });
  },
  snippets(): Promise<Snippet[]> {
    return request<Snippet[]>("/api/snippets");
  },
  health(): Promise<{ status: string; providers_configured: string[] }> {
    return request("/health");
  },
};

/* ---------- SSE streaming ---------- */
export type StreamEvent =
  | { kind: "provider"; provider: string }
  | { kind: "token"; text: string }
  | { kind: "done"; turn: MentorTurn }
  | { kind: "error"; detail: string; transport?: boolean };

export async function* streamMessage(
  sessionId: string,
  content: string,
  signal?: AbortSignal,
): AsyncGenerator<StreamEvent> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/api/sessions/${sessionId}/messages/stream`, {
      method: "POST",
      headers: headers(),
      body: JSON.stringify({ content }),
      signal,
    });
  } catch {
    // The request never reached the server: a plain-JSON retry is safe.
    yield {
      kind: "error",
      detail: "Could not reach the mentor. Check your connection.",
      transport: true,
    };
    return;
  }
  if (!res.ok || !res.body) {
    let detail = `Request failed (${res.status}).`;
    try {
      const body = (await res.json()) as { detail?: unknown };
      if (body && typeof body.detail === "string") detail = body.detail;
    } catch {
      /* keep default */
    }
    yield { kind: "error", detail };
    return;
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let event = "";
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const blocks = buffer.split("\n\n");
      buffer = blocks.pop() ?? "";
      for (const block of blocks) {
        let data = "";
        for (const line of block.split("\n")) {
          if (line.startsWith("event:")) event = line.slice(6).trim();
          else if (line.startsWith("data:")) data += line.slice(5).trim();
        }
        if (!event || !data) continue;
        try {
          const payload = JSON.parse(data) as Record<string, unknown>;
          if (event === "provider" && typeof payload.provider === "string")
            yield { kind: "provider", provider: payload.provider };
          else if (event === "token" && typeof payload.text === "string")
            yield { kind: "token", text: payload.text };
          else if (event === "done") yield { kind: "done", turn: payload as unknown as MentorTurn };
          else if (event === "error")
            // Server-side failure: the user message is already stored,
            // so the caller must surface this, never retry it.
            yield { kind: "error", detail: String(payload.detail ?? "Stream failed.") };
        } catch {
          /* ignore malformed chunk */
        }
        event = "";
      }
    }
  } finally {
    reader.releaseLock();
  }
}
