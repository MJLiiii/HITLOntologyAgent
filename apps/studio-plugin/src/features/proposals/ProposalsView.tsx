import { useCallback, useEffect, useState } from 'react';
import type { Project, Proposal, Revision, Session, Triple } from '../../api/generated';
import type { BundleRequest, ProposalRequest, PublishRequest, ReviewRequest, RevisionRequest, Submission } from '../../api/openapi';
import { errorMessage, post, request, runJob } from '../../api/client';
import { Badge, date, Empty, ErrorNotice, EvidenceList, Loading, PanelHeading, short, TripleTable } from '../../components/ui';
import { Icon } from '../../components/Icons';
import { AssessmentCard, ValidationReportCard } from '../validation/ValidationView';
import { ReviewTimer } from './ReviewTimer';

type Action = 'revise' | 'validate' | 'repair' | 'assess' | 'submit' | 'accept' | 'request_changes' | 'reject' | 'publish';
type ActionHandler = (action: Action, body?: Record<string, unknown>) => Promise<void>;
const isTerminal = (status: string) => ['published','rejected'].includes(status);
const tripleKey = (triple: Triple) => JSON.stringify([triple.subject,triple.predicate,triple.object,triple.object_type || 'iri',triple.datatype || null,triple.language || null]);
function revisionDelta(previous: {additions:Triple[];deletions:Triple[]}, next: {additions:Triple[];deletions:Triple[]}) {
  const difference = (left:Triple[],right:Triple[]) => {const keys=new Set(right.map(tripleKey));return left.filter(triple=>!keys.has(tripleKey(triple)));};
  return {
    additions:[...difference(next.additions,previous.additions),...difference(previous.deletions,next.deletions)],
    deletions:[...difference(previous.additions,next.additions),...difference(next.deletions,previous.deletions)],
  };
}

function ChangeEditor({label, triples, onChange}: {label: string; triples: Triple[]; onChange: (value: Triple[]) => void}) {
  function update(index: number, patch: Partial<Triple>) { onChange(triples.map((t,i) => i === index ? {...t,...patch} : t)); }
  return <div className="change-editor"><div className="section-heading"><h4>{label} <span className="count">{triples.length}</span></h4><button type="button" className="text-button small" onClick={() => onChange([...triples,{subject:'',predicate:'',object:'',object_type:'iri'}])}><Icon name="plus" size={14}/>Add triple</button></div>{triples.map((t,i) => <div className="triple-editor" key={i}><label>Subject IRI<input aria-label={`${label} ${i+1} subject`} value={t.subject} required onChange={e => update(i,{subject:e.target.value})}/></label><label>Predicate IRI<input aria-label={`${label} ${i+1} predicate`} value={t.predicate} required onChange={e => update(i,{predicate:e.target.value})}/></label><label>Object<input aria-label={`${label} ${i+1} object`} value={t.object} required onChange={e => update(i,{object:e.target.value})}/></label><label>Object type<select aria-label={`${label} ${i+1} object type`} value={t.object_type || 'iri'} onChange={e => update(i,{object_type:e.target.value as 'iri'|'literal',datatype:undefined,language:undefined})}><option value="iri">IRI</option><option value="literal">Literal</option></select></label><button type="button" aria-label={`Remove ${label.toLowerCase()} ${i+1}`} className="icon-button" onClick={() => onChange(triples.filter((_,j) => j !== i))}><Icon name="close" size={15}/></button></div>)}</div>;
}

