import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { get, getToken, post, setToken, unauthEvent } from "./api";

const USER_KEY = "rpa_user";

type AuthStatus = "checking" | "ready" | "auth" | "offline";

interface AuthValue {
  status: AuthStatus;
  mode: "open" | "auth";
  user: string | null;
  login: (username: string, password: string) => Promise<void>;
  setup: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  reprobe: () => void;
}

const AuthCtx = createContext<AuthValue | null>(null);

function storedUser(): string | null {
  return localStorage.getItem(USER_KEY);
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>("checking");
  const [mode, setMode] = useState<"open" | "auth">("auth");
  const [user, setUser] = useState<string | null>(storedUser);

  useEffect(() => {
    const onUnauth = () => {
      setToken(null);
      localStorage.removeItem(USER_KEY);
      setUser(null);
      setStatus("auth");
    };
    window.addEventListener(unauthEvent, onUnauth);
    return () => window.removeEventListener(unauthEvent, onUnauth);
  }, []);

  const probe = useCallback(async () => {
    setStatus("checking");
    let mode_: "open" | "auth" = "auth";
    try {
      await get<unknown>("/api/projects");
      if (!getToken()) mode_ = "open";
      setMode(mode_);
      setStatus("ready");
    } catch (e) {
      const code = (e as { status?: number }).status;
      if (code === 401) {
        setToken(null);
        localStorage.removeItem(USER_KEY);
        setUser(null);
        setMode("auth");
        setStatus("auth");
      } else if (code === 0) {
        setStatus("offline");
      } else {
        setMode(mode_);
        setStatus("ready");
      }
    }
  }, []);

  useEffect(() => {
    void probe();
  }, [probe]);

  const login = useCallback(async (username: string, password: string) => {
    const r = await post<{ token: string; user: string }>("/api/auth/login", {
      username,
      password,
    });
    setToken(r.token);
    localStorage.setItem(USER_KEY, r.user);
    setUser(r.user);
    setMode("auth");
    setStatus("ready");
  }, []);

  const setup = useCallback(
    async (username: string, password: string) => {
      await post("/api/auth/setup", { username, password });
      await login(username, password);
    },
    [login],
  );

  const logout = useCallback(async () => {
    try {
      await post("/api/auth/logout", undefined);
    } catch {
      /* token may already be invalid */
    }
    setToken(null);
    localStorage.removeItem(USER_KEY);
    setUser(null);
    setStatus("auth");
  }, []);

  const value = useMemo<AuthValue>(
    () => ({ status, mode, user, login, setup, logout, reprobe: () => void probe() }),
    [status, mode, user, login, setup, logout, probe],
  );

  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>;
}

export function useAuth(): AuthValue {
  const v = useContext(AuthCtx);
  if (!v) throw new Error("useAuth outside AuthProvider");
  return v;
}