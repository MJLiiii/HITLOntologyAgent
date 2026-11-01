"""Offline held-out evaluator. Deliberately not imported by the API or model runner.

The local credential and private directories exercise access boundaries. A real study
also requires a separate OS/service identity and agent-inaccessible mounts; this same-
user CLI does not create that deployment isolation by itself.
"""
from dataclasses import dataclass, field
import hashlib
import hmac
import json
import os
from pathlib import Path
import stat
from uuid import uuid4
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool

from oe_studio.artifacts import canonical_json
from oe_studio.experiments import measurements, sha, verify_record
from oe_studio.rdf import canonicalize, parse_ttl


class FrozenSchema(BaseModel):
    model_config = ConfigDict(extra='forbid')


class FileReference(FrozenSchema):
    path: str = Field(min_length=1, max_length=240)
    sha256: str = Field(pattern='^[a-f0-9]{64}$')


class ScheduledRun(FrozenSchema):
    task_id: str = Field(min_length=1, max_length=80)
    condition: Literal['A', 'B', 'C', 'D']
    replicate: int = Field(strict=True, ge=1, le=100)


class FrozenEvaluatorManifest(FrozenSchema):
    schema_version: Literal[1]
    protocol_id: str = Field(min_length=1, max_length=100)
    split: Literal['held_out']
    evaluator_subject: str = Field(min_length=1, max_length=100)
    outputs: FileReference
    task_packets: dict[str, FileReference] = Field(min_length=1, max_length=50)
    schedule: list[ScheduledRun] = Field(min_length=1, max_length=500)


class AskOracle(FrozenSchema):
    test_id: str = Field(min_length=1, max_length=80)
    kind: Literal['ask']
    query: str = Field(min_length=5, max_length=4000)
    expected: StrictBool


class EvaluationQuestion(FrozenSchema):
    id: str = Field(min_length=1, max_length=80)
    question: str = Field(min_length=5, max_length=1000)
    sparql_query: str = Field(min_length=5, max_length=4000)


class FrozenEvaluationPacket(FrozenSchema):
    split: Literal['held_out']
    base_ontology: str = Field(max_length=1048576)
    shapes_ttl: str = Field(default='', max_length=100000)
    tests: list[AskOracle] = Field(min_length=1, max_length=100)
    questions: list[EvaluationQuestion] = Field(min_length=1, max_length=100)


@dataclass(frozen=True)
class EvaluatorIdentity:
    subject: str
    kind: str
    credential: bytes = field(repr=False)


def authorize_evaluator(identity, expected_subject, expected_credential):
    if (identity.kind != 'evaluator' or identity.subject != expected_subject
            or len(expected_credential) < 32 or not hmac.compare_digest(identity.credential, expected_credential)):
        raise PermissionError('A separately provisioned evaluator credential is required')


def private_mount(path: Path, forbidden_roots) -> Path:
    path = Path(path)
    if path.is_symlink():
        raise PermissionError('Evaluator mount may not be a symlink')
    resolved = path.resolve(strict=True)
    info = resolved.stat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise PermissionError('Evaluator directories must be owned by the invoking evaluator and mode 0700')
    # The repository exclusion is intrinsic; a caller cannot omit it.
    for forbidden in [Path(__file__).resolve().parents[1], *forbidden_roots]:
        root = Path(forbidden).resolve()
        if resolved == root or resolved.is_relative_to(root) or root.is_relative_to(resolved):
            raise PermissionError('Held-out mounts must be separate from repository and application storage')
    return resolved


def _read(root, relative, expected_digest=None):
    relative = Path(relative)
    if relative.is_absolute() or '..' in relative.parts or not relative.parts:
        raise PermissionError('Evaluator reference must stay inside its input mount')
    path = root / relative
    for parent in [path, *path.parents]:
        if parent == root:
            break
        if parent.is_symlink():
            raise PermissionError('Symlinked evaluator input is forbidden')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
        value = stream.read(2 * 1024 * 1024 + 1)
    if len(value) > 2 * 1024 * 1024:
        raise ValueError('Evaluator input exceeds 2 MiB bound')
    if expected_digest is not None and sha(value) != expected_digest:
        raise ValueError('Frozen evaluator artifact digest mismatch')
    return value


