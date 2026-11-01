import { useMemo, useState } from 'react';
import type { Experiment, Project, Proposal, Session, SyntheticTask } from '../../api/generated';
import type { ExperimentRequest, SyntheticTaskJob } from '../../api/openapi';
import { errorMessage, runJob } from '../../api/client';
import { Badge, Empty, ErrorNotice, PanelHeading, percent } from '../../components/ui';
import { Icon } from '../../components/Icons';
import { ExperimentReview } from './ExperimentReview';
import { SyntheticTaskPanel } from './SyntheticTaskPanel';

const conditions = [
  {id:'A',name:'One-shot generation',description:'Initial candidate, no repair feedback.'},
  {id:'B',name:'Self-revision',description:'Revision without automated reports.'},
  {id:'C',name:'Reasoner-guided repair',description:'Repair informed by entailment checks.'},
  {id:'D',name:'Expert-reviewed workflow',description:'Automated repair plus human review.'},
];
const protocolOf = (run: Experiment) => run.protocol_id || 'demo-v1';
const phaseOf = (run: Experiment) => run.phase || 'automated';
const seconds = (value?: number|null) => value == null ? '—' : `${value.toFixed(1)}s`;
function mean(rows: Experiment[], key: 'strict_fitness'|'vocabulary_coverage') {
  const values = rows.flatMap(row => typeof row[key] === 'number' ? [row[key] as number] : []);
  return values.length ? values.reduce((a,b) => a+b, 0)/values.length : null;
}

