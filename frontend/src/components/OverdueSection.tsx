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
            <p className="overdue-task__title">{t.title}</p>
            <span className="overdue-task__date">
              from {formatShort(t.stack_id)}
            </span>
            <button type="button" onClick={() => pull.mutate(t.id)}>
              Pull to today
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

function formatShort(_: number | null): string {
  return "earlier";
}
