import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { useInvalidateStacks } from "../hooks/useInvalidateStacks";
import { TOPIC_KINDS, type PriorityHint } from "../types";
import { ShareModal } from "./ShareModal";
import { StackView } from "./StackView";

interface Props {
  stackId: number;
  todayDate: string;
  onBack: () => void;
}

const HINTS: { value: PriorityHint; label: string }[] = [
  { value: "top", label: "Top" },
  { value: "high", label: "High" },
  { value: "normal", label: "Normal" },
  { value: "low", label: "Low" },
];

function kindLabel(kind: string): string {
  return TOPIC_KINDS.find((k) => k.value === kind)?.label ?? kind;
}

export function TopicStackView({ stackId, todayDate, onBack }: Props) {
  const qc = useQueryClient();
  const invalidateStacks = useInvalidateStacks();
  const { data: stack, isLoading } = useQuery({
    queryKey: ["topic-stack", stackId],
    queryFn: () => api.getTopicStack(stackId),
  });
  const [name, setName] = useState("");
  const [hint, setHint] = useState<PriorityHint>("normal");
  const [shareOpen, setShareOpen] = useState(false);

  const create = useMutation({
    mutationFn: () =>
      api.createTask({
        name: name.trim(),
        stack_id: stackId,
        priority_hint: hint,
      }),
    onSuccess: () => {
      setName("");
      setHint("normal");
      invalidateStacks();
    },
  });

  const remove = useMutation({
    mutationFn: () => api.deleteTopicStack(stackId),
    onSuccess: () => {
      qc.removeQueries({ queryKey: ["topic-stack", stackId] });
      invalidateStacks();
      onBack();
    },
  });

  if (isLoading || !stack) {
    return <div className="empty">{isLoading ? "Loading…" : "—"}</div>;
  }

  return (
    <>
      <header className="stack-head">
        <div className="stack-head__date">
          {kindLabel(stack.kind).toUpperCase()} · STACK
          {stack.is_public && (
            <span className="stack-head__badge"> · Public</span>
          )}
        </div>
        <div className="topics__head">
          <h1 className="stack-head__title">{stack.name}</h1>
          <div className="topics__head-actions">
            <button type="button" onClick={onBack}>
              ← All stacks
            </button>
            <button type="button" onClick={() => setShareOpen(true)}>
              {stack.is_public ? "Public ↗" : "Share"}
            </button>
            <button
              type="button"
              className="modal__danger"
              onClick={() => {
                if (
                  window.confirm(
                    `Delete the "${stack.name}" stack and all its items?`
                  )
                ) {
                  remove.mutate();
                }
              }}
            >
              Delete
            </button>
          </div>
        </div>
      </header>

      <ShareModal
        stack={stack}
        open={shareOpen}
        onClose={() => setShareOpen(false)}
      />

      <form
        className="qc"
        onSubmit={(e) => {
          e.preventDefault();
          if (!name.trim() || create.isPending) return;
          create.mutate();
        }}
      >
        <div className="qc__input-wrap">
          <button
            type="submit"
            className="qc__plus"
            disabled={!name.trim() || create.isPending}
            aria-label="Add item"
          >
            + Add
          </button>
          <input
            className="qc__input"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={`add to ${stack.name}…`}
            autoFocus
          />
        </div>
        <div className="qc__hints" role="radiogroup" aria-label="Priority hint">
          {HINTS.map((h) => (
            <button
              key={h.value}
              type="button"
              role="radio"
              aria-checked={hint === h.value}
              className={`qc__hint${hint === h.value ? " qc__hint--active" : ""}`}
              onClick={() => setHint(h.value)}
            >
              {h.label}
            </button>
          ))}
        </div>
      </form>

      <StackView
        tasks={stack.tasks}
        stackRef={{ stackId }}
        // From a topic stack, the "move" action pulls into today's daily.
        moveTarget={{ date: todayDate, label: "TODAY" }}
      />
    </>
  );
}
