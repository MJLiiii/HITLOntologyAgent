import type { AuditEvent, Evidence, Experiment, Project, Publication, ReviewDecision, Revision, SourceDocument, TestSuite, Version } from './api/generated';
import type { Actor, ArtifactRef, BundleManifest, ModelProfileResponse } from './api/openapi';

// Complete synthetic wire fixtures: overrides keep each test focused without weakening API types.
export const testActor: Actor = {kind:'human',subject:'synthetic-reviewer',roles:['researcher','reviewer','approver']};
export const testArtifact: ArtifactRef = {id:'artifact',sha256:'a'.repeat(64),byte_length:0,media_type:'text/turtle',schema_version:1};
const createdAt = '2026-11-01T12:00:00Z';
export function modelProfileFixture(overrides:Partial<ModelProfileResponse>={}):ModelProfileResponse {
  return {id:'openai-terra',model:'gpt-6.1-terra',provider:'openai',purposes:['chat','proposal','repair','experiment','test_generation'],is_default:true,status:'configured_unverified',revision:'profile-revision',max_output_tokens:4096,structured_output:'json_schema',...overrides};
}
const manifest: BundleManifest = {
  assessment_mappings:[],assessment_mappings_digest:'mapping-digest',base_version_id:null,
  canonical_ontology_sha256:testArtifact.sha256,corpus_digest:'corpus-digest',corpus_snapshot_id:'corpus',
  engine_configuration:{},evidence:[],fixtures:testArtifact,inference_graph:'asserted_plus_rdfs',
  mapping_decision_id:null,mapping_evidence:[],mapping_source_snapshot_id:null,mappings:testArtifact,
  ontology:testArtifact,policy:{},profile:'rdfs',project_id:'p',questions:testArtifact,schema_version:1,
  scope_digest:'scope',shapes:testArtifact,tests:testArtifact,
};
export function projectFixture(overrides: Partial<Project> = {}): Project {
  return {id:'p',name:'Synthetic project',domain:'demo',approved_version_id:null,corpus_snapshot_id:'corpus',scope_accepted:true,scope_digest:'scope',competency_questions:[],mode:'local',pending_publication_id:null,review_policy_id:'synthetic-policy',...overrides};
}
export function versionFixture(overrides: Partial<Version> = {}): Version {
  return {id:'version',label:'Reference ontology',status:'reference',created_at:createdAt,commit:null,parent_version_id:null,source_snapshot_id:'corpus',ontology:testArtifact,ttl:'',triples:[],class_count:0,property_count:0,triple_count:0,...overrides};
}
export function evidenceFixture(overrides: Partial<Evidence> = {}): Evidence {
  return {id:'evidence',document_id:'document',title:'Synthetic source',quote:'Synthetic evidence.',resolved:true,adapter:'local',chunk:testArtifact,content_hash:testArtifact.sha256,created_at:createdAt,locator:'Characters 0–19',source_hash:testArtifact.sha256,span_start:0,span_end:19,status:'resolved',...overrides};
}
export function documentFixture(overrides: Partial<SourceDocument> = {}): SourceDocument {
  return {id:'document',title:'Synthetic source',edition:'1',classification:'synthetic',status:'uploaded',created_at:createdAt,artifact:testArtifact,chunk_count:0,content_hash:testArtifact.sha256,extraction:null,ingestion_run_id:null,ingestion_status:null,rights:'Synthetic engineering test',...overrides};
}
export function revisionFixture(overrides: Partial<Revision> = {}): Revision {
  return {id:'proposal',proposal_id:'proposal',revision_id:'revision',revision:1,title:'Synthetic candidate',summary:'Synthetic candidate',status:'draft',base_version_id:null,bundle_digest:'bundle',created_at:createdAt,actor:testActor,additions:[],deletions:[],evidence:[],evidence_ids:[],assumptions:[],rationale:'Synthetic test candidate',approval_ids:[],assessment:null,assessment_run_ids:[],validation:null,validation_run_id:null,corpus_snapshot_id:'corpus',fixtures:testArtifact,history:[],manifest,mappings:testArtifact,ontology:testArtifact,questions:testArtifact,shapes:testArtifact,tests:testArtifact,review_eligibility:{eligible:false,reasons:['Required checks have not run.']},stale:false,...overrides};
}
export function reviewFixture(overrides: Partial<ReviewDecision> = {}): ReviewDecision {
  return {id:'review',actor:testActor,bundle_digest:'bundle',created_at:createdAt,decision:'accept',proposal_id:'proposal',rationale:'SIMULATED ENGINEERING TEST',required_assessment_run_ids:['assessment'],review_policy_id:'synthetic-policy',revision:1,revision_id:'revision',status:'recorded',validation_run_id:'validation',...overrides};
}
export function publicationFixture(overrides: Partial<Publication> = {}): Publication {
  return {id:'publication',status:'completed',actor:testActor,approval_ids:['review'],bundle_digest:'bundle',created_at:createdAt,expected_commit:null,expected_head:null,idempotency_key:'synthetic-request',new_version_id:'version',proposal_id:'proposal',request_digest:'request-digest',revision:1,revision_id:'revision',...overrides};
}
export function auditFixture(overrides: Partial<AuditEvent> = {}): AuditEvent {
  return {id:'audit',action:'synthetic_action',actor:testActor,created_at:createdAt,detail_digest:'detail-digest',entity:'entity',event_hash:'event-hash',previous_event_hash:null,sequence:1,status:'recorded',time:createdAt,...overrides};
}
export function suiteFixture(overrides: Partial<TestSuite> = {}): TestSuite {
  return {id:'suite',status:'needs_review',digest:'suite-digest',revision_id:'revision',bundle_digest:'bundle',tests:[],actor:testActor,coverage_gaps:[],created_at:createdAt,fixture_artifacts:{},generator:{implementation_sha256:testArtifact.sha256,maximum_cases:20,mode:'deterministic_candidate_derived',oracle_policy:'Explicit human oracle review required.',version:'candidate-specs-v1'},input_manifest:{},origin:'synthetic',split:'development',...overrides};
}
export function experimentFixture(overrides: Partial<Experiment> = {}): Experiment {
  return {id:'experiment',protocol_id:'demo-v1',condition:'A',task_id:'demo-ownership',replicate:1,status:'completed',phase:'pre_review',created_at:createdAt,candidate_digest:null,candidate_ttl:null,correction_seconds:null,agent_manifest:{},answer_precision:null,answer_recall:null,approximate_fitness:null,assessment:{status:'not_run'},budget:{},case_counts:{},elapsed_seconds:null,evaluation_manifest:{},evaluation_status:'completed',initial_candidate_digest:null,limitations:['Synthetic engineering fixture; not a study observation.'],metrics:{},mode:'local',post_review_snapshot:null,pre_review_snapshot:null,repair_history:[],review_decisions:[],review_status:'not_requested',source_bundle_digest:'source-bundle',strict_fitness:null,structural_fitness:null,study_status:'not_approved',task_packet_digest:'task-packet',validation:{status:'not_run',cases:[]},vocabulary_coverage:null,vocabulary_utilisation:null,workload_id:'synthetic-workload',...overrides};
}
