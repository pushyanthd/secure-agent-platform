export interface Scope {
  task_id: string;
  version: number;
  actor: string;
  workspace: string;
  document_ids: string[];
  project_ids: string[];
  allowed_tools: string[];
  update_ticket_ids?: string[] | null;
  response_scope?: {
    recipient: string;
    max_classification: 'internal' | 'confidential';
    effect_receipt?: {
      template: 'ticket_update_v1';
      action: { tool: 'tickets.update'; arguments: Record<string, unknown> };
    } | null;
  } | null;
}
export interface Identity {
  subject: string;
  actor: string;
  workspace: string;
  role: 'operator' | 'observer';
  mode: string;
  profile: string;
}
export interface Scenario {
  id: string;
  task: string;
  scope: Scope;
}
export interface Run {
  episode_id: string;
  scenario_id: string;
  created_at: number;
  status: string;
}
export interface RunDetail extends Run {
  task: string;
  started_at: number | null;
  deadline: number | null;
  claims: number;
  mode: string;
  result: {
    reason?: string;
    model_calls?: number;
    generated_tokens?: number;
    elapsed_seconds?: number;
  };
}
export interface Step {
  step: number;
  elapsed_seconds: number;
  state: string;
  kind?: string;
  tool?: string;
  target?: string;
  decision?: { outcome: string; reason: string };
  approval_status?: string;
}
export interface Approval {
  id: string;
  status: string;
  expires_at: number;
  consumed: boolean | number;
}
export interface ApprovalDetail extends Approval {
  episode_id: string;
  task: string;
  execution_key: string;
  action_hash: string;
  nonce: string;
  snapshot: {
    action: { tool: string; arguments: Record<string, unknown> };
    contract: Scope;
    resource: { id: string; version: number; visibility?: string; [key: string]: unknown } | null;
    source?: { id: string; version: number; classification: string; body: string } | null;
    ticket?: {
      id: string;
      version: number;
      classification: string;
      title: string;
      body: string;
    } | null;
    policy_version: string;
    confidential: boolean;
  };
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
  ) {
    super(code);
  }
}

// A client belongs to one in-memory session. Logout aborts every outstanding request.
export class Api {
  private controller = new AbortController();
  constructor(private token: string) {}
  close() {
    this.controller.abort();
    this.token = '';
  }
  async get<T>(path: string): Promise<T> {
    return this.request<T>(path);
  }
  async post<T>(path: string, body: unknown, key?: string): Promise<T> {
    return this.request<T>(path, body, key);
  }
  private async request<T>(path: string, body?: unknown, key?: string): Promise<T> {
    if (!path.startsWith('/api/') || this.controller.signal.aborted) {
      throw new ApiError(0, 'SESSION_CLOSED');
    }
    const response = await fetch(path, {
      method: body === undefined ? 'GET' : 'POST',
      headers: {
        Authorization: `Bearer ${this.token}`,
        ...(body === undefined
          ? {}
          : { 'Content-Type': 'application/json', 'X-Agentguard-Request': '1' }),
        ...(key ? { 'Idempotency-Key': key } : {}),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
      credentials: 'omit',
      cache: 'no-store',
      redirect: 'error',
      mode: 'same-origin',
      signal: AbortSignal.any([this.controller.signal, AbortSignal.timeout(8000)]),
    });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new ApiError(
        response.status,
        typeof data.error === 'string' ? data.error : 'REQUEST_FAILED',
      );
    }
    return response.json() as Promise<T>;
  }
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401)
      return 'Your credential was not accepted. Reconnect with a current token.';
    if (error.code === 'APPROVAL_STALE_OR_INVALID')
      return 'This approval changed or expired. Refresh the run and inspect the current request before reviewing again.';
    if (error.code === 'IDEMPOTENCY_CONFLICT')
      return 'This submission no longer matches the saved request. Reconnect and inspect recent runs before starting another.';
    if (error.status === 403)
      return 'This action requires operator access from this local application.';
    if (error.status === 404) return 'This run or request is no longer available to your account.';
    if (error.status === 429)
      return 'Too many unfinished runs. Complete or cancel a run before submitting another.';
    if (error.status < 500 && error.status > 0)
      return 'The request could not be accepted. Refresh and try again.';
  }
  return 'Connection interrupted. Reconnecting automatically; actions are paused until the service responds.';
}
