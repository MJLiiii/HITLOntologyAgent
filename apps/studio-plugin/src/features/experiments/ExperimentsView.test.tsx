import { experimentFixture, projectFixture, reviewFixture, revisionFixture } from '../../test-fixtures';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ExperimentsView } from './ExperimentsView';
import type { Experiment, Project, Proposal, ReviewDecision, Session } from '../../api/generated';

const project: Project = projectFixture({id:'p',name:'Demo',domain:'demo',approved_version_id:null,corpus_snapshot_id:'corpus',scope_accepted:true,scope_digest:'scope'});
const session: Session = {actor:{kind:'human',subject:'reviewer',roles:['researcher','approver']},mode:'local',model_mode:'model'};
const pre: Experiment = experimentFixture({id:'pre/d',protocol_id:'model-pilot-v1',condition:'D',task_id:'demo-ownership',replicate:1,status:'waiting_human',phase:'pre_review',created_at:'2026-11-01',candidate_digest:'frozen-digest',candidate_ttl:'<https://example.org/Service> a <http://www.w3.org/2002/07/owl#Class> .',correction_seconds:null});
const proposal: Proposal = revisionFixture({id:'proposal-d',experiment_run_id:pre.id,revision:2,revision_id:'revision/d2',title:'Review D',status:'approved',base_version_id:null,bundle_digest:'reviewed-bundle',created_at:'2026-11-01'});
const review: ReviewDecision = reviewFixture({id:'human-review',proposal_id:proposal.id,revision:2,revision_id:proposal.revision_id,actor:{kind:'human',subject:'reviewer',roles:['reviewer']},decision:'request_changes',rationale:'The source needs a clearer ownership relation.',bundle_digest:'reviewed-bundle',validation_run_id:'validation',required_assessment_run_ids:['assessment']});
const props = (experiments: Experiment[] = []) => ({project,session,experiments,proposals:[] as Proposal[],onRefresh:vi.fn().mockResolvedValue(undefined),onOpenProposal:vi.fn()});
const choosePilot = () => fireEvent.change(screen.getByLabelText('Experiment protocol'),{target:{value:'model-pilot-v1'}});
const chooseRegistered = () => fireEvent.change(screen.getByLabelText('Experiment protocol'),{target:{value:'synthetic-task-v1'}});
afterEach(() => vi.unstubAllGlobals());

