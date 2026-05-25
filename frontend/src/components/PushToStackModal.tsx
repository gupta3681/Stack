import { useEffect } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { useInvalidateStacks } from "../hooks/useInvalidateStacks";
import { TOPIC_KINDS, type Stack, type StackKind } from "../types";

interface Props {
  open: boolean;
  /** The task being pushed. We need the id (to move) and the name (for the
   * dialog header copy). */
  taskId: number;
  taskName: string;
  onClose: () => void;
}

/**
 * Send a task currently in a daily stack into a topic stack. The natural
 * companion to PullFromStackModal — pull "Read X" into today, then if you
 * don't finish, push it back to "Reading: Books 2026" (or anywhere else).
 *
 * One-shot: each pick closes the modal. Unlike Pull (which is "grab several"),
 * a push is a single deliberate decision about where this one task belongs.
 */
export function PushToStackModal({
  open,
  taskId,
  taskName,
  onClose,
}: Props) {
  const invalidateStacks = useInvalidateStacks();

  const { data, isLoading } = useQuery({
    queryKey: ["topic-stacks"],
    queryFn: () => api.listTopicStacks(),
    enabled: open,
    staleTime: 0,
  });

  const push = useMutation({
    mutationFn: (stackId: number) => api.moveTask(taskId, { stackId }),
    onSuccess: () => {
      invalidateStacks();
      onClose();
    },
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

  const stacks = data ?? [];
  const byKind = new Map<StackKind, Stack[]>();
  for (const s of stacks) {
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
          <span className="modal__eyebrow">Push to a stack</span>
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
            Move <strong>"{taskName}"</strong> off this daily stack and into
            a topic stack. Useful if you didn't get to it today and want to
            send it back to its original list (or somewhere new).
          </p>

          {isLoading && <div className="pull__empty">Loading…</div>}

          {!isLoading && stacks.length === 0 && (
            <div className="pull__empty">
              — no topic stacks yet. Create one from the Stacks tab.
            </div>
          )}

          {TOPIC_KINDS.map((k) => {
            const list = byKind.get(k.value) ?? [];
            if (list.length === 0) return null;
            return (
              <section key={k.value} className="pull__kind">
                <h3 className="pull__kind-label">{k.label}</h3>
                <ul className="pull__tasks">
                  {list.map((s) => {
                    const pending =
                      push.isPending && push.variables === s.id;
                    return (
                      <li key={s.id}>
                        <button
                          type="button"
                          className="pull__task"
                          onClick={() => push.mutate(s.id!)}
                          disabled={pending || push.isPending}
                        >
                          <span className="pull__task-name">{s.name}</span>
                          <span className="pull__task-meta">
                            {s.tasks.length}{" "}
                            {s.tasks.length === 1 ? "item" : "items"}
                          </span>
                          <span className="pull__task-arrow" aria-hidden>
                            {pending ? "…" : "→"}
                          </span>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              </section>
            );
          })}
        </div>
      </div>
    </div>
  );
}
