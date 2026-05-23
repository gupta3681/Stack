import { useEffect, useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { api } from "../api/client";
import { useInvalidateStacks } from "../hooks/useInvalidateStacks";
import type { PriorityHint, Task } from "../types";

interface Props {
  task: Task;
  open: boolean;
  onClose: () => void;
}

const HINTS: { value: PriorityHint; label: string }[] = [
  { value: "top", label: "Top" },
  { value: "high", label: "High" },
  { value: "normal", label: "Normal" },
  { value: "low", label: "Low" },
];

function dueInputValue(due: string | null): string {
  return due ? due.slice(0, 10) : "";
}

export function TaskEditModal({ task, open, onClose }: Props) {
  const invalidate = useInvalidateStacks();
  const dialogRef = useRef<HTMLDivElement>(null);

  const [title, setTitle] = useState(task.title);
  const [description, setDescription] = useState(task.description ?? "");
  const [due, setDue] = useState(dueInputValue(task.due_at));
  const [priority, setPriority] = useState<PriorityHint>(
    task.priority_hint ?? "normal"
  );

  // Reset drafts when a different task opens (or the same task's data refreshes
  // from the server while the modal isn't open).
  useEffect(() => {
    if (!open) return;
    setTitle(task.title);
    setDescription(task.description ?? "");
    setDue(dueInputValue(task.due_at));
    setPriority(task.priority_hint ?? "normal");
  }, [open, task.id, task.title, task.description, task.due_at, task.priority_hint]);

  // Escape closes; auto-focus title input on open.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    const t = setTimeout(() => {
      dialogRef.current?.querySelector<HTMLInputElement>(".modal__title-input")?.focus();
    }, 30);
    return () => {
      window.removeEventListener("keydown", onKey);
      clearTimeout(t);
    };
  }, [open, onClose]);

  const save = useMutation({
    mutationFn: () =>
      api.updateTask(task.id, {
        title: title.trim() || task.title,
        // null clears the field (server respects null via exclude_unset semantics).
        description: description.trim() ? description.trim() : null,
        due_at: due ? `${due}T23:59:00` : null,
        priority_hint: priority,
      }),
    onSuccess: () => {
      invalidate();
      onClose();
    },
  });

  const remove = useMutation({
    mutationFn: () => api.deleteTask(task.id),
    onSuccess: () => {
      invalidate();
      onClose();
    },
  });

  if (!open) return null;

  return (
    <div
      className="modal-backdrop"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={dialogRef}
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-label="Edit task"
      >
        <div className="modal__head">
          <span className="modal__eyebrow">Edit task</span>
          <button
            type="button"
            className="modal__close"
            aria-label="Close"
            onClick={onClose}
          >
            ×
          </button>
        </div>

        <form
          className="modal__form"
          onSubmit={(e) => {
            e.preventDefault();
            if (!save.isPending) save.mutate();
          }}
        >
          <label className="modal__field">
            <span className="modal__label">Title</span>
            <input
              className="modal__title-input"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
            />
          </label>

          <label className="modal__field">
            <span className="modal__label">Description</span>
            <textarea
              rows={4}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="(optional)"
            />
          </label>

          <div className="modal__row">
            <label className="modal__field modal__field--inline">
              <span className="modal__label">Due</span>
              <input
                type="date"
                value={due}
                onChange={(e) => setDue(e.target.value)}
              />
            </label>
            {due && (
              <button
                type="button"
                className="modal__inline-clear"
                onClick={() => setDue("")}
                aria-label="Clear due date"
              >
                clear
              </button>
            )}
          </div>

          <fieldset className="modal__field">
            <span className="modal__label">Priority hint</span>
            <div className="modal__hints">
              {HINTS.map((h) => (
                <button
                  key={h.value}
                  type="button"
                  className={`qc__hint${priority === h.value ? " qc__hint--active" : ""}`}
                  onClick={() => setPriority(h.value)}
                  aria-pressed={priority === h.value}
                >
                  {h.label}
                </button>
              ))}
            </div>
          </fieldset>

          <div className="modal__actions">
            <button
              type="button"
              className="modal__danger"
              onClick={() => {
                if (window.confirm("Delete this task?")) remove.mutate();
              }}
              disabled={remove.isPending}
            >
              Delete
            </button>
            <div className="modal__actions-right">
              <button type="button" onClick={onClose}>
                Cancel
              </button>
              <button type="submit" disabled={save.isPending}>
                {save.isPending ? "Saving…" : "Save"}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}