export function ExperimentsView({project, experiments, proposals, session, onRefresh, onOpenProposal}: {
  project: Project; experiments: Experiment[]; proposals: Proposal[]; session: Session;
  onRefresh: () => Promise<void>; onOpenProposal: (id: string) => void;
}) {
  const [protocol, setProtocol] = useState<'demo-v1'|'model-pilot-v1'|'synthetic-task-v1'>('demo-v1');
  const [registration,setRegistration]=useState<SyntheticTask|null>(null);
  const [condition, setCondition] = useState<NonNullable<ExperimentRequest['condition']>>('all');
  const [status, setStatus] = useState('all');
  const [phase, setPhase] = useState('all');
  const [selectedId, setSelectedId] = useState('');
  const [linked, setLinked] = useState<Experiment|null>(null);
  const [busy, setBusy] = useState(false);
  const [stage, setStage] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const registered=protocol==='synthetic-task-v1';
  const protocolRuns = useMemo(() => experiments.filter(run => protocolOf(run) === protocol&&(!registered||run.task_id===registration?.task_id)), [experiments, protocol,registered,registration?.task_id]);
  const filtered = useMemo(() => protocolRuns.filter(run => (condition === 'all' || run.condition === condition)
    && (status === 'all' || run.status === status) && (phase === 'all' || phaseOf(run) === phase)), [protocolRuns, condition, status, phase]);
  const selected = protocolRuns.find(run => run.id === selectedId) || (linked?.id === selectedId ? linked : null);
  const phases = Array.from(new Set(filtered.map(phaseOf)));
  const compare = phases.length <= 1;
  const pilot = protocol === 'model-pilot-v1';

  async function run() {
    if(registered&&!registration)return;
    setBusy(true); setError(''); setNotice(''); setStage(registered?'Starting registered synthetic task':pilot?'Starting frozen model pilot':'Starting frozen demonstration');
    try {
      if(protocol==='synthetic-task-v1'&&registration) await runJob('POST /api/v1/projects/{p}/synthetic-task-jobs',{path:{p:project.id},body:{registration_id:registration.id,registration_digest:registration.registration_digest,condition,replicate_ids:[1]} satisfies SyntheticTaskJob},setStage);
      else if(protocol!=='synthetic-task-v1') await runJob('POST /api/v1/projects/{p}/experiment-jobs', {path:{p:project.id},body:{
        protocol_id:protocol, condition, task_ids:['demo-ownership'], replicate_ids:[1],
      } satisfies ExperimentRequest}, setStage);
      await onRefresh();
      setNotice(`${registered?'Registered task':pilot?'Model pilot':'Demo'} runs recorded. Inspect failures and missing measurements. Condition D requires an explicitly staged candidate and a real human decision.`);
    } catch (err) { setError(errorMessage(err)); } finally { setBusy(false); }
  }
  function chooseProtocol(value: typeof protocol) {
    setProtocol(value);setRegistration(null); setStatus('all'); setPhase('all'); setSelectedId(''); setNotice(''); setError('');
  }
  function linkedReview(result: Experiment) {
    setLinked(result); setSelectedId(result.id); setStatus('all'); setPhase('all');
    setNotice('A separate post-review record was saved. The original pre-review output and its metrics remain unchanged.');
  }

  return <div className="page-content">
    <PanelHeading title="Compare the process, not just the output" subtitle="Inspect conditions A–D on frozen tasks, with failures and missing metrics kept visible." action={<button className="button button-primary" disabled={busy||(registered&&!registration)} onClick={() => void run()}><Icon name="experiments" size={16}/>Run {condition==='all'?'A–D':condition} {registered?'registered task':pilot?'model pilot':'demo'}</button>}/>
    {error && <ErrorNotice message={error}/>}
    {notice && <div className="notice notice-success" role="status"><Icon name="check"/><span>{notice}</span></div>}
    <div className="experiment-protocol"><label>Experiment protocol<select value={protocol} onChange={event => chooseProtocol(event.target.value as typeof protocol)} disabled={busy}><option value="demo-v1">Frozen workflow demonstration</option><option value="model-pilot-v1">Configured model pilot</option><option value="synthetic-task-v1">Registered synthetic task</option></select></label><p className="muted small">{registered?'Runs one explicitly selected frozen task packet across A–D. Comparisons are scoped to that task.':pilot?'Calls the configured model using the same frozen task across A–D. Condition D shares C’s automated output and waits for a real review.':'Exercises the deterministic demonstration protocol. Select the model pilot to record actual model calls.'}</p></div>
    <div className="notice notice-info"><Icon name="shield"/><span>Synthetic development workload · one frozen task and one replicate. {pilot||registered?'Model-generated outputs are an engineering pilot, with no independent held-out evaluation.':'These records exercise the workflow.'} These protocols are engineering tests, not a real study or a completed expert evaluation.</span></div>
    {registered&&<SyntheticTaskPanel key={project.id} project={project} proposals={proposals} session={session} selected={registration} disabled={busy} onSelect={task=>{setRegistration(task);setSelectedId('');setStatus('all');setPhase('all');}}/>}
    <div className="condition-grid">{conditions.map(item => {
      const rows = protocolRuns.filter(run => run.condition === item.id);
      return <button className={`condition-card ${condition===item.id?'selected':''}`} aria-pressed={condition===item.id} key={item.id} onClick={() => setCondition(condition===item.id?'all':item.id as typeof condition)}><span className="condition-letter">{item.id}</span><h3>{item.name}</h3><p>{item.description}</p><span className="condition-count">{rows.length} recorded {rows.length===1?'run':'runs'}<Icon name="chevron" size={14}/></span></button>;
    })}</div>
    {busy && <div role="status" className="inline-loading"><span className="spinner"/>{stage.replaceAll('_',' ')}…</div>}
    <div className="stat-grid experiments-stats"><div className="stat-card"><span>Selected records</span><strong>{filtered.length}</strong><small>All scheduled outcomes</small></div><div className="stat-card"><span>Human review linked</span><strong>{filtered.filter(run => run.phase === 'post_review').length}</strong><small>Separate immutable records</small></div><div className="stat-card"><span>Mean strict fitness</span><strong>{percent(compare?mean(filtered,'strict_fitness'):null)}</strong><small>{compare?'Available observations only':'Choose one phase to compare'}</small></div><div className="stat-card"><span>Mean vocabulary coverage</span><strong>{percent(compare?mean(filtered,'vocabulary_coverage'):null)}</strong><small>{compare?'Available observations only':'Choose one phase to compare'}</small></div></div>
    <section className="panel"><div className="panel-controls experiment-controls"><div className="filter-controls">
      <label>Condition<select aria-label="Filter experiment condition" value={condition} onChange={event => setCondition(event.target.value as typeof condition)}><option value="all">All conditions</option>{conditions.map(item => <option key={item.id} value={item.id}>{item.id} · {item.name}</option>)}</select></label>
      <label>Phase<select aria-label="Filter experiment phase" value={phase} onChange={event => setPhase(event.target.value)}><option value="all">All phases</option>{Array.from(new Set(protocolRuns.map(phaseOf))).map(value => <option key={value} value={value}>{value.replaceAll('_',' ')}</option>)}</select></label>
      <label>Status<select aria-label="Filter experiment status" value={status} onChange={event => setStatus(event.target.value)}><option value="all">All outcomes</option>{Array.from(new Set(protocolRuns.map(run => run.status))).map(value => <option key={value} value={value}>{value.replaceAll('_',' ')}</option>)}</select></label>
    </div><div className="export-actions"><a className="button button-secondary small" href={`/api/v1/projects/${encodeURIComponent(project.id)}/experiments/export?format=csv`} download><Icon name="download" size={14}/>All CSV</a><a className="button button-quiet small" href={`/api/v1/projects/${encodeURIComponent(project.id)}/experiments/export?format=json`} download>JSON</a></div></div>
      {filtered.length ? <div className="table-scroll"><table className="experiments-table"><thead><tr><th>Condition / task</th><th>Outcome</th><th>Coverage</th><th>Utilisation</th><th>Strict fit</th><th>Approx. fit</th><th>Precision / recall</th><th>Elapsed</th><th>Active correction</th><th>Record</th></tr></thead><tbody>{filtered.map(run => <tr key={run.id}><td><strong><span className="table-condition">{run.condition}</span>{run.task_id}</strong><small>Replicate {run.replicate} · {phaseOf(run).replaceAll('_',' ')}</small></td><td><Badge status={run.status}/></td><td>{percent(run.vocabulary_coverage)}</td><td>{percent(run.vocabulary_utilisation)}</td><td>{percent(run.strict_fitness)}</td><td>{percent(run.approximate_fitness)}</td><td>{percent(run.answer_precision)} / {percent(run.answer_recall)}</td><td>{seconds(run.elapsed_seconds)}</td><td>{seconds(run.correction_seconds)}</td><td><button className="text-button small" aria-label={`Inspect experiment ${run.id}`} onClick={() => setSelectedId(selectedId===run.id?'':run.id)}>{selectedId===run.id?'Close':'Inspect'}</button></td></tr>)}</tbody></table></div> : <Empty icon="experiments" title={protocolRuns.length?'No runs match these filters':'A reproducible comparison starts here'}>{protocolRuns.length?'Choose another condition, phase, or outcome.':`Run the ${registered?'selected registered task':pilot?'configured model pilot':'synthetic demonstration'} to record the frozen task across the selected conditions.`}</Empty>}
      <div className="report-footer">— means unavailable, never zero. Pre-review and post-review records are separate. Exports contain every protocol and phase, including failures.</div>
    </section>
    {selected && <section className="panel experiment-detail"><div className="section-heading"><div><span className="card-eyebrow">{protocolOf(selected)} · {phaseOf(selected).replaceAll('_',' ')}</span><h2>Condition {selected.condition} · {selected.task_id}</h2></div><Badge status={selected.status}/></div>
      <dl className="experiment-record-fields"><div><dt>Immutable record</dt><dd><code>{selected.id}</code></dd></div><div><dt>Candidate digest</dt><dd><code>{selected.candidate_digest || 'Unavailable'}</code></dd></div><div><dt>Model</dt><dd>{selected.model?.name || 'No model recorded'}{selected.model?.temperature != null && ` · temperature ${selected.model.temperature}`}</dd></div><div><dt>Evaluation</dt><dd>{selected.evaluation_status?.replaceAll('_',' ') || 'Inspect exported reports'}</dd></div>{selected.parent_run_id && <div><dt>Original pre-review record</dt><dd><button className="text-button small" onClick={() => setSelectedId(selected.parent_run_id!)}><code>{selected.parent_run_id}</code></button></dd></div>}{selected.linked_review_id && <div><dt>Linked human decision</dt><dd><a href={`/api/v1/projects/${encodeURIComponent(project.id)}/reviews/${encodeURIComponent(selected.linked_review_id)}`} target="_blank" rel="noreferrer"><code>{selected.linked_review_id}</code><Icon name="external" size={12}/></a></dd></div>}</dl>
      {selected.phase==='post_review' && <p className="notice notice-info">Human decision: {selected.review_status?.replaceAll('_',' ') || 'See linked record'}. Active correction: {selected.correction_seconds==null?'unavailable; no complete timer ledger was supplied':seconds(selected.correction_seconds)}.{selected.time_to_acceptance_right_censored && ' Time to acceptance is right-censored because the decision was not acceptance.'}</p>}
      {selected.limitations?.map((limitation,index) => <p className="small muted" key={index}>{limitation}</p>)}
      {selected.candidate_ttl && <details className="experiment-artifact"><summary>Inspect frozen candidate Turtle</summary><pre>{selected.candidate_ttl}</pre></details>}
      {!!selected.repair_history?.length && <details className="experiment-artifact"><summary>Inspect recorded repair attempts</summary><pre>{JSON.stringify(selected.repair_history,null,2)}</pre></details>}
      {selected.validation && <details className="experiment-artifact"><summary>Inspect frozen validation report</summary><pre>{JSON.stringify(selected.validation,null,2)}</pre></details>}
      {selected.assessment && <details className="experiment-artifact"><summary>Inspect frozen assessment report</summary><pre>{JSON.stringify(selected.assessment,null,2)}</pre></details>}
      {['model-pilot-v1','synthetic-task-v1'].includes(protocolOf(selected)) && selected.condition==='D' && selected.phase==='pre_review' && selected.status==='waiting_human' && <ExperimentReview key={selected.id} run={selected} project={project} proposals={proposals} session={session} onRefresh={onRefresh} onOpenProposal={onOpenProposal} onLinked={linkedReview}/>}
    </section>}
    <div className="experiment-notes"><div><Icon name="branch" size={19}/><h3>Frozen inputs</h3><p>Compare runs from the same corpus, task, profile, and protocol. Keep pre-review and post-review outputs separate.</p></div><div><Icon name="shield" size={19}/><h3>Human review stays human</h3><p>Condition D records its review phase explicitly. A missing expert decision remains missing.</p></div><div><Icon name="clock" size={19}/><h3>Failures stay in the record</h3><p>Unavailable engines, failed expectations, and missing measurements remain inspectable in the export.</p></div></div>
  </div>;
}
