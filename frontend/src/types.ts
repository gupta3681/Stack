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
  title: string;
  description: string | null;
  position: number;
  status: TaskStatus;
  priority_hint: PriorityHint | null;
  due_at: string | null;
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
}

export interface CreateTopicStackInput {
  kind: Exclude<StackKind, "daily">;
  name: string;
  intention?: string | null;
}

export interface CreateTaskInput {
  title: string;
  description?: string | null;
  stack_date?: string | null;
  stack_id?: number | null;
  priority_hint?: PriorityHint | null;
  due_at?: string | null;
}

export interface UpdateTaskInput {
  title?: string;
  description?: string | null;
  status?: TaskStatus;
  due_at?: string | null;
  priority_hint?: PriorityHint | null;
}

export interface AuthUser {
  id: number;
  email: string;
  display_name: string | null;
}

export interface LoginInput {
  email: string;
  password: string;
}

export interface SignupInput extends LoginInput {
  display_name?: string | null;
}