describe('model pilot experiment workflow', () => {
  it('loads every registration page before offering the complete task selector',async()=>{
    const tasks=['first','later'].map(name=>({id:`registration-${name}`,task_id:`task-${name}`,instruction:`Synthetic task ${name}.`,revision:2,proposal_id:proposal.id,revision_id:proposal.revision_id,bundle_digest:proposal.bundle_digest,registration_digest:`digest-${name}`,protocol_id:'synthetic-task-v1',packet:{id:`packet-${name}`,sha256:`hash-${name}`}}));
    const reads:string[]=[];
    vi.stubGlobal('fetch',vi.fn(async(path:string)=>{reads.push(path);const later=new URL(path,'http://localhost').searchParams.has('cursor');return new Response(JSON.stringify({items:[tasks[later?1:0]],next_cursor:later?null:'task/page-2'}));}));
    render(<ExperimentsView {...props()}/>);chooseRegistered();
    await screen.findByRole('option',{name:'task-later'});
    expect(screen.getByRole('option',{name:'task-first'})).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Registered synthetic task'),{target:{value:'registration-later'}});
    expect(screen.getByText('digest-later')).toBeInTheDocument();
    expect(reads).toEqual(['/api/v1/projects/p/synthetic-tasks','/api/v1/projects/p/synthetic-tasks?cursor=task%2Fpage-2']);
  });

  it('shows a historical packet hash without constructing a link from a missing artifact ID',async()=>{
    const task={id:'legacy-registration',task_id:'legacy-task',instruction:'Inspect synthetic ownership.',proposal_id:proposal.id,revision:2,revision_id:proposal.revision_id,bundle_digest:proposal.bundle_digest,registration_digest:'legacy-registration-digest',protocol_id:'synthetic-task-v1',packet:{sha256:'legacy-packet-hash',byte_length:12,media_type:'application/json',schema_version:1}};
    vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify({items:[task]}))));
    render(<ExperimentsView {...props()}/>);chooseRegistered();
    await screen.findByRole('option',{name:'legacy-task'});
    fireEvent.change(screen.getByLabelText('Registered synthetic task'),{target:{value:'legacy-registration'}});
    expect(screen.getByText('legacy-packet-hash')).toBeInTheDocument();
    expect(screen.queryByRole('link',{name:'Inspect immutable task packet'})).not.toBeInTheDocument();
    expect(screen.getByText('Artifact link unavailable for this historical record.')).toBeInTheDocument();
  });

  it('registers the chosen exact revision only after a human supplies a task identity and instruction',async()=>{
    const task={id:'registration',task_id:'ownership-task',instruction:'Inspect service ownership evidence.',proposal_id:proposal.id,revision:2,revision_id:proposal.revision_id,bundle_digest:proposal.bundle_digest,registration_digest:'packet-digest',protocol_id:'synthetic-task-v1',packet:{id:'packet',sha256:'packet-hash'}};
    const writes:{path:string;body:unknown}[]=[];
    vi.stubGlobal('fetch',vi.fn(async(path:string,options:RequestInit={})=>{
      if(options.method==='POST'){writes.push({path,body:JSON.parse(String(options.body))});return new Response(JSON.stringify(task));}
      return new Response(JSON.stringify({items:[]}));
    }));
    render(<ExperimentsView {...props()} proposals={[proposal]}/>);chooseRegistered();
    await screen.findByLabelText('Registered synthetic task');
    fireEvent.change(screen.getByLabelText('Candidate revision for task'),{target:{value:proposal.id}});
    fireEvent.change(screen.getByLabelText('Synthetic task ID'),{target:{value:'ownership-task'}});
    fireEvent.change(screen.getByLabelText('Task instruction'),{target:{value:'Inspect service ownership evidence.'}});
    expect(writes).toEqual([]);
    fireEvent.click(screen.getByRole('button',{name:'Register frozen synthetic task'}));
    await screen.findByText(/Synthetic task registered/);
    expect(writes).toEqual([{path:'/api/v1/projects/p/synthetic-tasks',body:{proposal_id:proposal.id,revision:2,bundle_digest:proposal.bundle_digest,task_id:'ownership-task',instruction:'Inspect service ownership evidence.'}}]);
    expect(screen.getByLabelText('Registered synthetic task')).toHaveValue('registration');
    expect(screen.getByText('packet-digest')).toBeInTheDocument();
  });

  it('executes the exact registered packet and shows only the selected task in comparisons and D review',async()=>{
    const tasks=['one','two'].map(id=>({id:`registration-${id}`,task_id:`task-${id}`,instruction:`Synthetic task ${id}.`,revision:2,proposal_id:proposal.id,revision_id:proposal.revision_id,bundle_digest:proposal.bundle_digest,registration_digest:`digest-${id}`,protocol_id:'synthetic-task-v1',packet:{id:`packet-${id}`,sha256:`hash-${id}`}}));
    const writes:{path:string;body:unknown;headers:Headers}[]=[];
    vi.stubGlobal('fetch',vi.fn(async(path:string,options:RequestInit={})=>{
      if(options.method==='POST'){writes.push({path,body:JSON.parse(String(options.body)),headers:new Headers(options.headers)});return new Response(JSON.stringify({job_id:'registered-job'}));}
      if(path.endsWith('/jobs/registered-job'))return new Response(JSON.stringify({status:'succeeded',result:{runs:[]}}));
      return new Response(JSON.stringify({items:tasks}));
    }));
    const runs=tasks.map((task,index)=>({...pre,id:`run-${index}`,protocol_id:'synthetic-task-v1',task_id:task.task_id,strict_fitness:index,vocabulary_coverage:index}));
    render(<ExperimentsView {...props(runs)}/>);chooseRegistered();
    await screen.findByRole('option',{name:'task-one'});
    expect(screen.getByRole('button',{name:'Run A–D registered task'})).toBeDisabled();
    fireEvent.change(screen.getByLabelText('Registered synthetic task'),{target:{value:'registration-two'}});
    expect(screen.queryByRole('button',{name:'Inspect experiment run-0'})).not.toBeInTheDocument();
    expect(screen.getByRole('button',{name:'Inspect experiment run-1'})).toBeInTheDocument();
    expect(screen.queryByText('50%')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button',{name:'Run A–D registered task'}));
    await screen.findByText(/Registered task runs recorded/);
    expect(writes).toHaveLength(1);
    expect(writes[0].path).toBe('/api/v1/projects/p/synthetic-task-jobs');
    expect(writes[0].body).toEqual({registration_id:'registration-two',registration_digest:'digest-two',condition:'all',replicate_ids:[1]});
    expect(writes[0].headers.get('Idempotency-Key')).toBeTruthy();
    fireEvent.click(screen.getByRole('button',{name:'Inspect experiment run-1'}));
    expect(screen.getByRole('button',{name:'Stage condition D candidate'})).toBeInTheDocument();
  });

  it.each([
    ['pending scope',{...project,scope_accepted:false},session],
    ['service identity',project,{...session,actor:{...session.actor,kind:'service'}}],
  ])('does not register a synthetic task with %s',async(_label,currentProject,currentSession)=>{
    vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify({items:[]}))));
    render(<ExperimentsView {...props()} project={currentProject as Project} session={currentSession as Session} proposals={[proposal]}/>);chooseRegistered();
    await screen.findByLabelText('Registered synthetic task');
    expect(screen.getByRole('button',{name:'Register frozen synthetic task'})).toBeDisabled();
  });
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
