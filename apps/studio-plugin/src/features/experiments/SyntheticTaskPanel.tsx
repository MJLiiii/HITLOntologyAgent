import { useEffect, useState } from 'react';
import type { Project, Proposal, Session } from '../../api/generated';
import type { SyntheticTaskRegistration } from '../../api/openapi';
import { errorMessage, post, request } from '../../api/client';
import { ErrorNotice } from '../../components/ui';

export interface SyntheticTask { id:string;task_id:string;instruction:string;proposal_id:string;revision:number;revision_id:string;bundle_digest:string;registration_digest:string;protocol_id:'synthetic-task-v1';packet:{id:string;sha256:string};created_at?:string }

export function SyntheticTaskPanel({project,proposals,session,selected,onSelect,disabled}:{project:Project;proposals:Proposal[];session:Session;selected:SyntheticTask|null;onSelect:(task:SyntheticTask|null)=>void;disabled:boolean}) {
  const [tasks,setTasks]=useState<SyntheticTask[]>([]);
  const [proposalId,setProposalId]=useState('');
  const [taskId,setTaskId]=useState('');
  const [instruction,setInstruction]=useState('');
  const [loading,setLoading]=useState(true);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  const [notice,setNotice]=useState('');
  const base=`/projects/${encodeURIComponent(project.id)}`;
  const candidate=proposals.find(proposal=>proposal.id===proposalId);
  const human=session.actor.kind==='human'&&session.actor.roles.includes('researcher');
  const eligible=human&&project.scope_accepted&&project.domain==='demo';
  useEffect(()=>{let active=true;setLoading(true);void request<{items:SyntheticTask[]}>(base+'/synthetic-tasks').then(result=>{if(active)setTasks(result.items);}).catch(err=>{if(active)setError(errorMessage(err));}).finally(()=>{if(active)setLoading(false);});return()=>{active=false;};},[base]);
  async function register(event:React.FormEvent) {
    event.preventDefault();if(!eligible||!candidate||busy||disabled)return;
    setBusy(true);setError('');setNotice('');
    try {
      const task=await post<SyntheticTask>(base+'/synthetic-tasks',{proposal_id:candidate.id,revision:candidate.revision,bundle_digest:candidate.bundle_digest,task_id:taskId.trim(),instruction:instruction.trim()} satisfies SyntheticTaskRegistration);
      setTasks(current=>[...current,task]);onSelect(task);setTaskId('');setInstruction('');
      setNotice('Synthetic task registered as an immutable engineering packet. No ontology approval or study observation was created.');
    }catch(err){setError(errorMessage(err));}finally{setBusy(false);}
  }
  return <section className="panel synthetic-task-panel" aria-label="Registered synthetic tasks">
    <h3>Registered synthetic tasks</h3><p className="muted small">Freeze an exact candidate revision, accepted synthetic scope and evidence into a reusable engineering task. Registration is separate from ontology approval.</p>
    {error&&<ErrorNotice message={error}/>} {notice&&<div className="notice notice-success" role="status">{notice}</div>}
    <label>Registered synthetic task<select value={selected?.id||''} disabled={loading||busy||disabled} onChange={event=>onSelect(tasks.find(task=>task.id===event.target.value)||null)}><option value="">Choose one registered task</option>{tasks.map(task=><option key={task.id} value={task.id}>{task.task_id}</option>)}</select></label>
    {loading&&<p className="small muted" role="status">Loading frozen task registrations…</p>}
    {selected&&<div className="synthetic-task-details"><p>{selected.instruction}</p><dl><dt>Exact revision</dt><dd><code>{selected.revision_id}</code> · revision {selected.revision}</dd><dt>Bundle digest</dt><dd><code>{selected.bundle_digest}</code></dd><dt>Registration digest</dt><dd><code>{selected.registration_digest}</code></dd><dt>Frozen packet</dt><dd><a href={`/api/v1${base}/artifacts/${encodeURIComponent(selected.packet.id)}`} target="_blank" rel="noreferrer">Inspect immutable task packet</a><code>{selected.packet.sha256}</code></dd></dl></div>}
    <details className="synthetic-task-register" open={!tasks.length}><summary>Register a task from a candidate revision</summary><form onSubmit={event=>void register(event)}><fieldset disabled={busy||disabled||!eligible}><label>Candidate revision for task<select value={proposalId} onChange={event=>setProposalId(event.target.value)} required><option value="">Choose a candidate revision</option>{proposals.map(proposal=><option key={proposal.id} value={proposal.id}>{proposal.title} · revision {proposal.revision}</option>)}</select></label>{candidate&&<p className="field-help">Exact bundle <code>{candidate.bundle_digest}</code>. The server checks that the revision still matches before registering.</p>}<div className="form-grid"><label>Synthetic task ID<input value={taskId} onChange={event=>setTaskId(event.target.value)} pattern={'[a-z][a-z0-9_\\-]{0,79}'} maxLength={80} required placeholder="service-ownership-check"/></label><label>Task instruction<textarea value={instruction} onChange={event=>setInstruction(event.target.value)} minLength={5} maxLength={4000} required rows={3} placeholder="Describe the synthetic engineering task for this frozen packet…"/></label></div><p className="field-help">Use a unique project task ID starting with a lowercase letter; lowercase letters, digits, underscores and hyphens only.</p><button className="button button-secondary" type="submit" disabled={!eligible||!candidate||busy||disabled||!/^[a-z][a-z0-9_-]{0,79}$/.test(taskId.trim())||instruction.trim().length<5}>{busy?'Registering…':'Register frozen synthetic task'}</button></fieldset></form>{!eligible&&<p className="action-reason">A human researcher session and an explicitly accepted demo scope are required. This feature does not authorize a real study.</p>}</details>
  </section>;
}
