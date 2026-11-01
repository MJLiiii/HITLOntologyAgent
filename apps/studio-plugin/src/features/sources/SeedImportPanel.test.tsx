import { projectFixture } from '../../test-fixtures';
import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { SeedImportPanel } from './SeedImportPanel';
import type { Project, Session } from '../../api/generated';

const project:Project=projectFixture({id:'p',name:'Demo',domain:'demo',approved_version_id:null,corpus_snapshot_id:'frozen-corpus',scope_accepted:false,scope_digest:'exact-scope'});
const session:Session={actor:{subject:'human',kind:'human',roles:['researcher']},mode:'local',model_mode:'local'};
afterEach(()=>vi.unstubAllGlobals());

describe('staged Turtle seed import',()=>{
  it('sends the inspected Turtle, rationale and frozen corpus as an idempotent candidate job without approving it',async()=>{
    const writes:{path:string;body:unknown;headers:Headers}[]=[];
    vi.stubGlobal('fetch',vi.fn(async(path:string,options:RequestInit={})=>{
      if(options.method==='POST')writes.push({path,body:JSON.parse(String(options.body)),headers:new Headers(options.headers)});
      if(path.endsWith('/seed-imports'))return new Response(JSON.stringify({job_id:'seed-job'}));
      if(path.endsWith('/jobs/seed-job'))return new Response(JSON.stringify({id:'seed-job',status:'succeeded',result:{proposal_id:'seed-proposal',revision:1,bundle_digest:'candidate-bundle'}}));
      return new Response(JSON.stringify(project));
    }));
    const refresh=vi.fn().mockResolvedValue(undefined),open=vi.fn();
    render(<SeedImportPanel project={project} session={session} onRefresh={refresh} onOpenProposal={open}/>);
    fireEvent.click(screen.getByRole('button',{name:'Import seed ontology'}));
    const ttl='<https://example.org/oe-demo/Service> a <http://www.w3.org/2002/07/owl#Class> .';
    fireEvent.change(screen.getByLabelText('Seed ontology (Turtle)'),{target:{value:ttl}});
    fireEvent.change(screen.getByLabelText('Seed import rationale'),{target:{value:'Initial service vocabulary grounded in the frozen source library.'}});
    expect(writes).toEqual([]);
    fireEvent.click(screen.getByRole('button',{name:'Stage seed candidate'}));
    await screen.findByText(/Seed staged as candidate revision 1/);
    expect(writes).toHaveLength(1);
    expect(writes[0].path).toBe('/api/v1/projects/p/seed-imports');
    expect(writes[0].body).toEqual({ontology_ttl:ttl,corpus_snapshot_id:'frozen-corpus',profile:'rdfs',rationale:'Initial service vocabulary grounded in the frozen source library.'});
    expect(writes[0].headers.get('Idempotency-Key')).toBeTruthy();
    expect(refresh).toHaveBeenCalledOnce();
    expect(open).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button',{name:'Review seed candidate'}));
    expect(open).toHaveBeenCalledWith('seed-proposal');
  });
  it('does not offer seed import after an approved release',()=>{
    render(<SeedImportPanel project={{...project,approved_version_id:'released'}} session={session} onRefresh={vi.fn()} onOpenProposal={vi.fn()}/>);
    expect(screen.getByRole('button',{name:'Import seed ontology'})).toBeDisabled();
    expect(screen.getByText(/An approved release already exists/)).toBeInTheDocument();
  });
});
