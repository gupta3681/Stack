import { useQuery } from "@tanstack/react-query";
import { ApiError, api } from "../api/client";
import { TOPIC_KINDS } from "../types";

/**
 * Admin analytics view. Renders snapshot stat cards (users / tasks / stacks /
 * api tokens) plus the full users table. Read-only — destructive admin
 * actions live behind separate UI (and don't exist yet).
 *
 * Visibility is gated upstream: the App router only routes here when
 * `user.is_admin`. If a non-admin still hits the page somehow, the
 * underlying queries return 403 and we render a clear message.
 */
export function AdminPanel() {
  const statsQuery = useQuery({
    queryKey: ["admin-stats"],
    queryFn: () => api.getAdminStats(),
    // Admin data changes constantly (new signups, completions). Reload on
    // mount + focus.
    staleTime: 0,
  });
  const usersQuery = useQuery({
    queryKey: ["admin-users"],
    queryFn: () => api.listAdminUsers(),
    staleTime: 0,
  });

  const forbidden =
    (statsQuery.error instanceof ApiError && statsQuery.error.status === 403) ||
    (usersQuery.error instanceof ApiError && usersQuery.error.status === 403);

  if (forbidden) {
    return (
      <div className="admin">
        <header className="stack-head">
          <div className="stack-head__date">ADMIN</div>
          <h1 className="stack-head__title">No access</h1>
        </header>
        <div className="empty">
          Your account doesn't have admin privileges. If this is wrong, ask
          the server operator to add your email to <code>ADMIN_EMAILS</code>{" "}
          and log out + back in.
        </div>
      </div>
    );
  }

  const stats = statsQuery.data;
  const users = usersQuery.data;

  return (
    <div className="admin">
      <header className="stack-head">
        <div className="stack-head__date">
          ADMIN
          {stats && (
            <span className="stack-head__total">
              {" · "}
              {new Date(stats.generated_at + "Z").toLocaleString()}
            </span>
          )}
        </div>
        <h1 className="stack-head__title">Snapshot</h1>
      </header>

      {statsQuery.isLoading && <div className="empty">Loading…</div>}

      {stats && (
        <>
          <section className="admin__section">
            <h2 className="admin__section-title">Users</h2>
            <div className="admin__cards">
              <Stat label="Total" value={stats.users.total} />
              <Stat label="Active 7d" value={stats.users.active_last_7d} />
              <Stat label="Active 30d" value={stats.users.active_last_30d} />
              <Stat label="Admins" value={stats.users.admin_count} />
            </div>
          </section>

          <section className="admin__section">
            <h2 className="admin__section-title">Tasks</h2>
            <div className="admin__cards">
              <Stat label="Total" value={stats.tasks.total} />
              <Stat label="Pending" value={stats.tasks.pending} />
              <Stat label="In progress" value={stats.tasks.in_progress} />
              <Stat label="Done" value={stats.tasks.done} />
              <Stat label="Cancelled" value={stats.tasks.cancelled} />
              <Stat
                label="Completed today"
                value={stats.tasks.completed_today}
              />
              <Stat
                label="Completed 7d"
                value={stats.tasks.completed_last_7d}
              />
            </div>
          </section>

          <section className="admin__section">
            <h2 className="admin__section-title">Topic stacks</h2>
            <div className="admin__cards">
              <Stat label="Total" value={stats.stacks.topic_total} />
              <Stat label="Public" value={stats.stacks.public_count} />
              {TOPIC_KINDS.map((k) => (
                <Stat
                  key={k.value}
                  label={k.label}
                  value={stats.stacks.by_kind[k.value] ?? 0}
                />
              ))}
            </div>
          </section>

          <section className="admin__section">
            <h2 className="admin__section-title">API tokens</h2>
            <div className="admin__cards">
              <Stat label="Total" value={stats.api_tokens.total} />
              <Stat
                label="Used 7d"
                value={stats.api_tokens.used_last_7d}
              />
            </div>
          </section>

          {stats.recent_signups.length > 0 && (
            <section className="admin__section">
              <h2 className="admin__section-title">Recent signups</h2>
              <ul className="admin__list">
                {stats.recent_signups.map((u) => (
                  <li key={u.id} className="admin__list-row">
                    <span className="admin__list-name">
                      {u.display_name || u.email}
                    </span>
                    {u.display_name && (
                      <span className="admin__list-meta">{u.email}</span>
                    )}
                    <span className="admin__list-meta">
                      {formatStamp(u.created_at)}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </>
      )}

      <section className="admin__section">
        <h2 className="admin__section-title">All users</h2>
        {usersQuery.isLoading && <div className="empty">Loading…</div>}
        {users && users.length === 0 && (
          <div className="empty">— no users yet —</div>
        )}
        {users && users.length > 0 && (
          <div className="admin__table-wrap">
            <table className="admin__table">
              <thead>
                <tr>
                  <th>Email</th>
                  <th>Name</th>
                  <th className="admin__num">Tasks</th>
                  <th>Signed up</th>
                  <th>Last session</th>
                  <th>Admin</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id}>
                    <td>{u.email}</td>
                    <td>{u.display_name || "—"}</td>
                    <td className="admin__num">{u.task_count}</td>
                    <td>{formatStamp(u.created_at)}</td>
                    <td>{formatStamp(u.last_session_at)}</td>
                    <td>{u.is_admin ? "✓" : ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

interface StatProps {
  label: string;
  value: number;
}

function Stat({ label, value }: StatProps) {
  return (
    <div className="admin__stat">
      <div className="admin__stat-value">{value.toLocaleString()}</div>
      <div className="admin__stat-label">{label}</div>
    </div>
  );
}

function formatStamp(iso: string | null): string {
  if (!iso) return "—";
  // Postgres/SQLite naive datetimes — append Z only when not already
  // timezone-marked. Same pattern as ProfileModal.formatTokenDate.
  const hasTzSuffix = /(Z|[+-]\d{2}:?\d{2})$/.test(iso);
  const d = new Date(hasTzSuffix ? iso : iso + "Z");
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}
