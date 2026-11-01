"""Bounded calls to the pinned OntoCheck environment; scores never authorize publication."""
from __future__ import annotations

import json
import hashlib
import math
import os
from pathlib import Path
import subprocess
import tempfile
from uuid import uuid4

from .artifacts import canonical_json
from .assessment_contracts import ApprovedMapping
from .engine_isolation import isolated_command, python_runtime_paths

ROOT = Path(__file__).resolve().parents[4]
RESOURCE_ROOT = ROOT / 'resources/nltk'
COMMIT = '69d42e38979f381fe531ae547fcc49b8ad58ef15'
SCORES = ('vocabulary_coverage', 'vocabulary_utilisation', 'strict_fitness',
          'approximate_fitness', 'structural_fitness')
DEFAULT_QUESTIONS = [{
    'id': 'demo-cq-asset', 'question': 'Which assets have an owner?', 'required': True,
    'sparql_query': 'PREFIX ex: <https://example.org/oe-demo/> SELECT ?asset WHERE '
                    '{ ?asset a ex:Asset ; ex:ownedBy ?owner . ?owner a ex:Owner . }',
}]


def assess(ontology_ttl: str, *, base_ttl: str = '', bundle_digest: str,
           questions: list[dict] | None = None, mappings: list[dict] | None = None) -> dict:
    questions = DEFAULT_QUESTIONS if questions is None else questions
    mappings = [] if mappings is None else mappings
    report = {
        'id': str(uuid4()), 'bundle_digest': bundle_digest, 'status': 'error',
        'engine': {'name': 'OntoCheck', 'version': '0.1.3', 'commit': COMMIT,
                   'network': 'disabled', 'network_control': 'Python audit hook; no child processes'},
        **dict.fromkeys(SCORES), 'raw': {}, 'deltas': {}, 'denominators': {}, 'missing_reasons': {},
        'questions': questions, 'mappings': mappings, 'authorize_prefix_mapping': False,
        'limitations': [
            'Vocabulary overlap measures task coverage and utilisation, not answer correctness.',
            'Schema fitness is diagnostic; approximate matches are not approved equivalence mappings.',
            'Jena benchmark equivalence and held-out evaluation are not verified (TODO-ONTOCHECK-02).',
        ],
    }
    try:
        if not isinstance(mappings, list) or len(mappings) > 100:
            raise ValueError('At most 100 reviewed mappings are permitted')
        mappings = [ApprovedMapping.model_validate(item).model_dump() for item in mappings]
        if len({item['requirement_iri'] for item in mappings}) != len(mappings):
            raise ValueError('Each requirement can have only one approved correspondence')
    except ValueError as exc:
        report['status'] = 'unsupported'
        report['limitations'].append(f'Invalid reviewed mapping artifact: {exc}')
        return report
    report['mappings'] = mappings
    report['mappings_sha256'] = hashlib.sha256(canonical_json(mappings)).hexdigest()
    if (not isinstance(ontology_ttl, str) or not isinstance(base_ttl, str)
            or max(len(ontology_ttl), len(base_ttl)) > 1_000_000):
        report['limitations'].append('Assessment requires bounded local Turtle strings (maximum 1 MB each).')
        return report
    python = os.getenv('OE_ONTOCHECK_PYTHON', str(ROOT / '.venv-ontocheck/bin/python'))
    try:
        timeout = min(60.0, max(0.001, float(os.getenv('OE_ONTOCHECK_TIMEOUT_SECONDS', '20'))))
        with tempfile.TemporaryDirectory(prefix='oe-assessment-') as work:
            folder = Path(work)
            payload = {'ontology_ttl': ontology_ttl, 'base_ttl': base_ttl, 'questions': questions,
                       'mappings': mappings, 'nltk_data_dir': str(RESOURCE_ROOT.resolve())}
            request = folder / 'request.json'
            request.write_text(json.dumps(payload), encoding='utf-8')
            worker = Path(__file__).with_name('assessment_worker.py')
            command, isolation = isolated_command(
                [python, '-I', str(worker), str(request)], workdir=folder,
                readable=[worker, RESOURCE_ROOT, *python_runtime_paths(python)],
            )
            report['engine']['isolation'] = isolation
            report['engine']['network_control'] = 'macOS Seatbelt network denial plus Python audit hook'
            completed = subprocess.run(
                command,
                capture_output=True, text=True, timeout=timeout, cwd=folder, stdin=subprocess.DEVNULL,
                env={'PATH': str(Path(python).parent), 'LANG': 'C.UTF-8',
                     'TMPDIR': work, 'NLTK_DATA': str(RESOURCE_ROOT)},
            )
            if completed.returncode:
                raise RuntimeError('OntoCheck worker failed: ' + completed.stderr[-1000:])
            result = json.loads(completed.stdout)
            if not isinstance(result, dict) or result.get('status') not in {'completed', 'unsupported', 'error'}:
                raise RuntimeError('OntoCheck returned an invalid report status or schema')
            if result['status'] == 'completed':
                if (not all(key in result for key in SCORES)
                        or 'candidate' not in result.get('raw', {})
                        or result.get('denominators', {}).get('candidate', {}).get('questions') != len(questions)
                        or any(value is not None and (type(value) not in (int, float) or
                               not math.isfinite(value) or not 0 <= value <= 1)
                               for value in (result[key] for key in SCORES))):
                    raise RuntimeError('Successful OntoCheck report is missing required measurements')
            if result.get('raw') and (result.get('mappings') != mappings
                    or result.get('mappings_sha256') != report['mappings_sha256']
                    or any(raw.get('mappings_sha256') != report['mappings_sha256']
                           for raw in result['raw'].values())):
                raise RuntimeError('OntoCheck report does not match the reviewed mapping artifact')
            report['limitations'].extend(result.pop('limitations', []))
            report['engine'].update(result.pop('engine', {}))
            report.update(result)
    except subprocess.TimeoutExpired:
        report['status'] = 'timeout'
        report['limitations'].append('OntoCheck exceeded its wall-clock limit; no scores are eligible for review.')
    except (OSError, ValueError, RuntimeError) as exc:
        report['status'] = 'error'
        report['limitations'].append(f'OntoCheck unavailable or failed: {exc}')
    return report
