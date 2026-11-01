import { useEffect, useState } from 'react';
import type { AssessmentReport, Project, Proposal, Revision, Session, ValidationReport } from '../../api/generated';
import { errorMessage, request } from '../../api/client';
import { Badge, Empty, ErrorNotice, Loading, PanelHeading, percent, short } from '../../components/ui';
import { Icon } from '../../components/Icons';
import { TestOraclePanel } from './TestOraclePanel';
import { MappingPanel } from './MappingPanel';

export function ValidationReportCard({report}: {report: ValidationReport}) {
  const unavailable = ['error', 'timeout', 'unsupported', 'not_run'].includes(report.status);
  const title = report.status === 'passed' ? 'Required checks passed' : unavailable ? 'Validation could not complete' : 'Candidate needs correction';
  const engine = typeof report.engine === 'string' ? report.engine : report.engine ? `${report.engine.name}${report.engine.version ? ` ${report.engine.version}` : ''}` : '';
  return <section className="panel report-card"><div className="report-heading"><div className={`report-icon ${report.status === 'passed' ? 'good' : unavailable ? 'neutral' : 'bad'}`}><Icon name="validation" size={23}/></div><div><span className="card-eyebrow">LOGICAL VALIDATION</span><h3>{title}</h3><p>{report.profile.toUpperCase()} profile{engine && ` · ${engine}`}</p></div><Badge status={report.status}/></div>
    {unavailable && <p className="notice notice-info">An unavailable or broken validation engine is not a failed expectation and never counts as a pass.</p>}
    <div className="check-list">{report.cases.map(check => <div className="check-row" key={check.id}><Icon name={check.status === 'passed' ? 'check' : check.status === 'failed' ? 'close' : 'clock'} size={17}/><div><strong>{check.name || check.id}</strong>{check.message && <p>{check.message}</p>}{(check.expected !== undefined || check.actual !== undefined) && <details><summary>Inspect expectation</summary><pre>{JSON.stringify({expected:check.expected, actual:check.actual}, null, 2)}</pre></details>}</div><Badge status={check.status}/></div>)}</div>
    {report.limitations?.map((note,i) => <p className="report-limitation" key={i}>{note}</p>)}<div className="report-footer">Run <code title={report.id}>{short(report.id)}</code> · Applies to the exact revision and bundle</div>
  </section>;
}

