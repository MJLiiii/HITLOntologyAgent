import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ReviewTimer } from './ReviewTimer';
import type { ReviewTimingEvent, Session } from '../../api/generated';

const session:Session={actor:{subject:'reviewer',kind:'human',roles:['reviewer']},mode:'local',model_mode:'local'};
afterEach(()=>vi.unstubAllGlobals());

describe('explicit review timing',()=>{
  it('does not start on page view and persists only explicitly clicked timing events',async()=>{
    const writes:unknown[]=[];
    const events:ReviewTimingEvent[]=[];
    vi.stubGlobal('fetch',vi.fn(async(path:string,options:RequestInit={})=>{
      if(options.method==='POST'){
        const body=JSON.parse(String(options.body));writes.push(body);
        const event:ReviewTimingEvent={created_at:new Date().toISOString(),status:"recorded",id:`event-${events.length}`,revision_id:body.revision_id,event:body.event,active_seconds:body.event==='pause'?17.5:body.event==='end'?30:events.at(-1)?.active_seconds||0,time:new Date().toISOString(),actor:{subject:'reviewer',kind:'human',roles:['reviewer']}};
        events.push(event);return new Response(JSON.stringify(event));
      }
      expect(path).toBe('/api/v1/projects/p/review-sessions?revision_id=revision%2Fone');
      return new Response(JSON.stringify({items:events,next_cursor:null}));
    }));
    const first=render(<ReviewTimer projectId="p" revisionId="revision/one" session={session}/>);
    await waitFor(()=>expect(screen.getByRole('button',{name:'Start review timer'})).toBeEnabled());
    expect(writes).toHaveLength(0);
    fireEvent.click(screen.getByRole('button',{name:'Start review timer'}));
    await screen.findByText('Running');
    fireEvent.click(screen.getByRole('button',{name:'Pause review timer'}));
    await screen.findByText('Paused');
    expect(screen.getByLabelText('Active review time')).toHaveTextContent('00:17');
    first.unmount();
    render(<ReviewTimer projectId="p" revisionId="revision/one" session={session}/>);
    await screen.findByText('Paused');
    expect(writes).toHaveLength(2);
    expect(screen.getByLabelText('Active review time')).toHaveTextContent('00:17');
    fireEvent.click(screen.getByRole('button',{name:'Resume review timer'}));
    await screen.findByText('Running');
    fireEvent.click(screen.getByRole('button',{name:'End review timer'}));
    await screen.findByText('Ended');
    expect(screen.getByLabelText('Active review time')).toHaveTextContent('00:30');
    expect(writes).toEqual(['start','pause','resume','end'].map(event=>({revision_id:'revision/one',event})));
    expect(screen.getByText('30.0s recorded by the server')).toBeInTheDocument();
  });
  it('shows timing retrieval failure without silently starting a new timer',async()=>{
    vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response(JSON.stringify({code:'forbidden',message:'Human session required'}),{status:403})));
    render(<ReviewTimer projectId="p" revisionId="r" session={session}/>);
    await screen.findByRole('alert');
    expect(screen.getByRole('button',{name:'Start review timer'})).toBeDisabled();
    expect(screen.getByRole('button',{name:'Reload review timer'})).toBeEnabled();
  });
});
