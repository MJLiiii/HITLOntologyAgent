import { useCallback, useEffect, useState } from 'react';
import type { SourceDocument } from '../../api/generated';
import type { IngestRequest, TrustGraphRecoveryRequest, TrustGraphSnapshotRequest } from '../../api/openapi';
import { errorMessage, request, runJob } from '../../api/client';
import { Badge, ErrorNotice, EvidenceList, short } from '../../components/ui';
import { Icon } from '../../components/Icons';

interface Preparation { id:string; document_id:string; status:string; prepared:{seed_mode:string;approved_version_id:string|null;configuration_version:number;manifest_digest:string} }
interface Ingestion { id:string; document_id:string; preparation_id:string; status:string; receipt:{status:string;processing_id?:string;document_uri?:string;config_digest?:string;seed_digest?:string} }
interface Ingestions { configured:boolean; items:Ingestion[]; preparations:Preparation[] }
interface RegisteredChunks { chunk_uris:string[];source_id:string;selection_required:true;upstream_completion_supported:false;provenance_artifact?:{sha256:string} }
interface FrozenSelection { id:string;status:string;provider_snapshot:{status:'verified_selection';chunks:{evidence_id:string;source_id:string;upstream_chunk_uri:string;quote:string;span_start:number;span_end:number;chunk_artifact:{sha256:string};graph_uri:string;subgraph_uris:string[]}[]} }

