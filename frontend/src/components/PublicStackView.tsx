import { useQuery } from "@tanstack/react-query";
import { ApiError, api } from "../api/client";
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
            {stack.tasks.map((t, i) => (
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
                  <p className="task__title">{t.title}</p>
                  {t.description && (
                    <p className="task__desc">{t.description}</p>
                  )}
                  {priorityChipLabel(t.priority_hint) && (
                    <div className="task__meta">
                      <span className="task__chip">
                        {priorityChipLabel(t.priority_hint)}
                      </span>
                    </div>
                  )}
                </div>
              </li>
            ))}
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
