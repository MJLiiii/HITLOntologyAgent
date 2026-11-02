import { useCallback, useEffect, useState } from 'react';
import type { SourceDocument, TrustGraphIngestion as Ingestion, TrustGraphIngestions as Ingestions, TrustGraphRegisteredChunks as RegisteredChunks, TrustGraphFrozenSelection as FrozenSelection } from '../../api/generated';
import type { IngestRequest_Input, TrustGraphRecoveryRequest, TrustGraphSnapshotRequest } from '../../api/openapi';
import { errorMessage, operation, runJob } from '../../api/client';
import { Badge, ErrorNotice, EvidenceList, short } from '../../components/ui';
import { Icon } from '../../components/Icons';

async function readDiscoveryPages<T extends {next_cursor:string|null}>(read:(cursor?:string)=>Promise<T>):Promise<T[]> {
  const pages:T[]=[];
  const cursors=new Set<string>();
  let cursor:string|undefined;
  do {
    const page=await read(cursor);
    pages.push(page);
    cursor=page.next_cursor||undefined;
    if(cursor&&cursors.has(cursor))throw new Error('The server repeated a pagination cursor. Refresh to reload the complete list.');
    if(cursor)cursors.add(cursor);
  }while(cursor);
  return pages;
}

async function readIngestions(projectId:string):Promise<Ingestions> {
  const pages=await readDiscoveryPages(cursor=>operation('GET /api/v1/projects/{p}/trustgraph-ingestions',{path:{p:projectId},query:{cursor}}));
  return {...pages[0],items:pages.flatMap(page=>page.items),preparations:pages.flatMap(page=>page.preparations),next_cursor:null};
}

async function readRegisteredChunks(projectId:string,ingestionId:string):Promise<RegisteredChunks> {
  const pages=await readDiscoveryPages(cursor=>operation('GET /api/v1/projects/{p}/trustgraph-ingestions/{ingestion}/chunks',{path:{p:projectId,ingestion:ingestionId},query:{cursor}}));
  return {...pages[0],chunk_uris:pages.flatMap(page=>page.chunk_uris),next_cursor:null};
}

