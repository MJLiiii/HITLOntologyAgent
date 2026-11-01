import type { ApiJobResults, ApiOperations, JobRefResponse } from './openapi';

export class ApiError extends Error {
  constructor(message: string, readonly status: number, readonly code: string, readonly correlationId?: string) { super(message); this.name = 'ApiError'; }
}
type Key = keyof ApiOperations;
type RequiredKeys<T> = { [K in keyof T]-?: {} extends Pick<T, K> ? never : K }[keyof T];
type Part<K extends Key, P extends 'path' | 'query' | 'headers'> =
  ApiOperations[K][P] extends Record<string, never> ? { [F in P]?: never } :
  RequiredKeys<ApiOperations[K][P]> extends never ? { [F in P]?: ApiOperations[K][P] } : { [F in P]: ApiOperations[K][P] };
export type OperationOptions<K extends Key> = Part<K, 'path'> & Part<K, 'query'> & Part<K, 'headers'> &
  (ApiOperations[K]['body'] extends never ? { body?: never } :
    ApiOperations[K]['bodyRequired'] extends true ? { body: ApiOperations[K]['body'] } : { body?: ApiOperations[K]['body'] });

type RuntimeOptions = { path?: Record<string, string | number>; query?: Record<string, string | number | boolean | null | undefined>; headers?: Record<string, string | undefined>; body?: unknown };
async function send(key: Key, options: RuntimeOptions): Promise<unknown> {
  const space = key.indexOf(' ');
  const method = key.slice(0, space);
  let path = key.slice(space + 1).replace(/\{([^}]+)\}/g, (_, name: string) => {
    const value = options.path?.[name];
    if (value === undefined) throw new Error(`Missing path parameter ${name}`);
    return encodeURIComponent(String(value));
  });
  const query = new URLSearchParams();
  for (const [name, value] of Object.entries(options.query || {})) if (value != null) query.set(name, String(value));
  if (query.size) path += `?${query}`;
  const headers = new Headers();
  for (const [name, value] of Object.entries(options.headers || {})) if (value !== undefined) headers.set(name, value);
  const multipart = options.body instanceof FormData;
  if (options.body !== undefined && !multipart) headers.set('Content-Type', 'application/json');
  const response = await fetch(path, { method, headers, credentials: 'same-origin',
    body: options.body === undefined ? undefined : multipart ? options.body as FormData : JSON.stringify(options.body) });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: `Request failed (${response.status})` }));
    const detail = Array.isArray(error.details) ? error.details.map((item: {location?: string[]; message?: string}) => `${item.location?.join('.') || 'Request'}: ${item.message || 'Invalid value'}`).join('; ') : '';
    throw new ApiError(`${error.message || error.detail || `Request failed (${response.status})`}${detail ? ` · ${detail}` : ''}`, response.status, error.code || 'request_failed', error.correlation_id);
  }
  if (response.status === 204) return undefined;
  // Artifact bytes are never implicitly parsed, even when the stored type is JSON.
  if (key === 'GET /api/v1/projects/{p}/artifacts/{artifact_id}') return response.blob();
  if (response.headers.get('content-type')?.includes('text/csv')) return response.text();
  return response.json();
}

export function operation<K extends Key>(key: K, options: OperationOptions<NoInfer<K>>): Promise<ApiOperations[K]['response']> {
  return send(key, options as RuntimeOptions) as Promise<ApiOperations[K]['response']>;
}
type ListKey = { [K in Key]: ApiOperations[K]['response'] extends { items: unknown[]; next_cursor: string | null } ? K : never }[Key];
type ListItem<K extends ListKey> = ApiOperations[K]['response'] extends { items: (infer T)[] } ? T : never;
export async function list<K extends ListKey>(key: K, options: OperationOptions<NoInfer<K>>): Promise<ListItem<K>[]> {
  const items: ListItem<K>[] = [];
  const cursors = new Set<string>();
  let cursor: string | null = null;
  do {
    const page = await send(key, { ...options, query: { ...options.query, ...(cursor ? { cursor } : {}) } } as RuntimeOptions) as { items: ListItem<K>[]; next_cursor: string | null };
    items.push(...page.items);
    cursor = page.next_cursor;
    if (cursor && cursors.has(cursor)) throw new Error('The server repeated a pagination cursor. Refresh the workspace to reload the list.');
    if (cursor) cursors.add(cursor);
  } while (cursor);
  return items;
}

type JobKey = keyof ApiJobResults;
type JobOptions<K extends JobKey> = Omit<OperationOptions<K>, 'headers'> & { headers?: { 'idempotency-key'?: string } };
export async function runJob<K extends JobKey>(key: K, options: JobOptions<NoInfer<K>>, onStage?: (stage: string) => void): Promise<ApiJobResults[K]> {
  const ref = await send(key, { ...options, headers: { 'idempotency-key': crypto.randomUUID(), ...options.headers } } as RuntimeOptions) as JobRefResponse;
  const deadline = Date.now() + 120_000;
  while (Date.now() < deadline) {
    const job = await operation('GET /api/v1/jobs/{job_id}', { path: { job_id: ref.job_id } });
    onStage?.(job.stage);
    if (job.status === 'succeeded') {
      if (job.result == null) throw new Error('The job completed without a result. Refresh to inspect its status.');
      return job.result as ApiJobResults[K];
    }
    if (job.status === 'failed' || job.status === 'cancelled') throw new Error(job.error || `The job ${job.status}.`);
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
