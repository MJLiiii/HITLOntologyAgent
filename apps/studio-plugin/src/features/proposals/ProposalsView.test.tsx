import { evidenceFixture, modelProfileFixture, projectFixture, revisionFixture } from '../../test-fixtures';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { ProposalsView, RevisionDetail } from './ProposalsView';
import type { Revision, Project, Session } from '../../api/generated';
const project: Project = projectFixture({ id: 'p', name: 'Demo', domain: 'unselected', approved_version_id: 'head-new', corpus_snapshot_id: 'c', scope_accepted: true, scope_digest: 'scope', mode: 'demo' });
const session: Session = { actor: { subject: 'human', kind: 'human', roles: ['researcher', 'reviewer', 'approver'] }, mode: 'demo', model_mode: 'local' };
const revision: Revision = revisionFixture({ id: 'proposal', title: 'Add an owner', revision: 1, status: 'validated', base_version_id: 'head-old', bundle_digest: 'sha256:1234', created_at: '', rationale: 'Add ownership', additions: [{ subject: 'demo:Dataset', predicate: 'rdfs:subClassOf', object: 'demo:Asset' }], deletions: [], evidence: [evidenceFixture({ id: 'e', document_id: 'doc', title: 'Handbook', quote: '<script>alert(1)</script>', resolved: true })], review_eligibility: { eligible: true, reasons: [] }, validation_run_id: 'v', assessment_run_ids: ['a'] });
afterEach(() => vi.unstubAllGlobals());
describe('revision review', () => {
  it('creates a proposal with the explicitly chosen Claude profile',async()=>{
    const writes:Record<string,unknown>[]=[];
    vi.stubGlobal('fetch',vi.fn(async(path:string,options:RequestInit={})=>{
      if(path.endsWith('/model-profiles'))return new Response(JSON.stringify({items:[modelProfileFixture(),modelProfileFixture({id:'claude-sonnet',model:'claude-sonnet-4-6',provider:'anthropic',is_default:false})],next_cursor:null}));
      if(options.method==='POST'){writes.push(JSON.parse(String(options.body)));return new Response(JSON.stringify({job_id:'proposal-job'}));}
      if(path.endsWith('/jobs/proposal-job'))return new Response(JSON.stringify({status:'succeeded',result:{proposal_id:'new-proposal'}}));
      return new Response(JSON.stringify(project));
    }));
    render(<ProposalsView project={project} session={{...session,model_mode:'model'}} proposals={[]} onRefresh={vi.fn().mockResolvedValue(undefined)} onSources={vi.fn()}/>);
    fireEvent.click(screen.getByRole('button',{name:'New proposal'}));
    await screen.findByRole('option',{name:/claude-sonnet-4-6/});
    fireEvent.change(screen.getByLabelText('Proposal model'),{target:{value:'claude-sonnet'}});
    fireEvent.click(screen.getByRole('button',{name:'Generate candidate'}));
    await screen.findByText(/A candidate was created/);
    expect(writes).toEqual([expect.objectContaining({model_profile_id:'claude-sonnet',base_version_id:project.approved_version_id,corpus_snapshot_id:project.corpus_snapshot_id})]);
  });

  it('uses an explicit repair model only when the researcher selects an override',async()=>{
    const action=vi.fn().mockResolvedValue(undefined);
    const current={...project,approved_version_id:'head-old'};
    const failed:Revision={...revision,status:'validation_failed',validation:{id:'v',status:'failed',profile:'rdfs',cases:[]}};
    vi.stubGlobal('fetch',vi.fn(async(path:string)=>new Response(JSON.stringify({items:path.endsWith('/model-profiles')?[modelProfileFixture(),modelProfileFixture({id:'claude-sonnet',model:'claude-sonnet-4-6',provider:'anthropic',is_default:false})]:[],next_cursor:null}))));
    render(<RevisionDetail project={current} session={{...session,model_mode:'model'}} revision={failed} onRefresh={vi.fn()} onAction={action} busy={false}/>);
    await screen.findByRole('option',{name:/claude-sonnet-4-6/});
    expect(screen.getByLabelText('Repair model')).toHaveValue('');
    fireEvent.click(screen.getByRole('button',{name:'Request repair'}));
    expect(action).toHaveBeenLastCalledWith('repair',{model_profile_id:undefined});
    fireEvent.change(screen.getByLabelText('Repair model'),{target:{value:'claude-sonnet'}});
    fireEvent.click(screen.getByRole('button',{name:'Request repair'}));
    expect(action).toHaveBeenLastCalledWith('repair',{model_profile_id:'claude-sonnet'});
  });
  it('disables acceptance of a stale base and escapes source content', () => {
    render(<RevisionDetail project={project} session={session} revision={revision} onRefresh={vi.fn()} onAction={vi.fn()} busy={false} />);
    expect(screen.getByRole('button', { name: 'Accept revision' })).toBeDisabled();
    expect(screen.getByText(/approved head has changed/i)).toBeInTheDocument();
    expect(screen.getByText('<script>alert(1)</script>')).toBeInTheDocument();
    expect(document.querySelector('script')).toBeNull();
  });
  it('sends changes as an immutable successor revision', async () => {
    const action = vi.fn().mockResolvedValue(undefined);
    render(<RevisionDetail project={{...project, approved_version_id: 'head-old'}} session={session} revision={revision} onRefresh={vi.fn()} onAction={action} busy={false} />);
    fireEvent.click(screen.getByRole('button', { name: 'Create revision' }));
    fireEvent.change(screen.getByLabelText('Revision rationale'), {target: {value: 'Clarify ownership'}});
    fireEvent.click(screen.getByRole('button', { name: 'Save new revision' }));
    await waitFor(() => expect(action).toHaveBeenCalledWith('revise', expect.objectContaining({ parent_revision: 1, rationale: 'Clarify ownership' })));
  });
  it('translates removal from the proposed diff into a deletion from the prior candidate', async () => {
    const action=vi.fn().mockResolvedValue(undefined);
    render(<RevisionDetail project={{...project,approved_version_id:'head-old'}} session={session} revision={revision} onRefresh={vi.fn()} onAction={action} busy={false}/>);
    fireEvent.click(screen.getByRole('button',{name:'Create revision'}));
    fireEvent.click(screen.getByRole('button',{name:'Remove additions 1'}));
    fireEvent.change(screen.getByLabelText('Revision rationale'),{target:{value:'Remove the unsupported hierarchy'}});
    fireEvent.click(screen.getByRole('button',{name:'Save new revision'}));
    await waitFor(()=>expect(action).toHaveBeenCalledWith('revise',expect.objectContaining({structured_changes:{additions:[],deletions:revision.additions}})));
  });
  it('renders backend revision history without requiring synthetic audit events', () => {
    render(<RevisionDetail project={project} session={session} revision={{...revision,history:[{revision:1,status:'validated',created_at:'2026-11-01T10:00:00Z'}]}} onRefresh={vi.fn()} onAction={vi.fn()} busy={false}/>);
    fireEvent.click(screen.getByRole('tab',{name:'History'}));
    expect(screen.getByText('Revision 1')).toBeInTheDocument();
  });
  it('requires separate clicks for submission, acceptance, and publication of the same bundle', async () => {
    const current={...project,approved_version_id:'head-old',review_policy_id:'policy'};
    let candidate:Revision={...revision};
    const writes:{path:string;body:Record<string,unknown>;headers:Headers}[]=[];
    vi.stubGlobal('fetch',vi.fn(async (path:string,options:RequestInit={})=>{
      const body=options.body ? JSON.parse(String(options.body)) : {};
      if(options.method==='POST') {
        writes.push({path,body,headers:new Headers(options.headers)});
        if(path.endsWith('/review-submissions'))candidate={...candidate,status:'in_review'};
        if(path.endsWith('/reviews'))candidate={...candidate,status:'approved',approval_ids:['approval-exact']};
        if(path.endsWith('/publications')) {candidate={...candidate,status:'published'};return new Response(JSON.stringify({id:'publication',status:'completed',new_version_id:'new-head'}));}
      }
      return new Response(JSON.stringify(path.endsWith('/projects/p')?current:candidate));
    }));
    render(<ProposalsView project={current} session={session} proposals={[candidate]} onRefresh={vi.fn().mockResolvedValue(undefined)} onSources={vi.fn()}/>);
    await screen.findByRole('button',{name:'Submit for review'});
    expect(writes).toHaveLength(0);
    expect(screen.getByRole('button',{name:'Accept revision'})).toBeDisabled();
    fireEvent.click(screen.getByRole('button',{name:'Submit for review'}));
    await waitFor(()=>expect(screen.getByLabelText('Review rationale')).toBeEnabled());
    expect(writes).toHaveLength(1);
    expect(writes[0].headers.get('If-Match')).toBe('1');
    expect(writes[0].body).toEqual({proposal_id:'proposal',revision:1,validation_run_id:'v',required_assessment_run_ids:['a']});
    fireEvent.change(screen.getByLabelText('Review rationale'),{target:{value:'I checked the evidence and exact validation bundle.'}});
    fireEvent.click(screen.getByRole('button',{name:'Accept revision'}));
    await waitFor(()=>expect(screen.getByRole('button',{name:'Publish version'})).toBeEnabled());
    expect(writes).toHaveLength(2);
    expect(writes[1].body).toEqual(expect.objectContaining({decision:'accept',revision:1,bundle_digest:'sha256:1234',validation_run_id:'v',required_assessment_run_ids:['a'],review_policy_id:'policy'}));
    fireEvent.click(screen.getByRole('button',{name:'Publish version'}));
    await screen.findByRole('button',{name:'Published'});
    expect(writes).toHaveLength(3);
    expect(writes[2].headers.get('Idempotency-Key')).toBeTruthy();
    expect(writes[2].body).toEqual({proposal_id:'proposal',revision:1,bundle_digest:'sha256:1234',approval_ids:['approval-exact'],expected_head:'head-old'});
  });
  it('offers repair only for failed validation and blocks pending publication',()=>{
    const current={...project,approved_version_id:'head-old'};
    const failed:Revision={...revision,status:'validation_failed',validation:{id:'v',status:'failed',profile:'rdfs',cases:[]}};
    const view=render(<RevisionDetail project={current} session={session} revision={failed} onRefresh={vi.fn()} onAction={vi.fn()} busy={false}/>);
    expect(screen.getByRole('button',{name:'Request repair'})).toBeEnabled();
    expect(screen.getByText(/At most two attempts are allowed/)).toBeInTheDocument();
    view.rerender(<RevisionDetail project={{...current,pending_publication_id:'pending'}} session={session} revision={failed} onRefresh={vi.fn()} onAction={vi.fn()} busy={false}/>);
    expect(screen.getByRole('button',{name:'Request repair'})).toBeDisabled();
    view.rerender(<RevisionDetail project={current} session={session} revision={{...failed,validation:{id:'v',status:'error',profile:'rdfs',cases:[]}}} onRefresh={vi.fn()} onAction={vi.fn()} busy={false}/>);
    expect(screen.queryByRole('button',{name:'Request repair'})).not.toBeInTheDocument();
  });
  it('requests a bounded exact-bundle repair and selects the unvalidated successor without automatic approval',async()=>{
    const current={...project,approved_version_id:'head-old'};
    const failed:Revision={...revision,status:'validation_failed',validation:{id:'v',status:'failed',profile:'rdfs',cases:[{id:'CQ-01',name:'Hierarchy expectation',status:'failed'}]}};
    const successor:Revision={...revision,revision:2,status:'draft',bundle_digest:'bundle-two',validation_run_id:null,assessment_run_ids:[],review_eligibility:{eligible:false,reasons:['Required validation has not passed for this exact bundle']}};
    const writes:{path:string;body:unknown;headers:Headers}[]=[];
    vi.stubGlobal('fetch',vi.fn(async(path:string,options:RequestInit={})=>{
      if(options.method==='POST')writes.push({path,body:JSON.parse(String(options.body)),headers:new Headers(options.headers)});
      if(path.endsWith('/projects/p'))return new Response(JSON.stringify(current));
      if(path.endsWith('/repair-jobs'))return new Response(JSON.stringify({job_id:'repair-job'}));
      if(path.endsWith('/jobs/repair-job'))return new Response(JSON.stringify({id:'repair-job',status:'succeeded',result:{proposal_id:'proposal',revision:2,bundle_digest:'bundle-two',repair_attempt:1}}));
      return new Response(JSON.stringify(path.endsWith('/revisions/2')?successor:failed));
    }));
    const refresh=vi.fn().mockResolvedValue(undefined);
    render(<ProposalsView project={current} session={session} proposals={[failed]} onRefresh={refresh} onSources={vi.fn()}/>);
    fireEvent.click(await screen.findByRole('button',{name:'Request repair'}));
    await screen.findByText('CANDIDATE REVISION 2');
    expect(screen.getByText(/Repair attempt 1 of 2 created revision 2/)).toBeInTheDocument();
    expect(screen.getByRole('button',{name:'Accept revision'})).toBeDisabled();
    expect(writes).toHaveLength(1);
    expect(writes[0].path).toBe('/api/v1/projects/p/repair-jobs');
    expect(writes[0].body).toEqual({proposal_id:'proposal',revision:1,bundle_digest:'sha256:1234'});
    expect(writes[0].headers.get('Idempotency-Key')).toBeTruthy();
    expect(refresh).toHaveBeenCalledOnce();
  });
});
