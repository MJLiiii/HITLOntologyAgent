import { useEffect, useState } from 'react';
import type { ReviewTimingEvent, Session } from '../../api/generated';
import type { ReviewSessionEvent } from '../../api/openapi';
import { errorMessage, list, post } from '../../api/client';
import { ErrorNotice } from '../../components/ui';
import { Icon } from '../../components/Icons';

function duration(seconds:number) {
  const total=Math.max(0,Math.floor(seconds));
  const hours=Math.floor(total/3600), minutes=Math.floor(total%3600/60), remainder=total%60;
  return `${hours?`${hours}:`:''}${String(minutes).padStart(2,'0')}:${String(remainder).padStart(2,'0')}`;
}

export function ReviewTimer({projectId,revisionId,session,disabled=false}: {projectId:string;revisionId:string;session:Session;disabled?:boolean}) {
  const [events,setEvents]=useState<ReviewTimingEvent[]>([]);
  const [loading,setLoading]=useState(true);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  const [clock,setClock]=useState(Date.now());
  const [reload,setReload]=useState(0);
  const path=`/projects/${encodeURIComponent(projectId)}/review-sessions`;
  const ownEvents=events.filter(event=>!event.actor || event.actor.subject===session.actor.subject);
  const latest=ownEvents.at(-1);
  const running=latest?.event==='start'||latest?.event==='resume';
  const paused=latest?.event==='pause';
  const recorded=latest?.active_seconds ?? 0;
  const started=latest?Date.parse(latest.time):NaN;
  const elapsed=recorded+(running&&Number.isFinite(started)?Math.max(0,clock-started)/1000:0);
  const human=session.actor.kind==='human';
  const blocked=disabled||busy||loading||!human;
  useEffect(()=>{
    let active=true;setLoading(true);setError('');setEvents([]);
    list<ReviewTimingEvent>(`${path}?revision_id=${encodeURIComponent(revisionId)}`).then(result=>{if(active){setEvents(result);setClock(Date.now());}}).catch(err=>{if(active)setError(errorMessage(err));}).finally(()=>{if(active)setLoading(false);});
    return()=>{active=false;};
  },[path,revisionId,reload]);
  useEffect(()=>{
    if(!running)return;
    const interval=window.setInterval(()=>setClock(Date.now()),1000);
    return()=>window.clearInterval(interval);
  },[running,latest?.id]);
  async function record(event:ReviewTimingEvent['event']) {
    if(blocked)return;
    setBusy(true);setError('');
    try {
      const result=await post<ReviewTimingEvent>(path,{revision_id:revisionId,event} satisfies ReviewSessionEvent);
      setEvents(previous=>[...previous,result]);setClock(Date.now());
    }catch(err){
      setError(errorMessage(err));
      try{setEvents(await list<ReviewTimingEvent>(`${path}?revision_id=${encodeURIComponent(revisionId)}`));}catch{/* Retain the original action error. */}
    }finally{setBusy(false);}
  }
  return <div className="review-timer"><div className="timer-topline"><div className="timer-title"><Icon name="clock" size={17}/><strong>Review time</strong><span className={`timer-state ${running?'running':''}`}>{loading?'Loading timing…':running?'Running':paused?'Paused':latest?'Ended':'Not started'}</span></div><output className="timer-value" aria-label="Active review time">{duration(elapsed)}</output><button className="icon-button" aria-label="Reload review timer" disabled={busy||loading} onClick={()=>setReload(value=>value+1)}><Icon name="refresh" size={14}/></button></div>
    <div className="timer-actions">{!running&&!paused?<button className="button button-secondary small" disabled={blocked||!!error} onClick={()=>void record('start')}>Start review timer</button>:<><button className="button button-secondary small" disabled={blocked} onClick={()=>void record(running?'pause':'resume')}>{running?'Pause review timer':'Resume review timer'}</button><button className="button button-quiet small" disabled={blocked} onClick={()=>void record('end')}>End review timer</button></>}<span>{recorded.toFixed(1)}s recorded by the server{running?' · live total estimated above':''}</span></div>
    <p className="timer-note">{running?'Timing continues until you explicitly pause or end it, including while you navigate.':'Timing starts only when you click Start. Pauses are excluded from the recorded active total.'} Records belong to you and this exact revision.</p>
    {error&&<ErrorNotice message={error}/>}{!human&&<p className="action-reason">A human session is required to record review time.</p>}
    {!!ownEvents.length&&<details className="timer-history"><summary>Recorded timing events ({ownEvents.length})</summary><ol>{ownEvents.map(event=><li key={event.id}><strong>{event.event}</strong><time dateTime={event.time}>{new Date(event.time).toLocaleString()}</time><span>{event.active_seconds.toFixed(1)}s active</span></li>)}</ol></details>}
  </div>;
}
