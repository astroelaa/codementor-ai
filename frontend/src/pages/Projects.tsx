import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  Check,
  ChevronRight,
  FolderKanban,
  Loader2,
  Play,
  Plus,
  RefreshCw,
  Sparkles,
} from "lucide-react";
import { ApiError, api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useToast } from "../lib/toast";
import { Reveal } from "../components/Reveal";
import { EmptyState } from "../components/bits";
import { LANGUAGES } from "../lib/detect";

export function Projects() {
  const { user } = useAuth();
  const toast = useToast();
  const queryClient = useQueryClient();
  const [openId, setOpenId] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [language, setLanguage] = useState("python");
  const [stack, setStack] = useState("");
  const [briefText, setBriefText] = useState("");
  const [briefBusy, setBriefBusy] = useState(false);
  const [newMilestone, setNewMilestone] = useState("");
  const [newTask, setNewTask] = useState<Record<string, string>>({});

  const list = useQuery({
    queryKey: ["projects"],
    queryFn: api.listProjects,
    enabled: !!user,
    retry: 1,
  });
  const detail = useQuery({
    queryKey: ["project", openId],
    queryFn: () => api.getProject(openId!),
    enabled: !!user && !!openId,
    retry: 1,
  });
  const next = useQuery({
    queryKey: ["project-next", openId],
    queryFn: () => api.nextTask(openId!),
    enabled: !!user && !!openId,
    retry: 1,
  });

  const invalidateList = () => {
    void queryClient.invalidateQueries({ queryKey: ["projects"] });
    void queryClient.invalidateQueries({ queryKey: ["project", openId] });
    void queryClient.invalidateQueries({ queryKey: ["project-next", openId] });
  };
  const fail = (e: unknown, what: string) =>
    toast("error", e instanceof ApiError ? e.message : `Could not ${what}.`);

  async function create(e: FormEvent) {
    e.preventDefault();
    if (!title.trim()) return;
    try {
      const p = await api.createProject({
        title: title.trim(),
        language,
        stack: stack.trim(),
      });
      setTitle("");
      setStack("");
      void queryClient.invalidateQueries({ queryKey: ["projects"] });
      setOpenId(p.id);
    } catch (err) {
      fail(err, "create the project");
    }
  }

  async function generateBrief() {
    if (!openId || briefText.trim().length < 10 || briefBusy) return;
    setBriefBusy(true);
    try {
      await api.generateBrief(openId, briefText.trim());
      setBriefText("");
      invalidateList();
      toast("success", "Brief generated — milestones and tasks added below.");
    } catch (err) {
      fail(err, "generate the brief");
    } finally {
      setBriefBusy(false);
    }
  }

  async function cycleStatus(
    kind: "milestone" | "task",
    id: string,
    current: string,
  ) {
    const nextStatus = current === "todo" ? "doing" : current === "doing" ? "done" : "todo";
    try {
      if (kind === "milestone") await api.updateMilestone(id, { status: nextStatus });
      else await api.updateTask(id, { status: nextStatus });
      invalidateList();
    } catch (err) {
      fail(err, "update the status");
    }
  }

  if (!user) {
    return (
      <main className="mx-auto w-[min(760px,92%)] py-16">
        <EmptyState
          title="Sign in for projects"
          body="Describe a project idea, keep a persistent brief with milestones and tasks, and link mentor sessions to your current task."
        />
        <div className="mt-5 flex justify-center gap-3">
          <Link to="/login" className="btn btn-ghost">Log in</Link>
          <Link to="/signup" className="btn btn-primary">Sign up free</Link>
        </div>
      </main>
    );
  }

  const project = detail.data ?? null;

  return (
    <main className="mx-auto w-[min(1200px,92%)] py-8 md:py-12">
      <Reveal>
        <p className="eyebrow">Build with me</p>
        <h1 className="h2-serif mt-2 text-3xl md:text-4xl">Projects</h1>
        <p className="mt-2 max-w-xl text-[15px] text-(--muted)">
          Turn an idea into a brief with milestones, work through tasks one at a
          time, and link mentor sessions to real project context.
        </p>
      </Reveal>

      <div className="mt-6 grid items-start gap-5 lg:grid-cols-[340px_1fr]">
        <Reveal>
          <div className="card p-5">
            <h2 className="flex items-center gap-2 font-bold">
              <FolderKanban size={17} strokeWidth={1.5} className="text-(--accent-text)" />
              New project
            </h2>
            <form onSubmit={create} className="mt-3 flex flex-col gap-3">
              <div>
                <label className="label" htmlFor="proj-title">Title</label>
                <input
                  id="proj-title"
                  className="input"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="Todo CLI"
                  maxLength={200}
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="label" htmlFor="proj-lang">Language</label>
                  <select
                    id="proj-lang"
                    value={language}
                    onChange={(e) => setLanguage(e.target.value)}
                    className="input"
                  >
                    {LANGUAGES.map((l) => (
                      <option key={l.value} value={l.value}>{l.label}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="label" htmlFor="proj-stack">Stack</label>
                  <input
                    id="proj-stack"
                    className="input"
                    value={stack}
                    onChange={(e) => setStack(e.target.value)}
                    placeholder="stdlib only"
                    maxLength={200}
                  />
                </div>
              </div>
              <button type="submit" className="btn btn-primary btn-sm self-start" disabled={!title.trim()}>
                <Plus size={15} strokeWidth={1.5} /> Create project
              </button>
            </form>

            <h2 className="mt-6 font-bold">Your projects</h2>
            {list.isPending ? (
              <div className="mt-3 flex flex-col gap-2" aria-label="Loading projects">
                <div className="skeleton h-12" />
                <div className="skeleton h-12" />
              </div>
            ) : list.isError ? (
              <div className="mt-3 flex items-center gap-2 text-sm text-(--muted)">
                Could not load.
                <button type="button" onClick={() => void list.refetch()} className="btn btn-ghost btn-sm">
                  <RefreshCw size={14} strokeWidth={1.5} /> Retry
                </button>
              </div>
            ) : (list.data ?? []).length === 0 ? (
              <p className="mt-3 text-sm text-(--muted)">No projects yet — create one above.</p>
            ) : (
              <ul className="mt-3 flex flex-col gap-2">
                {(list.data ?? []).map((p) => (
                  <li key={p.id}>
                    <button
                      type="button"
                      onClick={() => setOpenId(openId === p.id ? null : p.id)}
                      aria-expanded={openId === p.id}
                      className={`w-full rounded-xl border px-3.5 py-2.5 text-left transition-colors ${
                        openId === p.id
                          ? "border-(--accent) bg-(--accent-soft)"
                          : "border-(--border) bg-(--surface) hover:border-(--border-strong)"
                      }`}
                    >
                      <span className="flex items-center gap-2 text-sm font-semibold">
                        {p.title}
                        <ChevronRight size={14} strokeWidth={1.5} className="ml-auto text-(--faint)" />
                      </span>
                      <span className="mt-1 block text-xs text-(--muted)">
                        {p.language} · {p.milestone_count} milestones · {p.open_task_count} open tasks
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </Reveal>

        <Reveal delay={0.06}>
          <div className="card min-h-[300px] p-5 md:p-6">
            {!openId || !project ? (
              <EmptyState
                title={detail.isPending && openId ? "Loading project…" : "Select a project"}
                body="Pick a project to see its brief, milestones, tasks, and what to work on next."
              />
            ) : (
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="text-xl font-extrabold tracking-tight">{project.title}</h2>
                  <span className="tag">{project.language}</span>
                  <span className={`tag ${project.status === "done" ? "border-(--success)" : ""}`}>
                    {project.status}
                  </span>
                  <Link to={`/app?project=${project.id}`} className="btn btn-primary btn-sm ml-auto">
                    <Play size={14} strokeWidth={1.5} /> Start session
                  </Link>
                </div>
                {project.objective && (
                  <p className="serif-body mt-3 text-(--muted)">{project.objective}</p>
                )}
                {project.stack && (
                  <p className="mt-2 text-[13px] text-(--muted)">Stack: {project.stack}</p>
                )}
                {project.architecture && (
                  <details className="mt-3">
                    <summary className="cursor-pointer text-[13px] font-semibold text-(--muted)">
                      Architecture
                    </summary>
                    <p className="mt-2 rounded-xl bg-(--bg-soft) p-3 text-sm leading-relaxed text-(--muted)">
                      {project.architecture}
                    </p>
                  </details>
                )}

                {next.data && !next.data.done && next.data.task && (
                  <div className="mt-4 rounded-xl border border-(--border-strong) bg-(--accent-soft) p-4">
                    <p className="label">Up next</p>
                    <p className="font-semibold">{next.data.task.title}</p>
                    <p className="mt-1 text-[13px] text-(--muted)">{next.data.guidance}</p>
                    <Link to={`/app?project=${project.id}`} className="btn btn-primary btn-sm mt-3">
                      Work on it with the mentor <ArrowRight size={14} strokeWidth={1.5} />
                    </Link>
                  </div>
                )}
                {next.data?.done && (
                  <p className="mt-4 flex items-center gap-2 rounded-xl border border-(--success) p-4 text-sm font-semibold text-(--success)">
                    <Check size={16} strokeWidth={1.5} /> Everything here is done. Nice work.
                  </p>
                )}

                <div className="mt-5 border-t border-(--border) pt-4">
                  <p className="label">Generate a brief from an idea</p>
                  <textarea
                    className="input min-h-20 resize-y"
                    value={briefText}
                    onChange={(e) => setBriefText(e.target.value)}
                    placeholder="Describe the project in a few sentences… (min 10 characters)"
                    aria-label="Project idea for the brief generator"
                  />
                  <button
                    type="button"
                    onClick={() => void generateBrief()}
                    disabled={briefBusy || briefText.trim().length < 10}
                    className="btn btn-ghost btn-sm mt-2"
                  >
                    {briefBusy ? <Loader2 size={14} strokeWidth={1.5} className="animate-spin" /> : <Sparkles size={14} strokeWidth={1.5} />}
                    {briefBusy ? "Generating…" : "Generate brief + milestones"}
                  </button>
                </div>

                <div className="mt-5 border-t border-(--border) pt-4">
                  <p className="label">Milestones</p>
                  <div className="flex flex-col gap-3">
                    {project.milestones.map((m) => (
                      <div key={m.id} className="rounded-xl border border-(--border) bg-(--bg-soft) p-3.5">
                        <div className="flex items-center gap-2">
                          <button
                            type="button"
                            onClick={() => void cycleStatus("milestone", m.id, m.status)}
                            className="tag"
                            title="Click to advance status"
                          >
                            {m.status === "done" ? <Check size={12} strokeWidth={2} /> : null}
                            {m.status}
                          </button>
                          <span className="text-sm font-semibold">{m.title}</span>
                        </div>
                        {m.detail && <p className="mt-1 text-[13px] text-(--muted)">{m.detail}</p>}
                        <ul className="mt-2 flex flex-col gap-1.5">
                          {m.tasks.map((t) => (
                            <li key={t.id} className="flex items-center gap-2 text-[13px]">
                              <button
                                type="button"
                                onClick={() => void cycleStatus("task", t.id, t.status)}
                                aria-label={`Mark ${t.title} (currently ${t.status})`}
                                title="Click to advance status"
                                className={`grid size-5 shrink-0 place-items-center rounded-md border text-[11px] font-bold ${
                                  t.status === "done"
                                    ? "border-(--success) bg-(--success) text-black"
                                    : t.status === "doing"
                                      ? "border-(--accent) text-(--accent-text)"
                                      : "border-(--border-strong) text-(--faint)"
                                }`}
                              >
                                {t.status === "done" ? <Check size={12} strokeWidth={2.5} /> : t.status === "doing" ? "…" : ""}
                              </button>
                              <span className={t.status === "done" ? "text-(--muted) line-through" : ""}>
                                {t.title}
                              </span>
                            </li>
                          ))}
                        </ul>
                        <div className="mt-2 flex gap-2">
                          <input
                            className="input min-w-0 flex-1 !py-1.5 text-[13px]"
                            value={newTask[m.id] ?? ""}
                            onChange={(e) => setNewTask((s) => ({ ...s, [m.id]: e.target.value }))}
                            onKeyDown={(e) => {
                              if (e.key === "Enter" && (newTask[m.id] ?? "").trim()) {
                                void api.addTask(m.id, (newTask[m.id] ?? "").trim()).then(() => {
                                  setNewTask((s) => ({ ...s, [m.id]: "" }));
                                  invalidateList();
                                }).catch((err) => fail(err, "add the task"));
                              }
                            }}
                            placeholder="New task…"
                            aria-label={`New task in ${m.title}`}
                          />
                          <button
                            type="button"
                            className="btn btn-ghost btn-sm"
                            disabled={!(newTask[m.id] ?? "").trim()}
                            onClick={() => {
                              const v = (newTask[m.id] ?? "").trim();
                              if (!v) return;
                              void api.addTask(m.id, v).then(() => {
                                setNewTask((s) => ({ ...s, [m.id]: "" }));
                                invalidateList();
                              }).catch((err) => fail(err, "add the task"));
                            }}
                          >
                            <Plus size={14} strokeWidth={1.5} />
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                  <form
                    className="mt-3 flex gap-2"
                    onSubmit={(e) => {
                      e.preventDefault();
                      if (!newMilestone.trim() || !openId) return;
                      void api.addMilestone(openId, newMilestone.trim()).then(() => {
                        setNewMilestone("");
                        invalidateList();
                      }).catch((err) => fail(err, "add the milestone"));
                    }}
                  >
                    <input
                      className="input min-w-0 flex-1"
                      value={newMilestone}
                      onChange={(e) => setNewMilestone(e.target.value)}
                      placeholder="New milestone…"
                      aria-label="New milestone title"
                    />
                    <button type="submit" className="btn btn-ghost btn-sm" disabled={!newMilestone.trim()}>
                      <Plus size={14} strokeWidth={1.5} /> Add
                    </button>
                  </form>
                </div>
              </div>
            )}
          </div>
        </Reveal>
      </div>
    </main>
  );
}