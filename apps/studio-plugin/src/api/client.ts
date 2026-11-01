import type { Job, JobRef, Page } from './generated';
export class ApiError extends Error {
  constructor(message: string, readonly status: number, readonly code: string, readonly correlationId?: string) { super(message); this.name = 'ApiError'; }
}
export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json');
  const response = await fetch(`/api/v1${path}`, { ...options, headers, credentials: 'same-origin' });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: `Request failed (${response.status})` }));
    const detail = Array.isArray(error.details) ? error.details.map((item: {location?: string[]; message?: string}) => `${item.location?.join('.') || 'Request'}: ${item.message || 'Invalid value'}`).join('; ') : '';
    throw new ApiError(`${error.message || error.detail || `Request failed (${response.status})`}${detail ? ` · ${detail}` : ''}`, response.status, error.code || 'request_failed', error.correlation_id);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}
export async function list<T>(path: string): Promise<T[]> {
  const items: T[] = [];
  const cursors = new Set<string>();
  let cursor: string | null = null;
  do {
    const page: Page<T> = await request<Page<T>>(`${path}${cursor ? `${path.includes('?') ? '&' : '?'}cursor=${encodeURIComponent(cursor)}` : ''}`);
    items.push(...page.items);
    cursor = page.next_cursor;
    if (cursor && cursors.has(cursor)) throw new Error('The server repeated a pagination cursor. Refresh the workspace to reload the list.');
    if (cursor) cursors.add(cursor);
  } while (cursor);
  return items;
}
export const post = <T>(path: string, body: unknown, headers: Record<string, string> = {}) => request<T>(path, {method: 'POST', body: JSON.stringify(body), headers});
export async function runJob<T>(path: string, body: unknown, onStage?: (stage: string) => void): Promise<T> {
  const ref = await post<JobRef>(path, body, { 'Idempotency-Key': crypto.randomUUID() });
  const deadline = Date.now() + 120_000;
  while (Date.now() < deadline) {
    const job = await request<Job<T>>(`/jobs/${encodeURIComponent(ref.job_id)}`);
    onStage?.(job.stage || job.status);
    if (job.status === 'succeeded') {
      if (job.result == null) throw new Error('The job completed without a result. Refresh to inspect its status.');
      return job.result;
    }
    if (job.status === 'failed' || job.status === 'cancelled') throw new Error(typeof job.error === 'string' ? job.error : job.error?.message || `The job ${job.status}.`);
    await new Promise(resolve => setTimeout(resolve, 800));
  }
  throw new Error(`Job ${ref.job_id} is still running after two minutes. Refresh the workspace to check its result; it has not been marked successful.`);
}
export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return 'Your session has expired. Reload the page to sign in again.';
    if (error.status === 403) return `You do not have permission to perform this action. ${error.message}`;
    if (error.status === 409) return `This revision or approved head has changed. Refresh before continuing. ${error.message}`;
  }
  return error instanceof Error ? error.message : 'The request could not complete. Please try again.';
}
