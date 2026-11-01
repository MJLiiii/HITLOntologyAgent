import { useEffect, useState } from 'react';
import type { AuditEvent, Project, Publication, ReviewDecision, Version } from '../../api/generated';
import { errorMessage, list, request } from '../../api/client';
import { Badge, ErrorNotice, Loading, short } from '../../components/ui';
import { Icon } from '../../components/Icons';

export function VersionProvenance({project,version,onOpenProposal,onSelectVersion}: {project:Project;version:Version;onOpenProposal?:(id:string)=>void;onSelectVersion?:(id:string)=>void}) {
  const [events,setEvents]=useState<AuditEvent[]>([]);
  const [publication,setPublication]=useState<Publication|null>(null);
  const [reviews,setReviews]=useState<ReviewDecision[]>([]);
  const [loading,setLoading]=useState(true);
  const [error,setError]=useState('');
  const [allEvents,setAllEvents]=useState(false);
  const [reload,setReload]=useState(0);
  const base=`/projects/${encodeURIComponent(project.id)}`;
  const apiLink=(path:string)=>`/api/v1${base}${path}`;
  const head=project.approved_version_id===version.id;
  useEffect(()=>{
    let active=true;setLoading(true);setError('');setPublication(null);setReviews([]);setEvents([]);
    async function load() {
      const reads=await Promise.allSettled([list<AuditEvent>(`${base}/audit`),version.publication_id?request<Publication>(`${base}/publications/${encodeURIComponent(version.publication_id)}`):Promise.resolve(null)]);
      if(!active)return;
      const failures:string[]=[];
      if(reads[0].status==='fulfilled')setEvents(reads[0].value);else failures.push(errorMessage(reads[0].reason));
      if(reads[1].status==='fulfilled'){
        const receipt=reads[1].value;setPublication(receipt);
        if(receipt?.approval_ids.length){
          const decisions=await Promise.allSettled(receipt.approval_ids.map(id=>request<ReviewDecision>(`${base}/reviews/${encodeURIComponent(id)}`)));
          if(!active)return;
          setReviews(decisions.flatMap(result=>result.status==='fulfilled'?[result.value]:[]));
          decisions.forEach(result=>{if(result.status==='rejected')failures.push(errorMessage(result.reason));});
        }
      }else failures.push(errorMessage(reads[1].reason));
      if(active){setError(failures.join(' '));setLoading(false);}
    }
    void load();return()=>{active=false;};
  },[base,version.id,version.publication_id,reload]);
  const entities=new Set([version.id,version.publication_id,version.source_snapshot_id,publication?.id,publication?.proposal_id,publication?.revision_id,...(publication?.approval_ids||[])]);
  const shown=allEvents?events:events.filter(event=>entities.has(event.entity));
  return <section className="panel provenance-panel"><div className="report-heading"><div className="report-icon"><Icon name="branch" size={23}/></div><div><span className="card-eyebrow">VERSION PROVENANCE · READ ONLY</span><h3>{head?'Current approved head':version.status==='approved'?'Historical approved version':'Demonstration reference · not approved'}</h3><p>Inspect the exact publication, review decisions, and recorded audit events behind {version.label}.</p></div><button className="icon-button" aria-label="Refresh version provenance" disabled={loading} onClick={()=>setReload(value=>value+1)}><Icon name="refresh" size={17}/></button></div>
    <div className="provenance-body">{project.pending_publication_id&&<div className="notice notice-info"><Icon name="clock"/><span>A publication is pending. The approved head remains <code>{project.approved_version_id||'unset'}</code> until publication completes. <a href={apiLink(`/publications/${encodeURIComponent(project.pending_publication_id)}`)} target="_blank" rel="noreferrer">Inspect pending publication</a></span></div>}{error&&<ErrorNotice message={error}/>}
      <dl className="provenance-fields"><div><dt>Version</dt><dd><a href={apiLink(`/versions/${encodeURIComponent(version.id)}`)} target="_blank" rel="noreferrer"><code>{version.id}</code><Icon name="external" size={12}/></a></dd></div><div><dt>Approved head</dt><dd><code>{project.approved_version_id||'Not established'}</code>{head&&<Badge status="approved">Current head</Badge>}</dd></div><div><dt>Parent version</dt><dd>{version.parent_version_id?<button className="text-button small" onClick={()=>onSelectVersion?.(version.parent_version_id!)}><code>{version.parent_version_id}</code><Icon name="chevron" size={13}/></button>:'None · initial version'}</dd></div><div><dt>Corpus snapshot</dt><dd><code>{version.source_snapshot_id||'Not recorded'}</code></dd></div><div><dt>Bundle digest</dt><dd><code>{version.bundle_digest||'Reference fixture · no reviewed bundle'}</code></dd></div><div><dt>Git commit</dt><dd><code>{version.commit||'Not published to Git'}</code></dd></div>{version.publication_id&&<div><dt>Publication receipt</dt><dd><a href={apiLink(`/publications/${encodeURIComponent(version.publication_id)}`)} target="_blank" rel="noreferrer"><code>{version.publication_id}</code><Icon name="external" size={12}/></a>{publication&&<Badge status={publication.status}/>}</dd></div>}{publication&&<div><dt>Exact candidate</dt><dd>{onOpenProposal?<button className="text-button small" onClick={()=>onOpenProposal(publication.proposal_id)}>Open proposal<Icon name="chevron" size={13}/></button>:null}<a href={apiLink(`/proposals/${encodeURIComponent(publication.proposal_id)}/revisions/${publication.revision}`)} target="_blank" rel="noreferrer">Revision {publication.revision}<Icon name="external" size={12}/></a><code>{publication.revision_id}</code></dd></div>}</dl>
      {loading&&<Loading label="Loading publication and audit records…"/>}
      {!!reviews.length&&<section className="approval-records"><h4>Recorded human decisions</h4>{reviews.map(review=><article className="approval-record" key={review.id}><div className="section-heading"><strong>{review.actor.subject}</strong><Badge status={review.decision==='accept'?'approved':review.decision}>{review.decision}</Badge><a href={apiLink(`/reviews/${encodeURIComponent(review.id)}`)} target="_blank" rel="noreferrer" aria-label={`Inspect review ${review.id}`}><Icon name="external" size={13}/></a></div><p>{review.rationale}</p><div className="review-provenance-links"><a href={apiLink(`/validation-runs/${encodeURIComponent(review.validation_run_id)}`)} target="_blank" rel="noreferrer">Validation <code>{short(review.validation_run_id)}</code><Icon name="external" size={12}/></a>{review.required_assessment_run_ids.map(id=><a href={apiLink(`/assessment-runs/${encodeURIComponent(id)}`)} target="_blank" rel="noreferrer" key={id}>Assessment <code>{short(id)}</code><Icon name="external" size={12}/></a>)}</div><div className="small muted">Accepted bundle <code>{review.bundle_digest}</code></div></article>)}</section>}
      {version.manifest&&<details className="manifest-details"><summary>Inspect immutable version manifest</summary><pre>{JSON.stringify(version.manifest,null,2)}</pre></details>}
      <section className="version-audit"><div className="section-heading"><h4>Recorded audit history <span className="count">{shown.length}</span></h4><label className="audit-filter"><input type="checkbox" checked={allEvents} onChange={event=>setAllEvents(event.target.checked)}/>All project events</label></div><p className="small muted">{allEvents?'Showing the project event chain. Events may refer to other versions.':'Showing events whose entity matches this version’s publication, candidate, reviews, or corpus snapshot.'}</p>
        {!loading&&!shown.length?<p className="audit-empty muted small">No matching audit events are available for this selection.</p>:<ol className="audit-record-list">{shown.map(event=><li key={event.id}><div className="audit-event-icon"><Icon name={event.action==='ontology_published'?'branch':event.action.includes('review')?'shield':'clock'} size={15}/></div><div><div className="audit-event-title"><strong>{event.action.replaceAll('_',' ')}</strong><time dateTime={event.time}>{new Date(event.time).toLocaleString()}</time></div><p>{typeof event.actor==='string'?event.actor:event.actor.subject} · Entity <code>{event.entity}</code></p><details><summary>Inspect chain record{event.sequence?` #${event.sequence}`:''}</summary><dl><dt>Event hash</dt><dd><code>{event.event_hash}</code></dd><dt>Previous event hash</dt><dd><code>{event.previous_event_hash||'None · first event'}</code></dd>{event.detail_digest&&<><dt>Detail digest</dt><dd><code>{event.detail_digest}</code></dd></>}</dl></details></div></li>)}</ol>}
      </section>
    </div><div className="report-footer">Publication and review links open the exact read-only API record. Browsing does not change the approved head.</div>
  </section>;
}
