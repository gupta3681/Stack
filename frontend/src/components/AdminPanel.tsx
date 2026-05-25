import { useQuery } from "@tanstack/react-query";
import { ApiError, api } from "../api/client";
import { TOPIC_KINDS, type AdminStats } from "../types";

/**
 * Admin analytics view. Mono-friendly visuals (no chart library — all SVG
 * inline so total control over styling + zero bundle cost):
 *
 *   - StackedBar: horizontal stacked bar of task status (pending /
 *     in_progress / done / cancelled), opacity-tiered.
 *   - HorizontalBars: per-kind topic-stack counts, side-by-side.
 *   - Sparkline: 30-day time series for signups + task completions.
 *
 * Read-only. Visibility is gated upstream (App routes here only for
 * is_admin users); the page also handles 403 if the gate slips.
 */
export function AdminPanel() {
  const statsQuery = useQuery({
    queryKey: ["admin-stats"],
    queryFn: () => api.getAdminStats(),
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
            <Sparkline
              series={stats.timeseries.signups_by_day}
              label="Signups · last 30 days"
            />
          </section>

          <section className="admin__section">
            <h2 className="admin__section-title">Tasks</h2>
            <div className="admin__cards">
              <Stat label="Total" value={stats.tasks.total} />
              <Stat
                label="Completed today"
                value={stats.tasks.completed_today}
              />
              <Stat
                label="Completed 7d"
                value={stats.tasks.completed_last_7d}
              />
            </div>
            <StatusBar tasks={stats.tasks} />
            <Sparkline
              series={stats.timeseries.completions_by_day}
              label="Completions · last 30 days"
            />
          </section>

          <section className="admin__section">
            <h2 className="admin__section-title">Topic stacks</h2>
            <div className="admin__cards">
              <Stat label="Total" value={stats.stacks.topic_total} />
              <Stat label="Public" value={stats.stacks.public_count} />
            </div>
            <KindBars byKind={stats.stacks.by_kind} />
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

// ── Stat card ──────────────────────────────────────────────────────────────

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

// ── Visuals ────────────────────────────────────────────────────────────────

/**
 * Single horizontal bar split into 4 segments — pending / in_progress /
 * done / cancelled — with opacity tiers (0.95 / 0.7 / 0.4 / 0.2) so the
 * distribution reads at a glance without any color. A legend underneath
 * matches each tier to its number.
 *
 * If all four counts are zero we render a hollow bar with an "—" label.
 */
function StatusBar({ tasks }: { tasks: AdminStats["tasks"] }) {
  const segments = [
    { key: "pending", label: "Pending", count: tasks.pending, opacity: 0.95 },
    { key: "in_progress", label: "In progress", count: tasks.in_progress, opacity: 0.7 },
    { key: "done", label: "Done", count: tasks.done, opacity: 0.4 },
    { key: "cancelled", label: "Cancelled", count: tasks.cancelled, opacity: 0.2 },
  ];
  const total = segments.reduce((s, x) => s + x.count, 0);

  return (
    <div className="admin__chart">
      <div className="admin__chart-caption">Status distribution</div>
      <div className="admin__bar">
        {total === 0 ? (
          <div className="admin__bar-empty">— no tasks yet —</div>
        ) : (
          segments
            .filter((s) => s.count > 0)
            .map((s) => (
              <div
                key={s.key}
                className="admin__bar-segment"
                style={{
                  flexGrow: s.count,
                  background: `rgba(41, 41, 41, ${s.opacity})`,
                }}
                title={`${s.label}: ${s.count}`}
              >
                {/* Inline the count if the segment is wide enough; the CSS
                 * hides it when not, so a 1-task segment doesn't show "1"
                 * stretched across 5 pixels. */}
                <span className="admin__bar-segment-label">{s.count}</span>
              </div>
            ))
        )}
      </div>
      <div className="admin__legend">
        {segments.map((s) => (
          <div key={s.key} className="admin__legend-item">
            <span
              className="admin__legend-swatch"
              style={{ background: `rgba(41, 41, 41, ${s.opacity})` }}
              aria-hidden
            />
            <span className="admin__legend-label">{s.label}</span>
            <span className="admin__legend-value">{s.count}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Horizontal bars for topic-stack counts by kind. One row per kind, label
 * left, bar grows from there, count on the right. Kinds with zero counts
 * still render (gives the full vocabulary at a glance + makes "what's
 * empty" visible).
 */
function KindBars({
  byKind,
}: {
  byKind: AdminStats["stacks"]["by_kind"];
}) {
  const rows = TOPIC_KINDS.map((k) => ({
    label: k.label,
    count: byKind[k.value] ?? 0,
  }));
  const max = Math.max(1, ...rows.map((r) => r.count));

  return (
    <div className="admin__chart">
      <div className="admin__chart-caption">By kind</div>
      <ul className="admin__kindbars">
        {rows.map((r) => (
          <li key={r.label} className="admin__kindbar-row">
            <span className="admin__kindbar-label">{r.label}</span>
            <span className="admin__kindbar-track">
              <span
                className="admin__kindbar-fill"
                style={{ width: `${(r.count / max) * 100}%` }}
              />
            </span>
            <span className="admin__kindbar-value">{r.count}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/**
 * Tiny inline SVG sparkline + area fill. Takes a 30-element series. If
 * everything is zero we render a flat baseline rather than nothing.
 *
 * Pure ink stroke. No axes — the caption tells you the window, the peak
 * label tells you the scale. That's enough for a trend chart of this size.
 */
function Sparkline({
  series,
  label,
}: {
  series: { date: string; count: number }[];
  label: string;
}) {
  const w = 600;
  const h = 60;
  const pad = 2;
  const n = series.length;
  const max = Math.max(1, ...series.map((d) => d.count));
  const xStep = (w - pad * 2) / Math.max(1, n - 1);

  const points = series.map((d, i) => {
    const x = pad + i * xStep;
    const y = h - pad - (d.count / max) * (h - pad * 2);
    return { x, y, count: d.count, date: d.date };
  });
  const pathD = points
    .map((p, i) => (i === 0 ? `M${p.x},${p.y}` : `L${p.x},${p.y}`))
    .join(" ");
  // Closed area for the fill — go to bottom-right, then bottom-left, then
  // back to start. Used as a low-opacity wash under the stroke.
  const areaD =
    pathD +
    ` L${w - pad},${h - pad} L${pad},${h - pad} Z`;

  const total = series.reduce((s, d) => s + d.count, 0);
  const peak = Math.max(...series.map((d) => d.count));

  return (
    <div className="admin__chart">
      <div className="admin__chart-caption">
        <span>{label}</span>
        <span className="admin__chart-meta">
          {total} total · peak {peak}/day
        </span>
      </div>
      <svg
        className="admin__spark"
        viewBox={`0 0 ${w} ${h}`}
        preserveAspectRatio="none"
        role="img"
        aria-label={label}
      >
        <path d={areaD} fill="rgba(41, 41, 41, 0.08)" />
        <path
          d={pathD}
          fill="none"
          stroke="var(--ink)"
          strokeWidth="1.5"
          vectorEffect="non-scaling-stroke"
        />
      </svg>
    </div>
  );
}

// ── Util ───────────────────────────────────────────────────────────────────

function formatStamp(iso: string | null): string {
  if (!iso) return "—";
  const hasTzSuffix = /(Z|[+-]\d{2}:?\d{2})$/.test(iso);
  const d = new Date(hasTzSuffix ? iso : iso + "Z");
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}
