/* Typed client for the CodeMentor AI backend. */

/* Canonical variable is VITE_API_BASE_URL (see frontend/.env.example and
   .github/workflows/pages.yml); VITE_API_URL is a legacy fallback.
   Local dev (vite) falls back to the local backend. Production builds NEVER
   fall back to localhost: with no URL configured every request fails fast
   with a clear configuration error instead of pretending the API works. */
const CONFIGURED_BASE =
  (import.meta.env.VITE_API_BASE_URL || "").trim().replace(/\/$/, "") ||
  (import.meta.env.VITE_API_URL || "").trim().replace(/\/$/, "");

export const API_BASE =
  CONFIGURED_BASE || (import.meta.env.DEV ? "http://127.0.0.1:8000" : "");

/** True in production builds with no backend URL configured. */
export const API_MISCONFIGURED = API_BASE === "";

const MISCONFIGURED_DETAIL =
  "The app is not connected to its backend (API URL is not configured). " +
  "If you deploy this yourself, set VITE_API_BASE_URL and rebuild.";

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
  goal: string;
  mode: string;
  project_id: string | null;
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
export interface SessionSummary {
  id: string;
  language: string;
  status: string;
  understanding_score: number;
  message_count: number;
  updated_at: string;
}
export interface SessionListItem extends SessionSummary {
  goal: string;
  code: string;
  created_at: string;
  solved_at: string | null;
  hints_left: number;
}
export interface DashboardData {
  total_sessions: number;
  solved_sessions: number;
  streak_days: number;
  avg_understanding: number;
  languages: { language: string; sessions: number }[];
  weak_spots: { type: string; count: number }[];
  badges: Badge[];
  recent_sessions: SessionSummary[];
}
export interface SkillProgress {
  slug: string;
  name: string;
  encounters: number;
  score: number;
}
export interface PathItem {
  id: string;
  title: string;
  detail: string;
  status: "todo" | "doing" | "done";
  position: number;
}
export interface LearningPath {
  id: string;
  title: string;
  source: "weak-spots" | "starter" | string;
  is_active: boolean;
  created_at: string;
  items: PathItem[];
}
export interface DocResult {
  id: string;
  explanation: string;
  example: string;
  question: string;
  created_at: string;
}
export interface DocHistoryItem extends DocResult {
  language: string;
  input_text: string;
}
export interface ProjectTask {
  id: string;
  title: string;
  detail: string;
  status: "todo" | "doing" | "done";
  position: number;
}
export interface Milestone {
  id: string;
  title: string;
  detail: string;
  status: "todo" | "doing" | "done";
  position: number;
  tasks: ProjectTask[];
}
export interface ProjectSummary {
  id: string;
  title: string;
  language: string;
  status: string;
  milestone_count: number;
  open_task_count: number;
  updated_at: string;
}
export interface ProjectDetail {
  id: string;
  title: string;
  objective: string;
  language: string;
  stack: string;
  architecture: string;
  status: string;
  created_at: string;
  updated_at: string;
  milestones: Milestone[];
}
export interface BriefResult {
  objective: string;
  requirements: string[];
  architecture: string;
  milestones: { title: string; tasks: string[] }[];
}
export interface NextTask {
  done: boolean;
  milestone: Milestone | null;
  task: ProjectTask | null;
  guidance: string;
}
export interface ResourceLink {
  language: string;
  title: string;
  url: string;
  license: string;
}
export interface Notification {
  id: string;
  type: string;
  title: string;
  body: string;
  read: boolean;
  created_at: string;
}
export interface MemoryData {
  weak_spots: { type: string; count: number }[];
  misconceptions: {
    id: string;
    type: string;
    description: string;
    session_id: string | null;
    created_at: string;
  }[];
}
export interface SourceRef {
  title: string;
  url: string;
}
export interface MentorTurn {
  reply: string;
  understanding_score: number;
  hints_left: number;
  misconception: Misconception | null;
  next_topics: string[];
  message_id: string;
  provider: string;
  sources: SourceRef[];
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
export interface RegistryLanguage {
  key: string;
  label: string;
  highlight: string;
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
  is_verified: boolean;
  notify_security_emails: boolean;
  notify_progress_emails: boolean;
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
  if (!API_BASE) throw new ApiError(0, MISCONFIGURED_DETAIL);
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
  resendVerification(): Promise<{ message: string }> {
    return request<{ message: string }>("/api/auth/resend-verification", {
      method: "POST",
    });
  },
  verifyEmail(token: string): Promise<{ message: string }> {
    return request<{ message: string }>("/api/auth/verify-email", {
      method: "POST",
      body: JSON.stringify({ token }),
    });
  },
  forgotPassword(email: string): Promise<{ message: string }> {
    return request<{ message: string }>("/api/auth/forgot-password", {
      method: "POST",
      body: JSON.stringify({ email }),
    });
  },
  resetPassword(token: string, new_password: string): Promise<{ message: string }> {
    return request<{ message: string }>("/api/auth/reset-password", {
      method: "POST",
      body: JSON.stringify({ token, new_password }),
    });
  },

