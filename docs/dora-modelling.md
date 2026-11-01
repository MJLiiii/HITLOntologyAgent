# DORA contractual-obligation ontology specification

Status: user-selected domain and approved source-preparation scope, 1 November 2026. This is the design for the first ontology test. It is not an executed ontology candidate, an approved legal interpretation, or an application review decision. Source bytes and extracts are available in the [public packet](../research/corpora/dora-v1/README.md).

## Purpose and modelling boundary

Represent which contractual requirements the selected EU provisions establish, their applicability, the parties/roles involved, the rights they protect, and their precise source provisions. Start with DORA Article 30 and Regulation 2024/1773, then extend to subcontracting. The register of information supplies a structural cross-check; ESMA Q&A 2646 supplies a separately labelled interpretation.

Three kinds of evidence must remain separate:

| Statement | Evidence required | Initial scope |
|---|---|---|
| A legal provision requires a contractual term | Official provision plus preserved conditions/derogations | Included |
| An executed contract contains that term | Identified contract version and clause | No actual contracts supplied |
| A party performed an obligation | Identified performance event and evidence | No performance evidence supplied |

No financial institution or provider is instantiated as a real party. Generic legal roles are modelled; any later illustrative entities/contracts must be explicitly synthetic. A missing triple means no supported assertion in the selected graph, not legal non-compliance or logical negation.

## Concept and relationship design

Use named resources and the admitted RDFS subset for vocabulary structure. Conditions, exceptions and time expressions are represented as explicit resources/text with citations; RDFS does not execute deontic, temporal or defeasible legal reasoning. The eventual DORA namespace is an application-adaptation decision: this document does not silently reuse the ownership-demo namespace or claim a production namespace.

| Concept group | Proposed concepts | Intended meaning |
|---|---|---|
| Parties and roles | `FinancialEntity`, `ICTThirdPartyProvider`, `Subcontractor`, `CompetentAuthority`, `PartyRole` | Keep an organisation's role in an arrangement distinct from its identity. A subcontractor is a provider acting in a service supply chain. |
| Service context | `ICTService`, `BusinessFunction`, `CriticalOrImportantFunction`, `ContractualArrangement` | A service supports a function; the function's criticality governs certain requirements. Do not equate this with a provider designated critical under DORA's oversight regime. |
| Normative content | `LegalProvision`, `ContractualRequirement`, `ObligationSpecification`, `RightSpecification`, `ApplicabilityCondition`, `ExceptionCondition` | A requirement may specify a future contractual duty/right without asserting an actual contract or performance. |
| Traceability | `SourceDocument`, `EvidenceExcerpt`, `TemporalCondition`, `InterpretationNote` | Preserve authority, edition, locator, trigger/notice wording and uncertainty. |

Every requirement record needs a stable ID, paraphrased label, legal requirement subject, obligation bearer/right holder where stated, action or right specification, applicability conditions, any exception, and one or more evidence references. The legal requirement subject and the proposed contractual obligation bearer are separate fields. Use `not_explicit` rather than inventing a bearer where a provision only prescribes contract content.

| Relationship | Meaning |
|---|---|
| `derivedFromProvision`, `supportedByExcerpt`, `partOfDocument` | Requirement -> legal provision -> exact source evidence/document. |
| `requiresTerm`, `specifiesObligation`, `specifiesRight` | Legal requirement -> required contractual content. |
| `hasRequirementSubject`, `hasBearerRole`, `hasRightHolderRole`, `hasBeneficiaryRole` | Separate statutory responsibility, contractual duty, right and beneficiary. Allow multiple roles where the text names them. |
| `appliesUnder`, `qualifiedByException`, `hasTemporalCondition` | Preserve scope, triggering event, derogation and timing. |
| `coversService`, `supportsFunction`, `hasProviderRole`, `subcontractsTo` | Arrangement/service/function and service-chain relationships; the last relation is contextual to the arrangement/service, not an unqualified global organisation relation. |
| `clarifiedBy` | Link an interpretation to its legislative subject without promoting Q&A text to legislation. |

