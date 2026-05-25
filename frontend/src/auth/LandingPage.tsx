import { useState, type FormEvent } from "react";
import { useAuth } from "./AuthContext";
import { ApiError } from "../api/client";

type Mode = "signup" | "login";

/**
 * Public landing page shown to anonymous visitors.
 *
 * Pitches the product (hero copy + mock stack + three feature blurbs)
 * with the signup form inline on the right so the path from "what is
 * this?" to "I have an account" is one screen. The mock stack reuses
 * the production .task/.task__title/etc. classes so visitors see the
 * actual visual language they'd be signing up for.
 */
export function LandingPage() {
  const { login, signup } = useAuth();
  const [mode, setMode] = useState<Mode>("signup");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (busy) return;
    setError(null);

    if (mode === "signup" && password !== confirmPassword) {
      setError("Passwords don't match.");
      return;
    }

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

  const toggleMode = () => {
    setMode((m) => (m === "signup" ? "login" : "signup"));
    setError(null);
    setConfirmPassword("");
  };

  return (
    <div className="landing">
      <header className="landing__topbar">
        <div className="landing__brand-row">
          <svg
            className="landing__logo"
            viewBox="0 0 32 32"
            aria-hidden="true"
          >
            <rect x="5" y="7" width="22" height="4" />
            <rect x="5" y="14" width="22" height="4" opacity="0.6" />
            <rect x="5" y="21" width="22" height="4" opacity="0.3" />
          </svg>
          <span className="landing__brand">STACK</span>
        </div>
      </header>

      <section className="landing__hero">
        <div className="landing__hero-copy">
          <div className="landing__eyebrow">A productivity experiment</div>
          <h1 className="landing__tagline">
            Your priorities,
            <br />
            rendered at the size
            <br />
            they deserve.
          </h1>
          <p className="landing__lede">
            Stack is a to-do app with an opinion. The top of every stack is{" "}
            <em>physically larger</em> than the rest — you should feel the
            weight of the one thing that's next, not scan a flat list to
            find it.
          </p>
          <p className="landing__lede">
            Already agent-readable: an API token lets your CLI or Claude
            Code add tasks, pull from a topic stack into today, and mark
            things done — same endpoints the web app calls. The deeper bet
            is on what comes next: an agent that reads across your stacks
            and proposes what should move where, based on what you're
            focused on right now.
          </p>
        </div>

        <aside className="landing__hero-auth" aria-label="Get started">
          <div className="landing__auth-eyebrow">
            {mode === "signup" ? "Create your account" : "Welcome back"}
          </div>

          <form className="landing__auth-form" onSubmit={submit}>
            <label className="landing__auth-field">
              <span className="landing__auth-label">Email</span>
              <input
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </label>

            <label className="landing__auth-field">
              <span className="landing__auth-label">Password</span>
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
              <>
                <label className="landing__auth-field">
                  <span className="landing__auth-label">Confirm password</span>
                  <input
                    type="password"
                    autoComplete="new-password"
                    required
                    minLength={8}
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                  />
                </label>
                <label className="landing__auth-field">
                  <span className="landing__auth-label">
                    Display name (optional)
                  </span>
                  <input
                    type="text"
                    autoComplete="name"
                    value={displayName}
                    onChange={(e) => setDisplayName(e.target.value)}
                  />
                </label>
              </>
            )}

            {error && <div className="landing__auth-error">{error}</div>}

            <button
              type="submit"
              disabled={busy}
              className="landing__auth-submit"
            >
              {busy
                ? mode === "login"
                  ? "Signing in…"
                  : "Creating account…"
                : mode === "login"
                  ? "Log in"
                  : "Create account"}
            </button>
          </form>

          <p className="landing__auth-toggle">
            {mode === "signup"
              ? "Already have an account?"
              : "New here?"}{" "}
            <button
              type="button"
              className="landing__auth-toggle-btn"
              onClick={toggleMode}
            >
              {mode === "signup" ? "Log in" : "Create an account"}
            </button>
          </p>
        </aside>
      </section>

      <section className="landing__demo">
        <div className="landing__demo-caption">
          THIS IS WHAT IT LOOKS LIKE ↓
        </div>
        <div className="landing__demo-card">
          <header className="stack-head">
            <div className="stack-head__date">TODAY · DEMO</div>
            <h1 className="stack-head__title">TODAY'S STACK</h1>
            <div className="stack-head__intention">
              <span>ship onboarding rewrite by EOD</span>
            </div>
          </header>
          <div className="ondeck-label" aria-hidden>
            On top ↓
          </div>
          <ul className="tasks landing__demo-tasks">
            <li className="task task--p0">
              <div className="task__pos">01</div>
              <div className="task__body">
                <p className="task__title">Onboarding rewrite — final pass</p>
                <div className="task__meta">
                  <span className="task__chip">high</span>
                  <span className="task__chip">DUE TODAY</span>
                </div>
              </div>
            </li>
            <li className="task task--p1">
              <div className="task__pos">02</div>
              <div className="task__body">
                <p className="task__title">Review eng PR queue</p>
              </div>
            </li>
            <li className="task task--p2">
              <div className="task__pos">03</div>
              <div className="task__body">
                <p className="task__title">
                  Pasta tonight — pull Italian cookbook from Reading
                </p>
              </div>
            </li>
            <li className="task task--p3">
              <div className="task__pos">04</div>
              <div className="task__body">
                <p className="task__title">End-of-quarter retro doc</p>
              </div>
            </li>
          </ul>
        </div>
      </section>

      <section className="landing__features">
        <article className="landing__feature">
          <div className="landing__feature-label">01 · Daily stacks</div>
          <h3 className="landing__feature-title">What you're doing today.</h3>
          <p className="landing__feature-body">
            One stack per day. Today, Tomorrow. The top is rendered larger
            on purpose — you should feel the weight of the one thing
            that's next. Hit play to start a live timer; it keeps ticking
            even with the tab closed.
          </p>
        </article>
        <article className="landing__feature">
          <div className="landing__feature-label">02 · Topic stacks + sharing</div>
          <h3 className="landing__feature-title">Long-lived backlogs. Public when you want.</h3>
          <p className="landing__feature-body">
            Reading, Watching, Listening, Buy, Ideas. Long-lived lists you
            pull from. Flip any one public to share with anyone — no account
            needed.
          </p>
        </article>
        <article className="landing__feature">
          <div className="landing__feature-label">03 · Rich context per task</div>
          <h3 className="landing__feature-title">More than a title.</h3>
          <p className="landing__feature-body">
            Each task carries a link and notes alongside the title. Click
            to open the link; the notes stay attached for the deeper
            context.
          </p>
        </article>
        <article className="landing__feature">
          <div className="landing__feature-label">04 · Agent-friendly</div>
          <h3 className="landing__feature-title">Your CLI knows your stack.</h3>
          <p className="landing__feature-body">
            Mint a personal API token in your profile, then any agent or
            script can read your stacks, add tasks, complete or move them,
            even share a list — over the same REST endpoints the web app
            uses. A Claude Code skill ships in the repo so the curl
            recipes are one symlink away.
          </p>
        </article>
      </section>

      <section className="landing__vision">
        <div className="landing__vision-label">What's coming next</div>
        <h2 className="landing__vision-title">
          An AI agent that reorders your stacks for you.
        </h2>
        <div className="landing__vision-body">
          <p>
            The agent reads <em>across</em> all your stacks, sees what
            you're focused on right now, and proposes what should move up
            next. Priority as a function of context — not a static label.
          </p>
          <p>
            Every suggestion comes with an explanation. You accept,
            reject, or take pieces.
          </p>
          <p className="landing__vision-anchor">
            The way tasks are structured today is what makes the agent
            possible tomorrow.
          </p>
        </div>
      </section>

      <footer className="landing__footer">
        <div className="landing__footer-pitch">
          <h2 className="landing__footer-title">Start your first stack.</h2>
          <p className="landing__footer-body">
            Sign up takes 30 seconds. No card, no email confirmation.
          </p>
        </div>
        <div className="landing__footer-meta">
          STACK · An experiment in treating priority as a first-class data type.
        </div>
      </footer>
    </div>
  );
}
