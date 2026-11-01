"""Finite synthetic packet evidence reconciliation, independent of queue status.

This verifies a copied observation, not global completion or remote immutability.
It deliberately does not switch the application provider or grant review rights.
"""
import hashlib

from ...artifacts import digest

PROV = 'http://www.w3.org/ns/prov#'
TG = 'https://trustgraph.ai/ns/'
SOURCE_GRAPH = 'urn:graph:source'
RETRIEVAL_GRAPH = 'urn:graph:retrieval'


def reconcile_synthetic_snapshot(packet, observations, retrieval):
    issues, reports = [], {}
    if (packet.get('mode') != 'synthetic_engineering_smoke'
            or packet.get('real_study_approved') is not False
            or packet.get('expected_chunk_count_per_flow') != 1
            or not isinstance(packet.get('source'), str)
            or not 0 < len(packet['source'].encode()) < 2000):
        raise ValueError('Only the bounded single-chunk synthetic packet is admitted')
    content = packet['source'].encode()
    source_hash = hashlib.sha256(content).hexdigest()
    if source_hash != packet.get('source_sha256') or len(content) != packet.get('byte_length'):
        raise ValueError('Frozen source hash or byte length differs')
    documents = packet.get('documents', {})
    if not documents or len(documents) > 2 or set(documents) != set(observations):
        raise ValueError('Observation scope differs from the frozen synthetic packet')

    for flow, document in documents.items():
        row = observations[flow]
        local_issues = []
        children = row.get('children', [])
        graph = row.get('source_graph', {}).get('response', [])
        if len(graph) >= 2000 or any(t.get('g') != SOURCE_GRAPH for t in graph):
            local_issues.append('source_graph_scope_or_limit')
        child_id = None
        if len(children) != 1:
            local_issues.append('expected_exactly_one_chunk')
        else:
            child = children[0]
            meta = child.get('metadata', {}).get('document-metadata', {})
            child_id = meta.get('id')
            if (not child_id or meta.get('parent-id') != document or meta.get('document-type') != 'chunk'
                    or child.get('content', '').encode() != content or child.get('sha256') != source_hash
                    or row.get('source_sha256') != source_hash):
                local_issues.append('exact_source_chunk_identity_hash_or_quote')

        def links(subject, predicate):
            return [t.get('o', {}) for t in graph if t.get('s', {}).get('i') == subject
                    and t.get('p', {}).get('i') == predicate and t.get('g') == SOURCE_GRAPH]

        if {'t': 'i', 'i': document} not in links(child_id, PROV + 'wasDerivedFrom'):
            local_issues.append('chunk_parent_provenance_missing')
        required = {'kg-extract-ontology'} if 'ontology' in flow else {'kg-extract-definitions', 'kg-extract-relationships'}
        observed, facts = set(), []
        for statement in graph:
            if statement.get('p', {}).get('i') != TG + 'contains' or statement.get('o', {}).get('t') != 't':
                continue
            subgraph = statement.get('s', {}).get('i')
            if {'t': 'i', 'i': child_id} not in links(subgraph, PROV + 'wasDerivedFrom'):
                continue
            for activity in links(subgraph, PROV + 'wasGeneratedBy'):
                for agent in links(activity.get('i'), PROV + 'wasAssociatedWith'):
                    name = agent.get('i', '').removeprefix('https://trustgraph.ai/agent/')
                    if name in required:
                        observed.add(name)
                        facts.append(statement['o']['tr'])
        if observed != required:
            local_issues.append('required_extraction_stage_evidence_missing')
        result = retrieval.get(flow, {})
        raw = result.get('raw', {})
        sources = raw.get('sources', [])
        trace = result.get('retrieval_graph', {}).get('response', [])
        if (result.get('status') != 'returned' or raw.get('end_of_session') is not True
                or not sources or any(s.get('uri') != document for s in sources)
                or not trace or len(trace) >= 2000 or any(t.get('g') != RETRIEVAL_GRAPH for t in trace)):
            local_issues.append('grounded_retrieval_or_trace_missing')
        reports[flow] = {'verified': not local_issues, 'issues': local_issues,
                         'required_stages': sorted(required), 'observed_stages': sorted(observed),
                         'source_sha256': source_hash, 'chunk_uri': child_id, 'quoted_facts': facts,
                         'observation_digest': digest(row), 'retrieval_digest': digest(result)}
        issues.extend(f'{flow}:{issue}' for issue in local_issues)
    report = {'schema_version': 1, 'mode': 'synthetic_snapshot_reconciliation',
              'packet_digest': digest(packet), 'bounded_snapshot_verified': not issues,
              'upstream_completion_supported': False, 'corpus_freeze_allowed': False,
              'review_eligible': False, 'reason': 'Copied evidence only; live provider ledger and immutable corpus integration remain gated',
              'flows': reports, 'issues': issues}
    return report | {'report_digest': digest(report)}
