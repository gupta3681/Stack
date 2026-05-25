import { useQuery } from "@tanstack/react-query";
import { ApiError, api } from "../api/client";
import {
  TOPIC_KINDS,
  type AdminStats,
  type ColumnInfo,
  type SchemaInfo,
  type TableInfo,
} from "../types";

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
  const schemaQuery = useQuery({
    queryKey: ["admin-schema"],
    queryFn: () => api.getAdminSchema(),
    // Schema only changes on deploy — cheap to leave cached forever; this
    // override just unbinds from the global 5s staleTime so we don't even
    // bother revalidating in the background.
    staleTime: 60 * 60 * 1000,
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

      {schemaQuery.data && (
        <section className="admin__section">
          <h2 className="admin__section-title">Schema</h2>
          <SchemaERD schema={schemaQuery.data} />
          <div className="admin__schema-grid">
            {schemaQuery.data.tables.map((t) => (
              <TableCard key={t.name} table={t} />
            ))}
          </div>
        </section>
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

// ── Schema diagram ─────────────────────────────────────────────────────────

/**
 * Layout for the inline SVG ERD. Hand-positioned for Stack's 5 domain
 * tables: `users` sits center-top, the four children fan out across the
 * row below. FK arrows fan up to users from each child; the one
 * non-user FK (tasks → stacks) draws as a horizontal arrow on the same
 * row.
 *
 * If we ever add a 6th+ table, redo the positions or punt to a layout
 * library (dagre, elkjs). For 5 it's faster + lighter to position by hand.
 */
const ERD_W = 880;
const ERD_H = 280;
const ERD_BOX_W = 150;
const ERD_BOX_H = 60;

const ERD_BOXES: Record<string, { x: number; y: number }> = {
  users: { x: 365, y: 20 },
  sessions: { x: 30, y: 180 },
  api_tokens: { x: 210, y: 180 },
  stacks: { x: 510, y: 180 },
  tasks: { x: 700, y: 180 },
};

/** Pre-computed FK arrows. Each is [fromTable, toTable, geometry]. */
const ERD_ARROWS: { from: string; to: string }[] = [
  { from: "sessions", to: "users" },
  { from: "api_tokens", to: "users" },
  { from: "stacks", to: "users" },
  { from: "tasks", to: "users" },
  { from: "tasks", to: "stacks" }, // sibling — drawn horizontally
];

function SchemaERD({ schema }: { schema: SchemaInfo }) {
  const colCounts = new Map(
    schema.tables.map((t) => [t.name, t.columns.length])
  );

  return (
    <div className="admin__erd-wrap">
      <div className="admin__chart-caption">Relationships</div>
      <svg
        className="admin__erd"
        viewBox={`0 0 ${ERD_W} ${ERD_H}`}
        role="img"
        aria-label="Entity relationship diagram"
      >
        <defs>
          <marker
            id="erd-arrow"
            viewBox="0 0 10 10"
            refX="9"
            refY="5"
            markerWidth="8"
            markerHeight="8"
            orient="auto-start-reverse"
          >
            <path d="M0,0 L10,5 L0,10 z" fill="var(--ink)" />
          </marker>
        </defs>

        {/* Arrows first so the boxes paint over the line endpoints. */}
        {ERD_ARROWS.map((a, i) => {
          const from = ERD_BOXES[a.from];
          const to = ERD_BOXES[a.to];
          if (!from || !to) return null;
          // Sibling row (tasks → stacks): horizontal from left edge of
          // `from` to right edge of `to`, both at row midline.
          if (from.y === to.y) {
            const y = from.y + ERD_BOX_H / 2;
            return (
              <line
                key={i}
                x1={from.x}
                y1={y}
                x2={to.x + ERD_BOX_W}
                y2={y}
                stroke="var(--ink)"
                strokeWidth="1"
                markerEnd="url(#erd-arrow)"
              />
            );
          }
          // Parent-child: from top-center of child up to bottom-center
          // of parent (users sits above all four).
          const x1 = from.x + ERD_BOX_W / 2;
          const y1 = from.y;
          const x2 = to.x + ERD_BOX_W / 2;
          const y2 = to.y + ERD_BOX_H;
          return (
            <line
              key={i}
              x1={x1}
              y1={y1}
              x2={x2}
              y2={y2}
              stroke="var(--ink)"
              strokeWidth="1"
              markerEnd="url(#erd-arrow)"
            />
          );
        })}

        {/* Boxes */}
        {Object.entries(ERD_BOXES).map(([name, pos]) => {
          const count = colCounts.get(name) ?? 0;
          return (
            <g key={name} transform={`translate(${pos.x}, ${pos.y})`}>
              <rect
                width={ERD_BOX_W}
                height={ERD_BOX_H}
                fill="var(--canvas)"
                stroke="var(--ink)"
                strokeWidth="1"
              />
              <text
                x={ERD_BOX_W / 2}
                y={26}
                textAnchor="middle"
                className="admin__erd-name"
              >
                {name}
              </text>
              <text
                x={ERD_BOX_W / 2}
                y={46}
                textAnchor="middle"
                className="admin__erd-sub"
              >
                {count} cols
              </text>
            </g>
          );
        })}
      </svg>
      <div className="admin__erd-legend">
        Arrows point from the FK column to its referenced table. Tables
        without arrows are top-level (no FK out).
      </div>
    </div>
  );
}

/**
 * Per-table column detail card. The diagram above gives you the
 * topology — these cards give you "what's actually in each table" so
 * you can think about where a new field belongs.
 */
function TableCard({ table }: { table: TableInfo }) {
  return (
    <div className="admin__schema-card">
      <div className="admin__schema-card-head">
        <span className="admin__schema-card-name">{table.name}</span>
        <span className="admin__schema-card-count">
          {table.columns.length} cols
        </span>
      </div>
      <ul className="admin__schema-cols">
        {table.columns.map((c) => (
          <ColumnRow key={c.name} col={c} />
        ))}
      </ul>
    </div>
  );
}

function ColumnRow({ col }: { col: ColumnInfo }) {
  return (
    <li className="admin__schema-col">
      <span className="admin__schema-col-name">{col.name}</span>
      <span className="admin__schema-col-type">{shortType(col.type)}</span>
      <span className="admin__schema-col-flags">
        {col.primary_key && (
          <span className="admin__schema-flag" title="Primary key">
            PK
          </span>
        )}
        {col.references && (
          <span
            className="admin__schema-flag admin__schema-flag--fk"
            title={`References ${col.references}`}
          >
            → {col.references.split(".")[0]}
          </span>
        )}
        {col.unique && !col.primary_key && (
          <span className="admin__schema-flag" title="Unique">
            uniq
          </span>
        )}
        {col.nullable && (
          <span
            className="admin__schema-flag admin__schema-flag--null"
            title="Nullable"
          >
            ?
          </span>
        )}
        {col.indexed && !col.primary_key && !col.unique && (
          <span className="admin__schema-flag" title="Indexed">
            idx
          </span>
        )}
      </span>
    </li>
  );
}

/** SQLAlchemy types come back as long strings like "VARCHAR(320)". The
 * ERD doesn't need that fidelity; trim to the kind. */
function shortType(t: string): string {
  return t.replace(/\(.*\)/, "").toLowerCase();
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
