import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { TrustGraphPanel } from './TrustGraphPanel';
import type { SourceDocument } from '../../api/generated';

const sources:SourceDocument[]=[{id:'source',title:'Synthetic ownership policy',edition:'1',classification:'synthetic',status:'uploaded',created_at:''}];
const preparation={id:'preparation',document_id:'source',job_id:'job',status:'submission_started',prepared:{seed_mode:'ordinary',approved_version_id:null,configuration_version:7,manifest_digest:'digest'}};
const receipt={id:'ingestion',document_id:'source',preparation_id:'preparation',status:'queued',receipt:{status:'queued',flow_id:'flow',collection_id:'collection'},upstream_completion_supported:false};
afterEach(()=>vi.unstubAllGlobals());

describe('explicit TrustGraph selected snapshot',()=>{
  it('hides ingestion controls when the server has no provider binding',async()=>{
    const fetcher=vi.fn(async()=>new Response(JSON.stringify({configured:false,items:[],preparations:[]})));
    vi.stubGlobal('fetch',fetcher);
    render(<TrustGraphPanel projectId="p" sources={sources} onRefresh={vi.fn()}/>);
    await waitFor(()=>expect(fetcher).toHaveBeenCalled());
    expect(screen.queryByRole('button',{name:'Submit to TrustGraph'})).not.toBeInTheDocument();
  });

  it('reports an upstream receipt as queued without automatically freezing a corpus',async()=>{
    const writes:{path:string;body:unknown;headers:Headers}[]=[];
    let submitted=false;
    vi.stubGlobal('fetch',vi.fn(async(path:string,options:RequestInit={})=>{
      if(options.method==='POST'){writes.push({path,body:JSON.parse(String(options.body)),headers:new Headers(options.headers)});return new Response(JSON.stringify({job_id:'submit'}));}
      if(path.endsWith('/jobs/submit')){submitted=true;return new Response(JSON.stringify({status:'succeeded',result:receipt}));}
      return new Response(JSON.stringify({configured:true,items:submitted?[receipt]:[],preparations:submitted?[preparation]:[]}));
    }));
    render(<TrustGraphPanel projectId="p" sources={sources} onRefresh={vi.fn()}/>);
    await screen.findByRole('button',{name:'Submit to TrustGraph'});
    fireEvent.change(screen.getByLabelText('Source for TrustGraph'),{target:{value:'source'}});
    fireEvent.click(screen.getByRole('button',{name:'Submit to TrustGraph'}));
    await screen.findByText(/Upstream submission recorded/);
    expect(screen.getByText('Upstream queued')).toBeInTheDocument();
    expect(screen.getByText(/Processing completion is unverified/)).toBeInTheDocument();
    expect(writes).toHaveLength(1);
    expect(writes[0].path).toBe('/api/v1/projects/p/trustgraph-ingestions');
    expect(writes[0].body).toEqual({document_id:'source'});
    expect(writes[0].headers.get('Idempotency-Key')).toBeTruthy();
  });

  it('requires an explicit passage choice and sends only the checked URI, then shows verified quoted evidence',async()=>{
    const writes:{path:string;body:unknown}[]=[];
    vi.stubGlobal('fetch',vi.fn(async(path:string,options:RequestInit={})=>{
      if(options.method==='POST'){writes.push({path,body:JSON.parse(String(options.body))});return new Response(JSON.stringify({job_id:'freeze'}));}
      if(path.endsWith('/jobs/freeze'))return new Response(JSON.stringify({status:'succeeded',result:{id:'corpus',status:'frozen',provider_snapshot:{status:'verified_selection',chunks:[{evidence_id:'e',upstream_chunk_uri:'urn:chunk:chosen',source_id:'source',quote:'Payroll is owned by Platform.',span_start:0,span_end:29,chunk_artifact:{sha256:'verified-hash'},graph_uri:'urn:graph:source',subgraph_uris:['urn:subgraph:1']}]}}}));
      if(path.endsWith('/chunks'))return new Response(JSON.stringify({chunk_uris:['urn:chunk:chosen','urn:chunk:other'],source_id:'source',selection_required:true,upstream_completion_supported:false}));
      return new Response(JSON.stringify({configured:true,items:[receipt],preparations:[preparation]}));
    }));
    const refresh=vi.fn().mockResolvedValue(undefined);
    render(<TrustGraphPanel projectId="p" sources={sources} onRefresh={refresh}/>);
    fireEvent.click(await screen.findByRole('button',{name:'Inspect registered chunks'}));
    await screen.findByLabelText('urn:chunk:chosen');
    expect(screen.getByRole('button',{name:'Verify and freeze selected passages'})).toBeDisabled();
    expect(writes).toEqual([]);
    fireEvent.click(screen.getByLabelText('urn:chunk:chosen'));
    fireEvent.click(screen.getByRole('button',{name:'Verify and freeze selected passages'}));
    await screen.findByText('Payroll is owned by Platform.');
    expect(screen.getByText('Verified')).toBeInTheDocument();
    expect(screen.getByText('urn:subgraph:1')).toBeInTheDocument();
    expect(writes).toEqual([{path:'/api/v1/projects/p/trustgraph-snapshots',body:{ingestion_run_id:'ingestion',chunk_uris:['urn:chunk:chosen']}}]);
    expect(refresh).toHaveBeenCalledOnce();
  });

  it('recovers only the chosen persisted preparation and does not resubmit a document',async()=>{
    const writes:{path:string;body:unknown}[]=[];
    vi.stubGlobal('fetch',vi.fn(async(path:string,options:RequestInit={})=>{
      if(options.method==='POST'){writes.push({path,body:JSON.parse(String(options.body))});return new Response(JSON.stringify({job_id:'recover'}));}
      if(path.endsWith('/jobs/recover'))return new Response(JSON.stringify({status:'succeeded',result:receipt}));
      return new Response(JSON.stringify({configured:true,items:[],preparations:[preparation]}));
    }));
    render(<TrustGraphPanel projectId="p" sources={sources} onRefresh={vi.fn()}/>);
    fireEvent.click(await screen.findByRole('button',{name:'Recover existing submission'}));
    await screen.findByText(/Existing upstream submission reattached/);
    expect(writes).toEqual([{path:'/api/v1/projects/p/trustgraph-ingestion-recoveries',body:{preparation_id:'preparation'}}]);
  });

  it('keeps a failed verification actionable without claiming a snapshot was frozen',async()=>{
    vi.stubGlobal('fetch',vi.fn(async(path:string,options:RequestInit={})=>{
      if(options.method==='POST')return new Response(JSON.stringify({job_id:'failed'}));
      if(path.endsWith('/jobs/failed'))return new Response(JSON.stringify({status:'failed',error:'Configuration changed; start a new configured preparation.'}));
      if(path.endsWith('/chunks'))return new Response(JSON.stringify({chunk_uris:['urn:chunk:chosen'],source_id:'source',selection_required:true,upstream_completion_supported:false}));
      return new Response(JSON.stringify({configured:true,items:[receipt],preparations:[preparation]}));
    }));
    const refresh=vi.fn();
    render(<TrustGraphPanel projectId="p" sources={sources} onRefresh={refresh}/>);
    fireEvent.click(await screen.findByRole('button',{name:'Inspect registered chunks'}));
    fireEvent.click(await screen.findByLabelText('urn:chunk:chosen'));
    fireEvent.click(screen.getByRole('button',{name:'Verify and freeze selected passages'}));
    expect(await screen.findByRole('alert')).toHaveTextContent('Configuration changed');
    expect(screen.queryByText('Verified selected passages')).not.toBeInTheDocument();
    expect(refresh).not.toHaveBeenCalled();
  });
});
