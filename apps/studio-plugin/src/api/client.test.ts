import { describe, it, expect, vi, afterEach } from 'vitest';
import { operation, errorMessage, list, runJob } from './client';
afterEach(() => vi.unstubAllGlobals());
describe('generated API operations', () => {
  it('preserves authorization errors rather than presenting success', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({code:'forbidden',message:'Approver role required'}), { status: 403 })));
    try { await operation('GET /api/v1/projects/{p}/reviews', {path:{p:'p'}}); expect.fail('should reject'); }
    catch (error) { expect(errorMessage(error)).toContain('do not have permission'); expect(errorMessage(error)).toContain('Approver role required'); }
  });
  it('loads all pages without dropping records after the first page',async()=>{
    const fetcher=vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({items:[{id:'first'}],next_cursor:'opaque/cursor'}))).mockResolvedValueOnce(new Response(JSON.stringify({items:[{id:'last'}],next_cursor:null})));
    vi.stubGlobal('fetch',fetcher);
    expect(await list('GET /api/v1/projects/{p}/versions',{path:{p:'p'}})).toEqual([{id:'first'},{id:'last'}]);
    expect(fetcher.mock.calls[1][0]).toBe('/api/v1/projects/p/versions?cursor=opaque%2Fcursor');
  });
  it('uses a fresh idempotency key and reports the actual string job error',async()=>{
    const fetcher=vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({job_id:'job'}))).mockResolvedValueOnce(new Response(JSON.stringify({id:'job',status:'failed',error:'Runner unavailable'})));
    vi.stubGlobal('fetch',fetcher);
    await expect(runJob('POST /api/v1/projects/{p}/validation-jobs',{path:{p:'p'},body:{proposal_id:'proposal',revision:1,bundle_digest:'hash'}})).rejects.toThrow('Runner unavailable');
    expect(new Headers(fetcher.mock.calls[0][1].headers).get('Idempotency-Key')).toBeTruthy();
  });
  it('encodes path values and serializes generated query parameters',async()=>{
    const fetcher=vi.fn().mockResolvedValue(new Response(JSON.stringify({items:[],next_cursor:null})));
    vi.stubGlobal('fetch',fetcher);
    await operation('GET /api/v1/projects/{p}/reviews',{path:{p:'a/b'},query:{revision_id:'r & 2',limit:7}});
    expect(fetcher.mock.calls[0][0]).toBe('/api/v1/projects/a%2Fb/reviews?revision_id=r+%26+2&limit=7');
  });
  it('preserves multipart uploads and raw artifact bytes',async()=>{
    const fetcher=vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({id:'doc'}))).mockResolvedValueOnce(new Response('{"raw":true}',{headers:{'content-type':'application/json'}}));
    vi.stubGlobal('fetch',fetcher);
    const body=new FormData();body.set('title','Synthetic document');
    await operation('POST /api/v1/projects/{p}/documents',{path:{p:'p'},body});
    expect(fetcher.mock.calls[0][1].body).toBe(body);
    expect(new Headers(fetcher.mock.calls[0][1].headers).has('Content-Type')).toBe(false);
    const blob=await operation('GET /api/v1/projects/{p}/artifacts/{artifact_id}',{path:{p:'p',artifact_id:'a'}});
    expect(blob).toBeInstanceOf(Blob);
    const text = await new Promise<string>((resolve, reject) => { const reader=new FileReader(); reader.onload=()=>resolve(String(reader.result)); reader.onerror=reject; reader.readAsText(blob); });
    expect(text).toBe('{"raw":true}');
  });
});

// Compiled negative assertions: endpoint identity must constrain both request and
// response; job results are inferred from the generated worker-kind mapping.
function compileContract() {
  const project = operation('GET /api/v1/projects/{p}', {path:{p:'p'}});
  project.then(value => value.scope_accepted satisfies boolean);
  // @ts-expect-error nonexistent response property
  project.then(value => value.nonexistent);
  // @ts-expect-error wrong path parameter
  operation('GET /api/v1/projects/{p}', {path:{project:'p'}});
  // @ts-expect-error required body is missing
  operation('POST /api/v1/projects', {});
  // @ts-expect-error scope body is not a project request
  operation('POST /api/v1/projects', {body:{scope_digest:'d',decision:'accept',rationale:'okay'}});
  // @ts-expect-error response operation cannot accept a mutation body
  operation('GET /api/v1/projects/{p}', {path:{p:'p'},body:{name:'wrong'}});
  // @ts-expect-error request does not match this job endpoint
  runJob('POST /api/v1/projects/{p}/question-jobs',{path:{p:'p'},body:{proposal_id:'q',revision:1,bundle_digest:'d'}});
  const answer = runJob('POST /api/v1/projects/{p}/question-jobs', {path:{p:'p'},body:{question:'Who owns Atlas?'}});
  answer.then(value => value.answer satisfies string);
  // @ts-expect-error question jobs cannot claim a proposal result
  answer.then(value => value.proposal_id);
  // @ts-expect-error callers cannot substitute their own response shape
  runJob<{proposal_id:string}>('POST /api/v1/projects/{p}/question-jobs', {path:{p:'p'},body:{question:'Who owns Atlas?'}});
  // @ts-expect-error non-page endpoint cannot be paginated
  list('GET /api/v1/projects/{p}',{path:{p:'p'}});
}
void compileContract;
