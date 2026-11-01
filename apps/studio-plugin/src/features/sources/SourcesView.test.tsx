import { documentFixture, testArtifact } from '../../test-fixtures';
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { SourceCard } from './SourcesView';
describe('source state', () => {
  it('keeps incomplete PDF extraction out of retrieval and shows the reason', () => {
    render(<SourceCard source={documentFixture({ id:'pdf', title:'Scanned source', edition:'1', classification:'public', status:'incomplete', created_at:'', extraction:{record_id:'extraction',report:testArtifact,status:'unsupported',diagnostics:['No text; OCR required']} })} onIngest={() => {}} busy={false}/>);
    expect(screen.getByText('Extraction incomplete')).toBeInTheDocument();
    expect(screen.getByText('No text; OCR required')).toBeInTheDocument();
    expect(screen.queryByText('Ready for retrieval')).not.toBeInTheDocument();
  });
  it('does not confuse upload with ingestion completion', () => {
    render(<SourceCard source={documentFixture({ id: 's', title: 'Uploaded handbook', edition: '1', classification: 'synthetic', status: 'uploaded', created_at: '' })} onIngest={() => {}} busy={false} />);
    expect(screen.getByText('Uploaded · not yet processed')).toBeInTheDocument();
    expect(screen.getByRole('button', {name: 'Process source'})).toBeEnabled();
    expect(screen.queryByText('Ready for retrieval')).not.toBeInTheDocument();
  });
});
