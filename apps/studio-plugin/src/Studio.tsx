import { useCallback, useEffect, useState } from 'react';
import type { Experiment, Project, Proposal, Session, SourceDocument, Version } from './api/generated';
import { ApiError, errorMessage, list, request } from './api/client';
import { Icon, type IconName } from './components/Icons';
import { Badge, ErrorNotice, Loading, short } from './components/ui';
import { ChatView } from './features/chat/ChatView';
import { OntologyView } from './features/ontology/OntologyView';
import { SourcesView } from './features/sources/SourcesView';
import { ProposalsView } from './features/proposals/ProposalsView';
import { ValidationView } from './features/validation/ValidationView';
import { ExperimentsView } from './features/experiments/ExperimentsView';
import './styles.css';

const navigation: {id:string;title:string;icon:IconName;description:string}[] = [
  {id:'chat',title:'Chat',icon:'chat',description:'Explore knowledge, grounded in evidence'},
  {id:'ontology',title:'Ontology',icon:'ontology',description:'Vocabulary and immutable version history'},
  {id:'sources',title:'Sources',icon:'sources',description:'The evidence behind your knowledge'},
  {id:'proposals',title:'Proposals',icon:'proposals',description:'A clear path from candidate to approved version'},
  {id:'validation',title:'Validation',icon:'validation',description:'Logical checks and task fitness'},
  {id:'experiments',title:'Experiments',icon:'experiments',description:'Reproducible comparisons across conditions A–D'},
];

