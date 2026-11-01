import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MappingPanel } from './MappingPanel';
import type { Evidence, MappingConfig, MappingEntry, MappingSet, Project, Session } from '../../api/generated';

const project:Project={id:'p',name:'Demo',domain:'demo',approved_version_id:null,corpus_snapshot_id:'corpus',scope_accepted:true,scope_digest:'scope'};
const session:Session={actor:{subject:'human-reviewer',kind:'human',roles:['researcher','reviewer']},mode:'local',model_mode:'local'};
const passage:Evidence={id:'evidence-one',document_id:'document',title:'Service glossary',quote:'A service has an accountable owner.',resolved:true};
const empty:MappingConfig={decision_id:null,digest:'empty-digest',scope_digest:'scope',mappings:[]};
const entry:MappingEntry={requirement_iri:'https://example.org/task/Service',ontology_iri:'https://example.org/oe-demo/Service',relation_type:'canonical_correspondence',rationale:'Both identify the service described in the source glossary.',evidence_ids:['evidence-one']};
afterEach(()=>vi.unstubAllGlobals());

function mockMappingServer(initial:MappingConfig=empty) {
  let config={...initial},currentProject={...project};
  const sets:MappingSet[]=[],writes:{path:string;body:Record<string,unknown>}[]=[];
  vi.stubGlobal('fetch',vi.fn(async(path:string,options:RequestInit={})=>{
    if(options.method==='POST'){
      const body=JSON.parse(String(options.body));writes.push({path,body});
      if(path.endsWith('/mapping-sets')){const set:MappingSet={id:'set-one',digest:'set-digest',scope_digest:'scope',status:'needs_review',mappings:body.mappings};sets.push(set);return new Response(JSON.stringify(set));}
      if(path.endsWith('/mapping-decisions')){sets[0].status=body.decision==='accept'?'accepted':'rejected';if(body.decision==='accept'){config={decision_id:'decision-one',digest:'active-digest',scope_digest:'scope',mappings:sets[0].mappings.map(mapping=>({...mapping,reviewer:'human-reviewer',review_id:'decision-one'}))};currentProject={...currentProject,assessment_mapping_decision_id:'decision-one',assessment_mappings_digest:'active-digest'};}return new Response(JSON.stringify({id:'decision-one',...body,mappings:config.mappings}));}
    }
    if(path.endsWith('/mapping-config'))return new Response(JSON.stringify(config));
    if(path.endsWith('/mapping-sets'))return new Response(JSON.stringify({items:sets,next_cursor:null}));
    if(path.endsWith('/corpus-evidence'))return new Response(JSON.stringify({items:[passage],next_cursor:null}));
    if(path.endsWith('/projects/p'))return new Response(JSON.stringify(currentProject));
    throw new Error(`Unexpected path ${path}`);
  }));
  return {writes,sets,getProject:()=>currentProject};
}

describe('reviewed assessment mappings',()=>{
  it('requires evidence and a separate human decision before activating a full-IRI correspondence',async()=>{
    const server=mockMappingServer();let view:ReturnType<typeof render>;
    const refresh=vi.fn(async()=>view.rerender(<MappingPanel project={server.getProject()} session={session} onRefresh={refresh}/>));
    view=render(<MappingPanel project={project} session={session} onRefresh={refresh}/>);
    await waitFor(()=>expect(screen.getByRole('button',{name:'Propose mapping set'})).toBeEnabled());
    fireEvent.click(screen.getByRole('button',{name:'Propose mapping set'}));
    fireEvent.click(screen.getByRole('button',{name:'Add correspondence'}));
    fireEvent.change(screen.getByLabelText('Requirement IRI 1'),{target:{value:entry.requirement_iri}});
    fireEvent.change(screen.getByLabelText('Ontology IRI 1'),{target:{value:entry.ontology_iri}});
    fireEvent.change(screen.getByLabelText('Correspondence rationale 1'),{target:{value:entry.rationale}});
    fireEvent.click(screen.getByRole('button',{name:'Submit mapping proposal'}));
    expect(await screen.findByRole('alert')).toHaveTextContent('Select at least one resolved evidence passage');
    expect(server.writes).toHaveLength(0);
    fireEvent.click(screen.getByRole('checkbox',{name:/Service glossary/}));
    fireEvent.click(screen.getByRole('button',{name:'Submit mapping proposal'}));
    await screen.findByText(/A mapping set was proposed/);
    expect(server.writes).toEqual([{path:'/api/v1/projects/p/mapping-sets',body:{mappings:[entry]}}]);
    expect(screen.getByRole('button',{name:'Accept mapping set'})).toBeDisabled();
    fireEvent.change(screen.getByLabelText('Mapping decision rationale'),{target:{value:'The source confirms compatible service terms for assessment.'}});
    fireEvent.click(screen.getByRole('button',{name:'Accept mapping set'}));
    await screen.findByText('1 active reviewed correspondences');
    expect(server.writes[1]).toEqual({path:'/api/v1/projects/p/mapping-decisions',body:{mapping_set_id:'set-one',digest:'set-digest',decision:'accept',rationale:'The source confirms compatible service terms for assessment.'}});
    expect(server.writes).toHaveLength(2);
    expect(screen.getByText('human-reviewer')).toBeInTheDocument();
    expect(screen.getByText(/No OWL equivalence axiom was added/)).toBeInTheDocument();
    expect(screen.getByText(/Create a successor candidate and rerun validation/)).toBeInTheDocument();
  });
  it('proposes clearing mappings as an empty set without clearing the active configuration before acceptance',async()=>{
    const server=mockMappingServer({decision_id:'old-decision',digest:'old-digest',scope_digest:'scope',mappings:[{...entry,reviewer:'earlier-human',review_id:'old-decision'}]});
    render(<MappingPanel project={project} session={session} onRefresh={vi.fn().mockResolvedValue(undefined)}/>);
    await screen.findByText('1 active reviewed correspondences');
    fireEvent.click(screen.getByRole('button',{name:'Propose mapping set'}));
    fireEvent.click(screen.getByRole('button',{name:'Clear all draft mappings'}));
    fireEvent.click(screen.getByRole('button',{name:'Submit mapping proposal'}));
    await screen.findByText('Empty set: accepting this proposal clears the active mapping configuration.');
    expect(server.writes).toEqual([{path:'/api/v1/projects/p/mapping-sets',body:{mappings:[]}}]);
    expect(screen.getByText('1 active reviewed correspondences')).toBeInTheDocument();
    expect(screen.getByRole('button',{name:'Accept mapping set'})).toBeDisabled();
  });
});
