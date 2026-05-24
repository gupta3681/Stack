import { useEffect, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { api } from "../api/client";
import { useInvalidateStacks } from "../hooks/useInvalidateStacks";
import { formatMinutes } from "../lib/format";

interface Props {
  stackDate: string;
  intention: string | null;
  label: string;
  /** Sum of estimate_minutes across active (non-done/cancelled) tasks. */
  totalEstimateMinutes?: number | null;
}

function formatDate(iso: string): string {
  const [y, m, d] = iso.split("-");
  return `${y} / ${m} / ${d}`;
}

export function StackHeader({
  stackDate,
  intention,
  label,
  totalEstimateMinutes,
}: Props) {
  const invalidateStacks = useInvalidateStacks();
  const [draft, setDraft] = useState(intention ?? "");

  useEffect(() => {
    setDraft(intention ?? "");
  }, [intention, stackDate]);

  const save = useMutation({
    mutationFn: (value: string) =>
      api.updateStackIntention(stackDate, value.trim() || null),
    onSuccess: () => invalidateStacks(),
  });

  return (
    <header className="stack-head">
      <div className="stack-head__date">
        {formatDate(stackDate)}
        {totalEstimateMinutes && totalEstimateMinutes > 0 ? (
          <span className="stack-head__total">
            {" · "}
            {formatMinutes(totalEstimateMinutes)} planned
          </span>
        ) : null}
      </div>
      <h1 className="stack-head__title">{label}</h1>
      <div className="stack-head__intention">
        <input
          value={draft}
          placeholder="— set an intention for this stack"
          onChange={(e) => setDraft(e.target.value)}
          onBlur={() => {
            if ((draft.trim() || null) !== (intention ?? null)) save.mutate(draft);
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.currentTarget.blur();
            }
          }}
        />
      </div>
    </header>
  );
}