export function TrustGraphPanel({projectId,sources,onRefresh}:{projectId:string;sources:SourceDocument[];onRefresh:()=>Promise<void>}) {
  const base=`/projects/${encodeURIComponent(projectId)}`;
  const [data,setData]=useState<Ingestions|null>(null);
  const [sourceId,setSourceId]=useState('');
  const [active,setActive]=useState<Ingestion|null>(null);
  const [chunks,setChunks]=useState<RegisteredChunks|null>(null);
  const [selected,setSelected]=useState<string[]>([]);
  const [frozen,setFrozen]=useState<FrozenSelection|null>(null);
  const [busy,setBusy]=useState(false);
  const [stage,setStage]=useState('');
  const [error,setError]=useState('');
  const [notice,setNotice]=useState('');
  const reload=useCallback(async()=>{setData(await request<Ingestions>(base+'/trustgraph-ingestions'));},[base]);
  useEffect(()=>{let mounted=true;void request<Ingestions>(base+'/trustgraph-ingestions').then(value=>{if(mounted)setData(value);}).catch(err=>{if(mounted)setError(errorMessage(err));});return()=>{mounted=false;};},[base]);
  const title=(id:string)=>sources.find(source=>source.id===id)?.title || `Source ${short(id)}`;
  const recoverable=data?.preparations.filter(preparation=>!data.items.some(item=>item.preparation_id===preparation.id)) || [];

  async function submit(preparationId?:string) {
    if(busy || (!preparationId&&!sourceId))return;
    setBusy(true);setError('');setNotice('');setStage(preparationId?'Inspecting the existing upstream submission':'Submitting the source to TrustGraph');
    try {
      if(preparationId) await runJob<Ingestion>(base+'/trustgraph-ingestion-recoveries',{preparation_id:preparationId} satisfies TrustGraphRecoveryRequest,setStage);
      else await runJob<Ingestion>(base+'/trustgraph-ingestions',{document_id:sourceId} satisfies IngestRequest,setStage);
      await reload();
      setNotice(preparationId?'Existing upstream submission reattached. Inspect its registered chunks before selecting passages.':'Upstream submission recorded. Inspect registered chunks when they become available.');
    }catch(err){setError(errorMessage(err));await reload().catch(()=>{});}finally{setBusy(false);}
  }
  async function inspect(ingestion:Ingestion) {
    setBusy(true);setError('');setChunks(null);setSelected([]);setActive(ingestion);setStage('Reading registered chunk identities');
    try{setChunks(await request<RegisteredChunks>(`${base}/trustgraph-ingestions/${encodeURIComponent(ingestion.id)}/chunks`));}
    catch(err){setError(errorMessage(err));}finally{setBusy(false);}
  }
  async function freeze() {
    if(busy||!active||!selected.length||selected.length>50)return;
    setBusy(true);setError('');setNotice('');setFrozen(null);setStage('Verifying selected passages and freezing exact evidence');
    try {
      const result=await runJob<FrozenSelection>(base+'/trustgraph-snapshots',{ingestion_run_id:active.id,chunk_uris:selected} satisfies TrustGraphSnapshotRequest,setStage);
      setFrozen(result);setSelected([]);await onRefresh();
      setNotice('Selected passages verified and frozen in a new local corpus. Existing proposals retain their original corpus.');
    }catch(err){setError(errorMessage(err));}finally{setBusy(false);}
  }
  if(data&&!data.configured)return null;
  if(!data&&!error)return <p className="small muted" role="status">Checking optional TrustGraph connection…</p>;
  return <section className="panel trustgraph-panel" aria-labelledby="trustgraph-title">
    <div className="report-heading"><div className="report-icon"><Icon name="sources" size={23}/></div><div><span className="card-eyebrow">OPTIONAL SOURCE PROVIDER</span><h3 id="trustgraph-title">TrustGraph source selection</h3><p>Freeze verified passages from a server-configured upstream source.</p></div><button className="button button-secondary small" disabled={busy} onClick={()=>{setError('');void reload().catch(err=>setError(errorMessage(err)));}}><Icon name="refresh" size={14}/>Refresh submissions</button></div>
    <div className="trustgraph-body">
      {error&&<ErrorNotice message={error}/>}{notice&&<div className="notice notice-success" role="status">{notice}</div>}
      {data?.configured&&<>
        <div className="notice notice-info"><Icon name="shield"/><span>Processing completion is unverified. A submission receipt means queued upstream. A snapshot contains only the passages you select and the server verifies; it does not establish that all upstream processing is complete.</span></div>
        <div className="trustgraph-submit"><label>Source for TrustGraph<select value={sourceId} disabled={busy} onChange={event=>setSourceId(event.target.value)}><option value="">Choose an uploaded text source</option>{sources.filter(source=>source.status!=='withdrawn').map(source=><option key={source.id} value={source.id}>{source.title}</option>)}</select></label><button className="button button-secondary" disabled={busy||!sourceId} onClick={()=>void submit()}>Submit to TrustGraph</button></div>
        <p className="field-help">UTF-8 text sources only. Use local processing for PDFs. The server fixes the workspace, collection, flow and approved seed; this form cannot override them.</p>
        {data.items.map(ingestion=><article className="trustgraph-record" key={ingestion.id}><div className="section-heading"><div><h4>{title(ingestion.document_id)}</h4><code>{short(ingestion.id)}</code></div><Badge status={ingestion.status}>Upstream {ingestion.receipt.status}</Badge></div><details><summary>Submission provenance</summary><dl><dt>Ingestion</dt><dd><code>{ingestion.id}</code></dd><dt>Preparation</dt><dd><code>{ingestion.preparation_id}</code></dd>{ingestion.receipt.processing_id&&<><dt>Upstream processing</dt><dd><code>{ingestion.receipt.processing_id}</code></dd></>}{ingestion.receipt.config_digest&&<><dt>Configuration digest</dt><dd><code>{ingestion.receipt.config_digest}</code></dd></>}{ingestion.receipt.seed_digest&&<><dt>Seed digest</dt><dd><code>{ingestion.receipt.seed_digest}</code></dd></>}</dl></details><button className="button button-secondary small" disabled={busy} onClick={()=>void inspect(ingestion)}>Inspect registered chunks</button></article>)}
        {recoverable.map(preparation=><article className="trustgraph-record" key={preparation.id}><h4>{title(preparation.document_id)} · saved preparation</h4><p>Preparation <code>{preparation.id}</code> has no recorded receipt. Recovery only reattaches a verified existing upstream attempt; it never resends an absent submission.</p><p className="small muted">Seed mode: {preparation.prepared.seed_mode.replaceAll('_',' ')} · Configuration version {preparation.prepared.configuration_version}{preparation.prepared.approved_version_id&&<> · Approved version <code>{preparation.prepared.approved_version_id}</code></>}</p><button className="button button-secondary small" disabled={busy} onClick={()=>void submit(preparation.id)}>Recover existing submission</button></article>)}
        {active&&chunks&&<div className="trustgraph-selection"><h4>Select passages from {title(chunks.source_id)}</h4><p className="field-help">These are registered chunk identities, not verified previews. Exact text, source spans and provenance are checked when you freeze the selection. Choose up to 50.</p>{chunks.chunk_uris.length?<fieldset disabled={busy}><legend>Registered chunk identities</legend>{chunks.chunk_uris.map(uri=><label key={uri}><input type="checkbox" checked={selected.includes(uri)} disabled={busy||(!selected.includes(uri)&&selected.length>=50)} onChange={event=>setSelected(current=>event.target.checked?[...current,uri]:current.filter(item=>item!==uri))}/><code>{uri}</code></label>)}</fieldset>:<p>No registered chunks are available yet. Refresh this submission after upstream extraction has produced them.</p>}<div className="form-actions"><span className="small muted">{selected.length} selected</span><button className="button button-primary" disabled={busy||!selected.length} onClick={()=>void freeze()}>Verify and freeze selected passages</button></div></div>}
        {frozen&&<div className="trustgraph-frozen"><h4>Verified selected passages</h4><p className="field-help">Local corpus <code>{frozen.id}</code>. Only this selection is verified; upstream completion remains unverified.</p><EvidenceList evidence={frozen.provider_snapshot.chunks.map(chunk=>({id:chunk.evidence_id,document_id:chunk.source_id,title:title(chunk.source_id),quote:chunk.quote,locator:`Characters ${chunk.span_start}–${chunk.span_end}`,content_hash:chunk.chunk_artifact.sha256,resolved:true}))}/>{frozen.provider_snapshot.chunks.map(chunk=><details key={chunk.evidence_id}><summary>Frozen provenance · {short(chunk.evidence_id)}</summary><dl><dt>Chunk URI</dt><dd><code>{chunk.upstream_chunk_uri}</code></dd><dt>Source graph</dt><dd><code>{chunk.graph_uri}</code></dd><dt>Extraction subgraphs</dt><dd>{chunk.subgraph_uris.map(uri=><code key={uri}>{uri}</code>)}</dd></dl></details>)}</div>}
      </>}
      {busy&&<div role="status" className="inline-loading"><span className="spinner"/>{stage.replaceAll('_',' ')}…</div>}
    </div>
  </section>;
}