The initial model must not assert `contractContainsTerm` or `obligationPerformed`. Those are reserved for later contract/performance evidence. Do not generate OWL equivalence from assessment mappings or RDFS entailments from an interpretation note.

## Initial requirement coverage

These are modelling targets with draft interpretations. Each reference identifies the complete retained extract; the paragraph/point narrows the claim. Split multiple duties/rights into distinct records while preserving their common conditions.

| ID family | Requirement or relation to model | Applicability and qualifications | Source |
|---|---|---|---|
| DORA-WRITTEN | Written allocation of rights/obligations, inclusion of SLAs, accessible durable contract document | General contractual requirement; do not invent a particular signing party's performance | [DORA Article 30](../research/corpora/dora-v1/extracts/dora-art-30.txt), paragraph 1 |
| DORA-GENERAL | Service description; subcontracting permission/conditions; locations/change notice; data safeguards and recovery; service levels; incident assistance; authority cooperation; termination/notice; training conditions | Separate all points (a)-(i). Preserve each conditional trigger, including the alternatives for incident-assistance cost | Same extract, paragraph 2(a)-(i) |
| DORA-CRITICAL | Detailed service targets, material-development reporting, contingency/security, TLPT cooperation, monitoring/audit and transition support | Additional requirements for ICT services supporting critical or important functions; general requirements still apply | Same extract, paragraph 3(a)-(f) |
| DORA-AUDIT | Audit/access rights, appointed actors, alternative assurance, cooperation and procedural details | Preserve other clients' rights qualification and the microenterprise derogation; do not convert an option to delegate into mandatory delegation | Same extract, paragraph 3(e)(i)-(iv) and final subparagraph |
| DORA-EXIT | Continued service during an adequate transition and migration/in-house options | Conditional on the applicable critical/important-function arrangements; no invented fixed number of days | Same extract, paragraph 3(f); [Article 28](../research/corpora/dora-v1/extracts/dora-art-28.txt), paragraphs 7-8 |
| POLICY-CLAUSES | Policy requiring written clauses, audit methods, limits on sole reliance on certifications/reports, signed material amendments | Policy requirements for the specified critical/important-function context, with the stated conditions for assurance methods | [2024/1773 Article 8](../research/corpora/dora-v1/extracts/policy-art-8.txt), paragraphs 1-4 |
| POLICY-MONITOR | Policy-defined performance measures, reporting and remedial monitoring | Preserve 'where appropriate' and other qualifications; do not assert a universal fixed penalty | [Article 9](../research/corpora/dora-v1/extracts/policy-art-9.txt), paragraphs 1-4 |
| POLICY-EXIT | Documented, reviewed and tested exit plan | Retain plausible scenarios, feasibility and compatibility with contractual exit/termination terms | [Article 10](../research/corpora/dora-v1/extracts/policy-art-10.txt) |
| SUBCONTRACT | Permitted services, due diligence, retained provider responsibility, monitoring and contractual conditions | Applies to the stated critical/important-function services or material parts; preserve Article 3 conditions and Article 4's full list | [2025/532 Article 3](../research/corpora/dora-v1/extracts/subcontracting-art-3.txt) and [Article 4](../research/corpora/dora-v1/extracts/subcontracting-art-4.txt) |
| SUB-CHANGE | Advance information, notice, approval/non-objection and objection/modification procedure | Distinguish explicit approval from no objection by the end of the notice period. Do not replace 'reasonable' with a fabricated duration | [Article 5](../research/corpora/dora-v1/extracts/subcontracting-art-5.txt), paragraphs 1-4 |
| SUB-TERMINATE | Financial entity's right to provide for termination in the specified circumstances | Preserve all three cases and the provision's modality; do not assert automatic termination has occurred | [Article 6](../research/corpora/dora-v1/extracts/subcontracting-art-6.txt), points (a)-(c) |
| REGISTER-LINKS | Contract reference, signing/using entities, provider identity, service, supported function and chain rank | Register relationships and reporting fields are a structural reference, not proof a contract contains every required term | [B_02.02](../research/corpora/dora-v1/extracts/register-B_02.02.txt), [B_05.02](../research/corpora/dora-v1/extracts/register-B_05.02.txt), [B_06.01](../research/corpora/dora-v1/extracts/register-B_06.01.txt), with the other selected templates |
| QA-AUDIT | Qualification of agreed audit frequency | Clarification: agreement must preserve risk-based and necessary ad-hoc audits. The question's 'once per year' example is not a rule | [ESMA Q&A 2646](../research/corpora/dora-v1/extracts/esma-qa-2646.txt), published answer |

