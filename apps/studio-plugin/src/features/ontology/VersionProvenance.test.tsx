import { auditFixture, projectFixture, publicationFixture, reviewFixture, versionFixture } from '../../test-fixtures';
import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { VersionProvenance } from './VersionProvenance';
import type { AuditEvent, Project, Publication, ReviewDecision, Version } from '../../api/generated';

const project:Project=projectFixture({id:'p',name:'Demo',domain:'demo',approved_version_id:'current-head',corpus_snapshot_id:'corpus',scope_accepted:true,scope_digest:'scope',pending_publication_id:'pending'});
const version:Version=versionFixture({id:'historical-version',label:'Approved release 1',created_at:'',status:'approved',triple_count:1,class_count:1,property_count:0,triples:[],parent_version_id:'parent-version',publication_id:'publication',bundle_digest:'exact-bundle',commit:'exact-git-commit',source_snapshot_id:'corpus'});
const receipt:Publication=publicationFixture({id:'publication',status:'completed',proposal_id:'proposal/one',revision:3,revision_id:'revision-three',approval_ids:['review/one'],bundle_digest:'exact-bundle'});
const review:ReviewDecision=reviewFixture({id:'review/one',actor:{subject:'human-reviewer',kind:'human',roles:['reviewer']},decision:'accept',bundle_digest:'exact-bundle',validation_run_id:'validation/one',required_assessment_run_ids:['assessment/one'],rationale:'<script>Evidence reviewed</script>'});
const events:AuditEvent[]=[auditFixture({id:'e1',action:'ontology_published',entity:'publication',actor:{subject:'human-publisher',kind:'human',roles:['approver']},time:'2026-11-01T12:00:00Z',event_hash:'event-hash-one',previous_event_hash:'previous-hash',detail_digest:'detail-hash',sequence:4}),auditFixture({id:'e2',action:'source_withdrawn',entity:'unrelated-source',actor:{subject:'other-human',kind:'human',roles:['researcher']},time:'2026-11-01T13:00:00Z',event_hash:'event-hash-two',previous_event_hash:'event-hash-one'})];
afterEach(()=>vi.unstubAllGlobals());

describe('immutable version provenance',()=>{
  it('links precise candidate/review/report records and distinguishes historical head and pending publication',async()=>{
    const fetcher=vi.fn(async(path:string,options:RequestInit={})=>{
      expect(options.method).not.toBe('POST');
      if(path.endsWith('/audit'))return new Response(JSON.stringify({items:events,next_cursor:null}));
      if(path.endsWith('/publications/publication'))return new Response(JSON.stringify(receipt));
      if(path.endsWith('/reviews/review%2Fone'))return new Response(JSON.stringify(review));
      throw new Error(`Unexpected request ${path}`);
    });
    vi.stubGlobal('fetch',fetcher);
    const open=vi.fn(),select=vi.fn();
    render(<VersionProvenance project={project} version={version} onOpenProposal={open} onSelectVersion={select}/>);
    expect(screen.getByText('Historical approved version')).toBeInTheDocument();
    expect(screen.getByRole('link',{name:'Inspect pending publication'})).toHaveAttribute('href','/api/v1/projects/p/publications/pending');
    await screen.findByText('human-reviewer');
    expect(screen.getByRole('link',{name:'Revision 3'})).toHaveAttribute('href','/api/v1/projects/p/proposals/proposal%2Fone/revisions/3');
    expect(screen.getByRole('link',{name:/Validation validation/})).toHaveAttribute('href','/api/v1/projects/p/validation-runs/validation%2Fone');
    expect(screen.getByRole('link',{name:/Assessment assessment/})).toHaveAttribute('href','/api/v1/projects/p/assessment-runs/assessment%2Fone');
    expect(screen.getByText('<script>Evidence reviewed</script>')).toBeInTheDocument();
    expect(document.querySelector('script')).toBeNull();
    expect(screen.getByText('ontology published')).toBeInTheDocument();
    expect(screen.queryByText('source withdrawn')).not.toBeInTheDocument();
    fireEvent.click(screen.getByLabelText('All project events'));
    expect(screen.getByText('source withdrawn')).toBeInTheDocument();
    expect(screen.getByText('previous-hash')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button',{name:'Open proposal'}));
    expect(open).toHaveBeenCalledWith('proposal/one');
    fireEvent.click(screen.getByRole('button',{name:'parent-version'}));
    expect(select).toHaveBeenCalledWith('parent-version');
  });
});
