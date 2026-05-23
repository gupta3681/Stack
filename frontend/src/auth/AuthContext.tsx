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
import { ApiError, api } from "../api/client";
import type { AuthUser, LoginInput, SignupInput } from "../types";

type Status = "loading" | "anonymous" | "authenticated";

interface AuthState {
  status: Status;
  user: AuthUser | null;
  login: (input: LoginInput) => Promise<void>;
  signup: (input: SignupInput) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthCtx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [status, setStatus] = useState<Status>("loading");

  useEffect(() => {
    let cancelled = false;
    api
      .me()
      .then((u) => {
        if (cancelled) return;
        setUser(u);
        setStatus("authenticated");
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 401) {
          setStatus("anonymous");
        } else {
          // Backend down or unexpected; treat as anonymous so login page shows.
          setStatus("anonymous");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (input: LoginInput) => {
    const u = await api.login(input);
    setUser(u);
    setStatus("authenticated");
  }, []);

  const signup = useCallback(async (input: SignupInput) => {
    const u = await api.signup(input);
    setUser(u);
    setStatus("authenticated");
  }, []);

  const logout = useCallback(async () => {
    // Clear the user-scoped query cache BEFORE network so a slow/failing
    // logout request can't briefly expose the previous user's data to a
    // re-login flow on the same browser.
    qc.clear();
    try {
      await api.logout();
    } finally {
      setUser(null);
      setStatus("anonymous");
    }
  }, [qc]);

  const value = useMemo<AuthState>(
    () => ({ status, user, login, signup, logout }),
    [status, user, login, signup, logout]
  );

  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthCtx);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
