import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ApiError, api, type User } from "./api";
import {
  AUTH_MISCONFIGURED_DETAIL,
  consumeAuthCallback,
  supabase,
} from "./supabase";

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string, name: string) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
  ensureGuest: () => Promise<User>;
  sendPasswordReset: (email: string) => Promise<void>;
  resetPassword: (password: string) => Promise<void>;
  changePassword: (currentPassword: string, newPassword: string) => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

function requireClient() {
  if (!supabase) throw new ApiError(0, AUTH_MISCONFIGURED_DETAIL);
  return supabase;
}

function authFailure(
  error: { message: string; status?: number } | null,
  fallback: string,
): never {
  throw new ApiError(error?.status ?? 400, error?.message || fallback);
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const queryClient = useQueryClient();

  const loadUser = useCallback(async (accessToken?: string) => {
    try {
      setUser(await api.me(accessToken));
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  const refresh = useCallback(async () => {
    if (!supabase) {
      setUser(null);
      setLoading(false);
      return;
    }
    const { data } = await supabase.auth.getSession();
    if (!data.session) {
      setUser(null);
      setLoading(false);
      return;
    }
    await loadUser(data.session.access_token);
  }, [loadUser]);

  useEffect(() => {
    let active = true;
    const subscription = supabase?.auth.onAuthStateChange((event, session) => {
      if (!active || event === "INITIAL_SESSION") return;
      if (event === "SIGNED_OUT" || event === "SIGNED_IN") queryClient.clear();
      if (!session) {
        setUser(null);
        setLoading(false);
        return;
      }
      window.setTimeout(() => {
        if (active) void loadUser(session.access_token);
      }, 0);
    }).data.subscription;

    void (async () => {
      try {
        await consumeAuthCallback();
      } catch {
        // An invalid recovery link is reported by the reset page.
      }
      if (!active) return;
      if (!supabase) {
        setUser(null);
        setLoading(false);
        return;
      }
      const { data } = await supabase.auth.getSession();
      if (!active) return;
      if (!data.session) {
        setUser(null);
        setLoading(false);
        return;
      }
      await loadUser(data.session.access_token);
    })();

    return () => {
      active = false;
      subscription?.unsubscribe();
    };
  }, [loadUser, queryClient]);

  const login = useCallback(
    async (email: string, password: string) => {
      const client = requireClient();
      const { error } = await client.auth.signInWithPassword({ email, password });
      if (error) authFailure(error, "Login failed. Try again.");
      await refresh();
    },
    [refresh],
  );

  const signup = useCallback(
    async (email: string, password: string, name: string) => {
      const client = requireClient();
      const { data: current } = await client.auth.getSession();
      if (current.session?.user.is_anonymous) {
        await client.auth.signOut();
      }
      const { data, error } = await client.auth.signUp({
        email,
        password,
        options: { data: { display_name: name } },
      });
      if (error) authFailure(error, "Could not create the account.");
      if (!data.session) {
        await client.auth.signOut({ scope: "local" });
        throw new ApiError(
          409,
          "Check your email to confirm the account, then log in.",
        );
      }
      await loadUser(data.session.access_token);
    },
    [loadUser],
  );

  const logout = useCallback(async () => {
    if (supabase) {
      try {
        const { error } = await supabase.auth.signOut();
        if (error) await supabase.auth.signOut({ scope: "local" });
      } catch {
        await supabase.auth.signOut({ scope: "local" }).catch(() => undefined);
      }
    }
    setUser(null);
    queryClient.clear();
  }, [queryClient]);

  const ensureGuest = useCallback(async (): Promise<User> => {
    const client = requireClient();
    const { data } = await client.auth.getSession();
    if (data.session) {
      try {
        const existing = await api.me(data.session.access_token);
        setUser(existing);
        return existing;
      } catch (err) {
        if (!(err instanceof ApiError) || err.status !== 401) throw err;
        await client.auth.signOut({ scope: "local" });
      }
    }
    const { data: anonymous, error } = await client.auth.signInAnonymously();
    if (error || !anonymous.session) {
      authFailure(error, "Could not start a guest session.");
    }
    const guest = await api.me(anonymous.session.access_token);
    setUser(guest);
    return guest;
  }, []);

  const sendPasswordReset = useCallback(async (email: string) => {
    const client = requireClient();
    const redirectTo = `${window.location.origin}${window.location.pathname}#/reset`;
    const { error } = await client.auth.resetPasswordForEmail(email, {
      redirectTo,
    });
    if (error) authFailure(error, "Could not send the reset email.");
  }, []);

  const resetPassword = useCallback(
    async (password: string) => {
      const client = requireClient();
      const { error } = await client.auth.updateUser({ password });
      if (error) authFailure(error, "Could not reset the password.");
      await refresh();
    },
    [refresh],
  );

  const changePassword = useCallback(
    async (currentPassword: string, newPassword: string) => {
      const client = requireClient();
      const { data: current, error: userError } = await client.auth.getUser();
      const email = current.user?.email;
      if (userError || !email) {
        authFailure(userError, "This account cannot change its password.");
      }
      const { error: verifyError } = await client.auth.signInWithPassword({
        email,
        password: currentPassword,
      });
      if (verifyError) authFailure(verifyError, "Current password is incorrect.");
      const { error } = await client.auth.updateUser({ password: newPassword });
      if (error) authFailure(error, "Could not change the password.");
      await client.auth.signOut({ scope: "others" });
      await refresh();
    },
    [refresh],
  );

  const value = useMemo(
    () => ({
      user,
      loading,
      login,
      signup,
      logout,
      refresh,
      ensureGuest,
      sendPasswordReset,
      resetPassword,
      changePassword,
    }),
    [
      user,
      loading,
      login,
      signup,
      logout,
      refresh,
      ensureGuest,
      sendPasswordReset,
      resetPassword,
      changePassword,
    ],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
