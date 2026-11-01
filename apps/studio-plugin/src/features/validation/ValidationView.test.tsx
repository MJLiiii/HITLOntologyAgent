import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { ValidationReportCard, AssessmentCard } from './ValidationView';
describe('validation reporting', () => {
  it('distinguishes engine errors from failed expectations', () => {
    render(<ValidationReportCard report={{ id: 'v1', status: 'error', profile: 'rdfs', cases: [{ id: 'parser', name: 'RDF parser', status: 'error', message: 'Runner unavailable' }] }} />);
    expect(screen.getByText('Validation could not complete')).toBeInTheDocument();
    expect(screen.getByText('Runner unavailable')).toBeInTheDocument();
    expect(screen.queryByText('Required checks passed')).not.toBeInTheDocument();
  });
  it('makes approximate support visibly distinct from approval', () => {
    render(<AssessmentCard report={{ id: 'a1', status: 'succeeded', vocabulary_coverage: 0.7, vocabulary_utilisation: 0.5, strict_fitness: 0.6, approximate_fitness: 0.9, mappings: [{ source: 'Owner', target: 'ResponsibleParty', tier: 'approximate', approved: false }] }} />);
    expect(screen.getByText('Task-vocabulary coverage')).toBeInTheDocument();
    expect(screen.getByText('Ontology-vocabulary utilisation')).toBeInTheDocument();
    expect(screen.getByText('Suggestion · not an equivalence')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /accept mapping/i })).not.toBeInTheDocument();
  });
  it('renders the actual engine object and assessment questions without inventing individual results', () => {
    render(<><ValidationReportCard report={{id:'v',status:'passed',profile:'rdfs',engine:{name:'Apache Jena',version:'5.3.0'},cases:[]}}/><AssessmentCard report={{id:'a',status:'completed',vocabulary_coverage:1,vocabulary_utilisation:0.5,strict_fitness:1,approximate_fitness:1,questions:[{id:'CQ-01',question:'Who owns this service?'}]}}/></>);
    expect(screen.getByText('RDFS profile · Apache Jena 5.3.0')).toBeInTheDocument();
    expect(screen.getByText('Included in assessment')).toBeInTheDocument();
  });
  it('shows frozen mapping provenance without asserting OWL equivalence',()=>{
    render(<AssessmentCard report={{id:'assessment',status:'completed',vocabulary_coverage:1,vocabulary_utilisation:1,strict_fitness:1,approximate_fitness:1,mappings_sha256:'exact-mapping-hash',mappings:[{requirement_iri:'https://example.org/task/Asset',ontology_iri:'https://example.org/oe-demo/Service',relation_type:'canonical_correspondence',rationale:'Reviewed correspondence for this task.',evidence_ids:['evidence-one'],reviewer:'expert-one',review_id:'mapping-review-one'}],mapping_diagnostics:{candidate:{compatible:true}}}}/>);
    expect(screen.getByText('exact-mapping-hash')).toBeInTheDocument();
    expect(screen.getByText('expert-one')).toBeInTheDocument();
    expect(screen.getByText('mapping-review-one')).toBeInTheDocument();
    expect(screen.getByText('Reviewed tool correspondence · not OWL equivalence')).toBeInTheDocument();
    expect(screen.queryByText('Suggestion · not an equivalence')).not.toBeInTheDocument();
  });
});

describe('validation report identities', () => {
  it('identifies real Jena cases without optional display names and exposes their exact oracle', () => {
    render(<ValidationReportCard report={{id:'run-real-shape', status:'failed', profile:'rdfs', engine:{name:'Apache Jena',version:'6.2.0'}, cases:[{id:'CQ-01', status:'failed', expected:true, actual:false, message:'Actual result did not match the explicit oracle'}]}}/>);
    expect(screen.getByText('CQ-01')).toBeInTheDocument();
    fireEvent.click(screen.getByText('Inspect expectation'));
    expect(screen.getByText(/"expected": true/)).toHaveTextContent('"actual": false');
  });
});
