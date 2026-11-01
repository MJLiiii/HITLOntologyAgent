import { useState } from 'react';
import type { Project, Session } from '../../api/generated';
import type { SeedImportRequest } from '../../api/openapi';
import { errorMessage, request, runJob } from '../../api/client';
import { ErrorNotice, short } from '../../components/ui';
import { Icon } from '../../components/Icons';

export function SeedImportPanel({project,session,onRefresh,onOpenProposal}: {project:Project;session:Session;onRefresh:()=>Promise<void>;onOpenProposal:(id:string)=>void}) {
  const [open,setOpen]=useState(false);
  const [turtle,setTurtle]=useState('');
  const [rationale,setRationale]=useState('');
  const [busy,setBusy]=useState(false);
  const [stage,setStage]=useState('');
  const [error,setError]=useState('');
  const [candidate,setCandidate]=useState<{proposal_id:string;revision:number;bundle_digest:string}|null>(null);
  const human=session.actor.kind==='human';
  const eligible=human&&session.actor.roles.includes('researcher')&&!project.approved_version_id&&!project.pending_publication_id&&!!project.corpus_snapshot_id;
  async function readFile(file?:File) {
    if(!file)return;
    setError('');
    if(!file.name.toLowerCase().endsWith('.ttl')){setError('Choose a Turtle file with a .ttl extension.');return;}
    if(file.size>1048576){setError('Choose a Turtle file no larger than 1 MiB.');return;}
    try{setTurtle(await file.text());}catch(err){setError(errorMessage(err));}
  }
  async function stageSeed(event:React.FormEvent) {
    event.preventDefault();if(!eligible||busy)return;
    setBusy(true);setError('');setCandidate(null);setStage('Checking the current corpus and approved head');
    try {
      const current=await request<Project>(`/projects/${encodeURIComponent(project.id)}`);
      if(current.approved_version_id || current.pending_publication_id || current.corpus_snapshot_id!==project.corpus_snapshot_id || current.scope_digest!==project.scope_digest){await onRefresh();throw new Error('The approved head, scope, or corpus changed. Review the current workspace before staging this seed.');}
      const result=await runJob<{proposal_id:string;revision:number;bundle_digest:string}>(`/projects/${encodeURIComponent(project.id)}/seed-imports`,{ontology_ttl:turtle,corpus_snapshot_id:project.corpus_snapshot_id!,profile:'rdfs',rationale:rationale.trim()} satisfies SeedImportRequest,setStage);
      await onRefresh();setCandidate(result);setOpen(false);
    }catch(err){setError(errorMessage(err));}finally{setBusy(false);}
  }
  return <section className="panel seed-panel"><div className="report-heading"><div className="report-icon"><Icon name="ontology" size={23}/></div><div><span className="card-eyebrow">START FROM AN EXISTING ONTOLOGY</span><h3>Stage a Turtle seed for review</h3><p>Import an initial candidate against a frozen corpus before the first approved release.</p></div><button className="button button-secondary small" disabled={busy||!eligible} onClick={()=>setOpen(!open)}><Icon name="plus" size={15}/>Import seed ontology</button></div><div className="seed-body">
    {error&&<ErrorNotice message={error}/>} {candidate&&<div className="notice notice-success" role="status"><Icon name="check"/><span>Seed staged as candidate revision {candidate.revision}, bundle <code>{short(candidate.bundle_digest)}</code>. It is not approved. Run validation and assessment, then submit it for human review.</span><button className="text-button small" onClick={()=>onOpenProposal(candidate.proposal_id)}>Review seed candidate<Icon name="chevron" size={14}/></button></div>}
    {!eligible&&<p className="action-reason">{project.approved_version_id?'An approved release already exists. Use a proposal to change the ontology.':project.pending_publication_id?'Finish the pending publication before importing a seed.':!project.corpus_snapshot_id?'Process evidence and freeze a corpus snapshot before importing a seed.':'A human researcher session is required to stage a seed candidate.'}</p>}
    {open&&<form className="seed-form" onSubmit={event=>void stageSeed(event)}><div className="notice notice-info"><Icon name="shield"/><span>Staging creates an immutable proposal only. The seed is never accepted, validated, or published automatically.</span></div><div className="seed-context"><span>Corpus <code>{project.corpus_snapshot_id}</code></span><span>Profile <strong>RDFS</strong></span><span>Scope <code>{short(project.scope_digest)}</code></span></div><label>Read a Turtle file<input type="file" accept=".ttl,text/turtle" disabled={busy} onChange={event=>void readFile(event.target.files?.[0])}/></label><label>Seed ontology (Turtle)<textarea className="code-input" value={turtle} onChange={event=>setTurtle(event.target.value)} rows={10} maxLength={1048576} disabled={busy} required placeholder={'@prefix demo: <https://example.org/oe-demo/> .\n@prefix owl: <http://www.w3.org/2002/07/owl#> .\n\ndemo:Service a owl:Class .'}/></label><p className="field-help">UTF-8 Turtle, up to 1 MiB and 100 triple additions. The server parses the ontology and checks the fixed modelling profile; no imports are fetched by this form.</p><label>Seed import rationale<textarea value={rationale} onChange={event=>setRationale(event.target.value)} rows={3} minLength={5} maxLength={4000} disabled={busy} required placeholder="Explain the source and purpose of this initial ontology…"/></label><div className="form-actions"><button type="button" className="button button-secondary" disabled={busy} onClick={()=>setOpen(false)}>Cancel import</button><button type="submit" className="button button-primary" disabled={busy||!eligible||!turtle.trim()||rationale.trim().length<5}>Stage seed candidate<Icon name="chevron" size={15}/></button></div></form>}
    {busy&&<div className="inline-loading" role="status"><span className="spinner"/>{stage.replaceAll('_',' ')}…</div>}
  </div></section>;
}
