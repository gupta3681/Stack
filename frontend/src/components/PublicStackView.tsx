import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ApiError, api } from "../api/client";
import { parseMd } from "../lib/markdown";
import { safeHref } from "../lib/url";
import { TOPIC_KINDS, type PriorityHint } from "../types";

interface Props {
  slug: string;
}

function kindLabel(kind: string): string {
  return TOPIC_KINDS.find((k) => k.value === kind)?.label ?? kind;
}

function priorityChipLabel(hint: PriorityHint | null): string | null {
  if (!hint || hint === "normal") return null;
  return hint;
}

/**
 * Logged-out, read-only viewer for a shared topic stack. No drag handles,
 * no action buttons, no edit affordances — just the stack rendered with
 * the same Mono prominence scaling visitors will recognize from the app.
 */
export function PublicStackView({ slug }: Props) {
  const query = useQuery({
    queryKey: ["public-stack", slug],
    queryFn: () => api.getPublicStack(slug),
    retry: false,
  });

  // Per-task expand state. Context bodies can run long; visitors should
  // scan the list first and opt in to read.
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  const toggleExpanded = (i: number) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(i)) next.delete(i);
      else next.add(i);
      return next;
    });

  if (query.isLoading) {
    return <div className="boot-screen">Loading…</div>;
  }

  if (query.error) {
    const notFound =
      query.error instanceof ApiError && query.error.status === 404;
    return (
      <div className="app">
        <header className="topbar">
          <a href="/" className="topbar__brand">
            STACK
          </a>
        </header>
        <div className="public-empty">
          {notFound
            ? "This stack isn't shared, or the link is wrong."
            : "Couldn't load this stack."}
        </div>
      </div>
    );
  }

  const stack = query.data!;
  const owner = stack.owner_display_name?.trim() || "anonymous";

  return (
    <div className="app">
      <header className="topbar">
        <a href="/" className="topbar__brand">
          STACK
        </a>
        <nav className="topbar__nav">
          <a href="/" className="nav-link">
            Make your own ↗
          </a>
        </nav>
      </header>

      <header className="stack-head">
        <div className="stack-head__date">
          {kindLabel(stack.kind).toUpperCase()} · STACK
          {" · "}
          BY {owner.toUpperCase()}
        </div>
        <h1 className="stack-head__title">{stack.name}</h1>
        {stack.intention && (
          <div className="stack-head__intention">
            <span>{stack.intention}</span>
          </div>
        )}
      </header>

      {stack.tasks.length === 0 ? (
        <div className="empty">— this stack has nothing queued —</div>
      ) : (
        <>
          <div className="ondeck-label" aria-hidden>
            On top ↓
          </div>
          <ul className="tasks">
            {stack.tasks.map((t, i) => {
              // Strip frontmatter — the title and direct_link from the
              // frontmatter are already represented by the linked heading,
              // and showing `name: ...` as raw text is just noise.
              const parsed = t.context_md ? parseMd(t.context_md) : null;
              const body = parsed?.body.trim() ?? "";
              // safeHref guards against pre-validator data or any non-http(s)
              // URL that somehow slipped through.
              const link = safeHref(t.direct_link);
              const Title = link ? (
                <a
                  href={link}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="task__title-link"
                >
                  {t.name} <span aria-hidden>↗</span>
                </a>
              ) : (
                <>{t.name}</>
              );
              return (
                <li
                  key={i}
                  className={`task ${
                    i === 0
                      ? "task--p0"
                      : i === 1
                        ? "task--p1"
                        : i === 2
                          ? "task--p2"
                          : i === 3
                            ? "task--p3"
                            : "task--prest"
                  }`}
                >
                  <div className="task__pos">
                    {String(i + 1).padStart(2, "0")}
                  </div>
                  <div className="task__body">
                    <p className="task__title">{Title}</p>
                    {(body || priorityChipLabel(t.priority_hint)) && (
                      <div className="task__meta">
                        {priorityChipLabel(t.priority_hint) && (
                          <span className="task__chip">
                            {priorityChipLabel(t.priority_hint)}
                          </span>
                        )}
                        {body && (
                          <button
                            type="button"
                            className={`task__chip task__chip--toggle${
                              expanded.has(i) ? " task__chip--toggle-open" : ""
                            }`}
                            onClick={() => toggleExpanded(i)}
                            aria-expanded={expanded.has(i)}
                          >
                            {expanded.has(i) ? "Hide context ↑" : "Show context ↓"}
                          </button>
                        )}
                      </div>
                    )}
                    {body && expanded.has(i) && (
                      <div className="task__public-context">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                          {body}
                        </ReactMarkdown>
                      </div>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        </>
      )}

      <footer className="public-footer">
        <p>
          Shared from <a href="/">Stack</a> — a priority queue for what's
          next.
        </p>
      </footer>
    </div>
  );
}
