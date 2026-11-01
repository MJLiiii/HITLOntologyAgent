import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { TestOraclePanel } from './TestOraclePanel';
import type { Project, Revision, Session, TestSuite } from '../../api/generated';

const project:Project={id:'p',name:'Demo',domain:'demo',approved_version_id:null,corpus_snapshot_id:'corpus',scope_accepted:true,scope_digest:'scope'};
const session:Session={actor:{subject:'human',kind:'human',roles:['researcher','reviewer']},mode:'local',model_mode:'local'};
const revision:Revision={id:'proposal',revision_id:'revision-one',title:'Seed',revision:1,status:'draft',base_version_id:null,bundle_digest:'bundle-one',created_at:'',rationale:'Grounded seed',additions:[],deletions:[],evidence:[]};
const suite:TestSuite={id:'suite',status:'needs_review',digest:'suite-digest',revision_id:'revision-one',bundle_digest:'bundle-one',tests:[{test_id:'negative-ask',kind:'ask',query:'ASK { ?service a <https://example.org/Team> }',expected:false,rationale:'Services and teams are separate.',oracle_status:'needs_review'}]};
afterEach(()=>vi.unstubAllGlobals());

describe('human test oracle',()=>{
  it('renders negative ASK as non-entailment and requires explicit rationale and acceptance',async()=>{
    let currentSuite={...suite};
    const decisions:Record<string,unknown>[]=[];
    vi.stubGlobal('fetch',vi.fn(async(path:string,options:RequestInit={})=>{
      if(path.endsWith('/test-oracle-decisions')) {decisions.push(JSON.parse(String(options.body)));currentSuite={...currentSuite,status:'accepted'};return new Response(JSON.stringify({...revision,revision:2,revision_id:'revision-two',bundle_digest:'bundle-two',status:'draft'}));}
      if(path.endsWith('/test-suites'))return new Response(JSON.stringify({items:[currentSuite],next_cursor:null}));
      if(path.endsWith('/proposals'))return new Response(JSON.stringify({items:[revision],next_cursor:null}));
      return new Response(JSON.stringify(project));
    }));
    const onRefresh=vi.fn().mockResolvedValue(undefined), onOpen=vi.fn();
    render(<TestOraclePanel project={project} session={session} revision={revision} onRefresh={onRefresh} onOpenProposal={onOpen}/>);
    await screen.findByText('negative-ask');
    expect(screen.getByText(/does not prove logical negation/)).toBeInTheDocument();
    expect(screen.getByText('false')).toBeInTheDocument();
    expect(screen.getByRole('button',{name:'Accept test expectations'})).toBeDisabled();
    expect(decisions).toHaveLength(0);
    fireEvent.change(screen.getByLabelText('Oracle decision rationale'),{target:{value:'The evidence distinguishes services from teams.'}});
    fireEvent.click(screen.getByRole('button',{name:'Accept test expectations'}));
    await waitFor(()=>expect(onOpen).toHaveBeenCalledWith('proposal'));
    expect(onRefresh).toHaveBeenCalledOnce();
    expect(decisions).toEqual([{test_suite_id:'suite',test_suite_digest:'suite-digest',decision:'accept',rationale:'The evidence distinguishes services from teams.'}]);
    expect(screen.getByRole('status')).toHaveTextContent('successor revision 2');
  });
  it('generates suggestions without automatically deciding their expected results',async()=>{
    let generated=false;
    const writes:string[]=[];
    vi.stubGlobal('fetch',vi.fn(async(path:string,options:RequestInit={})=>{
      if(options.method==='POST')writes.push(path);
      if(path.endsWith('/test-generation-jobs')){generated=true;return new Response(JSON.stringify({job_id:'job'}));}
      if(path.endsWith('/jobs/job'))return new Response(JSON.stringify({id:'job',status:'succeeded',result:suite}));
      return new Response(JSON.stringify({items:generated?[suite]:[],next_cursor:null}));
    }));
    render(<TestOraclePanel project={project} session={session} revision={revision} onRefresh={vi.fn()} onOpenProposal={vi.fn()}/>);
    await waitFor(()=>expect(screen.getByRole('button',{name:'Suggest development tests'})).toBeEnabled());
    fireEvent.click(screen.getByRole('button',{name:'Suggest development tests'}));
    await screen.findByText('negative-ask');
    expect(writes).toEqual(['/api/v1/projects/p/test-generation-jobs']);
    expect(screen.getByRole('button',{name:'Accept test expectations'})).toBeDisabled();
  });
});
