import { useRef, useState, useEffect } from 'react';
import type { Answer, Project, Session, SourceDocument, Version } from '../../api/generated';
import type { QuestionRequest } from '../../api/openapi';
import { errorMessage, runJob } from '../../api/client';
import { Badge, EvidenceList, ErrorNotice, TripleTable, short } from '../../components/ui';
import { Icon } from '../../components/Icons';
import { ModelSelector, useModelSelection } from '../../components/ModelSelector';
interface Message { id: string; role: 'user' | 'assistant'; content: string; result?: Answer }
const sourceLabels={ontology_version:'Ontology version sources',project_current:'Current source corpus',explicit:'Selected source corpus'};
const suggestions = [
  {icon: 'ontology' as const, title: 'Understand the ontology', prompt: 'What concepts and relationships are in this ontology?'},
  {icon: 'sources' as const, title: 'Follow the evidence', prompt: 'What do the sources say about service ownership?'},
  {icon: 'proposals' as const, title: 'Find the missing connections', prompt: 'Which ownership relationships could improve this ontology?'},
];
export function ChatView({project, session, versions, sources, onNavigate}: {project: Project; session: Session; versions: Version[]; sources: SourceDocument[]; onNavigate: (view: string) => void}) {
  const canResearch=session.mode!=='team'||session.actor.roles.includes('researcher');
  const model=useModelSelection(project.id,'chat',{enabled:session.model_mode!=='local'});
  const conversationId = useRef(crypto.randomUUID());
  const [messages, setMessages] = useState<Message[]>([]);
  const [question, setQuestion] = useState('');
  const [busy, setBusy] = useState(false);
  const [stage, setStage] = useState('Retrieving evidence');
  const [error, setError] = useState('');
  const [sourceSelection,setSourceSelection]=useState<'ontology_version'|'current'>('ontology_version');
  const end = useRef<HTMLDivElement>(null);
  const textarea = useRef<HTMLTextAreaElement>(null);
  const version = versions.find(v => v.id === project.approved_version_id) || versions[0];
  useEffect(() => { if (messages.length) end.current?.scrollIntoView?.({behavior:'smooth', block:'end'}); }, [messages.length, busy]);
  async function send(text = question) {
    if (!canResearch || !model.ready || !text.trim() || busy) return;
    const prompt = text.trim();
    const history = messages.slice(-12).map(({role, content}) => ({role, content}));
    setMessages(prev => [...prev, {id: crypto.randomUUID(), role:'user', content:prompt}]);
    setQuestion(''); setBusy(true); setError('');
    try {
      const result = await runJob('POST /api/v1/projects/{p}/question-jobs', {path:{p:project.id},body:{question: prompt, history, conversation_id:conversationId.current, ...(model.profileId?{model_profile_id:model.profileId}:{}), ...(sourceSelection==='current'&&project.corpus_snapshot_id?{corpus_snapshot_id:project.corpus_snapshot_id}:{})} satisfies QuestionRequest}, setStage);
      setMessages(prev => [...prev, {id: crypto.randomUUID(), role:'assistant', content:result.answer, result}]);
    } catch (err) { setError(errorMessage(err)); setQuestion(prompt); }
    finally { setBusy(false); textarea.current?.focus(); }
  }
  return <div className="chat-grid"><div className="chat-column">
    <div className="chat-toolbar"><div className="small muted"><span className="live-dot"/> Grounded in your workspace</div><button className="text-button small" onClick={() => {conversationId.current = crypto.randomUUID(); setMessages([]); setQuestion(''); setError('');}} disabled={busy || !messages.length}><Icon name="plus" size={15}/>New conversation</button></div>
    <div className={`conversation ${messages.length ? 'has-messages' : ''}`} aria-live="polite">
      {!messages.length && <div className="chat-welcome"><div className="welcome-mark"><Icon name="spark" size={30}/></div><span className="eyebrow">KNOWLEDGE, CONNECTED</span><h1>Good questions.<br/><span>Better ontologies.</span></h1><p>Explore your sources, understand relationships, and develop your ontology with evidence at every step.</p><div className="suggestion-list">{suggestions.map(s => <button className="suggestion" key={s.title} onClick={() => void send(s.prompt)} disabled={busy||!canResearch||!model.ready}><div className="suggestion-icon"><Icon name={s.icon}/></div><span><strong>{s.title}</strong><small>{s.prompt}</small></span><Icon name="chevron" size={16}/></button>)}</div><div className="welcome-note"><Icon name="shield" size={14}/> Every ontology change stays under human review.</div></div>}
      {messages.map(message => <div className={`message message-${message.role}`} key={message.id}><div className={`avatar ${message.role === 'assistant' ? 'avatar-studio' : ''}`}>{message.role === 'assistant' ? <Icon name="spark" size={17}/> : 'Y'}</div><div className="message-body"><div className="message-label">{message.role === 'assistant' ? 'Ontology Studio' : 'You'}{message.role === 'assistant' && <span>{session.model_mode === 'local' ? 'Local retrieval' : 'Grounded assistant'}</span>}</div><div className="answer-text">{message.content.split('\n').filter(Boolean).map((line,i) => <p key={i}>{line}</p>)}</div>{message.result && <>
        {!!message.result.evidence?.length && <div className="answer-section"><h3><Icon name="sources" size={15}/> Sources <span className="count">{message.result.evidence.length}</span></h3><EvidenceList evidence={message.result.evidence} compact/></div>}
        {!!message.result.triples?.length && <details className="answer-triples" open><summary><Icon name="ontology" size={16}/> Ontology results <span className="count">{message.result.triples.length} triples</span></summary><TripleTable triples={message.result.triples} compact/></details>}
        {message.result.limitations?.map((note,i) => <p key={i} className="answer-limit small muted">{note}</p>)}
        {message.result.source_selection&&<p className="answer-source-context small muted" aria-label="Answer source context">{sourceLabels[message.result.source_selection]}{message.result.corpus_snapshot_id&&<> · <code title={message.result.corpus_snapshot_id}>{short(message.result.corpus_snapshot_id)}</code></>}</p>}
        <div className="answer-footer"><Icon name="shield" size={13}/> Read-only answer · {message.result.version_id ? `version ${short(message.result.version_id)}${message.result.ontology_status === 'reference' ? ' · demo reference, not approved' : message.result.ontology_status === 'candidate' ? ' · candidate, not approved' : ''}` : 'workspace evidence'}</div>
      </>}</div></div>)}
      {busy && <div className="message message-assistant"><div className="avatar avatar-studio"><Icon name="spark" size={17}/></div><div className="thinking" role="status"><span className="spinner"/>{stage.replaceAll('_',' ')}…</div></div>}
      <div ref={end}/>
    </div>
    <div className="composer-wrap"><div className="chat-model-selection"><ModelSelector label="Chat model" selection={model} disabled={busy||!canResearch} onChange={()=>{conversationId.current=crypto.randomUUID();setMessages([]);setError('');}}/>{model.enabled&&<p className="field-help">Changing models starts a new conversation.</p>}</div><div className="chat-source-selection"><label>Answer sources<select value={sourceSelection==='current'&&!project.corpus_snapshot_id?'ontology_version':sourceSelection} disabled={busy||!canResearch} onChange={event=>setSourceSelection(event.target.value as 'ontology_version'|'current')}><option value="ontology_version">Ontology version sources</option>{project.corpus_snapshot_id&&<option value="current">Current source corpus</option>}</select></label>{sourceSelection==='current'&&project.corpus_snapshot_id&&<code title={project.corpus_snapshot_id}>{short(project.corpus_snapshot_id)}</code>}</div>{sourceSelection==='current'&&project.corpus_snapshot_id&&<p className="chat-source-note">This source corpus may be newer than the ontology. Reading it does not approve or change the ontology.</p>}{error && <ErrorNotice message={error} onDismiss={() => setError('')}/>}<form className="composer" onSubmit={e => {e.preventDefault(); void send();}}><label htmlFor="chat-question" className="sr-only">Ask about your ontology or sources</label><textarea ref={textarea} id="chat-question" maxLength={4000} value={question} onChange={e => setQuestion(e.target.value)} placeholder="Ask about your ontology or sources…" rows={2} disabled={busy||!canResearch} onKeyDown={e => {if(e.key === 'Enter' && !e.shiftKey){e.preventDefault(); void send();}}}/><div className="composer-bottom"><span className="composer-context"><Icon name="ontology" size={14}/>{version?.label || 'Workspace context'}<span className="separator-dot">·</span>{sourceSelection==='current'&&project.corpus_snapshot_id?'Current source corpus':'Ontology version sources'}</span><button className="send-button" type="submit" aria-label="Send question" disabled={!canResearch || !question.trim() || busy || !model.ready}>{busy ? <span className="spinner"/> : <Icon name="arrow" size={20}/>}</button></div></form><p className="composer-hint">{session.model_mode === 'local' ? 'Local retrieval mode. Answers use matching source passages; no language model is connected.' : 'Answers are grounded in retrieved evidence. Review the cited sources before accepting a change.'}</p></div>
  </div><aside className="context-rail" aria-label="Workspace context"><div className="context-title"><Icon name="ontology" size={17}/><h2>Working context</h2></div><section className="context-card"><div className="card-eyebrow">ONTOLOGY</div><h3>{project.name}</h3><Badge status={project.approved_version_id ? 'approved' : 'reference'}>{project.approved_version_id ? 'Approved version' : 'Demo reference · not approved'}</Badge><div className="context-metrics"><div><strong>{version?.class_count ?? 0}</strong><span>Classes</span></div><div><strong>{version?.property_count ?? 0}</strong><span>Properties</span></div><div><strong>{version?.triple_count ?? 0}</strong><span>Triples</span></div></div><button className="card-link" onClick={() => onNavigate('ontology')}>Explore ontology<Icon name="chevron" size={15}/></button></section>
  <section className="context-section"><div className="section-label"><h3>Source library</h3><span className="count">{sources.length}</span></div>{sources.slice(0,4).map(source => <button className="source-mini" key={source.id} onClick={() => onNavigate('sources')}><div className="document-icon"><Icon name="file" size={16}/></div><span><strong>{source.title}</strong><small>{source.classification} · {source.chunk_count ?? 0} chunks</small></span></button>)}<button className="text-button small context-link" onClick={() => onNavigate('sources')}>View all sources<Icon name="chevron" size={14}/></button></section>
  <section className="workflow-note"><div className="workflow-note-icon"><Icon name="shield" size={18}/></div><h3>Built for thoughtful change</h3><p>Explore in chat. Propose a change. Validate the candidate. Review every release.</p><button className="text-button small" onClick={() => onNavigate('proposals')}>Open proposals<Icon name="chevron" size={14}/></button></section><div className="context-footnote"><Icon name="branch" size={14}/><span>Current source corpus <code>{short(project.corpus_snapshot_id)}</code><br/>Public & synthetic sources only</span></div>
  </aside></div>;
}
