import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ExperimentsView } from './ExperimentsView';
import type { Experiment, Project, Proposal, ReviewDecision, Session } from '../../api/generated';

const project: Project = {id:'p',name:'Demo',domain:'demo',approved_version_id:null,corpus_snapshot_id:'corpus',scope_accepted:true,scope_digest:'scope'};
const session: Session = {actor:{kind:'human',subject:'reviewer',roles:['researcher','approver']},mode:'local',model_mode:'ollama'};
const pre: Experiment = {id:'pre/d',protocol_id:'model-pilot-v1',condition:'D',task_id:'demo-ownership',replicate:1,status:'waiting_human',phase:'pre_review',created_at:'2026-11-01',candidate_digest:'frozen-digest',candidate_ttl:'<https://example.org/Service> a <http://www.w3.org/2002/07/owl#Class> .',correction_seconds:null};
const proposal: Proposal = {id:'proposal-d',experiment_run_id:pre.id,revision:2,revision_id:'revision/d2',title:'Review D',status:'approved',base_version_id:null,bundle_digest:'reviewed-bundle',created_at:'2026-11-01'};
const review: ReviewDecision = {id:'human-review',proposal_id:proposal.id,revision:2,revision_id:proposal.revision_id,actor:{kind:'human',subject:'reviewer'},decision:'request_changes',rationale:'The source needs a clearer ownership relation.',bundle_digest:'reviewed-bundle',validation_run_id:'validation',required_assessment_run_ids:['assessment']};
const props = (experiments: Experiment[] = []) => ({project,session,experiments,proposals:[] as Proposal[],onRefresh:vi.fn().mockResolvedValue(undefined),onOpenProposal:vi.fn()});
const choosePilot = () => fireEvent.change(screen.getByLabelText('Experiment protocol'),{target:{value:'model-pilot-v1'}});
afterEach(() => vi.unstubAllGlobals());