  /* ---------- mentor ---------- */
  createSession(
    language: string,
    code: string,
    goal = "debug",
    projectId?: string | null,
    mode?: "practice" | "mycode",
  ): Promise<SessionDetail> {
    return request<SessionDetail>("/api/sessions", {
      method: "POST",
      body: JSON.stringify({
        language,
        code,
        goal,
        project_id: projectId ?? null,
        ...(mode ? { mode } : {}),
      }),
    });
  },
  listSessions(): Promise<SessionListItem[]> {
    return request<SessionListItem[]>("/api/sessions");
  },
  getSession(id: string): Promise<SessionDetail> {
    return request<SessionDetail>(`/api/sessions/${id}`);
  },
  postMessage(sessionId: string, content: string, code?: string): Promise<MentorTurn> {
    return request<MentorTurn>(`/api/sessions/${sessionId}/messages`, {
      method: "POST",
      body: JSON.stringify({
        content,
        ...(code !== undefined ? { code } : {}),
      }),
    });
  },
  requestHint(sessionId: string, code?: string): Promise<MentorTurn> {
    return request<MentorTurn>(`/api/sessions/${sessionId}/hints`, {
      method: "POST",
      body: JSON.stringify({ ...(code !== undefined ? { code } : {}) }),
    });
  },
  submitExplanation(sessionId: string, explanation: string, code?: string): Promise<ExplainResult> {
    return request<ExplainResult>(`/api/sessions/${sessionId}/explain`, {
      method: "POST",
      body: JSON.stringify({
        explanation,
        ...(code !== undefined ? { code } : {}),
      }),
    });
  },
  snippets(): Promise<Snippet[]> {
    return request<Snippet[]>("/api/snippets");
  },
  languages(): Promise<RegistryLanguage[]> {
    return request<RegistryLanguage[]>("/api/languages");
  },
  dashboard(): Promise<DashboardData> {
    return request<DashboardData>("/api/dashboard");
  },
  skills(): Promise<SkillProgress[]> {
    return request<SkillProgress[]>("/api/skills");
  },
  learningPath(): Promise<LearningPath | null> {
    return request<LearningPath | null>("/api/learning-path");
  },
  regeneratePath(): Promise<LearningPath> {
    return request<LearningPath>("/api/learning-path/regenerate", { method: "POST" });
  },
  updatePathItem(id: string, status: string): Promise<PathItem> {
    return request<PathItem>(`/api/learning-path/items/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    });
  },
  simplifyDocs(text: string, language: string): Promise<DocResult> {
    return request<DocResult>("/api/docs/simplify", {
      method: "POST",
      body: JSON.stringify({ text, language }),
    });
  },
  docHistory(): Promise<DocHistoryItem[]> {
    return request<DocHistoryItem[]>("/api/docs/history");
  },
  resources(language?: string): Promise<ResourceLink[]> {
    const q = language ? `?language=${encodeURIComponent(language)}` : "";
    return request<ResourceLink[]>(`/api/resources${q}`);
  },
  listProjects(): Promise<ProjectSummary[]> {
    return request<ProjectSummary[]>("/api/projects");
  },
  getProject(id: string): Promise<ProjectDetail> {
    return request<ProjectDetail>(`/api/projects/${id}`);
  },
  createProject(body: { title: string; objective?: string; language?: string; stack?: string }): Promise<ProjectDetail> {
    return request<ProjectDetail>("/api/projects", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },
  updateProject(id: string, body: Record<string, string>): Promise<ProjectDetail> {
    return request<ProjectDetail>(`/api/projects/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    });
  },
  generateBrief(id: string, description: string): Promise<BriefResult> {
    return request<BriefResult>(`/api/projects/${id}/brief`, {
      method: "POST",
      body: JSON.stringify({ description }),
    });
  },
  addMilestone(id: string, title: string, detail = ""): Promise<Milestone> {
    return request<Milestone>(`/api/projects/${id}/milestones`, {
      method: "POST",
      body: JSON.stringify({ title, detail }),
    });
  },
  updateMilestone(id: string, body: Record<string, string>): Promise<Milestone> {
    return request<Milestone>(`/api/projects/milestones/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    });
  },
  addTask(milestoneId: string, title: string): Promise<ProjectTask> {
    return request<ProjectTask>(`/api/projects/milestones/${milestoneId}/tasks`, {
      method: "POST",
      body: JSON.stringify({ title }),
    });
  },
  updateTask(id: string, body: Record<string, string>): Promise<ProjectTask> {
    return request<ProjectTask>(`/api/projects/tasks/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    });
  },
  nextTask(id: string): Promise<NextTask> {
    return request<NextTask>(`/api/projects/${id}/next`);
  },
  notifications(): Promise<Notification[]> {
    return request<Notification[]>("/api/notifications");
  },
  unreadCount(): Promise<{ count: number }> {
    return request<{ count: number }>("/api/notifications/unread-count");
  },
  markNotificationRead(id: string): Promise<Notification> {
    return request<Notification>(`/api/notifications/${id}/read`, { method: "PATCH" });
  },
  markAllNotificationsRead(): Promise<{ updated: number }> {
    return request<{ updated: number }>("/api/notifications/read-all", { method: "POST" });
  },
  readMemory(): Promise<MemoryData> {
    return request<MemoryData>("/api/memory");
  },
  deleteMisconception(id: string): Promise<{ deleted: string }> {
    return request<{ deleted: string }>(`/api/memory/misconceptions/${id}`, {
      method: "DELETE",
    });
  },
  updatePreferences(patch: { notify_security_emails?: boolean; notify_progress_emails?: boolean }): Promise<User> {
    return request<User>("/api/auth/me", {
      method: "PATCH",
      body: JSON.stringify(patch),
    });
  },
  health(): Promise<{ status: string; environment: string; providers_configured: string[]; email_delivery: boolean }> {
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
  code?: string,
  signal?: AbortSignal,
): AsyncGenerator<StreamEvent> {
  if (!API_BASE) {
    yield { kind: "error", detail: MISCONFIGURED_DETAIL };
    return;
  }
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/api/sessions/${sessionId}/messages/stream`, {
      method: "POST",
      headers: headers(),
      body: JSON.stringify({
        content,
        ...(code !== undefined ? { code } : {}),
      }),
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
