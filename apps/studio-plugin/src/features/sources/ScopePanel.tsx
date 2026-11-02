import { useEffect, useState } from 'react';
import type { Project, ScopeVersion, Session } from '../../api/generated';
import type { CompetencyQuestion, ScopeDecision, ScopeUpload } from '../../api/openapi';
import { errorMessage, list, operation } from '../../api/client';
import { Badge, date, ErrorNotice, Loading, short } from '../../components/ui';
import { Icon } from '../../components/Icons';

const namespace='https://example.org/oe-demo/';
export function ScopePanel({project,session,onRefresh}: {project:Project;session:Session;onRefresh:()=>Promise<void>}) {
  const [scope,setScope]=useState<ScopeVersion|null>(null);
  const [versions,setVersions]=useState<ScopeVersion[]>([]);
  const [inspected,setInspected]=useState<ScopeVersion|null>(null);
  const [draft,setDraft]=useState<ScopeUpload|null>(null);
  const [draftDigest,setDraftDigest]=useState('');
  const [reviewing,setReviewing]=useState(false);
  const [rationale,setRationale]=useState('');
  const [loading,setLoading]=useState(true);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  const [notice,setNotice]=useState('');
  const [reload,setReload]=useState(0);
  const base=`/projects/${encodeURIComponent(project.id)}`;
  const human=session.actor.kind==='human';
  const canEdit=human&&session.actor.roles.includes('researcher')&&!project.pending_publication_id;
  const canAccept=human&&(session.mode!=='team'||session.actor.roles.includes('approver'))&&project.domain==='demo'&&!project.pending_publication_id;
  const viewed=inspected||scope;
  const historical=!!inspected&&inspected.digest!==project.scope_digest;
  useEffect(()=>{
    let active=true;setLoading(true);setError('');
    Promise.all([operation('GET /api/v1/projects/{p}/scope',{path:{p:project.id}}),list('GET /api/v1/projects/{p}/scopes',{path:{p:project.id}})]).then(([current,history])=>{if(active){setScope(current);setVersions(history);setInspected(null);}}).catch(err=>{if(active)setError(errorMessage(err));}).finally(()=>{if(active)setLoading(false);});
    return()=>{active=false;};
  },[base,project.scope_digest,reload]);
  function edit() {
    if(!scope)return;
    setDraft({title:scope.title,purpose:scope.purpose,namespace,competency_questions:scope.competency_questions.map(question=>({...question,required:true})),shapes_ttl:scope.shapes_ttl,fixtures_ttl:scope.fixtures_ttl});setDraftDigest(project.scope_digest);setInspected(null);setReviewing(false);setError('');setNotice('');
  }
  function updateQuestion(index:number,patch:Partial<CompetencyQuestion>) {
    setDraft(value=>value?{...value,competency_questions:value.competency_questions.map((question,i)=>i===index?{...question,...patch}:question)}:value);
  }
  async function save(event:React.FormEvent) {
    event.preventDefault();if(!draft||busy||!canEdit)return;
    const ids=draft.competency_questions.map(question=>question.id.trim());
    if(new Set(ids).size!==ids.length){setError('Competency-question IDs must be unique.');return;}
    setBusy(true);setError('');setNotice('');
    try {
      const current=await operation('GET /api/v1/projects/{p}',{path:{p:project.id}});
      if(current.scope_digest!==draftDigest||current.pending_publication_id){await onRefresh();throw new Error('The scope or publication state changed. Review the current scope before saving a new version.');}
      await operation('POST /api/v1/projects/{p}/scope',{path:{p:project.id},body:draft satisfies ScopeUpload});
      await onRefresh();setDraft(null);setRationale('');setReviewing(false);setReload(value=>value+1);
      setNotice('A new scope version was saved and is awaiting explicit human acceptance. Earlier proposals keep their original scope; create new candidates against this version.');
    }catch(err){setError(errorMessage(err));}finally{setBusy(false);}
  }
  async function decide(decision:'accept'|'reject') {
    if(!scope||busy||!human||rationale.trim().length<5)return;
    setBusy(true);setError('');setNotice('');
    try {
      const current=await operation('GET /api/v1/projects/{p}',{path:{p:project.id}});
      if(current.scope_digest!==scope.digest||current.pending_publication_id){await onRefresh();throw new Error('The scope or publication state changed. Review the refreshed scope before deciding.');}
      await operation('POST /api/v1/projects/{p}/scope-decisions',{path:{p:project.id},body:{scope_digest:scope.digest,decision,rationale:rationale.trim()} satisfies ScopeDecision});
      await onRefresh();setReviewing(false);setRationale('');setNotice(decision==='accept'?'This exact synthetic scope was accepted. Ontology candidates still require their own validation, assessment, and release review.':'This scope was rejected. It remains available for inspection and cannot authorize release review.');
    }catch(err){setError(errorMessage(err));}finally{setBusy(false);}
  }
  return <section className="panel scope-panel"><div className="report-heading"><div className="report-icon"><Icon name="shield" size={23}/></div><div><span className="card-eyebrow">VERSIONED SCOPE & REQUIRED CHECKS</span><h3>{historical?'Historical scope · read only':project.scope_accepted?'Current synthetic scope is accepted':'Define the boundary of this ontology'}</h3><p>Scope labels describe this synthetic demonstration. A Deloitte study domain remains unselected.</p></div><Badge status={historical?'historical':project.scope_accepted?'approved':'draft'}>{historical?'Historical version':project.scope_accepted?'Scope accepted':'Scope pending'}</Badge></div><div className="scope-body">
    {error&&<ErrorNotice message={error}/>} {notice&&<div className="notice notice-info" role="status"><Icon name="shield"/><span>{notice}</span></div>}
    {loading?<Loading label="Loading scope and immutable versions…"/>:viewed&&<>
      <div className="scope-summary"><div><h3>{viewed.title}</h3><p>{viewed.purpose}</p></div><div className="scope-summary-meta"><span>Digest <code title={viewed.digest}>{short(viewed.digest)}</code></span><span>{viewed.competency_questions.length} required ASK questions</span><span>Namespace <code>{viewed.namespace}</code></span></div></div>
      <div className="scope-controls">{historical?<button className="button button-secondary small" onClick={()=>setInspected(null)}>Return to current scope</button>:<><button className="button button-secondary small" disabled={busy||!canEdit} onClick={edit}><Icon name="plus" size={14}/>Create scope version</button><button className="button button-primary small" disabled={busy||!human||!!draft||!!project.pending_publication_id} onClick={()=>{setReviewing(!reviewing);setRationale('');}}>Review current scope<Icon name="chevron" size={14}/></button></>}<button className="icon-button" aria-label="Reload scope versions" disabled={busy} onClick={()=>setReload(value=>value+1)}><Icon name="refresh" size={15}/></button></div>
      {!draft&&<details className="scope-inspection"><summary>Inspect competency questions, shapes, and fixtures</summary><div className="scope-question-list">{viewed.competency_questions.map(question=><article className="scope-question" key={question.id}><div className="section-heading"><h4>{question.id}</h4><Badge status="required">Required · ASK {String(question.expected)}</Badge></div><p>{question.question}</p><pre>{question.sparql_query}</pre>{!question.expected&&<p className="negative-ask-note">Expected false means no matching entailment in this test graph; it does not prove logical negation.</p>}</article>)}</div><details><summary>SHACL shapes</summary><pre>{viewed.shapes_ttl||'No SHACL shapes configured.'}</pre></details><details><summary>Test fixtures</summary><pre>{viewed.fixtures_ttl||'No additional fixture triples configured.'}</pre></details></details>}
    </>}
    {draft&&<form className="scope-editor" onSubmit={event=>void save(event)}><div className="notice notice-info"><Icon name="branch"/><span>Saving appends a scope version and clears scope acceptance. Existing proposal bundles remain immutable and cannot be released under a changed scope.</span></div><div className="form-grid"><label>Scope/domain label<input value={draft.title} onChange={event=>setDraft({...draft,title:event.target.value})} minLength={3} maxLength={120} required disabled={busy}/></label><label>Namespace<input value={namespace} readOnly/></label></div><label>Scope purpose and rationale<textarea value={draft.purpose} onChange={event=>setDraft({...draft,purpose:event.target.value})} rows={3} minLength={5} maxLength={4000} required disabled={busy}/></label><div className="section-heading"><h4>Required competency questions</h4><button className="text-button small" type="button" disabled={busy||draft.competency_questions.length>=20} onClick={()=>setDraft({...draft,competency_questions:[...draft.competency_questions,{id:'',question:'',sparql_query:'ASK {\n  \n}',expected:true,required:true}]})}><Icon name="plus" size={14}/>Add ASK question</button></div>{draft.competency_questions.map((question,index)=><div className="scope-question-editor" key={index}><div className="question-editor-top"><label>Question {index+1} ID<input value={question.id} onChange={event=>updateQuestion(index,{id:event.target.value})} maxLength={80} required disabled={busy}/></label><label>Expected ASK result {index+1}<select value={String(question.expected)} onChange={event=>updateQuestion(index,{expected:event.target.value==='true'})} disabled={busy}><option value="true">True · matching entailment</option><option value="false">False · no matching entailment</option></select></label><button className="icon-button" type="button" aria-label={`Remove competency question ${index+1}`} disabled={busy||draft.competency_questions.length<=1} onClick={()=>setDraft({...draft,competency_questions:draft.competency_questions.filter((_,i)=>i!==index)})}><Icon name="close" size={15}/></button></div><label>Competency question {index+1}<input value={question.question} onChange={event=>updateQuestion(index,{question:event.target.value})} minLength={5} maxLength={1000} required disabled={busy}/></label><label>ASK query {index+1}<textarea className="code-input" value={question.sparql_query} onChange={event=>updateQuestion(index,{sparql_query:event.target.value})} rows={3} minLength={5} maxLength={4000} required disabled={busy}/></label>{!question.expected&&<p className="negative-ask-note">A false ASK expectation means non-entailment in the test graph, not proof of negation.</p>}</div>)}<div className="scope-rdf-editors"><label>SHACL shapes (Turtle)<textarea className="code-input" value={draft.shapes_ttl||''} onChange={event=>setDraft({...draft,shapes_ttl:event.target.value})} rows={7} maxLength={100000} disabled={busy}/></label><label>Test fixtures (Turtle)<textarea className="code-input" value={draft.fixtures_ttl||''} onChange={event=>setDraft({...draft,fixtures_ttl:event.target.value})} rows={7} maxLength={100000} disabled={busy}/></label></div><p className="field-help">One to twenty uniquely identified ASK questions. Every question is required. The server parses SPARQL and Turtle before saving; the ontology profile remains fixed to RDFS.</p><div className="form-actions"><button className="button button-secondary" type="button" disabled={busy} onClick={()=>setDraft(null)}>Cancel scope edits</button><button className="button button-primary" type="submit" disabled={busy||!canEdit}>Save scope version</button></div></form>}
    {reviewing&&!draft&&!historical&&scope&&<div className="scope-review"><h4>Record a human scope decision</h4><p>Inspect the exact digest <code>{short(scope.digest)}</code>, required questions, shapes, and fixtures above. This decision does not accept an ontology release.</p><label>Scope decision rationale<textarea value={rationale} onChange={event=>setRationale(event.target.value)} rows={3} minLength={5} maxLength={4000} disabled={busy} placeholder="Explain why this scope and these required expectations are appropriate…"/></label><div className="form-actions"><button className="button button-secondary" disabled={busy||!human||rationale.trim().length<5} onClick={()=>void decide('reject')}>Reject scope</button><button className="button button-primary" disabled={busy||!canAccept||rationale.trim().length<5} onClick={()=>void decide('accept')}><Icon name="check" size={15}/>Accept scope</button></div>{!canAccept&&<p className="action-reason">Only a human can accept the synthetic demo scope, and no publication may be pending.</p>}</div>}
    {versions.length>0&&<details className="scope-history"><summary>Saved scope versions ({versions.length})</summary><div>{versions.map(version=><button className="scope-history-row" key={version.id||version.digest} onClick={()=>{setInspected(version);setDraft(null);setReviewing(false);}}><Icon name="branch" size={15}/><span><strong>{version.title}</strong><small>{date(version.created_at)} · <code>{short(version.digest)}</code></small></span><Badge status={version.digest===project.scope_digest?'current':'historical'}>{version.digest===project.scope_digest?'Current':'Historical'}</Badge><Icon name="chevron" size={14}/></button>)}</div></details>}
    {project.pending_publication_id&&<p className="action-reason">A publication is pending. Finish or reconcile it before changing or accepting scope.</p>}
    {busy&&<div className="inline-loading" role="status"><span className="spinner"/>Recording the explicit scope action…</div>}
  </div></section>;
}