describe('model pilot experiment workflow', () => {
  it('uses the selected protocol only after an explicit run and retains fixed synthetic task/replicate inputs', async () => {
    const writes: {path:string;body:unknown;headers:Headers}[] = [];
    vi.stubGlobal('fetch',vi.fn(async (path:string,options:RequestInit={}) => {
      if (options.method==='POST') {writes.push({path,body:JSON.parse(String(options.body)),headers:new Headers(options.headers)}); return new Response(JSON.stringify({job_id:'experiment-job'}));}
      return new Response(JSON.stringify({id:'experiment-job',status:'succeeded',result:{runs:[]}}));
    }));
    const view = props(); render(<ExperimentsView {...view}/>);
    expect(screen.getByRole('button',{name:'Run A–D demo'})).toBeEnabled();
    choosePilot();
    expect(writes).toHaveLength(0);
    fireEvent.click(screen.getByRole('button',{name:'Run A–D model pilot'}));
    await screen.findByText(/Model pilot runs recorded/);
    expect(writes).toHaveLength(1);
    expect(writes[0].path).toBe('/api/v1/projects/p/experiment-jobs');
    expect(writes[0].body).toEqual({protocol_id:'model-pilot-v1',condition:'all',task_ids:['demo-ownership'],replicate_ids:[1]});
    expect(writes[0].headers.get('Idempotency-Key')).toBeTruthy();
    expect(view.onRefresh).toHaveBeenCalledOnce();
  });

  it('stages D as a candidate without running checks, recording a review, or navigating automatically', async () => {
    const writes: {path:string;body:unknown}[] = [];
    vi.stubGlobal('fetch',vi.fn(async(path:string,options:RequestInit={}) => {
      if(options.method==='POST') {writes.push({path,body:options.body});return new Response(JSON.stringify({...proposal,revision:1,status:'draft'}));}
      return new Response(JSON.stringify({items:[],next_cursor:null}));
    }));
    const view=props([pre]);render(<ExperimentsView {...view}/>);choosePilot();
    fireEvent.click(screen.getByRole('button',{name:'Inspect experiment pre/d'}));
    expect(writes).toHaveLength(0);
    fireEvent.click(screen.getByRole('button',{name:'Stage condition D candidate'}));
    await screen.findByText(/Candidate revision 1 staged/);
    expect(writes).toEqual([{path:'/api/v1/projects/p/experiments/pre%2Fd/proposal',body:undefined}]);
    expect(view.onOpenProposal).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button',{name:'Open candidate revision 1'}));
    expect(view.onOpenProposal).toHaveBeenCalledWith('proposal-d');
  });

  it('links a fetched human review into a new post record while keeping absent correction time unavailable', async () => {
    const writes: {path:string;body:unknown}[] = [];
    const post: Experiment = {...pre,id:'post-review',phase:'post_review',status:'human_reviewed',parent_run_id:pre.id,linked_review_id:review.id,review_status:review.decision,time_to_acceptance_right_censored:true};
    vi.stubGlobal('fetch',vi.fn(async(path:string,options:RequestInit={}) => {
      if(options.method==='POST') {writes.push({path,body:JSON.parse(String(options.body))});return new Response(JSON.stringify(post));}
      expect(path).toBe('/api/v1/projects/p/reviews?revision_id=revision%2Fd2');
      return new Response(JSON.stringify({items:[review],next_cursor:null}));
    }));
    const view=props([pre]);render(<ExperimentsView {...view} proposals={[proposal]}/>);choosePilot();
    fireEvent.click(screen.getByRole('button',{name:'Inspect experiment pre/d'}));
    await screen.findByLabelText('Recorded human decision');
    expect(writes).toHaveLength(0);
    fireEvent.change(screen.getByLabelText('Recorded human decision'),{target:{value:review.id}});
    expect(screen.getByText(review.rationale)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button',{name:'Link review as new post-review record'}));
    await screen.findByText(/A separate post-review record was saved/);
    expect(writes).toEqual([{path:'/api/v1/projects/p/experiments/pre%2Fd/review-results',body:{review_id:'human-review'}}]);
    expect(screen.getByText(/no complete timer ledger was supplied/)).toBeInTheDocument();
    expect(screen.getByText(/right-censored/)).toBeInTheDocument();
    expect(pre.status).toBe('waiting_human');
    expect(screen.getByRole('button',{name:'Inspect experiment pre/d'})).toBeInTheDocument();
  });

  it('never offers review linking to a service identity', async () => {
    vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response(JSON.stringify({items:[review],next_cursor:null}))));
    render(<ExperimentsView {...props([pre])} proposals={[proposal]} session={{...session,actor:{...session.actor,kind:'service'}}}/>);choosePilot();
    fireEvent.click(screen.getByRole('button',{name:'Inspect experiment pre/d'}));
    fireEvent.change(await screen.findByLabelText('Recorded human decision'),{target:{value:review.id}});
    expect(screen.getByRole('button',{name:'Link review as new post-review record'})).toBeDisabled();
    expect(screen.getByText(/authorized human approver session is required/)).toBeInTheDocument();
  });

  it('keeps demo/model protocols and pre/post phase metrics separate', async () => {
    const post:Experiment={...pre,id:'post',phase:'post_review',status:'human_reviewed',strict_fitness:1,vocabulary_coverage:1};
    const demo:Experiment={...pre,id:'demo',protocol_id:'demo-v1',phase:'automated'};
    render(<ExperimentsView {...props([{...pre,strict_fitness:0,vocabulary_coverage:0},post,demo])}/>);
    expect(screen.getByRole('button',{name:'Inspect experiment demo'})).toBeInTheDocument();
    expect(screen.queryByRole('button',{name:'Inspect experiment pre/d'})).not.toBeInTheDocument();
    choosePilot();
    expect(screen.queryByRole('button',{name:'Inspect experiment demo'})).not.toBeInTheDocument();
    expect(screen.getAllByText('Choose one phase to compare')).toHaveLength(2);
    fireEvent.change(screen.getByLabelText('Filter experiment phase'),{target:{value:'post_review'}});
    expect(screen.queryByRole('button',{name:'Inspect experiment pre/d'})).not.toBeInTheDocument();
    expect(screen.getByRole('button',{name:'Inspect experiment post'})).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByText('Choose one phase to compare')).not.toBeInTheDocument());
  });
});
