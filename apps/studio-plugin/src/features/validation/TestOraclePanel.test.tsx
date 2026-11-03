import { modelProfileFixture, projectFixture, revisionFixture, suiteFixture } from '../../test-fixtures';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { TestOraclePanel } from './TestOraclePanel';
import type { Project, Revision, Session, TestSuite } from '../../api/generated';

const project:Project=projectFixture({id:'p',name:'Demo',domain:'demo',approved_version_id:null,corpus_snapshot_id:'corpus',scope_accepted:true,scope_digest:'scope'});
const session:Session={actor:{subject:'human',kind:'human',roles:['researcher','reviewer']},mode:'local',model_mode:'local'};
const revision:Revision=revisionFixture({id:'proposal',revision_id:'revision-one',title:'Seed',revision:1,status:'draft',base_version_id:null,bundle_digest:'bundle-one',created_at:'',rationale:'Grounded seed',additions:[],deletions:[],evidence:[]});
const suite:TestSuite=suiteFixture({id:'suite',status:'needs_review',digest:'suite-digest',revision_id:'revision-one',bundle_digest:'bundle-one',tests:[{test_id:'negative-ask',kind:'ask',query:'ASK { ?service a <https://example.org/Team> }',expected:false,rationale:'Services and teams are separate.',oracle_status:'needs_review'}]});
afterEach(()=>vi.unstubAllGlobals());

describe('human test oracle',()=>{
  it('keeps historical fixture hashes inspectable without inventing an artifact link',async()=>{
    const legacy={...suite,fixture_artifacts:{'negative-ask':{sha256:'legacy-fixture-hash',byte_length:12,media_type:'text/turtle',schema_version:1}}};
    vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify({items:[legacy],next_cursor:null}))));
    render(<TestOraclePanel project={project} session={session} revision={revision} onRefresh={vi.fn()} onOpenProposal={vi.fn()}/>);
    const artifact=await screen.findByLabelText('Fixture artifact for negative-ask');
    expect(artifact).toHaveTextContent('legacy-fixture-hash');
    expect(screen.queryByRole('link',{name:'Open immutable fixture artifact'})).not.toBeInTheDocument();
    expect(artifact).toHaveTextContent('Artifact link unavailable for this historical record.');
  });

  it('exposes candidate coverage gaps, linked inputs and exact SHACL violations before an oracle decision',async()=>{
    const detailed={...suite,generator:{mode:'deterministic_candidate_derived',version:'candidate-specs-v1',oracle_policy:'No engine output defines expectations.'},coverage_gaps:[{code:'scenario_unavailable',detail:'Boundary coverage needs a human oracle.'}],fixture_artifacts:{'shape-test':{id:'fixture-artifact',sha256:'fixture-hash',media_type:'text/turtle'}},tests:[{test_id:'shape-test',kind:'shacl',scenario:'missing_data',expected_conforms:false,expected_violations:[{focusNode:'https://example.org/focus',path:'https://example.org/owner',sourceShape:'https://example.org/OwnerShape',severity:'http://www.w3.org/ns/shacl#Violation'}],rationale:'Missing owner must violate the minimum count.',oracle_status:'needs_review',question_ids:['ownership-question'],change_ids:['addition-17'],assumptions:['This is a synthetic fixture.'],oracle_source:'Human-reviewed ownership requirement',target_ontology_sha256:'candidate-hash',fixture_sha256:'fixture-hash',fixtures_ttl:'<https://example.org/focus> a <https://example.org/Service> .'}]};
    const writes:string[]=[];
    vi.stubGlobal('fetch',vi.fn(async(path:string,options:RequestInit={})=>{if(options.method==='POST')writes.push(path);return new Response(JSON.stringify({items:[detailed],next_cursor:null}));}));
    render(<TestOraclePanel project={project} session={session} revision={revision} onRefresh={vi.fn()} onOpenProposal={vi.fn()}/>);
    await screen.findByText('shape-test');
    expect(screen.getByText('deterministic candidate derived')).toBeInTheDocument();
    expect(screen.getByText('Boundary coverage needs a human oracle.')).toBeInTheDocument();
    expect(screen.getByText('missing data')).toBeInTheDocument();
    expect(screen.getByText('ownership-question')).toBeInTheDocument();
    expect(screen.getByText('addition-17')).toBeInTheDocument();
    expect(screen.getByText('This is a synthetic fixture.')).toBeInTheDocument();
    expect(screen.getByText('Human-reviewed ownership requirement')).toBeInTheDocument();
    const violations=screen.getByLabelText('Expected SHACL violations for shape-test');
    for(const value of ['https://example.org/focus','https://example.org/owner','https://example.org/OwnerShape','http://www.w3.org/ns/shacl#Violation'])expect(violations).toHaveTextContent(value);
    expect(screen.getByLabelText('Fixture artifact for shape-test')).toHaveTextContent('fixture-artifact');
    expect(screen.getByText('candidate-hash')).toBeInTheDocument();
    expect(screen.getByText('false')).toBeInTheDocument();
    expect(writes).toEqual([]);
  });
  it('shows typed SELECT rows with their exact comparison semantics',async()=>{
    const rows={...suite,tests:[{test_id:'literal-test',kind:'select_rows',query:'SELECT ?label WHERE { ?s ?p ?label }',expected:[{label:{kind:'literal',value:'Service',datatype:'http://www.w3.org/1999/02/22-rdf-syntax-ns#langString',lang:'en'}}],comparison:'contains',rationale:'Preserve the exact label and language.',oracle_status:'needs_review'}]};
    vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify({items:[rows],next_cursor:null}))));
    render(<TestOraclePanel project={project} session={session} revision={revision} onRefresh={vi.fn()} onOpenProposal={vi.fn()}/>);
    const expected=await screen.findByLabelText('Expected result for literal-test');
    expect(expected).toHaveTextContent('"kind": "literal"');
    expect(expected).toHaveTextContent('"lang": "en"');
    expect(expected).toHaveTextContent('langString');
    expect(screen.getByText('contains')).toBeInTheDocument();
  });
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

