import { useState, type FormEvent } from "react";
import { useAuth } from "./AuthContext";
import { ApiError } from "../api/client";

type Mode = "login" | "signup";

export function LoginPage() {
  const { login, signup } = useAuth();
  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (busy) return;
    setError(null);
    setBusy(true);
    try {
      if (mode === "login") {
        await login({ email, password });
      } else {
        await signup({
          email,
          password,
          display_name: displayName.trim() || null,
        });
      }
    } catch (err) {
      if (err instanceof ApiError) setError(err.message);
      else setError("Something went wrong.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth-shell">
      <div className="auth-box">
        <div className="auth-brand">STACK</div>
        <div className="auth-tabs">
          <button
            type="button"
            className={`auth-tab${mode === "login" ? " auth-tab--active" : ""}`}
            onClick={() => {
              setMode("login");
              setError(null);
            }}
          >
            Log in
          </button>
          <button
            type="button"
            className={`auth-tab${mode === "signup" ? " auth-tab--active" : ""}`}
            onClick={() => {
              setMode("signup");
              setError(null);
            }}
          >
            Sign up
          </button>
        </div>

        <form onSubmit={submit} className="auth-form">
          <label className="auth-field">
            <span className="auth-label">Email</span>
            <input
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </label>

          <label className="auth-field">
            <span className="auth-label">Password</span>
            <input
              type="password"
              autoComplete={
                mode === "login" ? "current-password" : "new-password"
              }
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>

          {mode === "signup" && (
            <label className="auth-field">
              <span className="auth-label">Display name (optional)</span>
              <input
                type="text"
                autoComplete="name"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
              />
            </label>
          )}

          {error && <div className="auth-error">{error}</div>}

          <button type="submit" disabled={busy} className="auth-submit">
            {busy
              ? mode === "login"
                ? "Signing in…"
                : "Creating account…"
              : mode === "login"
                ? "Log in"
                : "Create account"}
          </button>
        </form>

        <p className="auth-foot">
          {mode === "login"
            ? "New here? Use the Sign up tab."
            : "Already have an account? Use the Log in tab."}
        </p>
      </div>
    </div>
  );
}
