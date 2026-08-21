import { createContext, useContext, useEffect, useState } from "react";
import { api, setAuthToken } from "../api";
import type { Parent } from "../types";

interface AuthState {
  parent: Parent | null;
  token: string | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string, name: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [parent, setParent] = useState<Parent | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // Load parent profile whenever token changes (mount, login, signup, logout).
  useEffect(() => {
    if (!token) {
      setParent(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    api
      .me()
      .then((p) => setParent(p))
      .catch(() => {
        // Token invalid or expired — clear it.
        sessionStorage.removeItem("tifl_token");
        setAuthToken(null);
        setToken(null);
        setParent(null);
      })
      .finally(() => setLoading(false));
  }, [token]);

  // Restore token from sessionStorage on mount.
  useEffect(() => {
    const saved = sessionStorage.getItem("tifl_token");
    if (saved) {
      setAuthToken(saved);
      setToken(saved);
    } else {
      setLoading(false);
    }
  }, []);

  const login = async (email: string, password: string) => {
    const { access_token } = await api.login(email, password);
    sessionStorage.setItem("tifl_token", access_token);
    setAuthToken(access_token);
    setToken(access_token);
  };

  const signup = async (email: string, password: string, name: string) => {
    const { access_token } = await api.signup(email, password, name);
    sessionStorage.setItem("tifl_token", access_token);
    setAuthToken(access_token);
    setToken(access_token);
  };

  const logout = () => {
    sessionStorage.removeItem("tifl_token");
    setAuthToken(null);
    setToken(null);
    setParent(null);
  };

  return (
    <AuthContext.Provider
      value={{ parent, token, loading, login, signup, logout }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
