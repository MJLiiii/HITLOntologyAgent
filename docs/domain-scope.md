# Domain scope — decision pending

No Deloitte domain or use case has been selected or signed off. The software operates on the explicitly synthetic `demo` namespace `https://example.org/oe-demo/`; this fixture is not a Deloitte scope decision or a regulatory interpretation.

The four candidates remain open:

| Candidate | Bounded possibility | Scope decision needed |
|---|---|---|
| Financial regulatory compliance, including DORA | Selected ICT services, providers, evidence and obligations | Exact provisions, editions and expert interpretation |
| Financial crime, including AML | Synthetic due-diligence evidence workflow | Exclude customer records and operational decisions |
| Risk management | Limited risks, controls, owners and evidence | Agree taxonomy and assessment meaning |
| Data governance | Ownership, classification and limited policy relationships | Separate business meaning from access enforcement |

The supervisor, domain expert and student must select one use case, identify its owner and intended users, agree source authority and precedence, and sign the included concepts, relationships and exclusions. Selection criteria are document availability, expert access, modelling ambiguity, measurable questions, confidentiality burden and calendar feasibility.

Before study collection, record source editions, retrieval/effective dates, rights, classification and retention; name the reviewer, final approver and escalation owner; obtain consent and review availability; approve question-to-IRI bindings, imports and mappings; freeze development versus held-out cases and acceptance criteria. The target capacity is 5–15 short documents, 10–20 competency questions and 10–30 initial vocabulary terms, adjusted before freezing. These are planning targets, not observed results.

The demo asks whether Payroll Service inherits Service membership and whether Operations Team owns it. Synthetic source text explicitly states both. A third finite negative test checks that Payroll is not inferred to be a Team. RDFS is sufficient. `hasOwner` domain/range infer types; SHACL separately checks required ownership. The demo may proceed without confidential material. Domain implementation, real reviewers and confirmatory research remain gated by the decisions above and `research/protocol.yaml`.
