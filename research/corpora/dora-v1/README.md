# DORA public source packet v1

Prepared on 1 November 2026 for the user-selected financial regulatory compliance domain: modelling contractual obligations between financial entities and ICT third-party service providers. This packet contains **five public documents**, nine retained official representations and 44 complete article, template or contextual extracts. The ontology design is in [the modelling specification](../../../docs/dora-modelling.md); the authorization boundary is in [the domain scope](../../../docs/domain-scope.md).

## Source register

| ID / role | Official source and retained originals | Selected material | Publication / entry into force / separate application |
|---|---|---|---|
| `dora` / primary | [Regulation (EU) 2022/2554](https://eur-lex.europa.eu/eli/reg/2022/2554/oj); [HTML](originals/32022R2554-en.html), [PDF](originals/32022R2554-en.pdf) | Articles 2-3 and 28-30; Articles 4 and 64 retained for proportionality and dates | 2022-12-27 / 2023-01-16 / 2025-01-17, Article 64 |
| `policy` / core supplement | [Delegated Regulation (EU) 2024/1773](https://eur-lex.europa.eu/eli/reg_del/2024/1773/oj/eng); [HTML](originals/32024R1773-en.html), [PDF](originals/32024R1773-en.pdf) | Articles 3-10, especially 8-10; Articles 1-2 and 11 retained for scope and dates | 2024-06-25 / 2024-07-15 / no separate date in Article 11 |
| `subcontracting` / extension | [Delegated Regulation (EU) 2025/532](https://eur-lex.europa.eu/eli/reg_del/2025/532/oj/eng); [complete HTML](originals/32025R0532-en.html) | Articles 3-6; Articles 1-2 and 7 retained for scope and dates | 2025-07-02 / 2025-07-22 / no separate date in Article 7 |
| `register` / structural reference | [Implementing Regulation (EU) 2024/2956](https://eur-lex.europa.eu/eli/reg_impl/2024/2956/oj/eng); [HTML](originals/32024R2956-en.html), [PDF](originals/32024R2956-en.pdf) | Annex I instructions and field tables B_02.01, B_02.02, B_03.01, B_03.02, B_05.01, B_05.02, B_06.01; Articles 1-7, general instructions and Annexes II-IV retained as context | 2024-12-02 / 2024-12-22 / no separate date in Article 7 |
| `esma` / interpretive supplement | [ESMA Q&A 2646](https://www.esma.europa.eu/publications-data/questions-answers/2646); [HTML](originals/ESMA_QA_2646-en.html), [PDF](originals/ESMA_QA_2646-en.pdf) | Complete question and answer about audit frequency | Published answer 2025-09-18; legislative entry/application dates not applicable |

The regulations are the adopted Official Journal English editions, rather than draft RTS consultation papers. The Q&A is supervisory clarification, not legislation. Entry into force is calculated from the publication date and the cited twenty-day provision; it is not substituted for DORA's separate application date. Contract-specific transition and remediation conditions remain in the extracts.

The packet freezes these editions for a reproducible modelling test. It is not a continuously updated legal register or an exhaustive certification of later amendments/corrigenda. Before future operational use, recheck the official document history and any relevant language corrections; create a successor packet rather than changing this baseline silently. Consolidated texts are documentary aids and do not replace the retained Official Journal provenance.

## Reading and modelling order

1. Read [DORA Article 30](extracts/dora-art-30.txt), with [definitions](extracts/dora-art-3.txt), [scope](extracts/dora-art-2.txt), [third-party principles](extracts/dora-art-28.txt), [concentration risk](extracts/dora-art-29.txt) and [proportionality](extracts/dora-art-4.txt).
2. Add the policy's [contractual clauses](extracts/policy-art-8.txt), [monitoring](extracts/policy-art-9.txt) and [exit plans](extracts/policy-art-10.txt), using Articles 1-7 for context.
3. Extend to subcontracting [conditions](extracts/subcontracting-art-4.txt), [material changes](extracts/subcontracting-art-5.txt) and [termination](extracts/subcontracting-art-6.txt), retaining Article 3's due diligence conditions.
4. Cross-check identities and relationships using the [contract field table](extracts/register-B_02.02.txt), [supply chain](extracts/register-B_05.02.txt) and [function identification](extracts/register-B_06.01.txt).
5. Use [ESMA Q&A 2646](extracts/esma-qa-2646.txt) as a separate interpretation case. The question's suggested annual limit is not the answer.

## Provenance and extraction

[manifest.json](manifest.json) records each document identifier, authority, classification, English edition, dates and their basis, canonical URL, download URL, retrieval timestamp, byte count and SHA-256. Each extract records its source file/hash, complete article or template locator, source selector and own hash. Article records include the native paragraph anchors and cross-reference links. For example, `dora-art-30` includes `030.001` through `030.005`; cite paragraph/point such as Article 30(2)(f) in addition to the extract ID.

All original files are unmodified downloaded bytes. EUR-Lex returned empty HTTP 202 challenge responses during direct download; the regulations' structured English editions were obtained through the official Publications Office CELLAR service. The register PDF is the Official Journal copy served by EBA; the Q&A PDF is ESMA's own print export. The manifest retains the exact successful HTTPS URLs. The subcontracting act is retained in full official XHTML: the Publications Office PDF request returned no PDF representation, and no substitute PDF was fabricated.

Extracts normalize whitespace and add line breaks/table-cell separators for readability. They do not paraphrase, repair wording, remove exceptions or synthesize missing text. Full article selections retain all paragraphs and lists. Template extracts retain the complete instructions and field table, including conditional fields. Relative links/footnotes can be resolved using the archived original and canonical source URL. Cross-referenced provisions outside the selected extracts remain in the full originals where present; other acts are explicit external context, not silently imported rules.

The register's PDF contains rotated tables; an exploratory layout-mode extraction warned of incomplete text and was discarded. Structured XHTML is therefore the source of the register extracts. The two-page ESMA PDF uses pinned `pypdf 6.21.4` default extraction. Original PDF pagination is preserved in the originals; normalized text is not a facsimile.

Attribution: European Union, Official Journal, for the four regulations; European Securities and Markets Authority for the Q&A. The original attribution and document identifiers are retained. [EUR-Lex legal notice](https://eur-lex.europa.eu/content/legal-notice/legal-notice.html) and [ESMA legal notice](https://www.esma.europa.eu/about-esma/legal-notice-and-data-protection) remain the rights references; this packet does not invent an MIT/CC licence for third-party source documents. Local copies are retained for reproducibility, with no automatic refresh or deletion.

## Verify and use

From the repository root:

```sh
.venv/bin/python research/corpora/dora-v1/verify.py
```

The offline check verifies every source/extract hash and PDF page count, reconstructs each selected extract from its retained source, checks planned coverage and verifies [SHA256SUMS](SHA256SUMS). A failure is not an ingestion pass. It makes no network/model request and changes no application state. The checksum list is an integrity baseline, not a signed approval or protection against an actor rewriting both files and checksums.

Use a small, explicitly selected subset per modelling task; do not concatenate the entire packet into a model prompt. The current model context is limited to 20 passages and 64 KiB in the registered protocol. Selection must preserve conditions and exceptions; if context is too large, narrow the task. The six question families in the modelling specification are proposed development expectations awaiting human review, not approved oracles or held-out evaluation material.

No API/types, application database, ontology Git refs, source classification rules, model configuration or A-D controls were changed. Public ingestion support does not imply this packet is admitted by the synthetic-only experiment runner. See [the runtime boundary](../../../docs/domain-scope.md#authorization-and-runtime-boundary).
