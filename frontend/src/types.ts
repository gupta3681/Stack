export type TaskStatus = "pending" | "in_progress" | "done" | "cancelled";
export type PriorityHint = "top" | "high" | "normal" | "low";
export type StackKind =
  | "daily"
  | "todo"
  | "reading"
  | "watching"
  | "listening"
  | "buy"
  | "ideas";

export const TOPIC_KINDS: { value: Exclude<StackKind, "daily">; label: string }[] = [
  { value: "todo", label: "To Do" },
  { value: "reading", label: "Reading" },
  { value: "watching", label: "Watching" },
  { value: "listening", label: "Listening" },
  { value: "buy", label: "Buy" },
  { value: "ideas", label: "Ideas" },
];

export interface Task {
  id: number;
  stack_id: number | null;
  name: string;
  // Long-form markdown body (with optional YAML frontmatter — convention only,
  // not parsed by the backend yet). Replaces the old `description` field.
  context_md: string | null;
  // Canonical URL for this task. Set → clicking the card opens it in a new tab.
  direct_link: string | null;
  position: number;
  status: TaskStatus;
  priority_hint: PriorityHint | null;
  due_at: string | null;
  // Optional time budget in minutes. Null = no estimate set.
  estimate_minutes: number | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  in_progress_started_at: string | null;
  accumulated_seconds: number;
}

export interface Stack {
  // null when the row hasn't been persisted yet (GET on a date with no tasks).
  id: number | null;
  kind: StackKind;
  // Set for daily stacks (kind="daily"); null for topic stacks.
  stack_date: string | null;
  // Set for topic stacks; null for daily (the date IS the identity).
  name: string | null;
  intention: string | null;
  tasks: Task[];
  // Topic-stack sharing. is_public toggles availability of the slug-based URL.
  // share_slug is generated on first share and persists across un-share /
  // re-share cycles (same URL each time).
  is_public: boolean;
  share_slug: string | null;
  // When true, the public viewer renders each task's context_md body.
  share_context_in_public: boolean;
}

export interface PublicTask {
  name: string;
  // Only populated when the owner opted in via share_context_in_public.
  context_md: string | null;
  direct_link: string | null;
  priority_hint: PriorityHint | null;
  due_at: string | null;
  estimate_minutes: number | null;
  position: number;
}

export interface PublicStack {
  kind: StackKind;
  name: string;
  intention: string | null;
  owner_display_name: string | null;
  tasks: PublicTask[];
}

export interface CreateTopicStackInput {
  kind: Exclude<StackKind, "daily">;
  name: string;
  intention?: string | null;
}

export interface CreateTaskInput {
  name: string;
  context_md?: string | null;
  direct_link?: string | null;
  stack_date?: string | null;
  stack_id?: number | null;
  priority_hint?: PriorityHint | null;
  due_at?: string | null;
  estimate_minutes?: number | null;
}

export interface UpdateTaskInput {
  name?: string;
  context_md?: string | null;
  direct_link?: string | null;
  status?: TaskStatus;
  due_at?: string | null;
  priority_hint?: PriorityHint | null;
  estimate_minutes?: number | null;
}

export interface AuthUser {
  id: number;
  email: string;
  display_name: string | null;
  onboarded: boolean;
  is_admin: boolean;
}

// ── Admin ──

export interface AdminStats {
  users: {
    total: number;
    active_last_7d: number;
    active_last_30d: number;
    admin_count: number;
  };
  tasks: {
    total: number;
    pending: number;
    in_progress: number;
    done: number;
    cancelled: number;
    completed_today: number;
    completed_last_7d: number;
  };
  stacks: {
    topic_total: number;
    /** Map of kind → count. Keys are subset of StackKind minus "daily". */
    by_kind: Partial<Record<Exclude<StackKind, "daily">, number>>;
    public_count: number;
  };
  api_tokens: {
    total: number;
    used_last_7d: number;
  };
  recent_signups: {
    id: number;
    email: string;
    display_name: string | null;
    created_at: string;
  }[];
  timeseries: {
    /** 30 contiguous days, oldest first, zero-filled. */
    signups_by_day: { date: string; count: number }[];
    completions_by_day: { date: string; count: number }[];
  };
  generated_at: string;
}

export interface AdminUser {
  id: number;
  email: string;
  display_name: string | null;
  created_at: string;
  is_admin: boolean;
  onboarded_at: string | null;
  task_count: number;
  last_session_at: string | null;
}

export interface ColumnInfo {
  name: string;
  type: string;
  primary_key: boolean;
  nullable: boolean;
  unique: boolean;
  indexed: boolean;
  /** "table.column" if this column is a FK, else null. */
  references: string | null;
}

export interface TableInfo {
  name: string;
  columns: ColumnInfo[];
}

export interface SchemaInfo {
  tables: TableInfo[];
}

export interface FeedbackInput {
  rating: number; // 1-5
  comments?: string | null;
  bugs?: string | null;
}

export interface FeedbackEntry {
  id: number;
  rating: number;
  comments: string | null;
  bugs: string | null;
  created_at: string;
  user_id: number;
  user_email: string;
  user_display_name: string | null;
}

export interface StackCounts {
  today: number;
  tomorrow: number;
  topic_stacks: number;
}

export interface LoginInput {
  email: string;
  password: string;
}

export interface SignupInput extends LoginInput {
  display_name?: string | null;
}

/** Bearer-auth token for CLIs / agents / the Claude Code skill file.
 * `token` field is ONLY present in the one-time create response — the list
 * endpoint never returns it. */
export interface ApiToken {
  id: number;
  name: string;
  prefix: string;
  created_at: string;
  last_used_at: string | null;
}

export interface ApiTokenCreated extends ApiToken {
  token: string;
}
