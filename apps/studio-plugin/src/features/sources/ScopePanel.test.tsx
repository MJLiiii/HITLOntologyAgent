import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ScopePanel } from './ScopePanel';
import type { Project, ScopeVersion, Session } from '../../api/generated';
import type { ScopeUpload } from '../../api/openapi';

const project:Project={id:'p',name:'Service knowledge',domain:'demo',approved_version_id:null,corpus_snapshot_id:'corpus',scope_accepted:false,scope_digest:'scope-one'};
const session:Session={actor:{subject:'human',kind:'human',roles:['researcher','reviewer']},mode:'local',model_mode:'local'};
const initial:ScopeVersion={id:null,title:'Service ownership demo',purpose:'A synthetic service ownership model.',namespace:'https://example.org/oe-demo/',digest:'scope-one',competency_questions:[{id:'CQ-01',question:'Is Payroll Service a service?',sparql_query:'ASK { <https://example.org/oe-demo/PayrollService> a <https://example.org/oe-demo/Service> }',expected:true,required:true}],shapes_ttl:'@prefix sh: <http://www.w3.org/ns/shacl#> .',fixtures_ttl:'@prefix demo: <https://example.org/oe-demo/> .'};
afterEach(()=>vi.unstubAllGlobals());

describe('versioned scope configuration and human acceptance',()=>{
  it('saves explicit ASK/shape/fixture changes as a pending version and requires a separate scope decision',async()=>{
    let currentProject={...project},currentScope={...initial};
    const history:ScopeVersion[]=[];
    const writes:{path:string;body:Record<string,unknown>}[]=[];
    vi.stubGlobal('fetch',vi.fn(async(path:string,options:RequestInit={})=>{
      if(options.method==='POST'){
        const body=JSON.parse(String(options.body));writes.push({path,body});
        if(path.endsWith('/scope')){currentScope={...(body as ScopeUpload),id:'scope-two',digest:'scope-two-digest',namespace:'https://example.org/oe-demo/',shapes_ttl:body.shapes_ttl,fixtures_ttl:body.fixtures_ttl};history.push(currentScope);currentProject={...currentProject,scope_digest:currentScope.digest,scope_accepted:false};}
        if(path.endsWith('/scope-decisions'))currentProject={...currentProject,scope_accepted:body.decision==='accept'};
      }
      if(path.endsWith('/projects/p'))return new Response(JSON.stringify(currentProject));
      if(path.endsWith('/scopes'))return new Response(JSON.stringify({items:history,next_cursor:null}));
      return new Response(JSON.stringify(currentScope));
    }));
    let view:ReturnType<typeof render>;
    const refresh=vi.fn(async()=>{view.rerender(<ScopePanel project={currentProject} session={session} onRefresh={refresh}/>);});
    view=render(<ScopePanel project={project} session={session} onRefresh={refresh}/>);
    fireEvent.click(await screen.findByRole('button',{name:'Create scope version'}));
    fireEvent.change(screen.getByLabelText('Scope/domain label'),{target:{value:'Synthetic team boundaries'}});
    fireEvent.change(screen.getByLabelText('Scope purpose and rationale'),{target:{value:'Keep service and team concepts separate in the demonstration.'}});
    fireEvent.change(screen.getByLabelText('Expected ASK result 1'),{target:{value:'false'}});
    fireEvent.change(screen.getByLabelText('Competency question 1'),{target:{value:'Is Payroll Service a team?'}});
    fireEvent.change(screen.getByLabelText('ASK query 1'),{target:{value:'ASK { <https://example.org/oe-demo/PayrollService> a <https://example.org/oe-demo/Team> }'}});
    fireEvent.click(screen.getByRole('button',{name:'Save scope version'}));
    await screen.findByText(/A new scope version was saved/);
    expect(writes).toHaveLength(1);
    expect(writes[0].path).toBe('/api/v1/projects/p/scope');
    expect(writes[0].body).toEqual(expect.objectContaining({title:'Synthetic team boundaries',namespace:'https://example.org/oe-demo/',shapes_ttl:initial.shapes_ttl,fixtures_ttl:initial.fixtures_ttl,competency_questions:[expect.objectContaining({id:'CQ-01',expected:false,required:true})]}));
    await waitFor(()=>expect(screen.getByRole('button',{name:'Review current scope'})).toBeEnabled());
    fireEvent.click(screen.getByRole('button',{name:'Review current scope'}));
    expect(screen.getByRole('button',{name:'Accept scope'})).toBeDisabled();
    fireEvent.change(screen.getByLabelText('Scope decision rationale'),{target:{value:'The scope and expected ASK result match the source evidence.'}});
    fireEvent.click(screen.getByRole('button',{name:'Accept scope'}));
    await screen.findByText('Current synthetic scope is accepted');
    expect(writes).toHaveLength(2);
    expect(writes[1]).toEqual({path:'/api/v1/projects/p/scope-decisions',body:{scope_digest:'scope-two-digest',decision:'accept',rationale:'The scope and expected ASK result match the source evidence.'}});
    expect(screen.getByText(/Expected false means no matching entailment/)).toBeInTheDocument();
  });
  it('preserves unsaved edits and refuses a save when the scope digest changed',async()=>{
    const writes:string[]=[];
    vi.stubGlobal('fetch',vi.fn(async(path:string,options:RequestInit={})=>{
      if(options.method==='POST')writes.push(path);
      if(path.endsWith('/projects/p'))return new Response(JSON.stringify({...project,scope_digest:'changed-elsewhere'}));
      return new Response(JSON.stringify(path.endsWith('/scopes')?{items:[],next_cursor:null}:initial));
    }));
    render(<ScopePanel project={project} session={session} onRefresh={vi.fn().mockResolvedValue(undefined)}/>);
    fireEvent.click(await screen.findByRole('button',{name:'Create scope version'}));
    fireEvent.change(screen.getByLabelText('Scope/domain label'),{target:{value:'My unsaved scope'}});
    fireEvent.click(screen.getByRole('button',{name:'Save scope version'}));
    await screen.findByRole('alert');
    expect(screen.getByRole('alert')).toHaveTextContent('scope or publication state changed');
    expect(screen.getByLabelText('Scope/domain label')).toHaveValue('My unsaved scope');
    expect(writes).toEqual([]);
  });
});
