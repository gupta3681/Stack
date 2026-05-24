import type {
  AuthUser,
  CreateTaskInput,
  CreateTopicStackInput,
  LoginInput,
  PublicStack,
  SignupInput,
  Stack,
  StackCounts,
  Task,
  UpdateTaskInput,
} from "../types";

const BASE = "/api";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (!headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  headers.set("X-Stack-CSRF", "1");

  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers,
    credentials: "include",
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      /* not JSON */
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  getStack: (stackDate: string) =>
    request<Stack>(`/stacks/${stackDate}`),

  getToday: () => request<Stack>("/stacks/today"),
  getTomorrow: () => request<Stack>("/stacks/tomorrow"),
  getOverdue: (today: string) =>
    request<Task[]>(`/stacks/overdue?today=${encodeURIComponent(today)}`),

  getCounts: (today: string) =>
    request<StackCounts>(`/stacks/counts?today=${encodeURIComponent(today)}`),

  listTopicStacks: () => request<Stack[]>("/stacks/topics"),

  getTopicStack: (stackId: number) =>
    request<Stack>(`/stacks/topics/${stackId}`),

  createTopicStack: (input: CreateTopicStackInput) =>
    request<Stack>("/stacks/topics", {
      method: "POST",
      body: JSON.stringify(input),
    }),

  updateTopicStack: (
    stackId: number,
    fields: { intention?: string | null; share_context_in_public?: boolean }
  ) =>
    request<Stack>(`/stacks/topics/${stackId}`, {
      method: "PATCH",
      body: JSON.stringify(fields),
    }),

  deleteTopicStack: (stackId: number) =>
    request<void>(`/stacks/topics/${stackId}`, { method: "DELETE" }),

  shareTopicStack: (stackId: number) =>
    request<Stack>(`/stacks/topics/${stackId}/share`, { method: "POST" }),

  unshareTopicStack: (stackId: number) =>
    request<Stack>(`/stacks/topics/${stackId}/unshare`, { method: "POST" }),

  getPublicStack: (slug: string) =>
    request<PublicStack>(`/public/stacks/${encodeURIComponent(slug)}`),

  updateStackIntention: (stackDate: string, intention: string | null) =>
    request<Stack>(`/stacks/${stackDate}`, {
      method: "PATCH",
      body: JSON.stringify({ intention }),
    }),

  createTask: (input: CreateTaskInput) =>
    request<Task>("/tasks", {
      method: "POST",
      body: JSON.stringify(input),
    }),

  updateTask: (id: number, input: UpdateTaskInput) =>
    request<Task>(`/tasks/${id}`, {
      method: "PATCH",
      body: JSON.stringify(input),
    }),

  deleteTask: (id: number) =>
    request<void>(`/tasks/${id}`, { method: "DELETE" }),

  moveTask: (
    id: number,
    target: { stackDate?: string | null; stackId?: number | null; position?: number }
  ) =>
    request<Task>(`/tasks/${id}/move`, {
      method: "POST",
      body: JSON.stringify({
        stack_date: target.stackDate ?? null,
        stack_id: target.stackId ?? null,
        position: target.position,
      }),
    }),

  reorder: (
    target: { stackDate?: string | null; stackId?: number | null },
    orderedIds: number[]
  ) =>
    request<Task[]>(`/tasks/reorder`, {
      method: "POST",
      body: JSON.stringify({
        stack_date: target.stackDate ?? null,
        stack_id: target.stackId ?? null,
        ordered_ids: orderedIds,
      }),
    }),

  startTask: (id: number) =>
    request<Task>(`/tasks/${id}/start`, { method: "POST" }),

  pauseTask: (id: number) =>
    request<Task>(`/tasks/${id}/pause`, { method: "POST" }),

  // ── Auth ──

  me: () => request<AuthUser>("/auth/me"),

  signup: (input: SignupInput) =>
    request<AuthUser>("/auth/signup", {
      method: "POST",
      body: JSON.stringify(input),
    }),

  login: (input: LoginInput) =>
    request<AuthUser>("/auth/login", {
      method: "POST",
      body: JSON.stringify(input),
    }),

  logout: () => request<void>("/auth/logout", { method: "POST" }),

  updateProfile: (input: { display_name?: string | null }) =>
    request<AuthUser>("/auth/me", {
      method: "PATCH",
      body: JSON.stringify(input),
    }),

  changePassword: (input: { current_password: string; new_password: string }) =>
    request<void>("/auth/change-password", {
      method: "POST",
      body: JSON.stringify(input),
    }),

  completeOnboarding: () =>
    request<AuthUser>("/auth/me/onboarded", { method: "POST" }),
};
