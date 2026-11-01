import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { Studio } from './Studio';

const project={id:'p',name:'Service knowledge',domain:'demo',mode:'demo',approved_version_id:null,corpus_snapshot_id:'corpus',scope_accepted:false,scope_digest:'scope'};
const session={actor:{subject:'local-human',kind:'human',roles:['researcher','reviewer','approver']},mode:'local',model_mode:'local'};
const page=(items:unknown[])=>({items,next_cursor:null});
function fixture(path:string) {
  if(path.endsWith('/session'))return session;
  if(path.endsWith('/projects'))return page([project]);
  if(path.endsWith('/projects/p'))return project;
  if(path.endsWith('/versions'))return page([{id:'reference',label:'Demo reference',status:'reference',created_at:'',triple_count:1,class_count:1,property_count:0,triples:[{subject:'https://example.org/Service',predicate:'http://www.w3.org/2000/01/rdf-schema#label',object:'Service',object_type:'literal'}]}]);
  if(path.endsWith('/documents'))return page([{id:'doc',title:'Service ownership policy',classification:'synthetic',edition:'1',created_at:'',status:'complete',chunk_count:1}]);
  return page([]);
}
afterEach(()=>{vi.unstubAllGlobals();vi.restoreAllMocks();window.history.replaceState(null,'','/');});

describe('workspace session and grounded conversation',()=>{
  it('uses a fragment bootstrap token only for session establishment and clears the fragment',async()=>{
    window.history.replaceState(null,'','/#session=synthetic-test-token');
    const fetcher=vi.fn(async(path:string)=>new Response(JSON.stringify(fixture(path))));
    vi.stubGlobal('fetch',fetcher);
    const save=vi.spyOn(Storage.prototype,'setItem');
    render(<Studio/>);
    await screen.findByText('Good questions.');
    const options=(fetcher.mock.calls as unknown as [string,RequestInit][])[0][1];
    expect(new Headers(options.headers).get('X-OE-Session-Token')).toBe('synthetic-test-token');
    expect(window.location.hash).toBe('');
    expect(save).not.toHaveBeenCalled();
    expect(screen.getByText('Demo reference · not approved')).toBeInTheDocument();
    expect(screen.getByText('No approved version')).toBeInTheDocument();
  });
  it('shows an explicit local unlock form after an unauthenticated session response',async()=>{
    let unlocked=false;
    const fetcher=vi.fn(async(path:string,options:RequestInit={})=>{
      if(path.endsWith('/session')) {
        unlocked=new Headers(options.headers).get('X-OE-Session-Token')==='operator-token';
        if(!unlocked)return new Response(JSON.stringify({code:'session_required',message:'Session token required'}),{status:401});
      }
      return new Response(JSON.stringify(fixture(path)));
    });
    vi.stubGlobal('fetch',fetcher);
    render(<Studio/>);
    const input=await screen.findByLabelText('Local session token');
    expect(input).toHaveAttribute('type','password');
    expect(screen.getByRole('button',{name:'Open workspace'})).toBeDisabled();
    fireEvent.change(input,{target:{value:'operator-token'}});
    fireEvent.click(screen.getByRole('button',{name:'Open workspace'}));
    await screen.findByText('Good questions.');
    expect(unlocked).toBe(true);
    expect(screen.queryByLabelText('Local session token')).not.toBeInTheDocument();
  });
  it('keeps a grounded answer, citations and triples while navigating without creating review writes',async()=>{
    const posts:string[]=[];
    vi.stubGlobal('fetch',vi.fn(async(path:string,options:RequestInit={})=>{
      if(options.method==='POST')posts.push(path);
      if(path.endsWith('/question-jobs'))return new Response(JSON.stringify({job_id:'answer-job'}));
      if(path.endsWith('/jobs/answer-job'))return new Response(JSON.stringify({id:'answer-job',status:'succeeded',result:{answer:'Payroll Service is owned by Operations Team.',version_id:'reference',ontology_status:'reference',evidence:[{id:'e',document_id:'doc',title:'Service ownership policy',quote:'Payroll Service is owned by Operations Team.',locator:'Paragraph 1',resolved:true}],triples:[{subject:'https://example.org/PayrollService',predicate:'https://example.org/hasOwner',object:'https://example.org/OperationsTeam'}]}}));
      return new Response(JSON.stringify(fixture(path)));
    }));
    render(<Studio/>);
    await screen.findByText('Good questions.');
    fireEvent.change(screen.getByLabelText('Ask about your ontology or sources'),{target:{value:'Who owns Payroll Service?'}});
    fireEvent.click(screen.getByRole('button',{name:'Send question'}));
    await screen.findByText('Ontology results');
    expect(screen.getByText('OperationsTeam')).toBeInTheDocument();
    expect(screen.getByText('Verified')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button',{name:'Ontology'}));
    fireEvent.click(screen.getByRole('button',{name:'Chat'}));
    await waitFor(()=>expect(screen.getByText('Ontology results')).toBeVisible());
    expect(posts).toEqual(['/api/v1/projects/p/question-jobs']);
  });
});
