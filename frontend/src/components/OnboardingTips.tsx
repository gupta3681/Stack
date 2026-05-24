import { useMutation } from "@tanstack/react-query";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";

/**
 * Lightweight first-run tips card. No tour library, no spotlight overlay —
 * just a Mono-styled block above the day's stack with the key affordances
 * the user might miss. Dismissed permanently via POST /auth/me/onboarded.
 */
export function OnboardingTips() {
  const { user, refresh } = useAuth();

  const dismiss = useMutation({
    mutationFn: () => api.completeOnboarding(),
    onSuccess: () => refresh(),
  });

  if (!user || user.onboarded) return null;

  return (
    <aside className="onboarding" aria-label="Quick tips">
      <div className="onboarding__eyebrow">Welcome to Stack</div>
      <h2 className="onboarding__title">A few things to know</h2>
      <ul className="onboarding__tips">
        <li>
          <span className="onboarding__key">01</span>
          <span>
            Drag a card by its <strong>position number</strong> to reorder —
            the top of the stack is what you're doing next.
          </span>
        </li>
        <li>
          <span className="onboarding__key">✎</span>
          <span>
            Click <strong>✎</strong> on any task to edit its title, direct
            link, markdown notes, due date, or priority.
          </span>
        </li>
        <li>
          <span className="onboarding__key">→</span>
          <span>
            <strong>→ TMRW</strong> bumps a task to tomorrow's stack — clear
            today's deck without losing the item.
          </span>
        </li>
        <li>
          <span className="onboarding__key">▶</span>
          <span>
            Hit <strong>▶</strong> to start a live timer on a task. It keeps
            counting until you pause or mark it done.
          </span>
        </li>
        <li>
          <span className="onboarding__key">⌗</span>
          <span>
            Use <strong>Stacks</strong> in the top nav for evergreen lists
            (Reading, Watching, etc.). Pull items into today when you're
            ready to work on them.
          </span>
        </li>
      </ul>
      <div className="onboarding__actions">
        <button
          type="button"
          onClick={() => dismiss.mutate()}
          disabled={dismiss.isPending}
        >
          {dismiss.isPending ? "Hiding…" : "Got it, hide this"}
        </button>
      </div>
    </aside>
  );
}