export function RevisionDetail({project, session, revision, onRefresh, onAction, busy}: {project: Project; session: Session; revision: Revision; onRefresh: () => void; onAction: ActionHandler; busy: boolean}) {
  const [section, setSection] = useState<'changes'|'evidence'|'checks'|'history'>('changes');
  const [editing, setEditing] = useState(false);
  const [rationale, setRationale] = useState('');
  const [reviewRationale, setReviewRationale] = useState('');
  const [additions, setAdditions] = useState(revision.additions);
  const [deletions, setDeletions] = useState(revision.deletions);
  const stale = revision.status !== 'published' && (!!revision.stale || revision.base_version_id !== project.approved_version_id);
  const human = session.actor.kind === 'human';
  const canResearch = human && session.actor.roles.includes('researcher');
  const canReview = human && session.actor.roles.includes('reviewer');
  const canApprove = human && session.actor.roles.includes('approver');
  const validationId = revision.validation_run_id || revision.validation?.id;
  const assessmentIds = revision.assessment_run_ids || (revision.assessment ? [revision.assessment.id] : []);
  const reportsReady = !!validationId && revision.validation?.status === 'passed' && assessmentIds.length > 0 && ['succeeded','passed','complete','completed'].includes(revision.assessment?.status || '');
  const eligibility = revision.review_eligibility;
  const ready = !stale && project.scope_accepted && (eligibility ? eligibility.eligible : reportsReady && revision.evidence.every(e => e.resolved));
  const submitted = revision.status === 'in_review';
  const accepted = revision.status === 'approved';
  const published = revision.status === 'published';
  const reasons = published ? [] : [...(stale ? ['The approved head has changed. This proposal needs a new base before it can be accepted or published.'] : []), ...(!project.scope_accepted ? ['Accept the demonstration scope in Sources before submitting a release for review.'] : []), ...(eligibility?.reasons || [])];
  const canEdit = canResearch && !stale && !isTerminal(revision.status);
  const superseded = revision.history?.some(event=>typeof event.revision==='number' && event.revision>revision.revision);
  const canRepair = canResearch && !stale && !superseded && !project.pending_publication_id && !accepted && !isTerminal(revision.status);
  async function saveRevision(event: React.FormEvent) {
    event.preventDefault();
    try {
      await onAction('revise', {parent_revision:revision.revision, structured_changes:revisionDelta(revision,{additions,deletions}), rationale:rationale.trim()} satisfies RevisionRequest);
      setEditing(false);
    } catch { /* Preserve the edit when the server rejects it; the parent displays the error. */ }
  }
  return <article className="revision-detail"><div className="revision-title"><div><div className="revision-eyebrow"><span className="card-eyebrow">CANDIDATE REVISION {revision.revision}</span><Badge status={revision.status}/></div><h2>{revision.title}</h2><p>{revision.summary || revision.rationale}</p></div><button aria-label="Refresh revision" className="icon-button" onClick={onRefresh} disabled={busy}><Icon name="refresh"/></button></div>
    <div className="revision-meta"><span><Icon name="branch" size={14}/>Base <code>{short(revision.base_version_id) === '—' ? 'empty · seed proposal' : short(revision.base_version_id)}</code></span><span title={revision.bundle_digest}>Bundle <code>{short(revision.bundle_digest)}</code></span><span>{date(revision.created_at)}</span></div>
    <div className="workflow-steps" aria-label="Release workflow">{['Propose','Validate','Assess','Review','Publish'].map((label,i) => {const done = i===0 || (i===1 && revision.validation?.status==='passed') || (i===2 && !!revision.assessment) || (i===3 && (accepted||published)) || (i===4 && published);return <div key={label} className={done ? 'done' : ''}><span>{done ? <Icon name="check" size={12}/> : i+1}</span>{label}</div>;})}</div>
    {!!reasons.length && <div className="notice notice-info"><Icon name="shield"/><div>{reasons.map((reason,i) => <p key={i}>{reason}</p>)}</div></div>}
    <div className="panel revision-content"><div className="panel-controls"><div className="tab-strip" role="tablist" aria-label="Revision details">{(['changes','evidence','checks','history'] as const).map(s => <button role="tab" aria-selected={section===s} key={s} className={section===s?'active':''} onClick={() => setSection(s)}>{s[0].toUpperCase()+s.slice(1)}{s==='evidence' && <span className="count">{revision.evidence.length}</span>}</button>)}</div><button className="text-button small" disabled={busy || !canEdit} title={!canEdit ? 'A researcher may create a successor to an unpublished revision.' : 'Creates an immutable successor; approvals do not carry over.'} onClick={() => {setAdditions(revision.additions);setDeletions(revision.deletions);setEditing(!editing);}}>Create revision<Icon name="plus" size={14}/></button></div>
      {editing && <form className="revision-editor" onSubmit={e => void saveRevision(e)}><h3>Create an immutable successor</h3><p className="muted small">Use absolute HTTP(S) IRIs. The current revision is preserved; checks and approvals must be repeated for the successor.</p><ChangeEditor label="Additions" triples={additions} onChange={setAdditions}/><ChangeEditor label="Deletions" triples={deletions} onChange={setDeletions}/><label>Revision rationale<textarea value={rationale} onChange={e => setRationale(e.target.value)} rows={3} minLength={5} required/></label><div className="form-actions"><button type="button" className="button button-secondary" onClick={() => setEditing(false)}>Cancel</button><button className="button button-primary" disabled={busy || rationale.trim().length<5} type="submit">Save new revision</button></div></form>}
      {section==='changes' && <div className="diff-content"><div className="rationale"><h4>Why this change</h4><p>{revision.rationale}</p></div><div className="diff-heading"><span className="diff-add">+ {revision.additions.length} additions</span><span className="diff-delete">− {revision.deletions.length} deletions</span></div><TripleTable triples={revision.additions} variant="added"/>{!!revision.deletions.length && <TripleTable triples={revision.deletions} variant="deleted"/>}{!!revision.assumptions?.length && <div className="assumptions"><h4>Assumptions to review</h4><ul>{revision.assumptions.map((item,i) => <li key={i}>{item}</li>)}</ul></div>}</div>}
      {section==='evidence' && <div className="tab-content">{revision.evidence.length ? <EvidenceList evidence={revision.evidence}/> : <Empty icon="sources" title="No evidence attached">Generated statements require source evidence before expert acceptance.</Empty>}</div>}
      {/* Keep the evidence visible beside the diff so rationale cannot be mistaken for a source. */}
      {section==='changes' && !!revision.evidence.length && <div className="diff-evidence"><h4>Supporting evidence</h4><EvidenceList evidence={revision.evidence}/></div>}
      {section==='checks' && <div className="tab-content report-stack">{revision.validation ? <ValidationReportCard report={revision.validation}/> : <p className="muted">Logical validation has not run.</p>}{revision.assessment ? <AssessmentCard report={revision.assessment}/> : <p className="muted">Vocabulary and task assessment has not run.</p>}</div>}
      {section==='history' && <div className="tab-content">{revision.history?.length ? <ol className="audit-list">{revision.history.map((event,i) => <li key={i}><Icon name="clock" size={15}/><div><strong>{event.event?.replaceAll('_',' ') || `Revision ${event.revision ?? i+1}`}</strong><p>{event.detail || event.status?.replaceAll('_',' ')}</p><span className="small muted">{date(event.created_at)}{event.actor && ` · ${event.actor}`}</span></div></li>)}</ol> : <p className="muted">This revision has no additional history events.</p>}</div>}
    </div>
    <section className="panel review-panel"><div className="section-heading"><div><span className="card-eyebrow">HUMAN REVIEW</span><h3>{published ? 'This revision has been published' : accepted ? 'Accepted and ready for publication' : 'A deliberate step at every stage'}</h3></div><Icon name="shield" size={23}/></div><p className="muted small">Validation, assessment, submission, acceptance, and publication are separate actions. Acceptance binds your decision to this exact bundle.</p>
      {revision.revision_id&&<ReviewTimer projectId={project.id} revisionId={revision.revision_id} session={session} disabled={busy}/>}
      <div className="review-check-actions"><button className="button button-secondary" disabled={busy||!canResearch||accepted||isTerminal(revision.status)} onClick={() => void onAction('validate')}><Icon name="validation" size={15}/>Run validation</button>{revision.validation?.status==='failed'&&<button className="button button-secondary" disabled={busy||!canRepair} onClick={()=>void onAction('repair')}><Icon name="spark" size={15}/>Request repair</button>}<button className="button button-secondary" disabled={busy||!canResearch||accepted||isTerminal(revision.status)} onClick={() => void onAction('assess')}><Icon name="experiments" size={15}/>Run assessment</button><button className="button button-secondary" disabled={busy||!canResearch||!ready||submitted||accepted||isTerminal(revision.status)} onClick={() => void onAction('submit')}>Submit for review<Icon name="chevron" size={15}/></button></div>
      {revision.validation?.status==='failed'&&<p className="action-reason">Repair uses failed competency-question diagnostics only. At most two attempts are allowed per proposal. Each attempt creates a successor; required checks must run again and no revision is automatically approved.{project.pending_publication_id?' A pending publication must finish before repair.':''}{stale||superseded?' Repair requires the latest revision against the current approved head.':''}</p>}
      {!ready && !reasons.length && !published && <p className="action-reason">Passing validation, completed assessment, and resolved evidence are required before submission.</p>}
      {!submitted && !accepted && !published && <p className="action-reason">Submit this revision for review before recording a decision.</p>}
      {!canResearch && <p className="action-reason">The researcher role is required to create revisions and run checks.</p>}
      {!accepted && !published && <><label>Review rationale<textarea value={reviewRationale} onChange={e => setReviewRationale(e.target.value)} placeholder="Explain the evidence and checks behind your decision…" rows={3} disabled={busy||!submitted}/></label><div className="review-decision-actions"><button className="button button-primary" disabled={busy||!canApprove||!ready||!submitted||reviewRationale.trim().length<5} onClick={() => void onAction('accept',{rationale:reviewRationale.trim()})}><Icon name="check" size={16}/>Accept revision</button><button className="button button-secondary" disabled={busy||!canReview||!submitted||reviewRationale.trim().length<5} onClick={() => void onAction('request_changes',{rationale:reviewRationale.trim()})}>Request changes</button><button className="button button-quiet" disabled={busy||!canReview||!submitted||reviewRationale.trim().length<5} onClick={() => void onAction('reject',{rationale:reviewRationale.trim()})}>Reject revision</button></div>{submitted && <p className="action-reason">A rationale of at least five characters and the appropriate human reviewer role are required.</p>}</>}
      <div className="publish-row"><div><strong>Publish approved version</strong><p>Record the accepted bundle as a new immutable version and advance the approved head.</p></div><button className="button button-primary" disabled={busy||!canApprove||!accepted||stale||!project.scope_accepted||!revision.approval_ids?.length} onClick={() => void onAction('publish')}><Icon name="branch" size={16}/>{published ? 'Published' : 'Publish version'}</button></div>{!accepted && !published && <p className="action-reason">Publication becomes available after explicit human acceptance.</p>}
    </section>
  </article>;
}

