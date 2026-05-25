import { useEffect } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { useInvalidateStacks } from "../hooks/useInvalidateStacks";
import { formatMinutes } from "../lib/format";
import { TOPIC_KINDS, type Stack, type StackKind, type Task } from "../types";

interface Props {
  open: boolean;
  /** ISO date (YYYY-MM-DD) of the daily stack being pulled into. */
  targetDate: string;
  /** Short label rendered in the section header — e.g. "TODAY". */
  targetLabel: string;
  onClose: () => void;
}

function isActive(t: Task): boolean {
  return t.status === "pending" || t.status === "in_progress";
}

/**
 * Pull tasks out of topic stacks (Reading, Watching, Interview Prep, …)
 * into a daily stack. The whole point of topic stacks is to keep a backlog
 * separate from "today" — this modal is how you promote items.
 *
 * Stays open after each pull so the user can grab a handful in one sitting.
 * Pulled tasks disappear from the list (cache invalidated) so it's clear
 * what's still up for grabs.
 */
export function PullFromStackModal({
  open,
  targetDate,
  targetLabel,
  onClose,
}: Props) {
  const invalidateStacks = useInvalidateStacks();

  const { data, isLoading } = useQuery({
    queryKey: ["topic-stacks"],
    queryFn: () => api.listTopicStacks(),
    enabled: open,
    // Fresh fetch each open so a task moved/added elsewhere is reflected.
    staleTime: 0,
  });

  const pull = useMutation({
    mutationFn: (taskId: number) =>
      api.moveTask(taskId, { stackDate: targetDate }),
    onSuccess: () => invalidateStacks(),
  });

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  // Group stacks by kind, drop ones whose active task count is zero.
  const visibleStacks: Stack[] = (data ?? [])
    .map((s) => ({ ...s, tasks: s.tasks.filter(isActive) }))
    .filter((s) => s.tasks.length > 0);

  const byKind = new Map<StackKind, Stack[]>();
  for (const s of visibleStacks) {
    if (!byKind.has(s.kind)) byKind.set(s.kind, []);
    byKind.get(s.kind)!.push(s);
  }

  return (
    <div
      className="modal-backdrop"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="modal modal--pull" role="dialog" aria-modal="true">
        <div className="modal__head">
          <span className="modal__eyebrow">
            Pull into {targetLabel.toUpperCase()}
          </span>
          <button
            type="button"
            className="modal__close"
            aria-label="Close"
            onClick={onClose}
          >
            ×
          </button>
        </div>

        <div className="modal__form pull">
          <p className="profile__hint">
            Click a task to move it into your{" "}
            {targetLabel.toLowerCase()} stack. It'll leave its topic stack and
            join {targetLabel.toLowerCase()}'s queue at the end.
          </p>

          {isLoading && <div className="pull__empty">Loading…</div>}

          {!isLoading && visibleStacks.length === 0 && (
            <div className="pull__empty">
              — no items waiting in any topic stack. Add some from the
              Stacks tab first.
            </div>
          )}

          {TOPIC_KINDS.map((k) => {
            const stacks = byKind.get(k.value) ?? [];
            if (stacks.length === 0) return null;
            return (
              <section key={k.value} className="pull__kind">
                <h3 className="pull__kind-label">{k.label}</h3>
                {stacks.map((s) => (
                  <div key={s.id} className="pull__stack">
                    <div className="pull__stack-name">{s.name}</div>
                    <ul className="pull__tasks">
                      {s.tasks.map((t) => {
                        const pulling =
                          pull.isPending && pull.variables === t.id;
                        return (
                          <li key={t.id}>
                            <button
                              type="button"
                              className="pull__task"
                              onClick={() => pull.mutate(t.id)}
                              disabled={pulling}
                            >
                              <span className="pull__task-name">{t.name}</span>
                              {t.estimate_minutes ? (
                                <span className="pull__task-meta">
                                  ~{formatMinutes(t.estimate_minutes)}
                                </span>
                              ) : null}
                              <span className="pull__task-arrow" aria-hidden>
                                {pulling ? "…" : `→ ${targetLabel}`}
                              </span>
                            </button>
                          </li>
                        );
                      })}
                    </ul>
                  </div>
                ))}
              </section>
            );
          })}
        </div>
      </div>
    </div>
  );
}
