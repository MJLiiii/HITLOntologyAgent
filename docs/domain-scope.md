# Domain scope - DORA source preparation selected

On 1 November 2026 the user selected **financial regulatory compliance**, with the use case **modelling contractual obligations between financial entities and ICT third-party service providers**. The user chose obligation modelling as the first test and approved preparation of the domain specification and public source corpus. This supersedes the earlier open choice among DORA, AML, risk management and data governance for this preparation work.

The bounded subject is EU DORA contractual requirements, centred on Article 30 of Regulation (EU) 2022/2554. General ICT-service contractual requirements and additional requirements for services supporting critical or important functions must remain distinguishable. The initial audience is the project researcher and a future human domain reviewer.

## Prepared materials

- [Public source packet](../research/corpora/dora-v1/README.md): five official English documents, retained originals, article/template extracts, source metadata and integrity verification.
- [Ontology modelling specification](dora-modelling.md): concept and relation design, staged requirement coverage, six competency-question families, acceptance checks and unresolved interpretation.
- [Source manifest](../research/corpora/dora-v1/manifest.json): exact source representations, editions, dates, retrieval locations, hashes and extract selectors.

The initial model represents a legal requirement to include a contractual term. A contract containing that term and a party performing the resulting obligation are separate statements requiring separate evidence. Actual contracts and performance are outside this first test.

## Authorization and runtime boundary

The selection authorizes this public-document preparation. It is not a Deloitte institutional sign-off, an expert interpretation, a recorded application scope/review decision, or consent for a study. No real institution, confidential contract, participant, expert rating, or review time is supplied or inferred.

The existing application still runs the explicitly synthetic `demo` namespace `https://example.org/oe-demo/`. Its project API admits only `demo` and `unselected`; the scope schema fixes that namespace. Public documents are accepted by source ingestion, but registered `synthetic-task-v1` experiments require synthetic evidence. DORA regulations must remain classified **public** and must not be relabelled to bypass these restrictions. No application/API changes or domain activation are included in this increment.

The existing Payroll/Operations ownership demo, its artifacts and research protocols are preserved. A subsequent adaptation must establish the DORA project/namespace, admissible source and experiment classifications, reviewed question-to-IRI bindings and approved test expectations before claiming an end-to-end DORA workflow result.

Before real study collection, the supervisor, domain expert and student still need to identify the institutional owner, reviewer, final approver and escalation owner; sign the included concepts, relationships and exclusions; confirm source rights and retention; obtain consent and availability; approve questions, mappings and acceptance criteria; and separate development from held-out material. The historical planning targets of 5-15 short documents, 10-20 competency questions and 10-30 vocabulary terms are not observed study results. See [the protocol](../research/protocol.yaml).