it('binds model test generation to the selected profile and candidate digest and preserves failure',async()=>{
  const writes:unknown[]=[];
  vi.stubGlobal('fetch',vi.fn(async(path:string,options:RequestInit={})=>{
    if(path.endsWith('/model-profiles'))return new Response(JSON.stringify({items:[modelProfileFixture(),modelProfileFixture({id:'tests-profile',is_default:false,provider:'anthropic',model:'claude-sonnet-4-6'})],next_cursor:null}));
    if(path.endsWith('/test-generation-jobs')){writes.push(JSON.parse(options.body as string));return new Response(JSON.stringify({job_id:'failed-job'}));}
    if(path.endsWith('/jobs/failed-job'))return new Response(JSON.stringify({status:'failed',error:'Model schema rejected'}));
    return new Response(JSON.stringify({items:[],next_cursor:null}));
  }));
  render(<TestOraclePanel project={project} session={session} revision={revision} onRefresh={vi.fn()} onOpenProposal={vi.fn()}/>);
  fireEvent.change(screen.getByLabelText('Test generator'),{target:{value:'model'}});
  await screen.findByRole('option',{name:/claude-sonnet-4-6/});
  fireEvent.change(screen.getByLabelText('Test generation model'),{target:{value:'tests-profile'}});
  fireEvent.click(screen.getByRole('button',{name:'Suggest development tests'}));
  await screen.findByText('Model schema rejected');
  expect(writes).toEqual([{proposal_id:revision.id,revision:revision.revision,generator_mode:'model',model_profile_id:'tests-profile',bundle_digest:revision.bundle_digest}]);
  expect(screen.queryByText(/Test suggestions are ready/)).not.toBeInTheDocument();
});
