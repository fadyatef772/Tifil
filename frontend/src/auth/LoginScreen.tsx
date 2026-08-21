import { useEffect, useState } from "react";
import { useAuth } from "./AuthContext";
import { t } from "../i18n";
import type { Lang } from "../types";

export default function LoginScreen({ lang, onSwitch }: { lang: Lang; onSwitch: () => void }) {
  const s = t[lang];
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => setError(null), []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await login(email, password);
    } catch {
      setError(s.invalidCredentials);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-stone-50 p-4">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm bg-white rounded-2xl shadow-lg p-8 space-y-5"
      >
        <div className="text-center">
          <span className="text-4xl" aria-hidden>🧸</span>
          <h1 className="text-2xl font-bold mt-2">{s.loginTitle}</h1>
        </div>

        {error && (
          <div className="bg-red-50 text-red-700 text-sm rounded-lg p-3 text-center">
            {error}
          </div>
        )}

        <div className="space-y-1">
          <label className="text-sm font-medium text-stone-600">{s.email}</label>
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full border border-stone-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400"
            dir="ltr"
          />
        </div>

        <div className="space-y-1">
          <label className="text-sm font-medium text-stone-600">{s.password}</label>
          <input
            type="password"
            required
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full border border-stone-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400"
            dir="ltr"
          />
          <p className="text-xs text-stone-400">{s.passwordMin}</p>
        </div>

        <button
          type="submit"
          disabled={busy}
          className="w-full py-2.5 rounded-lg bg-amber-400 hover:bg-amber-500 text-stone-900 font-semibold text-sm transition disabled:opacity-50"
        >
          {busy ? "..." : s.login}
        </button>

        <p className="text-center text-sm text-stone-500">
          {s.noAccount}{" "}
          <button
            type="button"
            onClick={onSwitch}
            className="text-amber-600 hover:underline font-medium"
          >
            {s.signup}
          </button>
        </p>
      </form>
    </div>
  );
}
