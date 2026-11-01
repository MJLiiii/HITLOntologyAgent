import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ChatView } from './ChatView';
import type { Project, Session, Version } from '../../api/generated';

const project:Project={id:'p',name:'Service knowledge',domain:'demo',approved_version_id:'approved',corpus_snapshot_id:'new-corpus',scope_accepted:true,scope_digest:'scope'};
const session:Session={actor:{subject:'human',kind:'human',roles:['researcher']},mode:'local',model_mode:'local'};
const versions:Version[]=[{id:'approved',label:'Approved version',status:'approved',source_snapshot_id:'historical-corpus',created_at:'',triples:[],class_count:1,property_count:1,triple_count:1}];
afterEach(()=>vi.unstubAllGlobals());

function wire(sourceSelection:string,corpus:string) {
  const writes:Record<string,unknown>[]=[];
  vi.stubGlobal('fetch',vi.fn(async(path:string,options:RequestInit={})=>{
    if(options.method==='POST'){writes.push(JSON.parse(String(options.body)));return new Response(JSON.stringify({job_id:'question'}));}
    return new Response(JSON.stringify({status:'succeeded',result:{answer:'The cited passage identifies Platform.',evidence:[],triples:[],version_id:'approved',ontology_status:'approved',corpus_snapshot_id:corpus,source_selection:sourceSelection,limitations:sourceSelection==='explicit'?['Selected source corpus differs from the ontology version sources.']:[]}}));
  }));
  return writes;
}

describe('explicit chat source selection',()=>{
  it('defaults to historical ontology sources without sending a current-corpus override',async()=>{
    const writes=wire('ontology_version','historical-corpus');
    render(<ChatView project={project} session={session} versions={versions} sources={[]} onNavigate={vi.fn()}/>);
    expect(screen.getByLabelText('Answer sources')).toHaveValue('ontology_version');
    fireEvent.change(screen.getByLabelText('Ask about your ontology or sources'),{target:{value:'Who owns this service?'}});
    fireEvent.click(screen.getByRole('button',{name:'Send question'}));
    await screen.findByText('The cited passage identifies Platform.');
    expect(writes).toEqual([{question:'Who owns this service?',history:[]}]);
    expect(screen.getByLabelText('Answer source context')).toHaveTextContent('Ontology version sources');
    expect(screen.getByLabelText('Answer source context')).toHaveTextContent('historical');
  });

  it('sends the exact current corpus only after selection and preserves the returned answer provenance',async()=>{
    const writes=wire('explicit','new-corpus');
    render(<ChatView project={project} session={session} versions={versions} sources={[]} onNavigate={vi.fn()}/>);
    fireEvent.change(screen.getByLabelText('Answer sources'),{target:{value:'current'}});
    expect(screen.getByText(/may be newer than the ontology/)).toBeInTheDocument();
    expect(screen.getByText(/does not approve or change the ontology/)).toBeInTheDocument();
    expect(writes).toEqual([]);
    fireEvent.change(screen.getByLabelText('Ask about your ontology or sources'),{target:{value:'What does the newer source say?'}});
    fireEvent.click(screen.getByRole('button',{name:'Send question'}));
    await screen.findByText('The cited passage identifies Platform.');
    expect(writes).toEqual([{question:'What does the newer source say?',history:[],corpus_snapshot_id:'new-corpus'}]);
    expect(screen.getByText('Selected source corpus differs from the ontology version sources.')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Answer sources'),{target:{value:'ontology_version'}});
    expect(screen.getByLabelText('Answer source context')).toHaveTextContent('Selected source corpus');
    expect(screen.getByLabelText('Answer source context')).toHaveTextContent('new-corpus');
  });

  it('does not offer a current-corpus override when the project has no frozen corpus',()=>{
    render(<ChatView project={{...project,corpus_snapshot_id:null}} session={session} versions={versions} sources={[]} onNavigate={vi.fn()}/>);
    expect(screen.queryByRole('option',{name:'Current source corpus'})).not.toBeInTheDocument();
    expect(screen.getByLabelText('Answer sources')).toHaveValue('ontology_version');
  });
});
