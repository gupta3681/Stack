import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api } from "../api/client";
import { useInvalidateStacks } from "../hooks/useInvalidateStacks";
import {
  parseMd,
  serializeMd,
  type KnownFrontmatterKey,
} from "../lib/markdown";
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

/**
 * Build the starting markdown for the modal. If the task already has
 * context_md, sync any missing frontmatter from the structured columns
 * (name, direct_link). Otherwise seed from columns alone.
 */
function initialMd(task: Task): string {
  const existing = task.context_md ?? "";
  if (existing) {
    const p = parseMd(existing);
    const merged: Record<string, string> = { ...p.fields };
    if (!merged.name && task.name) merged.name = task.name;
    if (!merged.direct_link && task.direct_link)
      merged.direct_link = task.direct_link;
    return serializeMd({ fields: merged, body: p.body });
  }
  const seed: Record<string, string> = {};
  if (task.name) seed.name = task.name;
  if (task.direct_link) seed.direct_link = task.direct_link;
  return serializeMd({ fields: seed, body: "" });
}

function dueInputValue(due: string | null): string {
  return due ? due.slice(0, 10) : "";
}

export function TaskEditModal({ task, open, onClose }: Props) {
  const invalidate = useInvalidateStacks();
  const dialogRef = useRef<HTMLDivElement>(null);

  const [contextMd, setContextMd] = useState<string>(() => initialMd(task));
  const [contextMode, setContextMode] = useState<"write" | "preview">("write");
  const [due, setDue] = useState(dueInputValue(task.due_at));
  const [priority, setPriority] = useState<PriorityHint>(
    task.priority_hint ?? "normal"
  );

  // The markdown is the source of truth. The three input fields are
  // derived from the parsed frontmatter; editing them rewrites the
  // markdown via setField below.
  const parsed = useMemo(() => parseMd(contextMd), [contextMd]);

  const setField = (key: KnownFrontmatterKey, value: string) => {
    const next: Record<string, string> = { ...parsed.fields };
    if (value) next[key] = value;
    else delete next[key];
    setContextMd(serializeMd({ fields: next, body: parsed.body }));
  };

  useEffect(() => {
    if (!open) return;
    setContextMd(initialMd(task));
    setContextMode("write");
    setDue(dueInputValue(task.due_at));
    setPriority(task.priority_hint ?? "normal");
  }, [
    open,
    task.id,
    task.name,
    task.direct_link,
    task.context_md,
    task.due_at,
    task.priority_hint,
  ]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    const t = setTimeout(() => {
      dialogRef.current
        ?.querySelector<HTMLInputElement>(".modal__title-input")
        ?.focus();
    }, 30);
    return () => {
      window.removeEventListener("keydown", onKey);
      clearTimeout(t);
    };
  }, [open, onClose]);

  const save = useMutation({
    mutationFn: () => {
      // On save, the markdown is canonical: pull name/direct_link out
      // of its frontmatter and send them as the structured columns too,
      // so list views (which don't parse markdown) stay current.
      const p = parseMd(contextMd);
      const fmName = p.fields.name?.trim();
      const fmLink = p.fields.direct_link?.trim();
      return api.updateTask(task.id, {
        name: fmName || task.name,
        direct_link: fmLink || null,
        context_md: contextMd.trim() ? contextMd : null,
        due_at: due ? `${due}T23:59:00` : null,
        priority_hint: priority,
      });
    },
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

  const nameValue = parsed.fields.name ?? "";
  const linkValue = parsed.fields.direct_link ?? "";
  const descriptionValue = parsed.fields.description ?? "";

  return (
    <div
      className="modal-backdrop"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={dialogRef}
        className="modal modal--wide"
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
            <span className="modal__label">Name</span>
            <input
              className="modal__title-input"
              value={nameValue}
              onChange={(e) => setField("name", e.target.value)}
              required
            />
          </label>

          <label className="modal__field">
            <span className="modal__label">Direct link</span>
            <input
              type="url"
              value={linkValue}
              onChange={(e) => setField("direct_link", e.target.value)}
              placeholder="https://… (clicking the task opens this)"
              inputMode="url"
              autoComplete="off"
              spellCheck={false}
            />
          </label>

          <label className="modal__field">
            <span className="modal__label">Description</span>
            <input
              value={descriptionValue}
              onChange={(e) => setField("description", e.target.value)}
              placeholder="one-line summary (shown in the frontmatter)"
            />
          </label>

          <fieldset className="modal__field">
            <div className="modal__context-head">
              <span className="modal__label">Context (markdown)</span>
              <div className="modal__tabs" role="tablist">
                <button
                  type="button"
                  role="tab"
                  aria-selected={contextMode === "write"}
                  className={`modal__tab${contextMode === "write" ? " modal__tab--active" : ""}`}
                  onClick={() => setContextMode("write")}
                >
                  WRITE
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={contextMode === "preview"}
                  className={`modal__tab${contextMode === "preview" ? " modal__tab--active" : ""}`}
                  onClick={() => setContextMode("preview")}
                >
                  PREVIEW
                </button>
              </div>
            </div>
            {contextMode === "write" ? (
              <textarea
                rows={12}
                value={contextMd}
                onChange={(e) => setContextMd(e.target.value)}
                placeholder={
                  "Why I want to read this, how I found it, what to look for…\n\n(The frontmatter at the top stays in sync with the inputs above.)"
                }
                className="modal__md-textarea"
                spellCheck={true}
              />
            ) : (
              <div className="modal__md-preview">
                {contextMd.trim() ? (
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {contextMd}
                  </ReactMarkdown>
                ) : (
                  <span className="modal__md-empty">nothing to preview</span>
                )}
              </div>
            )}
          </fieldset>

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
