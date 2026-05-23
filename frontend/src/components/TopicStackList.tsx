import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { TOPIC_KINDS, type CreateTopicStackInput, type Stack, type StackKind } from "../types";

interface Props {
  onOpen: (stackId: number) => void;
}

export function TopicStackList({ onOpen }: Props) {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["topic-stacks"],
    queryFn: api.listTopicStacks,
  });
  const [creating, setCreating] = useState(false);

  const create = useMutation({
    mutationFn: (input: CreateTopicStackInput) => api.createTopicStack(input),
    onSuccess: () => {
      setCreating(false);
      qc.invalidateQueries({ queryKey: ["topic-stacks"] });
    },
  });

  const stacks = data ?? [];

  // Group by kind for browsability.
  const byKind = new Map<StackKind, Stack[]>();
  for (const s of stacks) {
    if (!byKind.has(s.kind)) byKind.set(s.kind, []);
    byKind.get(s.kind)!.push(s);
  }

  return (
    <div className="topics">
      <div className="topics__head">
        <div>
          <div className="stack-head__date">YOUR STACKS</div>
          <h1 className="stack-head__title">All Stacks</h1>
        </div>
        <button type="button" onClick={() => setCreating(true)}>
          + New Stack
        </button>
      </div>

      {isLoading ? (
        <div className="empty">Loading…</div>
      ) : stacks.length === 0 ? (
        <div className="empty">
          — no topic stacks yet. Create one to start collecting items by theme.
        </div>
      ) : (
        <div className="topics__list">
          {TOPIC_KINDS.map((k) => {
            const items = byKind.get(k.value) ?? [];
            if (items.length === 0) return null;
            return (
              <section key={k.value} className="topics__group">
                <h2 className="section__title">{k.label}</h2>
                <ul className="topics__items">
                  {items.map((s) => (
                    <li
                      key={s.id}
                      className="topics__item"
                      onClick={() => onOpen(s.id!)}
                    >
                      <span className="topics__item-name">{s.name}</span>
                      <span className="topics__item-count">
                        {s.tasks.length}{" "}
                        {s.tasks.length === 1 ? "item" : "items"}
                      </span>
                    </li>
                  ))}
                </ul>
              </section>
            );
          })}
        </div>
      )}

      {creating && (
        <CreateTopicStackModal
          onCancel={() => setCreating(false)}
          onSubmit={(input) => create.mutate(input)}
          pending={create.isPending}
        />
      )}
    </div>
  );
}

interface CreateProps {
  onCancel: () => void;
  onSubmit: (input: CreateTopicStackInput) => void;
  pending: boolean;
}

function CreateTopicStackModal({ onCancel, onSubmit, pending }: CreateProps) {
  const [kind, setKind] = useState<Exclude<StackKind, "daily">>("reading");
  const [name, setName] = useState("");

  return (
    <div
      className="modal-backdrop"
      onClick={(e) => {
        if (e.target === e.currentTarget) onCancel();
      }}
    >
      <div className="modal" role="dialog" aria-modal="true">
        <div className="modal__head">
          <span className="modal__eyebrow">New stack</span>
          <button
            type="button"
            className="modal__close"
            aria-label="Close"
            onClick={onCancel}
          >
            ×
          </button>
        </div>
        <form
          className="modal__form"
          onSubmit={(e) => {
            e.preventDefault();
            if (!name.trim() || pending) return;
            onSubmit({ kind, name: name.trim() });
          }}
        >
          <fieldset className="modal__field">
            <span className="modal__label">Kind</span>
            <div className="modal__hints">
              {TOPIC_KINDS.map((k) => (
                <button
                  key={k.value}
                  type="button"
                  className={`qc__hint${kind === k.value ? " qc__hint--active" : ""}`}
                  onClick={() => setKind(k.value)}
                  aria-pressed={kind === k.value}
                >
                  {k.label}
                </button>
              ))}
            </div>
          </fieldset>

          <label className="modal__field">
            <span className="modal__label">Name</span>
            <input
              className="modal__title-input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={
                kind === "reading"
                  ? "e.g. Sci-Fi novels"
                  : kind === "watching"
                    ? "e.g. Foreign films"
                    : "give this stack a name"
              }
              required
              autoFocus
            />
          </label>

          <div className="modal__actions">
            <div />
            <div className="modal__actions-right">
              <button type="button" onClick={onCancel}>
                Cancel
              </button>
              <button type="submit" disabled={!name.trim() || pending}>
                {pending ? "Creating…" : "Create"}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}