export function TrustGraphPanel({projectId,sources,onRefresh,canResearch=true}:{projectId:string;canResearch?:boolean;sources:SourceDocument[];onRefresh:()=>Promise<void>}) {
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
  const reload=useCallback(async()=>{setData(await readIngestions(projectId));},[projectId]);
  useEffect(()=>{let mounted=true;void readIngestions(projectId).then(value=>{if(mounted)setData(value);}).catch(err=>{if(mounted)setError(errorMessage(err));});return()=>{mounted=false;};},[projectId]);
  const title=(id:string)=>sources.find(source=>source.id===id)?.title || `Source ${short(id)}`;
  const recoverable=data?.preparations.filter(preparation=>!data.items.some(item=>item.preparation_id===preparation.id)) || [];

  async function submit(preparationId?:string) {
    if(busy || (!preparationId&&!sourceId))return;
    setBusy(true);setError('');setNotice('');setStage(preparationId?'Inspecting the existing upstream submission':'Submitting the source to TrustGraph');
    try {
      if(preparationId) await runJob('POST /api/v1/projects/{p}/trustgraph-ingestion-recoveries',{path:{p:projectId},body:{preparation_id:preparationId} satisfies TrustGraphRecoveryRequest},setStage);
      else await runJob('POST /api/v1/projects/{p}/trustgraph-ingestions',{path:{p:projectId},body:{document_id:sourceId} satisfies IngestRequest_Input},setStage);
      await reload();
      setNotice(preparationId?'Existing upstream submission reattached. Inspect its registered chunks before selecting passages.':'Upstream submission recorded. Inspect registered chunks when they become available.');
    }catch(err){setError(errorMessage(err));await reload().catch(()=>{});}finally{setBusy(false);}
  }
  async function inspect(ingestion:Ingestion) {
    setBusy(true);setError('');setChunks(null);setSelected([]);setActive(ingestion);setStage('Reading registered chunk identities');
    try{setChunks(await readRegisteredChunks(projectId,ingestion.id));}
    catch(err){setError(errorMessage(err));}finally{setBusy(false);}
  }
  async function freeze() {
    if(busy||!active||!selected.length||selected.length>50)return;
    setBusy(true);setError('');setNotice('');setFrozen(null);setStage('Verifying selected passages and freezing exact evidence');
    try {
      const result=await runJob('POST /api/v1/projects/{p}/trustgraph-snapshots',{path:{p:projectId},body:{ingestion_run_id:active.id,chunk_uris:selected} satisfies TrustGraphSnapshotRequest},setStage);
      if(!result.provider_snapshot)throw new Error('The completed snapshot has no verified provider provenance. Refresh the source corpus before continuing.');
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
        <div className="trustgraph-submit"><label>Source for TrustGraph<select value={sourceId} disabled={busy} onChange={event=>setSourceId(event.target.value)}><option value="">Choose an uploaded text source</option>{sources.filter(source=>source.status!=='withdrawn').map(source=><option key={source.id} value={source.id}>{source.title}</option>)}</select></label><button className="button button-secondary" disabled={busy||!canResearch||!sourceId} onClick={()=>void submit()}>Submit to TrustGraph</button></div>
        <p className="field-help">UTF-8 text sources only. Use local processing for PDFs. The server fixes the workspace, collection, flow and approved seed; this form cannot override them.</p>
        {data.items.map(ingestion=><article className="trustgraph-record" key={ingestion.id}><div className="section-heading"><div><h4>{title(ingestion.document_id)}</h4><code>{short(ingestion.id)}</code></div><Badge status={ingestion.status}>Upstream {ingestion.receipt.status}</Badge></div><details><summary>Submission provenance</summary><dl><dt>Ingestion</dt><dd><code>{ingestion.id}</code></dd><dt>Preparation</dt><dd><code>{ingestion.preparation_id}</code></dd>{ingestion.receipt.processing_id&&<><dt>Upstream processing</dt><dd><code>{ingestion.receipt.processing_id}</code></dd></>}{ingestion.receipt.config_digest&&<><dt>Configuration digest</dt><dd><code>{ingestion.receipt.config_digest}</code></dd></>}{ingestion.receipt.seed_digest&&<><dt>Seed digest</dt><dd><code>{ingestion.receipt.seed_digest}</code></dd></>}</dl></details><button className="button button-secondary small" disabled={busy} onClick={()=>void inspect(ingestion)}>Inspect registered chunks</button></article>)}
        {recoverable.map(preparation=><article className="trustgraph-record" key={preparation.id}><h4>{title(preparation.document_id)} · saved preparation</h4><p>Preparation <code>{preparation.id}</code> has no recorded receipt. Recovery only reattaches a verified existing upstream attempt; it never resends an absent submission.</p><p className="small muted">Seed mode: {preparation.prepared.seed_mode.replaceAll('_',' ')} · Configuration version {preparation.prepared.configuration_version}{preparation.prepared.approved_version_id&&<> · Approved version <code>{preparation.prepared.approved_version_id}</code></>}</p><button className="button button-secondary small" disabled={busy||!canResearch} onClick={()=>void submit(preparation.id)}>Recover existing submission</button></article>)}
        {active&&chunks&&<div className="trustgraph-selection"><h4>Select passages from {title(chunks.source_id)}</h4><p className="field-help">These are registered chunk identities, not verified previews. Exact text, source spans and provenance are checked when you freeze the selection. Choose up to 50.</p>{chunks.chunk_uris.length?<fieldset disabled={busy}><legend>Registered chunk identities</legend>{chunks.chunk_uris.map(uri=><label key={uri}><input type="checkbox" checked={selected.includes(uri)} disabled={busy||(!selected.includes(uri)&&selected.length>=50)} onChange={event=>setSelected(current=>event.target.checked?[...current,uri]:current.filter(item=>item!==uri))}/><code>{uri}</code></label>)}</fieldset>:<p>No registered chunks are available yet. Refresh this submission after upstream extraction has produced them.</p>}<div className="form-actions"><span className="small muted">{selected.length} selected</span><button className="button button-primary" disabled={busy||!canResearch||!selected.length} onClick={()=>void freeze()}>Verify and freeze selected passages</button></div></div>}
        {frozen?.provider_snapshot&&<div className="trustgraph-frozen"><h4>Verified selected passages</h4><p className="field-help">Local corpus <code>{frozen.id}</code>. Only this selection is verified; upstream completion remains unverified.</p><EvidenceList evidence={frozen.provider_snapshot.chunks.map(chunk=>({id:chunk.evidence_id,document_id:chunk.source_id,title:title(chunk.source_id),quote:chunk.quote,locator:`Characters ${chunk.span_start}–${chunk.span_end}`,content_hash:chunk.chunk_artifact.sha256,resolved:true}))}/>{frozen.provider_snapshot.chunks.map(chunk=><details key={chunk.evidence_id}><summary>Frozen provenance · {short(chunk.evidence_id)}</summary><dl><dt>Chunk URI</dt><dd><code>{chunk.upstream_chunk_uri}</code></dd><dt>Source graph</dt><dd><code>{chunk.graph_uri}</code></dd><dt>Extraction subgraphs</dt><dd>{chunk.subgraph_uris.map(uri=><code key={uri}>{uri}</code>)}</dd></dl></details>)}</div>}
      </>}
      {busy&&<div role="status" className="inline-loading"><span className="spinner"/>{stage.replaceAll('_',' ')}…</div>}
    </div>
  </section>;
}
