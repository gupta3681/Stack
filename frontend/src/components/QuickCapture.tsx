import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { api } from "../api/client";
import { useInvalidateStacks } from "../hooks/useInvalidateStacks";
import type { PriorityHint } from "../types";

interface Props {
  stackDate: string;
}

const HINTS: { value: PriorityHint; label: string }[] = [
  { value: "top", label: "Top" },
  { value: "high", label: "High" },
  { value: "normal", label: "Normal" },
  { value: "low", label: "Low" },
];

export function QuickCapture({ stackDate }: Props) {
  const invalidateStacks = useInvalidateStacks();
  const [title, setTitle] = useState("");
  const [hint, setHint] = useState<PriorityHint>("normal");

  const create = useMutation({
    mutationFn: () =>
      api.createTask({
        title: title.trim(),
        stack_date: stackDate,
        priority_hint: hint,
      }),
    onSuccess: () => {
      setTitle("");
      setHint("normal");
      invalidateStacks();
    },
  });

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || create.isPending) return;
    create.mutate();
  };

  return (
    <form className="qc" onSubmit={submit}>
      <div className="qc__input-wrap">
        <button
          type="submit"
          className="qc__plus"
          disabled={!title.trim() || create.isPending}
          aria-label="Add task"
        >
          + Add
        </button>
        <input
          className="qc__input"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="what's next on the stack?"
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
  );
}