export function AssessmentCard({report}: {report: AssessmentReport}) {
  const metrics = [
    ['Task-vocabulary coverage', report.vocabulary_coverage, 'Task terms supported by the ontology'],
    ['Ontology-vocabulary utilisation', report.vocabulary_utilisation, 'Ontology terms used by the task'],
    ['Strict fitness', report.strict_fitness, 'Questions supported by exact mappings'],
    ['Approximate fitness', report.approximate_fitness, 'Includes suggested mappings; not approved equivalence'],
  ] as const;
  return <section className="panel report-card"><div className="report-heading"><div className="report-icon"><Icon name="experiments" size={23}/></div><div><span className="card-eyebrow">VOCABULARY & TASK FITNESS</span><h3>Is the ontology useful for this task?</h3><p>Assessment measures fit; it does not certify logical correctness.</p></div><Badge status={report.status}/></div><div className="assessment-metrics">{metrics.map(([label,value,description]) => <div className="assessment-metric" key={label}><span>{label}</span><strong>{percent(value)}</strong><div className="metric-track"><span style={{width:`${Math.max(0,Math.min(1,value ?? 0))*100}%`}}/></div><small>{value == null ? 'Unavailable · inspect run limitations' : description}</small></div>)}</div>
    {!!report.questions?.length && <div className="assessment-questions"><h4>Competency questions</h4>{report.questions.map(q => <div className="check-row" key={q.id}><span className="small muted">{q.id}</span><div><strong>{q.question}</strong>{!!q.missing_terms?.length && <p>Missing terms: {q.missing_terms.join(', ')}</p>}</div><Badge status={q.status || 'included'}>{q.status || 'Included in assessment'}</Badge></div>)}</div>}
    {(!!report.mappings?.length||report.mappings_sha256)&&<div className="assessment-mappings"><h4>Frozen mapping inputs</h4>{report.mappings_sha256&&<p className="mapping-report-digest">Mapping artifact SHA-256 <code>{report.mappings_sha256}</code></p>}{report.mappings?.map((mapping,i)=>{const reviewed=mapping.relation_type==='canonical_correspondence'&&!!mapping.reviewer&&!!mapping.review_id;return <div className="mapping-report-record" key={i}><div className="mapping-row"><code>{mapping.requirement_iri||mapping.source}</code><Icon name="chevron" size={14}/><code>{mapping.ontology_iri||mapping.target}</code><span className="mapping-note">{reviewed?'Reviewed tool correspondence · not OWL equivalence':'Suggestion · not an equivalence'}</span></div>{mapping.rationale&&<p>{mapping.rationale}</p>}{reviewed&&<div className="mapping-report-review">Reviewer <strong>{mapping.reviewer}</strong> · Review <code>{mapping.review_id}</code>{!!mapping.evidence_ids?.length&&<span> · Evidence {mapping.evidence_ids.map(id=><code key={id}>{id} </code>)}</span>}</div>}</div>;})}{!report.mappings?.length&&<p className="mapping-report-digest">No reviewed correspondences were supplied to this assessment.</p>}<p className="mapping-report-digest">These inputs belong to this report's frozen bundle. Changing active mappings requires a successor candidate and a new assessment.</p>{report.mapping_diagnostics&&<details className="mapping-diagnostics"><summary>Inspect mapping diagnostics</summary><pre>{JSON.stringify(report.mapping_diagnostics,null,2)}</pre></details>}</div>}
    {report.limitations?.map((note,i) => <p className="report-limitation" key={i}>{note}</p>)}<div className="report-footer">Run <code title={report.id}>{short(report.id)}</code> · Metrics are fractions displayed as percentages</div>
  </section>;
}

export function ValidationView({project, session, proposals, onOpenProposal, onRefresh}: {project: Project; session: Session; proposals: Proposal[]; onOpenProposal: (id: string) => void; onRefresh: () => Promise<void>}) {
  const [selected, setSelected] = useState('');
  const [revision, setRevision] = useState<Revision | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const proposal = proposals.find(p => p.id === selected) || proposals[0];
  useEffect(() => {
    if (!proposal) return;
    let active = true; setLoading(true); setError('');
    request<Revision>(`/projects/${encodeURIComponent(project.id)}/proposals/${encodeURIComponent(proposal.id)}/revisions/${proposal.revision}`)
      .then(result => {if(active) setRevision(result);})
      .catch(err => {if(active) setError(errorMessage(err));})
      .finally(() => {if(active) setLoading(false);});
    return () => {active = false;};
  }, [project.id, proposal?.id, proposal?.revision, proposal?.validation_run_id, proposal?.assessment_run_ids?.join(',')]);
  return <div className="page-content"><PanelHeading title="Confidence, with the evidence to match" subtitle="Logical checks and task fitness answer different questions. Inspect both before review."/>
    {error && <ErrorNotice message={error}/>}
    <MappingPanel project={project} session={session} onRefresh={onRefresh}/>
    {!proposal ? <Empty icon="validation" title="Every candidate gets a closer look">Create a proposal, then run validation and assessment. Reports stay attached to their exact revision.</Empty> : <><div className="panel selection-panel"><label>Candidate revision<select value={proposal.id} onChange={e => setSelected(e.target.value)}>{proposals.map(p => <option key={p.id} value={p.id}>{p.title} · Revision {p.revision}</option>)}</select></label><button className="button button-secondary" onClick={() => onOpenProposal(proposal.id)}>Open proposal<Icon name="chevron" size={15}/></button></div>
      {loading ? <Loading label="Loading validation and assessment…"/> : revision && <div className="report-stack">{revision.validation ? <ValidationReportCard report={revision.validation}/> : <div className="panel"><Empty icon="validation" title="Logical validation has not run">Open the proposal and select Run validation. No result is assumed.</Empty></div>}{revision.assessment ? <AssessmentCard report={revision.assessment}/> : <div className="panel"><Empty icon="experiments" title="Task assessment has not run">Open the proposal and select Run assessment to inspect vocabulary coverage and fitness.</Empty></div>}<TestOraclePanel project={project} session={session} revision={revision} onRefresh={onRefresh} onOpenProposal={onOpenProposal}/></div>}
    </>}
  </div>;
}
