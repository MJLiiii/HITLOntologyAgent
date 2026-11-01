import { describe, it, expect, vi, afterEach } from 'vitest';
import { request, errorMessage, list, runJob } from './client';
afterEach(() => vi.unstubAllGlobals());
describe('API errors', () => {
  it('preserves authorization errors rather than presenting success', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({code:'forbidden',message:'Approver role required'}), { status: 403 })));
    try { await request('/projects/p/reviews', {method:'POST'}); expect.fail('should reject'); }
    catch (error) { expect(errorMessage(error)).toContain('do not have permission'); expect(errorMessage(error)).toContain('Approver role required'); }
  });
  it('loads all pages without dropping records after the first page',async()=>{
    const fetcher=vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({items:[{id:'first'}],next_cursor:'opaque/cursor'}))).mockResolvedValueOnce(new Response(JSON.stringify({items:[{id:'last'}],next_cursor:null})));
    vi.stubGlobal('fetch',fetcher);
    expect(await list('/projects/p/versions')).toEqual([{id:'first'},{id:'last'}]);
    expect(fetcher.mock.calls[1][0]).toBe('/api/v1/projects/p/versions?cursor=opaque%2Fcursor');
  });
  it('uses a fresh idempotency key and reports a failed job as failure',async()=>{
    const fetcher=vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({job_id:'job'}))).mockResolvedValueOnce(new Response(JSON.stringify({id:'job',status:'failed',error:{message:'Runner unavailable'}})));
    vi.stubGlobal('fetch',fetcher);
    await expect(runJob('/projects/p/validation-jobs',{revision:1})).rejects.toThrow('Runner unavailable');
    expect(new Headers(fetcher.mock.calls[0][1].headers).get('Idempotency-Key')).toBeTruthy();
  });
});
