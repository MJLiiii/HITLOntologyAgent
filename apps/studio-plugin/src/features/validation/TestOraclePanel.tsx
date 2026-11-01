import { useEffect, useState } from 'react';
import type { Project, Revision, Session, TestSpec, TestSuite } from '../../api/generated';
import type { OracleDecision, TestGenerationRequest } from '../../api/openapi';
import { errorMessage, list, operation, runJob } from '../../api/client';
import { Badge, ErrorNotice, short } from '../../components/ui';
import { Icon } from '../../components/Icons';

function GeneratorDetails({suite}:{suite:TestSuite}) {
  return <div className="oracle-generator">{suite.generator&&<><p>Generator: <strong>{suite.generator.mode.replaceAll('_',' ')}</strong>{suite.generator.version&&<> · {suite.generator.version}</>}</p>{suite.generator.oracle_policy&&<p>{suite.generator.oracle_policy}</p>}{suite.generator.implementation_sha256&&<details><summary>Generator identity</summary><code>{suite.generator.implementation_sha256}</code></details>}</>}
    {!!suite.coverage_gaps?.length&&<div className="notice notice-info"><div><strong>Coverage gaps</strong><ul>{suite.coverage_gaps.map((gap,index)=><li key={`${gap.code}-${index}`}><span>{gap.detail}</span> <code>{gap.code}</code></li>)}</ul><p>Missing scenarios have no accepted oracle. This suite does not establish complete coverage.</p></div></div>}
  </div>;
}

function OracleDetails({test,fixture,base}:{test:TestSpec;fixture?:NonNullable<TestSuite['fixture_artifacts']>[string];base:string}) {
  return <div className="oracle-inputs"><dl>
    {test.scenario&&<><dt>Scenario</dt><dd>{test.scenario.replaceAll('_',' ')}</dd></>}
    {!!test.question_ids?.length&&<><dt>Competency questions</dt><dd>{test.question_ids.map(id=><code key={id}>{id}</code>)}</dd></>}
    {!!test.change_ids?.length&&<><dt>Candidate changes</dt><dd>{test.change_ids.map(id=><code key={id}>{id}</code>)}</dd></>}
    {test.oracle_source&&<><dt>Oracle source</dt><dd>{test.oracle_source}</dd></>}
    {test.comparison&&test.kind==='select_rows'&&<><dt>Row comparison</dt><dd>{test.comparison}</dd></>}
    {test.inference_mode&&<><dt>Inference mode</dt><dd>{test.inference_mode}</dd></>}
    {test.target_ontology_sha256&&<><dt>Candidate SHA-256</dt><dd><code>{test.target_ontology_sha256}</code></dd></>}
    {test.fixture_sha256&&<><dt>Fixture SHA-256</dt><dd><code>{test.fixture_sha256}</code></dd></>}
  </dl>
    {!!test.assumptions?.length&&<div><strong>Assumptions to review</strong><ul>{test.assumptions.map((assumption,index)=><li key={index}>{assumption}</li>)}</ul></div>}
    {test.kind==='shacl'&&<div className="oracle-violations"><strong>Expected SHACL violation signatures</strong>{test.expected_violations===undefined?<p>No exact violation signatures supplied; only the conformance expectation is checked.</p>:<pre aria-label={`Expected SHACL violations for ${test.test_id}`}>{JSON.stringify(test.expected_violations,null,2)}</pre>}</div>}
    {fixture&&<details><summary>Bound fixture artifact</summary><div aria-label={`Fixture artifact for ${test.test_id}`}>{fixture.id?<a href={`/api/v1${base}/artifacts/${encodeURIComponent(fixture.id)}`} target="_blank" rel="noreferrer">Open immutable fixture artifact</a>:<span>Artifact link unavailable for this historical record.</span>}<pre>{JSON.stringify(fixture,null,2)}</pre></div></details>}
  </div>;
}