export function ProposalsView({project, session, proposals, initialSelection, onRefresh, onSources}: {project: Project; session: Session; proposals: Proposal[]; initialSelection?: string; onRefresh: () => Promise<void>; onSources: () => void}) {
  const [selected, setSelected] = useState(initialSelection || '');
  const [revision, setRevision] = useState<Revision | null>(null);
  const [creating, setCreating] = useState(false);
  const [instruction, setInstruction] = useState('Create an evidence-grounded service ownership ontology from the synthetic source library.');
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [stage, setStage] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const proposal = proposals.find(p => p.id===selected) || proposals[0];
  const basePath = `/projects/${encodeURIComponent(project.id)}`;
  const revisionPath = proposal ? `${basePath}/proposals/${encodeURIComponent(proposal.id)}/revisions/${proposal.revision}` : '';
  const refreshRevision = useCallback(async () => {if(revisionPath) setRevision(await request<Revision>(revisionPath));}, [revisionPath]);
  useEffect(() => {if(initialSelection) setSelected(initialSelection);}, [initialSelection]);
  useEffect(() => {
    if(!revisionPath) {setRevision(null);return;}
    let active=true;setLoading(true);setError('');
    request<Revision>(revisionPath).then(value => {if(active)setRevision(value);}).catch(err => {if(active)setError(errorMessage(err));}).finally(() => {if(active)setLoading(false);});
    return () => {active=false;};
  }, [revisionPath, proposal?.status, proposal?.validation_run_id, proposal?.assessment_run_ids?.join(',')]);
  async function create(event: React.FormEvent) {
    event.preventDefault();setBusy(true);setError('');setNotice('');setStage('Preparing a candidate');
    try {
      const current = await request<Project>(basePath);
      if(current.approved_version_id !== project.approved_version_id || current.corpus_snapshot_id !== project.corpus_snapshot_id) {await onRefresh();throw new Error('The approved version or corpus snapshot changed. Review the current workspace before creating a proposal.');}
      const result = await runJob<{proposal_id: string; revision: number}>(`${basePath}/proposal-jobs`, {base_version_id:current.approved_version_id,corpus_snapshot_id:current.corpus_snapshot_id,competency_question_ids:[],instruction:instruction.trim()} satisfies ProposalRequest, setStage);
      await onRefresh();setSelected(result.proposal_id);setCreating(false);setNotice('A candidate was created. Inspect the evidence and run both validation and assessment.');
    } catch(err) {setError(errorMessage(err));} finally {setBusy(false);}
  }
  const action: ActionHandler = async (kind, extras={}) => {
    if(!revision || busy)return;
    setBusy(true);setError('');setNotice('');setStage(kind.replaceAll('_',' '));
    try {
      const [current, latest] = await Promise.all([request<Project>(basePath), request<Revision>(`${basePath}/proposals/${encodeURIComponent(revision.id)}/revisions/${revision.revision}`)]);
      if(current.approved_version_id!==project.approved_version_id || latest.bundle_digest!==revision.bundle_digest || latest.status!==revision.status) {await onRefresh();await refreshRevision();throw new Error('The project head or revision changed. Review the refreshed content and repeat your action.');}
      const bundle = {proposal_id:revision.id,revision:revision.revision,bundle_digest:revision.bundle_digest} satisfies BundleRequest;
      const reports = {validation_run_id:latest.validation_run_id || latest.validation?.id,required_assessment_run_ids:latest.assessment_run_ids || (latest.assessment ? [latest.assessment.id] : [])};
      const match = {'If-Match':String(revision.revision)};
      if(kind==='revise') {
        await post<Revision>(`${basePath}/proposals/${encodeURIComponent(revision.id)}/revisions`,extras,match);
        setNotice('A new revision was created. Previous checks and approvals remain with the earlier revision.');
      } else if(kind==='validate' || kind==='assess') {
        await runJob(`${basePath}/${kind==='validate'?'validation':'assessment'}-jobs`,bundle,setStage);
        setNotice(kind==='validate'?'Validation finished. Inspect the report before continuing.':'Assessment finished. Inspect coverage and fitness before continuing.');
      } else if(kind==='repair') {
        if(current.pending_publication_id)throw new Error('A publication is pending. Finish it before requesting repair.');
        if(latest.validation?.status!=='failed' || latest.stale || latest.history?.some(event=>typeof event.revision==='number'&&event.revision>revision.revision))throw new Error('Repair requires a failed expectation report on the latest revision against the current approved head. Engine errors cannot be repaired automatically.');
        const result=await runJob<{proposal_id:string;revision:number;bundle_digest:string;repair_attempt:number}>(`${basePath}/repair-jobs`,bundle,setStage);
        setSelected(result.proposal_id);
        setRevision(await request<Revision>(`${basePath}/proposals/${encodeURIComponent(result.proposal_id)}/revisions/${result.revision}`));
        setNotice(`Repair attempt ${result.repair_attempt} of 2 created revision ${result.revision}. Inspect the successor and rerun validation and assessment. No revision was approved or published.`);
      } else if(kind==='submit') {
        if(!reports.validation_run_id)throw new Error('This revision has no validation report. Run validation before submitting for review.');
        await post(`${basePath}/review-submissions`, {proposal_id:revision.id,revision:revision.revision,...reports,validation_run_id:reports.validation_run_id} satisfies Submission, match);
        setNotice('Submitted for human review. No decision has been recorded.');
      } else if(kind==='publish') {
        const result = await post<{id:string;status:string}>(`${basePath}/publications`, {...bundle,approval_ids:latest.approval_ids || [],expected_head:current.approved_version_id} satisfies PublishRequest,{'Idempotency-Key':crypto.randomUUID()});
        setNotice(result.status==='completed'?'The accepted revision is published as a new immutable approved version.':`Publication ${result.id} is ${result.status}. Refresh to inspect recovery; it has not been marked completed.`);
      } else {
        if(!reports.validation_run_id || !current.review_policy_id || typeof extras.rationale!=='string')throw new Error('A current validation report, review policy, and written rationale are required to record a decision.');
        await post(`${basePath}/reviews`, {...bundle,...reports,validation_run_id:reports.validation_run_id,decision:kind,rationale:extras.rationale,review_policy_id:current.review_policy_id} satisfies ReviewRequest);
        setNotice(kind==='accept'?'Your acceptance was recorded for this exact bundle. Publication requires a separate click.':`Review decision recorded: ${kind.replaceAll('_',' ')}.`);
      }
      await onRefresh();if(kind!=='revise'&&kind!=='repair')await refreshRevision();
    } catch(err) {setError(errorMessage(err));throw err;} finally {setBusy(false);}
  };
  // Event handlers consume errors here; the notice retains the actionable API detail.
  const safeAction: ActionHandler = async (kind,body) => {try {await action(kind,body);}catch(err) {if(kind==='revise')throw err;}};
  return <div className="page-content proposals-page"><PanelHeading title="From a useful idea to an approved change" subtitle="Every proposal is versioned, evidenced, checked, and deliberately reviewed." action={<button className="button button-primary" disabled={busy||!session.actor.roles.includes('researcher')} onClick={() => setCreating(!creating)}><Icon name="plus" size={16}/>New proposal</button>}/>
    {error && <ErrorNotice message={error} onDismiss={() => setError('')}/>}{notice && <div className="notice notice-success" role="status"><Icon name="check"/><span>{notice}</span></div>}
    {!project.scope_accepted && <div className="notice notice-info"><Icon name="shield"/><span>Demo scope acceptance is required before release review.</span><button className="text-button small" onClick={onSources}>Review scope<Icon name="chevron" size={14}/></button></div>}
    {creating && <form className="panel form-panel" onSubmit={e => void create(e)}><h3>{project.approved_version_id ? 'Describe your proposed change' : 'Create the first ontology candidate'}</h3><p className="muted small">The proposal uses the current frozen corpus and approved head. Generation never approves or publishes changes.</p><label>Proposal instruction<textarea value={instruction} onChange={e => setInstruction(e.target.value)} maxLength={4000} rows={3} required/></label><div className="form-actions"><button className="button button-secondary" type="button" onClick={() => setCreating(false)}>Cancel</button><button className="button button-primary" type="submit" disabled={busy||!instruction.trim()||!project.corpus_snapshot_id}><Icon name="spark" size={15}/>Generate candidate</button></div>{!project.corpus_snapshot_id && <p className="action-reason">Process sources and freeze a corpus snapshot first.</p>}</form>}
    {busy && <div className="inline-loading" role="status"><span className="spinner"/>{stage.replaceAll('_',' ')}…</div>}
    {!proposals.length ? <div className="panel"><Empty icon="proposals" title="The next version starts with a proposal">Describe a change to generate an inspectable candidate, or create the first ontology from your source library.</Empty><div className="empty-action"><button className="button button-secondary" onClick={() => setCreating(true)}>Create a proposal<Icon name="plus" size={15}/></button></div></div> : <><div className="proposal-picker"><label>Proposal<select value={proposal?.id || ''} disabled={busy} onChange={e => setSelected(e.target.value)}>{proposals.map(p => <option value={p.id} key={p.id}>{p.title} · Revision {p.revision} · {p.status.replaceAll('_',' ')}</option>)}</select></label><span className="small muted">{proposals.length} candidate{proposals.length===1?'':'s'} · immutable revisions</span></div>{loading ? <Loading label="Loading candidate revision…"/> : revision && <RevisionDetail key={`${revision.id}:${revision.revision}`} project={project} session={session} revision={revision} onRefresh={() => {void onRefresh();void refreshRevision().catch(err => setError(errorMessage(err)));}} onAction={safeAction} busy={busy}/>}</>}
  </div>;
}
