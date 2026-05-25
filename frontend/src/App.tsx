import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ApiError, api } from "./api/client";
import { useAuth } from "./auth/AuthContext";
import { LandingPage } from "./auth/LandingPage";
import { ProfileModal } from "./auth/ProfileModal";
import { StackHeader } from "./components/StackHeader";
import { QuickCapture } from "./components/QuickCapture";
import { StackView } from "./components/StackView";
import { OverdueSection } from "./components/OverdueSection";
import { OnboardingTips } from "./components/OnboardingTips";
import { PublicStackView } from "./components/PublicStackView";
import { PullFromStackModal } from "./components/PullFromStackModal";
import { TopicStackList } from "./components/TopicStackList";
import { TopicStackView } from "./components/TopicStackView";

type View =
  | { kind: "today" }
  | { kind: "tomorrow" }
  | { kind: "stacks-list" }
  | { kind: "stacks-detail"; stackId: number };

function todayISO(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function tomorrowISO(): string {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function AuthedApp() {
  const { user, logout } = useAuth();
  const [view, setView] = useState<View>({ kind: "today" });
  const [profileOpen, setProfileOpen] = useState(false);

  // Recompute on every render — no useMemo freeze. Crossing midnight (or any
  // re-render after the wall clock advances) picks up the new date naturally.
  const dates = { today: todayISO(), tomorrow: tomorrowISO() };

  const countsQuery = useQuery({
    queryKey: ["counts", dates.today],
    queryFn: () => api.getCounts(dates.today),
  });
  const counts = countsQuery.data;
  const navCount = (n: number | undefined) =>
    n === undefined ? "" : n > 0 ? ` (${n})` : "";

  return (
    <div className="app">
      <div className="topbar">
        <div className="topbar__brand">
          <svg
            className="topbar__logo"
            viewBox="0 0 32 32"
            aria-hidden="true"
          >
            <rect x="5" y="7" width="22" height="4" />
            <rect x="5" y="14" width="22" height="4" opacity="0.6" />
            <rect x="5" y="21" width="22" height="4" opacity="0.3" />
          </svg>
          <span>STACK</span>
        </div>
        <nav className="topbar__nav">
          <button
            type="button"
            className={`nav-link${view.kind === "today" ? " nav-link--active" : ""}`}
            onClick={() => setView({ kind: "today" })}
          >
            Today{navCount(counts?.today)}
          </button>
          <button
            type="button"
            className={`nav-link${view.kind === "tomorrow" ? " nav-link--active" : ""}`}
            onClick={() => setView({ kind: "tomorrow" })}
          >
            Tomorrow{navCount(counts?.tomorrow)}
          </button>
          <button
            type="button"
            className={`nav-link${view.kind === "stacks-list" || view.kind === "stacks-detail" ? " nav-link--active" : ""}`}
            onClick={() => setView({ kind: "stacks-list" })}
          >
            Stacks{navCount(counts?.topic_stacks)}
          </button>
          <span className="topbar__sep" aria-hidden>
            ·
          </span>
          <button
            type="button"
            className="topbar__user topbar__user--button"
            title={user?.email}
            onClick={() => setProfileOpen(true)}
          >
            {user?.display_name ?? user?.email}
          </button>
          <button type="button" className="nav-link" onClick={() => logout()}>
            Log out
          </button>
        </nav>
      </div>

      <ProfileModal open={profileOpen} onClose={() => setProfileOpen(false)} />

      <OnboardingTips />

      {view.kind === "today" || view.kind === "tomorrow" ? (
        <DailyStackPanel
          view={view.kind}
          today={dates.today}
          tomorrow={dates.tomorrow}
          logout={logout}
        />
      ) : view.kind === "stacks-list" ? (
        <TopicStackList
          onOpen={(stackId) => setView({ kind: "stacks-detail", stackId })}
        />
      ) : (
        <TopicStackView
          stackId={view.stackId}
          todayDate={dates.today}
          onBack={() => setView({ kind: "stacks-list" })}
        />
      )}
    </div>
  );
}

interface DailyPanelProps {
  view: "today" | "tomorrow";
  today: string;
  tomorrow: string;
  logout: () => void;
}

function DailyStackPanel({ view, today, tomorrow, logout }: DailyPanelProps) {
  const activeDate = view === "today" ? today : tomorrow;
  const activeLabel = view === "today" ? "Today" : "Tomorrow";
  const [pullOpen, setPullOpen] = useState(false);
  const stackQuery = useQuery({
    queryKey: ["stack", activeDate],
    queryFn: () => api.getStack(activeDate),
  });

  useEffect(() => {
    if (
      stackQuery.error instanceof ApiError &&
      stackQuery.error.status === 401
    ) {
      logout();
    }
  }, [stackQuery.error, logout]);

  const stack = stackQuery.data;
  if (!stack) {
    return <div className="empty">{stackQuery.isLoading ? "Loading…" : "—"}</div>;
  }

  // Sum estimates from tasks that are still on the plate. Done and
  // cancelled don't count toward "time still to spend today".
  const totalEstimateMinutes = stack.tasks.reduce((sum, t) => {
    if (t.status === "done" || t.status === "cancelled") return sum;
    return sum + (t.estimate_minutes ?? 0);
  }, 0);

  return (
    <>
      <StackHeader
        stackDate={stack.stack_date!}
        intention={stack.intention}
        label={view === "today" ? "TODAY'S STACK" : "TOMORROW'S STACK"}
        totalEstimateMinutes={totalEstimateMinutes}
      />
      <QuickCapture
        stackDate={stack.stack_date!}
        onPullClick={() => setPullOpen(true)}
      />
      <StackView
        tasks={stack.tasks}
        stackRef={{ stackDate: stack.stack_date! }}
        moveTarget={
          view === "today"
            ? { date: tomorrow, label: "TMRW" }
            : { date: today, label: "TODAY" }
        }
      />
      {view === "today" && <OverdueSection todayDate={today} />}
      <PullFromStackModal
        open={pullOpen}
        targetDate={activeDate}
        targetLabel={activeLabel}
        onClose={() => setPullOpen(false)}
      />
    </>
  );
}

/** Match /s/<slug> in the URL. Slug is the only segment we care about; we
 * don't introduce react-router for one public route. */
function getPublicSlug(): string | null {
  const m = window.location.pathname.match(/^\/s\/([A-Za-z0-9_-]+)\/?$/);
  return m ? m[1] : null;
}

export default function App() {
  const { status } = useAuth();

  // Public shared stack — bypass the auth gate entirely. No cookie needed,
  // no login flow, no AuthedApp chrome.
  const publicSlug = getPublicSlug();
  if (publicSlug) {
    return <PublicStackView slug={publicSlug} />;
  }

  if (status === "loading") {
    return <div className="boot-screen">—</div>;
  }
  if (status === "anonymous") {
    return <LandingPage />;
  }
  return <AuthedApp />;
}
