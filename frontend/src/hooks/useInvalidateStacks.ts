import { useQueryClient } from "@tanstack/react-query";

/**
 * Returns a function that invalidates every stack-related query.
 *
 * Use after any mutation that affects task content / position / status, so
 * the currently-visible stack (daily OR topic) refetches without the caller
 * having to know which view they're in.
 *
 * Query keys this matches (prefix match):
 *   ['stack', date]            — daily stack views (App.tsx)
 *   ['topic-stack', stackId]   — topic stack detail (TopicStackView)
 *   ['topic-stacks']           — topic stack list (TopicStackList)
 *   ['overdue', date]          — overdue feed (OverdueSection)
 *   ['counts', date]           — topbar nav badges
 */
export function useInvalidateStacks(): () => void {
  const qc = useQueryClient();
  return () => {
    qc.invalidateQueries({ queryKey: ["stack"] });
    qc.invalidateQueries({ queryKey: ["topic-stack"] });
    qc.invalidateQueries({ queryKey: ["topic-stacks"] });
    qc.invalidateQueries({ queryKey: ["overdue"] });
    qc.invalidateQueries({ queryKey: ["counts"] });
  };
}
