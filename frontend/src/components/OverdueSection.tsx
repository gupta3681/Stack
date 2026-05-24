import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { useInvalidateStacks } from "../hooks/useInvalidateStacks";
import type { Task } from "../types";

interface Props {
  todayDate: string;
}

export function OverdueSection({ todayDate }: Props) {
  const invalidateStacks = useInvalidateStacks();
  const { data } = useQuery({
    queryKey: ["overdue", todayDate],
    queryFn: () => api.getOverdue(todayDate),
  });

  const pull = useMutation({
    mutationFn: (id: number) => api.moveTask(id, { stackDate: todayDate }),
    onSuccess: () => invalidateStacks(),
  });

  // Dismiss = "I'm not doing this." Sets status=cancelled so the task drops
  // out of the overdue query (which filters to pending/in_progress only)
  // without claiming you completed it. The task row is preserved.
  const dismiss = useMutation({
    mutationFn: (id: number) =>
      api.updateTask(id, { status: "cancelled" }),
    onSuccess: () => invalidateStacks(),
  });

  const tasks = (data ?? []) as Task[];
  if (tasks.length === 0) return null;

  return (
    <section className="section">
      <h2 className="section__title">
        Overdue · {tasks.length} {tasks.length === 1 ? "item" : "items"}
      </h2>
      <ul className="tasks" style={{ borderTop: "none" }}>
        {tasks.map((t) => (
          <li key={t.id} className="overdue-task">
            <p className="overdue-task__title">{t.name}</p>
            <span className="overdue-task__date">
              from {formatShort(t.stack_id)}
            </span>
            <div className="overdue-task__actions">
              <button
                type="button"
                onClick={() => pull.mutate(t.id)}
                disabled={pull.isPending}
              >
                Pull to today
              </button>
              <button
                type="button"
                onClick={() => dismiss.mutate(t.id)}
                disabled={dismiss.isPending}
                aria-label={`Dismiss ${t.name}`}
              >
                Dismiss
              </button>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

function formatShort(_: number | null): string {
  return "earlier";
}
