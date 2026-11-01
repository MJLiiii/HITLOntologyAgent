import { useRef, useState } from 'react';
import type { Project, Session, SourceDocument } from '../../api/generated';
import { errorMessage, post, request, runJob } from '../../api/client';
import { Badge, date, Empty, ErrorNotice, PanelHeading, short } from '../../components/ui';
import { Icon } from '../../components/Icons';
import { ScopePanel } from './ScopePanel';
import { SeedImportPanel } from './SeedImportPanel';
export function SourceCard({source, onIngest, busy}: {source: SourceDocument; onIngest: (source: SourceDocument) => void; busy: boolean}) {
  const statusText: Record<string,string> = {uploaded: 'Uploaded · not yet processed', queued: 'Queued for processing', processing: 'Processing source', complete: 'Ready for retrieval', failed: 'Processing failed', incomplete: 'Extraction incomplete'};
  return <article className="source-card"><div className="source-card-top"><div className="source-file-icon"><Icon name="file" size={24}/></div><div><h3>{source.title}</h3><p>{source.edition || 'Unspecified edition'} · {source.classification}</p></div><Badge status={source.status}>{statusText[source.status] || source.status}</Badge></div><div className="source-card-meta"><span><Icon name="clock" size={14}/>{date(source.created_at)}</span><span>{source.chunk_count ?? 0} source chunks</span>{source.content_hash && <code title={source.content_hash}>{short(source.content_hash)}</code>}</div>{source.extraction?.diagnostics?.map((reason, i) => <p className="error-text" key={i}>{reason}</p>)}{source.error && <p className="error-text">{source.error}</p>}{source.text && <details className="source-preview"><summary>Preview source text</summary><p>{source.text}</p></details>}{['uploaded','failed','incomplete'].includes(source.status) && <button className="button button-secondary small" disabled={busy} onClick={() => onIngest(source)}><Icon name="refresh" size={14}/>Process source</button>}</article>;
}
export function SourcesView({project, session, sources, onRefresh, onOpenProposal}: {project: Project; session: Session; sources: SourceDocument[]; onRefresh: () => Promise<void>; onOpenProposal: (id:string) => void}) {
  const file = useRef<HTMLInputElement>(null);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [stage, setStage] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  async function ingest(source: SourceDocument) {
    setBusy(true); setError(''); setStage('Processing source');
    try { const result = await runJob<{status:string}>(`/projects/${encodeURIComponent(project.id)}/ingestions`, {document_id:source.id, configured_flow_key:'default'}, setStage); await onRefresh(); if (result.status !== 'completed') {setError('Extraction is incomplete. Inspect the document diagnostics; it cannot enter a corpus snapshot.'); setNotice('');} else {setNotice('Source processing completed. Freeze a new corpus snapshot to include it in future proposals.');} }
    catch (err) {setError(errorMessage(err));} finally {setBusy(false);}
  }
  async function upload(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const selectedFile = data.get('file') as File;
    if (!selectedFile?.size) {setError('Choose a document to upload.');return;}
    if (selectedFile.size > 20 * 1024 * 1024) {setError('Choose a file no larger than 20 MiB.');return;}
    setBusy(true); setError(''); setStage('Uploading source');
    try {await request<SourceDocument>(`/projects/${encodeURIComponent(project.id)}/documents`, {method:'POST',body:data}); await onRefresh(); setUploadOpen(false); setNotice('Document uploaded. Process the source before adding it to a corpus snapshot.');}
    catch(err) {setError(errorMessage(err));} finally {setBusy(false);}
  }
  async function freeze() {
    setBusy(true);setError('');setStage('Freezing evidence snapshot');
    try {await post(`/projects/${encodeURIComponent(project.id)}/corpus-snapshots`, {ingestion_run_ids:sources.filter(s => s.status === 'complete' && s.ingestion_run_id).map(s => s.ingestion_run_id)}); await onRefresh();setNotice('A new immutable corpus snapshot is ready. Existing proposals keep their original evidence snapshot.');}
    catch(err) {setError(errorMessage(err));} finally {setBusy(false);}
  }
  return <div className="page-content"><PanelHeading title="Knowledge starts with its sources" subtitle="Versioned documents and verified evidence keep your ontology grounded." action={<button className="button button-primary" onClick={() => setUploadOpen(!uploadOpen)}><Icon name="plus" size={16}/>Add source</button>}/>
    {error && <ErrorNotice message={error} onDismiss={() => setError('')}/>}{notice && <div className="notice notice-success" role="status"><Icon name="check"/><span>{notice}</span></div>}
    <ScopePanel project={project} session={session} onRefresh={onRefresh}/>
    {uploadOpen && <form className="panel form-panel" onSubmit={e => void upload(e)}><h3>Add a source document</h3><div className="form-grid"><label>Document title<input name="title" required placeholder="e.g. Service ownership handbook"/></label><label>Edition<input name="edition" required defaultValue="1.0"/></label><label>Classification<select name="classification"><option value="synthetic">Synthetic</option><option value="public">Public</option></select></label><label>Rights<input name="rights" required defaultValue="Synthetic demonstration material"/></label></div><label className="file-drop"><Icon name="sources" size={25}/><strong>Choose a document</strong><span>PDF, UTF-8 Text or Markdown · up to 20 MiB</span><input ref={file} type="file" name="file" accept=".pdf,.txt,.md" required/></label><div className="form-actions"><button className="button button-secondary" type="button" onClick={() => setUploadOpen(false)}>Cancel</button><button className="button button-primary" disabled={busy} type="submit">{busy ? 'Uploading…' : 'Upload document'}</button></div></form>}
    <div className="section-heading"><h2>Source library <span className="count">{sources.length}</span></h2><span className="small muted">{sources.filter(s => s.status === 'complete').length} ready for retrieval</span></div>
    {busy && <div role="status" className="inline-loading"><span className="spinner"/>{stage || 'Updating workspace'}…</div>}
    {sources.length ? <div className="source-grid">{sources.map(source => <SourceCard key={source.id} source={source} onIngest={s => void ingest(s)} busy={busy}/>)}</div> : <Empty icon="sources" title="Give your ontology a source">Upload a public or synthetic document, then process it to resolve evidence.</Empty>}
    <div className="panel corpus-panel"><div><div className="card-eyebrow">CURRENT CORPUS SNAPSHOT</div><h3><Icon name="branch" size={17}/><code>{short(project.corpus_snapshot_id)}</code></h3><p>Snapshots freeze the exact source editions behind a proposal. A new snapshot leaves previous evidence intact.</p></div><button className="button button-secondary" disabled={busy || !sources.some(s => s.status === 'complete' && s.ingestion_run_id)} onClick={() => void freeze()}>Freeze corpus snapshot</button></div>
    <SeedImportPanel project={project} session={session} onRefresh={onRefresh} onOpenProposal={onOpenProposal}/>
  </div>;
}
