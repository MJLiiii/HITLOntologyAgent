/** Generated OpenAPI response aliases. Do not edit. */
import type * as Wire from './openapi'

export type Answer = Wire.AnswerResponse
export type AssessmentMapping = Wire.ApprovedMapping
export type AssessmentReport = Wire.AssessmentReportResponse
export type AuditEvent = Wire.AuditResponse
export type Evidence = Wire.EvidenceResponse
export type Experiment = Wire.ExperimentResponse
export type IngestionResult = Wire.IngestionResult
export type JobRef = Wire.JobRefResponse
export type MappingConfig = Wire.MappingConfigResponse
export type MappingEntry = Wire.MappingDraft
export type MappingSet = Wire.MappingSetResponse
export type Project = Wire.ProjectResponse
export type Proposal = Wire.RevisionResponse
export type ProposalJobResult = Wire.ProposalJobResult
export type Publication = Wire.PublicationResponse
export type RepairJobResult = Wire.ProposalJobResult
export type ReviewDecision = Wire.ReviewResponse
export type ReviewTimingEvent = Wire.ReviewTimingResponse
export type Revision = Wire.RevisionResponse
export type ScopeVersion = Wire.ScopeResponse
export type SeedImportResult = Wire.ProposalJobResult
export type Session = Wire.SessionResponse
export type SourceDocument = Wire.DocumentResponse
export type SyntheticTask = Wire.SyntheticTaskResponse
export type TestSpec = Wire.TestSpecResponse
export type TestSuite = Wire.TestSuiteResponse
export type TrustGraphFrozenSelection = Wire.CorpusResponse
export type TrustGraphIngestion = Wire.TrustGraphIngestionResponse
export type TrustGraphIngestions = Wire.TrustGraphIngestionsResponse
export type TrustGraphPreparation = Wire.TrustGraphPreparationResponse
export type TrustGraphRegisteredChunks = Wire.TrustGraphRegisteredChunksResponse
export type ValidationReport = Wire.ValidationReportResponse
export type Version = Wire.VersionResponse
export type Triple = Wire.Triple
export type Page<T> = Omit<Wire.Page_ProjectResponse_, 'items'> & { items: T[] }
export type Job<T = Wire.JobResponse['result']> = Omit<Wire.JobResponse, 'result'> & { result: T | null }
