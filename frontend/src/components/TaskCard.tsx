import { useEffect, useState } from "react";
import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { useMutation } from "@tanstack/react-query";
import { api } from "../api/client";
import { useInvalidateStacks } from "../hooks/useInvalidateStacks";
import { safeHref } from "../lib/url";
import type { Task } from "../types";
import { TaskEditModal } from "./TaskEditModal";

interface Props {
  task: Task;
  positionIndex: number;
  moveTarget: { date: string; label: string } | null;
}

function prominenceClass(idx: number): string {
  if (idx === 0) return "task--p0";
  if (idx === 1) return "task--p1";
  if (idx === 2) return "task--p2";
  if (idx === 3) return "task--p3";
  return "task--prest";
}

function formatDuration(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(totalSeconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  const pad = (n: number) => String(n).padStart(2, "0");
  return h > 0 ? `${h}:${pad(m)}:${pad(sec)}` : `${pad(m)}:${pad(sec)}`;
}

function useLiveElapsed(
  active: boolean,
  startedAt: string | null,
  accumulated: number
): number {
  const [, setTick] = useState(0);
  useEffect(() => {
    if (!active) return;
    const id = setInterval(() => setTick((t) => t + 1), 1000);
    return () => clearInterval(id);
  }, [active]);
  if (!active || !startedAt) return accumulated;
  const startMs = new Date(startedAt + "Z").getTime();
  const liveSeconds = Math.floor((Date.now() - startMs) / 1000);
  return accumulated + Math.max(0, liveSeconds);
}

function dueDateChip(due: string | null): string | null {
  if (!due) return null;
  const d = new Date(due);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const target = new Date(d);
  target.setHours(0, 0, 0, 0);
  const days = Math.round(
    (target.getTime() - today.getTime()) / (1000 * 60 * 60 * 24)
  );
  if (days === 0) return "DUE TODAY";
  if (days === 1) return "DUE TMRW";
  if (days < 0) return `DUE ${Math.abs(days)}D AGO`;
  if (days < 7) return `DUE IN ${days}D`;
  return `DUE ${d.toLocaleDateString("en-US", { month: "short", day: "numeric" }).toUpperCase()}`;
}

export function TaskCard({ task, positionIndex, moveTarget }: Props) {
  const invalidateStacks = useInvalidateStacks();
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: task.id });

  const [editing, setEditing] = useState(false);

  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  const isDone = task.status === "done";
  const isActive = task.in_progress_started_at !== null;
  const elapsed = useLiveElapsed(
    isActive,
    task.in_progress_started_at,
    task.accumulated_seconds
  );

  const toggleDone = useMutation({
    mutationFn: () =>
      api.updateTask(task.id, { status: isDone ? "pending" : "done" }),
    onSuccess: invalidateStacks,
  });

  const remove = useMutation({
    mutationFn: () => api.deleteTask(task.id),
    onSuccess: invalidateStacks,
  });

  const move = useMutation({
    mutationFn: () =>
      moveTarget
        ? api.moveTask(task.id, { stackDate: moveTarget.date })
        : Promise.reject(),
    onSuccess: invalidateStacks,
  });

  const start = useMutation({
    mutationFn: () => api.startTask(task.id),
    onSuccess: invalidateStacks,
  });

  const pause = useMutation({
    mutationFn: () => api.pauseTask(task.id),
    onSuccess: invalidateStacks,
  });

  const dueChip = dueDateChip(task.due_at);
  const totalElapsed = elapsed;
  const showTimer = isActive || task.accumulated_seconds > 0;

  return (
    <>
      <li
        ref={setNodeRef}
        style={style}
        className={[
          "task",
          prominenceClass(positionIndex),
          isDragging ? "task--dragging" : "",
          isDone ? "task--done" : "",
          isActive ? "task--active" : "",
        ]
          .filter(Boolean)
          .join(" ")}
        {...attributes}
      >
        <div
          className="task__pos"
          {...listeners}
          style={{ cursor: "grab", touchAction: "none" }}
        >
          {String(positionIndex + 1).padStart(2, "0")}
        </div>

        <div
          className="task__body"
          {...listeners}
          style={{
            cursor: safeHref(task.direct_link) ? "pointer" : "grab",
            touchAction: "none",
          }}
          onClick={() => {
            // dnd-kit suppresses click when a real drag happens (past the
            // activation distance), so we only land here on a real click.
            // safeHref drops anything that isn't http(s) — defense in depth
            // even though the backend validator should already reject it.
            const link = safeHref(task.direct_link);
            if (link) {
              window.open(link, "_blank", "noopener,noreferrer");
            } else {
              setEditing(true);
            }
          }}
        >
          <p className="task__title">
            {task.name}
            {safeHref(task.direct_link) && (
              <span className="task__link-hint" aria-hidden>
                {" ↗"}
              </span>
            )}
          </p>
          {(task.priority_hint && task.priority_hint !== "normal") ||
          dueChip ||
          showTimer ? (
            <div className="task__meta">
              {task.priority_hint && task.priority_hint !== "normal" && (
                <span className="task__chip">{task.priority_hint}</span>
              )}
              {dueChip && <span className="task__chip">{dueChip}</span>}
              {showTimer && (
                <span
                  className={`task__chip${isActive ? " task__chip--live" : ""}`}
                >
                  {isActive ? "● " : ""}
                  {formatDuration(totalElapsed)}
                </span>
              )}
            </div>
          ) : null}
        </div>

        <div className="task__actions">
          {!isDone && (
            <button
              type="button"
              className="task__icon"
              aria-label={isActive ? "Pause" : "Start"}
              onClick={() => (isActive ? pause.mutate() : start.mutate())}
            >
              {isActive ? "⏸" : "▶"}
            </button>
          )}
          {moveTarget && (
            <button
              type="button"
              className="task__icon task__icon--text"
              aria-label={`Move to ${moveTarget.label}`}
              onClick={() => move.mutate()}
              disabled={move.isPending}
            >
              → {moveTarget.label}
            </button>
          )}
          <button
            type="button"
            className={`task__check${isDone ? " task__check--checked" : ""}`}
            aria-label={isDone ? "Mark pending" : "Mark done"}
            onClick={() => toggleDone.mutate()}
          />
          <button
            type="button"
            className="task__icon task__icon--more"
            aria-label="Edit task"
            title="Edit"
            onClick={() => setEditing(true)}
          >
            ✎
          </button>
          <button
            type="button"
            className="task__x"
            aria-label="Delete task"
            onClick={() => remove.mutate()}
            disabled={remove.isPending}
          >
            ×
          </button>
        </div>
      </li>

      <TaskEditModal task={task} open={editing} onClose={() => setEditing(false)} />
    </>
  );
}
