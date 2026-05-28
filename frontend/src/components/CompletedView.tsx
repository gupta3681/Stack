import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { formatMinutes } from "../lib/format";
import { safeHref } from "../lib/url";
import { TOPIC_KINDS, type CompletedTask, type StackKind } from "../types";
import { TaskEditModal } from "./TaskEditModal";

type KindFilter = StackKind | "all" | "backlog";
type RangeFilter = "all" | "7d" | "30d";

const KIND_LABELS: Record<StackKind, string> = {
  daily: "Daily",
  todo: "To Do",
  reading: "Reading",
  watching: "Watching",
  listening: "Listening",
  buy: "Buy",
  ideas: "Ideas",
};

// Source-chip order: Daily first, then the topic kinds in their canonical order.
const KIND_ORDER: StackKind[] = ["daily", ...TOPIC_KINDS.map((k) => k.value)];

const RANGES: [RangeFilter, string][] = [
  ["all", "All time"],
  ["7d", "7 days"],
  ["30d", "30 days"],
];

function formatDateOnly(iso: string): string {
  // iso is a plain date ("2026-05-20"); build a local Date so US timezones
  // don't shift `new Date("2026-05-20")` (UTC midnight) back a day.
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });
}

function formatCompletedAt(iso: string): string {
  // completed_at is a naive UTC datetime; append Z so it parses as UTC.
  return new Date(iso + "Z").toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function sourceLabel(t: CompletedTask): string {
  if (t.stack_id === null) return "Backlog";
  if (t.stack_kind === "daily") {
    return t.stack_date ? formatDateOnly(t.stack_date) : "Daily";
  }
  return t.stack_name ?? (t.stack_kind ? KIND_LABELS[t.stack_kind] : "Stack");
}

export function CompletedView() {
  const { data, isLoading } = useQuery({
    queryKey: ["completed"],
    queryFn: api.listCompletedTasks,
  });
  const all = data ?? [];

  const [search, setSearch] = useState("");
  const [kind, setKind] = useState<KindFilter>("all");
  const [range, setRange] = useState<RangeFilter>("all");
  const [editing, setEditing] = useState<CompletedTask | null>(null);

  // Only offer source chips for kinds (and backlog) that actually appear, so
  // the filter row reflects the user's real data instead of every possibility.
  const { kindsPresent, hasBacklog } = useMemo(() => {
    const present = new Set<StackKind>();
    let backlog = false;
    for (const t of all) {
      if (t.stack_id === null) backlog = true;
      else if (t.stack_kind) present.add(t.stack_kind);
    }
    return { kindsPresent: present, hasBacklog: backlog };
  }, [all]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    const now = Date.now();
    const windowMs =
      range === "7d"
        ? 7 * 86_400_000
        : range === "30d"
          ? 30 * 86_400_000
          : Infinity;
    return all.filter((t) => {
      if (kind === "backlog") {
        if (t.stack_id !== null) return false;
      } else if (kind !== "all" && t.stack_kind !== kind) {
        return false;
      }
      if (q) {
        const hay = `${t.name} ${t.context_md ?? ""}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      if (windowMs !== Infinity) {
        const c = t.completed_at ? new Date(t.completed_at + "Z").getTime() : 0;
        if (now - c > windowMs) return false;
      }
      return true;
    });
  }, [all, search, kind, range]);

  const totalMinutes = useMemo(
    () =>
      filtered.reduce(
        (sum, t) => sum + Math.round((t.accumulated_seconds ?? 0) / 60),
        0
      ),
    [filtered]
  );

  return (
    <div className="completed">
      <div className="topics__head">
        <div>
          <div className="stack-head__date">ARCHIVE</div>
          <h1 className="stack-head__title">Completed</h1>
        </div>
      </div>

      <div className="completed__controls">
        <input
          className="completed__search"
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search completed tasks across all stacks…"
          aria-label="Search completed tasks"
        />

        <div className="completed__filters">
          <div className="qc__hints" role="group" aria-label="Filter by source">
            <button
              type="button"
              className={`qc__hint${kind === "all" ? " qc__hint--active" : ""}`}
              onClick={() => setKind("all")}
            >
              All
            </button>
            {KIND_ORDER.filter((k) => kindsPresent.has(k)).map((k) => (
              <button
                key={k}
                type="button"
                className={`qc__hint${kind === k ? " qc__hint--active" : ""}`}
                onClick={() => setKind(k)}
              >
                {KIND_LABELS[k]}
              </button>
            ))}
            {hasBacklog && (
              <button
                type="button"
                className={`qc__hint${kind === "backlog" ? " qc__hint--active" : ""}`}
                onClick={() => setKind("backlog")}
              >
                Backlog
              </button>
            )}
          </div>

          <div className="qc__hints" role="group" aria-label="Filter by time">
            {RANGES.map(([value, label]) => (
              <button
                key={value}
                type="button"
                className={`qc__hint${range === value ? " qc__hint--active" : ""}`}
                onClick={() => setRange(value)}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {isLoading ? (
        <div className="empty">Loading…</div>
      ) : all.length === 0 ? (
        <div className="empty">— nothing completed yet.</div>
      ) : filtered.length === 0 ? (
        <div className="empty">— no matches.</div>
      ) : (
        <>
          <div className="completed__summary">
            {filtered.length} {filtered.length === 1 ? "task" : "tasks"}
            {totalMinutes > 0 && <> · {formatMinutes(totalMinutes)} tracked</>}
          </div>
          <ul className="completed__list">
            {filtered.map((t) => {
              const link = safeHref(t.direct_link);
              const minutes = Math.round((t.accumulated_seconds ?? 0) / 60);
              return (
                <li
                  key={t.id}
                  className="completed__item"
                  onClick={() => setEditing(t)}
                >
                  <div className="completed__main">
                    <span className="completed__name">{t.name}</span>
                    {link && (
                      <a
                        className="completed__link"
                        href={link}
                        target="_blank"
                        rel="noopener noreferrer"
                        onClick={(e) => e.stopPropagation()}
                        aria-label="Open link"
                      >
                        ↗
                      </a>
                    )}
                  </div>
                  <div className="completed__meta">
                    <span className="completed__source">{sourceLabel(t)}</span>
                    {minutes > 0 && (
                      <span className="task__chip">{formatMinutes(minutes)}</span>
                    )}
                    {t.completed_at && (
                      <span className="completed__date">
                        {formatCompletedAt(t.completed_at)}
                      </span>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        </>
      )}

      {editing && (
        <TaskEditModal
          task={editing}
          open
          onClose={() => setEditing(null)}
        />
      )}
    </div>
  );
}