def evaluate_frozen(input_dir, output_dir, identity, *, forbidden_roots, validate_fn=None, assess_fn=None):
    """Evaluate a fixed schedule, preserving missing/failed candidates and common oracles.

    manifest.json binds frozen-outputs.json plus one packet per task by content digest.
    Neither input packets nor output reports are written into application directories.
    """
    input_root = private_mount(Path(input_dir), forbidden_roots)
    output_root = private_mount(Path(output_dir), forbidden_roots)
    if (input_root == output_root or input_root.is_relative_to(output_root)
            or output_root.is_relative_to(input_root)):
        raise PermissionError('Evaluator input and output mounts must be separate')
    secret_path = input_root / '.evaluator.key'
    if stat.S_IMODE(secret_path.stat().st_mode) != 0o600 or secret_path.stat().st_uid != os.getuid():
        raise PermissionError('Evaluator credential file must be owned and mode 0600')
    manifest_bytes = _read(input_root, 'manifest.json')
    manifest = FrozenEvaluatorManifest.model_validate_json(manifest_bytes).model_dump()
    authorize_evaluator(identity, manifest['evaluator_subject'], _read(input_root, '.evaluator.key'))
    if manifest.get('split') != 'held_out' or manifest.get('schema_version') != 1:
        raise ValueError('An explicitly frozen held-out manifest is required')
    rows = json.loads(_read(input_root, manifest['outputs']['path'], manifest['outputs']['sha256']))
    indexed = {}
    for row in rows:
        verify_record(row)
        key = (row['task_id'], row['condition'], row['replicate'])
        if key in indexed:
            raise ValueError('Duplicate frozen task/condition/replicate output')
        if row['candidate_ttl'] is not None and sha(canonicalize(parse_ttl(row['candidate_ttl']))) != row['candidate_digest']:
            raise ValueError('Frozen candidate digest mismatch')
        indexed[key] = row
    packets = {task: FrozenEvaluationPacket.model_validate_json(_read(input_root, ref['path'], ref['sha256'])).model_dump()
               for task, ref in manifest['task_packets'].items()}
    schedule = [(r['task_id'], r['condition'], r['replicate']) for r in manifest['schedule']]
    if (not 1 <= len(schedule) <= 500 or len(set(schedule)) != len(schedule)
            or any(key not in schedule for key in indexed)
            or set(packets) != {key[0] for key in schedule}
            or any(key[1] not in ('A', 'B', 'C', 'D') or type(key[2]) is not int or key[2] < 1 for key in schedule)):
        raise ValueError('Frozen output schedule is empty, duplicated or inconsistent')
    if validate_fn is None:
        from oe_studio.validation import validate as validate_fn
    if assess_fn is None:
        from oe_studio.assessment import assess as assess_fn
    results = []
    for task, condition, replicate in schedule:
        packet = packets[task]
        if packet.get('split') != 'held_out' or not 1 <= len(packet.get('tests', [])) <= 100:
            raise ValueError('Each held-out task requires a nonempty frozen test workload')
        if len({t['test_id'] for t in packet['tests']}) != len(packet['tests']):
            raise ValueError('Duplicate held-out test identity')
        if any(t.get('kind') != 'ask' or type(t.get('expected')) is not bool for t in packet['tests']):
            raise ValueError('This evaluator admits finite ASK answer oracles only')
        row = indexed.get((task, condition, replicate))
        candidate = row['candidate_ttl'] if row else None
        if candidate is None:
            validation = {'status': 'error', 'cases': [], 'reason': 'frozen_candidate_missing_or_failed'}
            assessment = {'status': 'not_run'}
        else:
            def call(function, **kwargs):
                try:
                    return function(candidate, **kwargs)
                except Exception as exc:
                    return {'status': 'error', 'cases': [], 'reason': type(exc).__name__}
            validation = call(validate_fn, bundle_digest=row['candidate_digest'],
                              tests=packet['tests'], shapes_ttl=packet.get('shapes_ttl', ''))
            assessment = call(assess_fn, bundle_digest=row['candidate_digest'],
                              base_ttl=packet['base_ontology'], questions=packet['questions'])
        metrics, counts = measurements(validation, assessment, packet['tests'])
        # The evaluator does not observe generation usage or human work.
        for name in ('model_cost', 'model_tokens', 'correction_seconds'):
            metrics[name]['missing_reason'] = 'not_observed_by_evaluator'
        results.append({'task_id': task, 'condition': condition, 'replicate': replicate,
                        'frozen_run_id': row['id'] if row else None,
                        'frozen_record_digest': row['record_digest'] if row else None,
                        'candidate_digest': row['candidate_digest'] if row else None,
                        'held_out_packet_digest': manifest['task_packets'][task]['sha256'],
                        'metrics': metrics, 'case_counts': counts, 'validation': validation, 'assessment': assessment})
    report = {'schema_version': 1, 'id': str(uuid4()), 'protocol_id': manifest['protocol_id'],
              'split': 'held_out', 'evaluator_subject': identity.subject,
              'frozen_manifest_sha256': hashlib.sha256(manifest_bytes).hexdigest(),
              'deployment_isolation': 'operator_provided; same-user CLI alone is not an OS security boundary',
              'study_claim': None, 'results': results}
    path = output_root / (report['id'] + '.json')
    with path.open('xb') as stream:
        stream.write(canonical_json(report))
    path.chmod(0o600)
    return report, path