Article 30(4)'s consideration of public standard clauses and Article 30(5)'s RTS mandate remain retained context. Model them separately if included; an ESA rulemaking deadline is not a provider's contractual deadline. DORA Articles 2-4, 28-29 and the policy/subcontracting scope articles remain available to prevent overbroad applicability claims.

## Six competency-question families

These are proposed development expectations awaiting an actual human oracle decision. They are not executable or approved ASK tests yet; query/IRI bindings belong to the later candidate and application adaptation. Each family below has a positive target and a discrimination check.

| ID | Question and expected evidence | Discrimination check |
|---|---|---|
| DORA-CQ-01 | Which provisions require written rights/obligations? Return DORA 30(1), plus policy 8(1) in its narrower context; cite exact paragraphs | A source requirement must not imply that an actual contract was signed or contains the term |
| DORA-CQ-02 | Which requirements are general and which are additional for critical/important functions? Distinguish Article 30(2) from 30(3), preserving their cumulative relationship | A non-critical-function description must not receive every 30(3) requirement; an unknown classification remains unknown |
| DORA-CQ-03 | Who bears the duty and who benefits/holds the right? For incident assistance, identify the provider and financial entity under 30(2)(f); for audit, preserve the actors in 30(3)(e) | Do not reverse the roles or drop authority/appointed-party rights; retain the assistance cost alternatives |
| DORA-CQ-04 | What qualifies audit, notification, termination and exit? Return the condition/exception/temporal resources with 30(2)(b),(h), 30(3)(e),(f), 28(7)-(8), policy 8/10, and separate QA-AUDIT clarification | Preserve the microenterprise derogation, relevant triggers and qualitative time wording; never invent a fixed notice period |
| DORA-CQ-05 | Which requirements concern subcontracting/material changes? Return 2025/532 Articles 3-6 and the DORA 30(2)(a) link | Approval and non-objection are distinct paths; source conditions do not prove a subcontract was authorized or terminated |
| DORA-CQ-06 | Which provision supports each requirement? Return document ID, exact paragraph/point, source authority, edition, extract ID and original hash via the manifest | Missing/withdrawn/mismatched evidence must not be replaced with an invented citation or an interpretation labelled legislation |

## Acceptance and remaining interpretation

Source-preparation acceptance: all five official documents retained; all planned sections extracted in full; correct English edition/classification and separate dates recorded; each extract reproducible from its hashed original; links/locators resolvable; table structure and material conditions spot-checked against official presentation. See [packet verification](../research/corpora/dora-v1/README.md#verify-and-use).

Later candidate acceptance requires all six families to have reviewed, frozen query/expected-result bindings. Check vocabulary/IRI and artifact integrity, the admitted Jena RDFS/SHACL workload, CQ correctness and source fidelity separately. Run OntoCheck only after domain/namespace/question compatibility is established; unsupported assessment remains explicit. Structural or reasoning success does not establish legal compliance. Only an actual authorized human decision on the exact checked bundle permits publication.

Keep unresolved: interpretation of 'critical or important' for a particular function; 'material' changes; reasonable/adequate time periods; proportionality and entity-specific exemptions; how exceptions combine; sufficiency of alternative assurance; any other EU/national-law cross-reference not modelled. No wording is silently corrected: for example, the policy Article 9(3) cross-reference is retained as published rather than rewritten by the extractor. The originals control if normalized text/table presentation is ambiguous.

Implementation boundary: public corpus plus this design only. No candidate, SHACL shapes, synthetic contracts, benchmark observations, institutional approval, expert decision or timer data are fabricated. The [existing synthetic-only runtime restrictions](domain-scope.md#authorization-and-runtime-boundary) remain intact. The next implementation increment can bind this design to an admitted DORA project without rewriting the historical ownership demo.