export function Studio() {
  const [view,setView] = useState('chat');
  const [menu,setMenu] = useState(false);
  const [projects,setProjects] = useState<Project[]>([]);
  const [project,setProject] = useState<Project|null>(null);
  const [session,setSession] = useState<Session|null>(null);
  const [versions,setVersions] = useState<Version[]>([]);
  const [sources,setSources] = useState<SourceDocument[]>([]);
  const [proposals,setProposals] = useState<Proposal[]>([]);
  const [experiments,setExperiments] = useState<Experiment[]>([]);
  const [selection,setSelection] = useState('');
  const [loading,setLoading] = useState(true);
  const [refreshing,setRefreshing] = useState(false);
  const [error,setError] = useState('');
  const [locked,setLocked] = useState(false);
  const [unlockToken,setUnlockToken] = useState('');

  const loadProject = useCallback(async (id: string) => {
    const base=`/projects/${encodeURIComponent(id)}`;
    const [p,v,s,pr,e] = await Promise.all([request<Project>(base),list<Version>(`${base}/versions`),list<SourceDocument>(`${base}/documents`),list<Proposal>(`${base}/proposals`),list<Experiment>(`${base}/experiments`)]);
    setProject(p);setVersions(v);setSources(s);setProposals(pr);setExperiments(e);
  },[]);
  const initialize = useCallback(async (suppliedToken?:string) => {
    setLoading(true);setError('');
    try {
      const fragment=new URLSearchParams(window.location.hash.slice(1));
      const token=suppliedToken ?? fragment.get('session');
      const currentSession=await request<Session>('/session',token?{headers:{'X-OE-Session-Token':token}}:{});
      setSession(currentSession);setLocked(false);setUnlockToken('');
      if(fragment.has('session')) {fragment.delete('session');const remaining=fragment.toString();window.history.replaceState(window.history.state,'',`${window.location.pathname}${window.location.search}${remaining?`#${remaining}`:''}`);}
      const allProjects=await list<Project>('/projects');setProjects(allProjects);if(allProjects[0])await loadProject(allProjects[0].id);
    }
    catch(err){if(err instanceof ApiError && err.status===401){setSession(null);setLocked(true);setError('Use the local session link or token printed by the launcher to open this workspace.');}else setError(errorMessage(err));}finally{setLoading(false);}
  },[loadProject]);
  useEffect(()=>{void initialize();},[initialize]);
  const refresh = useCallback(async () => {
    if(!project)return;
    setRefreshing(true);setError('');
    try {await loadProject(project.id);}catch(err){setError(errorMessage(err));throw err;}finally{setRefreshing(false);}
  },[project?.id,loadProject]);
  function navigate(next: string) {if(navigation.some(n=>n.id===next)){setView(next);setMenu(false);}}
  function openProposal(id:string) {setSelection(id);navigate('proposals');}
  const active=navigation.find(n=>n.id===view)!;
  const currentVersion=versions.find(v=>v.id===project?.approved_version_id);

  if(loading) return <div className="ontology-studio boot-screen"><div className="brand-mark"><Icon name="ontology" size={25}/></div><h1>Ontology Studio</h1><Loading label="Opening your knowledge workspace…"/></div>;
  if(!session || !project) return <div className="ontology-studio boot-screen"><div className="brand-mark"><Icon name="ontology" size={25}/></div><h1>{locked?'Open your local workspace':'Connect to your workspace'}</h1><p className="muted">{locked?'Use the link or session token printed in the terminal by the local launcher.':'The Studio needs a running project API and an authenticated local session.'}</p>{error && <ErrorNotice message={error}/>}{locked?<form className="unlock-form" onSubmit={event=>{event.preventDefault();void initialize(unlockToken.trim());}}><label>Local session token<input type="password" value={unlockToken} onChange={event=>setUnlockToken(event.target.value)} autoComplete="off" spellCheck={false} required autoFocus/></label><button className="button button-primary" type="submit" disabled={!unlockToken.trim()}><Icon name="shield" size={16}/>Open workspace</button><p className="muted small">The token is used once to establish this browser session and is not saved in browser storage.</p></form>:<button className="button button-primary" onClick={()=>void initialize()}>Retry connection<Icon name="refresh" size={16}/></button>}</div>;
  return <div className={`ontology-studio studio-shell ${menu?'nav-open':''}`}><a href="#studio-content" className="skip-link">Skip to workspace</a>{menu && <button className="nav-backdrop" aria-label="Close navigation" onClick={()=>setMenu(false)}/>}<aside id="studio-navigation" className="sidebar" aria-label="Main navigation"><div className="brand"><div className="brand-mark"><Icon name="ontology" size={23}/></div><div><strong>Ontology Studio</strong><span>KNOWLEDGE WORKSPACE</span></div></div>
    <div className="project-switcher"><span className="project-avatar">{project.name[0]}</span><label><span className="card-eyebrow">PROJECT</span><select aria-label="Select project" value={project.id} disabled={refreshing} onChange={e=>{const id=e.target.value;setLoading(true);setSelection('');setView('chat');void loadProject(id).catch(err=>setError(errorMessage(err))).finally(()=>setLoading(false));}}>{projects.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select></label></div>
    <div className="nav-label">WORKSPACE</div><nav>{navigation.map(item=><button key={item.id} className={`nav-item ${view===item.id?'active':''}`} aria-current={view===item.id?'page':undefined} onClick={()=>navigate(item.id)}><Icon name={item.icon} size={19}/><span>{item.title}</span>{item.id==='proposals' && proposals.filter(p=>!['published','rejected'].includes(p.status)).length>0 && <span className="nav-count">{proposals.filter(p=>!['published','rejected'].includes(p.status)).length}</span>}</button>)}</nav>
    <div className="sidebar-bottom"><div className="environment-card"><div><span className="live-dot"/><strong>{project.mode==='demo'?'Synthetic demo':'Project workspace'}</strong></div><p>{session.model_mode==='local'?'Local retrieval is active':'Configured model is active'}</p><span>Human approval required</span></div><div className="user-profile"><span className="user-avatar">{session.actor.subject[0]?.toUpperCase() || 'L'}</span><div><strong>{session.mode==='demo'?'Local researcher':session.actor.subject}</strong><span>{session.actor.kind==='human'?'Human session':'Service session'}</span></div><Icon name="shield" size={17}/></div></div>
  </aside><div className="workspace"><header className="workspace-header"><button className="icon-button mobile-menu" aria-label="Open navigation" aria-expanded={menu} aria-controls="studio-navigation" onClick={()=>setMenu(!menu)}><Icon name="menu"/></button><div className="header-title"><span className="breadcrumb">Workspace <Icon name="chevron" size={12}/> {active.title}</span><h2>{active.title}<span>{active.description}</span></h2></div><div className="header-actions"><Badge status={project.approved_version_id?'approved':'reference'}>{currentVersion?.label || (project.approved_version_id?'Approved version':'No approved version')}</Badge><button className="icon-button" aria-label="Refresh workspace" disabled={refreshing} onClick={()=>void refresh().catch(()=>{})}><Icon name="refresh" size={17} className={refreshing?'rotating':''}/></button></div></header>
    <div className="workspace-context"><span><Icon name="branch" size={13}/>Corpus <code title={project.corpus_snapshot_id || ''}>{short(project.corpus_snapshot_id)}</code></span><span><span className="status-dot"/>{project.mode==='demo'?'Synthetic & public sources':'Project sources'}</span><span className="scope-state">{project.scope_accepted?'Scope accepted':'Scope awaiting human acceptance'}</span></div>
    <main id="studio-content" className={`workspace-main view-${view}`} tabIndex={-1}>{error && <div className="global-error"><ErrorNotice message={error} onDismiss={()=>setError('')}/></div>}
      <div hidden={view!=='chat'}><ChatView key={project.id} project={project} session={session} versions={versions} sources={sources} onNavigate={navigate}/></div>
      {view==='ontology' && <OntologyView project={project} versions={versions} onPropose={()=>navigate('proposals')} onOpenProposal={openProposal}/>}
      {view==='sources' && <SourcesView project={project} session={session} sources={sources} onRefresh={refresh} onOpenProposal={openProposal}/>}
      {view==='proposals' && <ProposalsView project={project} session={session} proposals={proposals} initialSelection={selection} onRefresh={refresh} onSources={()=>navigate('sources')}/>}
      {view==='validation' && <ValidationView project={project} session={session} proposals={proposals} onOpenProposal={openProposal} onRefresh={refresh}/>}
      {view==='experiments' && <ExperimentsView project={project} experiments={experiments} proposals={proposals} session={session} onRefresh={refresh} onOpenProposal={openProposal}/>}
    </main>
  </div></div>;
}