export function TestOraclePanel({project,session,revision,onRefresh,onOpenProposal}: {project:Project;session:Session;revision:Revision;onRefresh:()=>Promise<void>;onOpenProposal:(id:string)=>void}) {
  const [suites,setSuites]=useState<TestSuite[]>([]);
  const [rationale,setRationale]=useState('');
  const [busy,setBusy]=useState(false);
  const [loading,setLoading]=useState(true);
  const [stage,setStage]=useState('');
  const [error,setError]=useState('');
  const [notice,setNotice]=useState('');
  const [successor,setSuccessor]=useState<number|null>(null);
  const base=`/projects/${encodeURIComponent(project.id)}`;
  const relevant=suites.filter(suite=>suite.revision_id===revision.revision_id || suite.bundle_digest===revision.bundle_digest);
  const human=session.actor.kind==='human';
  const current=!revision.stale && revision.base_version_id===project.approved_version_id && !['published','rejected'].includes(revision.status);
  const canDecide=human && session.actor.roles.includes('reviewer') && current;
  useEffect(()=>{
    let active=true;setLoading(true);setError('');setRationale('');
    list('GET /api/v1/projects/{p}/test-suites',{path:{p:project.id}}).then(result=>{if(active)setSuites(result);}).catch(err=>{if(active)setError(errorMessage(err));}).finally(()=>{if(active)setLoading(false);});
    return()=>{active=false;};
  },[base,revision.revision_id,revision.bundle_digest]);
  async function generate() {
    setBusy(true);setError('');setNotice('');setSuccessor(null);setStage('Generating development test suggestions');
    try {
      await runJob('POST /api/v1/projects/{p}/test-generation-jobs',{path:{p:project.id},body:{proposal_id:revision.id,revision:revision.revision} satisfies TestGenerationRequest},setStage);
      setSuites(await list('GET /api/v1/projects/{p}/test-suites',{path:{p:project.id}}));
      setNotice('Test suggestions are ready for human review. No expectation has been accepted or added to the candidate.');
    }catch(err){setError(errorMessage(err));}finally{setBusy(false);}
  }
  async function decide(suite:TestSuite,decision:'accept'|'reject') {
    setBusy(true);setError('');setNotice('');setStage('Recording oracle decision');
    try {
      const [currentProject,latestProposals,currentSuites]=await Promise.all([operation('GET /api/v1/projects/{p}',{path:{p:project.id}}),list('GET /api/v1/projects/{p}/proposals',{path:{p:project.id}}),list('GET /api/v1/projects/{p}/test-suites',{path:{p:project.id}})]);
      const latest=latestProposals.find(proposal=>proposal.id===revision.id);
      const currentSuite=currentSuites.find(value=>value.id===suite.id);
      if(currentProject.approved_version_id!==project.approved_version_id || latest?.revision!==revision.revision || latest.bundle_digest!==revision.bundle_digest || currentSuite?.digest!==suite.digest || currentSuite.status!=='needs_review') {
        await onRefresh();setSuites(currentSuites);throw new Error('The candidate, approved head, or test suite changed. Review the refreshed content before deciding.');
      }
      const result=await operation('POST /api/v1/projects/{p}/test-oracle-decisions',{path:{p:project.id},body:{test_suite_id:suite.id,test_suite_digest:suite.digest,decision,rationale:rationale.trim()} satisfies OracleDecision});
      setSuites(await list('GET /api/v1/projects/{p}/test-suites',{path:{p:project.id}}));
      await onRefresh();setRationale('');
      if(decision==='accept' && 'revision' in result) {
        setSuccessor(result.revision);
        setNotice(`Test expectations accepted in successor revision ${result.revision}. Required checks remain intact. Validation, assessment, and release review must run again for the new bundle.`);
        onOpenProposal(result.id);
      }else setNotice('The suggested test suite was rejected. The candidate and its existing required checks are unchanged.');
    }catch(err){setError(errorMessage(err));}finally{setBusy(false);}
  }
  return <section className="panel oracle-panel"><div className="report-heading"><div className="report-icon"><Icon name="shield" size={23}/></div><div><span className="card-eyebrow">DEVELOPMENT TESTS · HUMAN ORACLE</span><h3>Review the expectation before testing the answer</h3><p>Suggested tests are untrusted until a human accepts their expected results.</p></div><button className="button button-secondary small" disabled={busy||loading||!human||!session.actor.roles.includes('researcher')||!current} onClick={()=>void generate()}><Icon name="spark" size={15}/>Suggest development tests</button></div>
    <div className="oracle-body">{error&&<ErrorNotice message={error}/>} {notice&&<div className="notice notice-info" role="status"><span>{notice}</span>{successor&&<button className="text-button small" onClick={()=>onOpenProposal(revision.id)}>Open revision {successor}<Icon name="chevron" size={14}/></button>}</div>}
      <div className="oracle-principle"><Icon name="validation" size={17}/><p>Existing required checks are preserved. Accepting a test suite creates a new immutable candidate; it does not validate, approve, or publish that candidate.</p></div>
      {(busy||loading)&&<div role="status" className="inline-loading"><span className="spinner"/>{loading?'Loading test suggestions':stage.replaceAll('_',' ')}…</div>}
      {!loading&&!relevant.length&&<p className="muted small oracle-empty">No additional test suite has been proposed for revision {revision.revision}. Suggest development tests to inspect their query, rationale, and expected result.</p>}
      {relevant.map(suite=><article className="oracle-suite" key={suite.id}><div className="section-heading"><h4>Suggested suite <code title={suite.digest}>{short(suite.digest)}</code></h4><Badge status={suite.status}/></div><GeneratorDetails suite={suite}/>{suite.tests.map(test=><details className="oracle-test" key={test.test_id} open><summary><span className="test-kind">{test.kind.replace('_',' ').toUpperCase()}</span><strong>{test.test_id}</strong><Badge status={suite.status==='needs_review'?'needs_review':suite.status}>{suite.status==='needs_review'?'Expectation needs review':suite.status}</Badge></summary><div className="oracle-test-content"><p>{test.rationale}</p><OracleDetails test={test} fixture={suite.fixture_artifacts?.[test.test_id]} base={base}/>{test.query&&<pre aria-label={`Query for ${test.test_id}`}>{test.query}</pre>}<div className="expected-result"><strong>Expected result</strong><code aria-label={`Expected result for ${test.test_id}`}>{JSON.stringify(test.kind==='shacl'?test.expected_conforms:test.expected,null,2)??'Not specified'}</code></div>{test.kind==='ask'&&test.expected===false&&<p className="negative-ask-note">A negative ASK expectation means the query should find no matching entailment in this test graph. It does not prove logical negation or the absence of a fact in the world.</p>}{test.fixtures_ttl&&<details><summary>Inspect test fixture</summary><pre>{test.fixtures_ttl}</pre></details>}{!!test.evidence_ids?.length&&<p className="small muted">Evidence: {test.evidence_ids.map(short).join(', ')}</p>}</div></details>)}
        {suite.status==='needs_review'&&<div className="oracle-decision"><label htmlFor={`oracle-rationale-${suite.id}`}>Oracle decision rationale</label><textarea id={`oracle-rationale-${suite.id}`} value={rationale} onChange={e=>setRationale(e.target.value)} rows={3} maxLength={4000} placeholder="Explain why these expected results are justified by the evidence…" disabled={busy||!canDecide}/><div className="form-actions"><button className="button button-secondary" disabled={busy||!canDecide||rationale.trim().length<5} onClick={()=>void decide(suite,'reject')}>Reject test expectations</button><button className="button button-primary" disabled={busy||!canDecide||rationale.trim().length<5} onClick={()=>void decide(suite,'accept')}><Icon name="check" size={15}/>Accept test expectations</button></div><p className="action-reason">A human reviewer and a rationale of at least five characters are required. The decision binds to this suite digest and candidate bundle.</p></div>}
      </article>)}
      {!current&&<p className="action-reason">Open the latest unpublished revision against the current approved head to propose or accept development tests.</p>}
    </div><div className="report-footer">Development tests only · held-out evaluation oracles are not exposed to generation.</div>
  </section>;
}
