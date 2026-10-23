import { FormEvent, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  AlertTriangle,
  KeyRound,
  Save,
  ShieldCheck,
  Trash2,
} from "lucide-react";
import { api, ApiError, type RegistryLanguage } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useTheme } from "../lib/theme";
import { useToast } from "../lib/toast";
import { Reveal } from "../components/Reveal";

const EXPERIENCE_LEVELS: { value: string; label: string }[] = [
  { value: "", label: "Not set" },
  { value: "beginner", label: "Beginner" },
  { value: "intermediate", label: "Intermediate" },
  { value: "advanced", label: "Advanced" },
];

const LEARNING_GOALS: { value: string; label: string }[] = [
  { value: "", label: "Not set" },
  { value: "debugging", label: "Get better at debugging" },
  { value: "projects", label: "Build my own projects" },
  { value: "interviews", label: "Prepare for interviews" },
  { value: "exams", label: "Prepare for exams" },
  { value: "concepts", label: "Deepen core concepts" },
];

function errText(e: unknown, fallback: string): string {
  return e instanceof ApiError ? e.message : fallback;
}

export function Profile() {
  const { user, refresh, logout, changePassword } = useAuth();
  const { theme, set: setTheme } = useTheme();
  const toast = useToast();
  const navigate = useNavigate();

  /* ----- identity ----- */
  const [displayName, setDisplayName] = useState(user?.display_name ?? "");
  useEffect(() => setDisplayName(user?.display_name ?? ""), [user?.display_name]);
  const [savingName, setSavingName] = useState(false);

  /* ----- preferences ----- */
  const [languages, setLanguages] = useState<RegistryLanguage[]>([]);
  useEffect(() => {
    void api.languages().then(setLanguages).catch(() => setLanguages([]));
  }, []);

  async function patchProfile(patch: Record<string, unknown>, ok: string) {
    try {
      await api.updateProfile(patch);
      await refresh();
      toast("success", ok);
    } catch (e) {
      toast("error", errText(e, "Could not save. Try again."));
    }
  }

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [changingPassword, setChangingPassword] = useState(false);
  const [passwordError, setPasswordError] = useState("");

  async function onChangePassword(e: FormEvent) {
    e.preventDefault();
    setPasswordError("");
    if (newPassword !== confirmPassword) {
      setPasswordError("The two new passwords do not match.");
      return;
    }
    setChangingPassword(true);
    try {
      await changePassword(currentPassword, newPassword);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      toast("success", "Password changed. Other sessions were logged out.");
    } catch (err) {
      setPasswordError(errText(err, "Could not change the password."));
    } finally {
      setChangingPassword(false);
    }
  }

  const [showDanger, setShowDanger] = useState(false);
  const [confirmWord, setConfirmWord] = useState("");
  const [deleting, setDeleting] = useState(false);

  async function onDelete() {
    setDeleting(true);
    try {
      await api.deleteAccount();
      await logout();
      navigate("/");
      toast("success", "Account deleted. All data has been removed.");
    } catch (err) {
      toast("error", errText(err, "Could not delete the account."));
    } finally {
      setDeleting(false);
    }
  }

  const languageOptions = useMemo(
    () => [
      { key: "", label: "Not set" },
      ...languages.map((l) => ({ key: l.key, label: l.label })),
    ],
    [languages],
  );

  if (!user) return null;

  return (
    <main className="mx-auto w-[min(760px,92%)] py-10 md:py-16">
      <Reveal>
        <h1 className="text-2xl font-extrabold tracking-tight md:text-3xl">
          Profile &amp; settings
        </h1>
        <p className="mt-1 text-sm text-(--muted)">
          Everything here saves to your account on the server.
        </p>

        {/* ---------------- identity ---------------- */}
        <section className="card mt-6 p-6 md:p-7" aria-labelledby="profile-id">
          <h2 id="profile-id" className="text-lg font-bold">Account</h2>

          <div className="mt-4 flex flex-col gap-4">
            <div>
              <span className="label">Email</span>
              <input
                className="input disabled:opacity-70"
                type="text"
                value={user.email ?? "Guest session"}
                disabled
                readOnly
                aria-readonly="true"
              />
              {user.is_anonymous && (
                <p className="mt-2 text-xs text-(--muted)">
                  This is a guest session.{" "}
                  <Link to="/signup" className="font-semibold text-(--accent-text)">
                    Create a free account
                  </Link>{" "}
                  for unlimited sessions and a permanent history.
                </p>
              )}
            </div>

            <form
              onSubmit={async (e) => {
                e.preventDefault();
                setSavingName(true);
                await patchProfile(
                  { display_name: displayName },
                  "Display name saved.",
                );
                setSavingName(false);
              }}
              className="flex flex-col gap-2"
            >
              <label className="label" htmlFor="profile-name">Display name</label>
              <div className="flex flex-col gap-2 sm:flex-row">
                <input
                  id="profile-name"
                  className="input flex-1"
                  maxLength={120}
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  placeholder="How the mentor greets you"
                />
                <button type="submit" className="btn btn-primary" disabled={savingName}>
                  <Save size={15} strokeWidth={1.5} aria-hidden />
                  {savingName ? "Saving…" : "Save name"}
                </button>
              </div>
            </form>
          </div>
        </section>

        {/* ---------------- preferences ---------------- */}
        <section className="card mt-6 p-6 md:p-7" aria-labelledby="profile-prefs">
          <h2 id="profile-prefs" className="text-lg font-bold">Preferences</h2>

          <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="label" htmlFor="profile-theme">Theme</label>
              <select
                id="profile-theme"
                className="input"
                value={theme}
                onChange={(e) => {
                  const next = e.target.value;
                  setTheme(next === "light" ? "light" : "dark");
                  void patchProfile({ theme: next }, "Theme saved.");
                }}
              >
                <option value="dark">Dark</option>
                <option value="light">Light</option>
              </select>
              <p className="mt-1 text-xs text-(--muted)">
                Also changeable anytime from the moon button.
              </p>
            </div>

            <div>
              <label className="label" htmlFor="profile-language">Preferred language</label>
              <select
                id="profile-language"
                className="input"
                value={user.preferred_language}
                onChange={(e) =>
                  void patchProfile(
                    { preferred_language: e.target.value },
                    "Preferred language saved.",
                  )
                }
              >
                {languageOptions.map((l) => (
                  <option key={l.key} value={l.key}>{l.label}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="label" htmlFor="profile-goal">Learning goal</label>
              <select
                id="profile-goal"
                className="input"
                value={user.learning_goal}
                onChange={(e) =>
                  void patchProfile(
                    { learning_goal: e.target.value },
                    "Learning goal saved.",
                  )
                }
              >
                {LEARNING_GOALS.map((g) => (
                  <option key={g.value} value={g.value}>{g.label}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="label" htmlFor="profile-level">Experience level</label>
              <select
                id="profile-level"
                className="input"
                value={user.experience_level}
                onChange={(e) =>
                  void patchProfile(
                    { experience_level: e.target.value },
                    "Experience level saved.",
                  )
                }
              >
                {EXPERIENCE_LEVELS.map((l) => (
                  <option key={l.value} value={l.value}>{l.label}</option>
                ))}
              </select>
            </div>
          </div>

          {!user.is_anonymous && (
            <div className="mt-4 flex flex-col gap-3">
              <label className="flex items-center justify-between gap-3 rounded-lg border border-(--border) px-3 py-2.5">
                <span className="flex items-center gap-2 text-sm font-semibold">
                  <ShieldCheck size={15} strokeWidth={1.5} aria-hidden />
                  Email me about account security
                </span>
                <input
                  type="checkbox"
                  className="size-4 accent-(--accent)"
                  checked={user.notify_security_emails}
                  onChange={(e) =>
                    void patchProfile(
                      { notify_security_emails: e.target.checked },
                      "Security email preference saved.",
                    )
                  }
                />
              </label>
              <label className="flex items-center justify-between gap-3 rounded-lg border border-(--border) px-3 py-2.5">
                <span className="text-sm font-semibold">
                  Email me about learning progress
                </span>
                <input
                  type="checkbox"
                  className="size-4 accent-(--accent)"
                  checked={user.notify_progress_emails}
                  onChange={(e) =>
                    void patchProfile(
                      { notify_progress_emails: e.target.checked },
                      "Progress email preference saved.",
                    )
                  }
                />
              </label>
            </div>
          )}
        </section>

        {!user.is_anonymous && (
          <section className="card mt-6 p-6 md:p-7" aria-labelledby="profile-password">
            <h2 id="profile-password" className="flex items-center gap-2 text-lg font-bold">
              <KeyRound size={17} strokeWidth={1.5} aria-hidden /> Change password
            </h2>
            <p className="mt-1 text-sm text-(--muted)">
              Requires your current password. All other sessions are logged out.
            </p>
            <form onSubmit={onChangePassword} className="mt-4 flex max-w-md flex-col gap-3">
            <div>
              <label className="label" htmlFor="cp-current">Current password</label>
              <input
                id="cp-current"
                className="input"
                type="password"
                required
                autoComplete="current-password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
              />
            </div>
            <div>
              <label className="label" htmlFor="cp-new">New password</label>
              <input
                id="cp-new"
                className="input"
                type="password"
                required
                minLength={8}
                autoComplete="new-password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
              />
            </div>
            <div>
              <label className="label" htmlFor="cp-confirm">Confirm new password</label>
              <input
                id="cp-confirm"
                className="input"
                type="password"
                required
                minLength={8}
                autoComplete="new-password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
              />
            </div>
            {passwordError && (
              <p role="alert" className="rounded-lg border border-(--danger) bg-(--danger)/10 px-3 py-2 text-sm">
                {passwordError}
              </p>
            )}
            <button type="submit" className="btn btn-primary self-start" disabled={changingPassword}>
              {changingPassword ? "Changing…" : "Change password"}
            </button>
          </form>
        </section>
        )}

        {/* ---------------- danger zone ---------------- */}
        <section className="card mt-6 border-(--danger)/40 p-6 md:p-7" aria-labelledby="profile-danger">
          <h2 id="profile-danger" className="flex items-center gap-2 text-lg font-bold text-(--danger)">
            <AlertTriangle size={17} strokeWidth={1.5} aria-hidden /> Danger zone
          </h2>
          <p className="mt-1 text-sm text-(--muted)">
            Deleting removes all your sessions, projects, badges, and activity permanently.
          </p>
          {!showDanger ? (
            <button type="button" className="btn btn-ghost mt-4 self-start" onClick={() => setShowDanger(true)}>
              <Trash2 size={15} strokeWidth={1.5} aria-hidden />
              Delete my account…
            </button>
          ) : (
            <form
              className="mt-4 flex max-w-md flex-col gap-3"
              onSubmit={(e) => {
                e.preventDefault();
                if (confirmWord !== "DELETE") return;
                void onDelete();
              }}
            >
              <div>
                <label className="label" htmlFor="del-word">
                  Type <strong>DELETE</strong> to confirm
                </label>
                <input
                  id="del-word"
                  className="input"
                  value={confirmWord}
                  onChange={(e) => setConfirmWord(e.target.value)}
                  autoComplete="off"
                  placeholder="DELETE"
                />
              </div>
              <div className="flex gap-2">
                <button
                  type="submit"
                  className="btn btn-primary bg-(--danger) text-white"
                  disabled={deleting || confirmWord !== "DELETE"}
                >
                  {deleting ? "Deleting…" : "Permanently delete account"}
                </button>
                <button
                  type="button"
                  className="btn btn-ghost"
                  onClick={() => {
                    setShowDanger(false);
                    setConfirmWord("");
                  }}
                >
                  Cancel
                </button>
              </div>
            </form>
          )}
        </section>
      </Reveal>
    </main>
  );
}
