"""Run the pinned Apache Jena validator; engine failures never become success.

Build once from the repository root (Java 21 or later):
    JAVA_HOME=/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home \
        mvn -o -f services/jena-runner/pom.xml package

The first build needs cached Maven dependencies; omit -o when preparing a networked
environment. Runtime uses no Maven or remote graph loading. OE_JAVA_EXECUTABLE and
OE_JENA_RUNNER_JAR may be set by the deployment, never by request payloads.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from uuid import uuid4

from .engine_isolation import isolated_command
from .engine_process import ENFORCEMENT, run_engine

ROOT = Path(__file__).resolve().parents[4]
RUNNER_JAR = Path(os.environ.get('OE_JENA_RUNNER_JAR', ROOT / 'services/jena-runner/target/oe-jena-runner.jar'))
_HOMEBREW_JAVA = Path('/opt/homebrew/opt/openjdk@21/bin/java')
JAVA_EXECUTABLE = Path(os.environ.get('OE_JAVA_EXECUTABLE') or
                       (str(_HOMEBREW_JAVA) if _HOMEBREW_JAVA.exists() else shutil.which('java') or '/usr/bin/java'))
PROFILE_FILE = ROOT / 'config/modelling-profile.json'
TIMEOUT_SECONDS = 30
MAX_INPUT_BYTES = 1_048_576
MAX_REPORT_BYTES = 4_194_304
MAX_OUTPUT_BYTES = 16 * 1024 * 1024
MAX_RSS_BYTES = 1024 * 1024 * 1024
MAX_TASKS = 128
RUNNER_VERSION = '0.1.0'
JENA_VERSION = '6.2.0'


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate(ontology_ttl: str, *, bundle_digest: str, shapes_ttl: str = '',
             fixtures_ttl: str = '', tests: list[dict] | None = None) -> dict:
    """Evaluate an immutable bundle with RDFS closure and explicit test oracles.

    SHACL checks global fixtures. A case's ``fixtures_ttl`` replaces global fixtures
    for that case, allowing deliberately invalid data to pass an expected-negative
    SHACL oracle. SELECT rows use {variable: {kind, value, datatype?, lang?}} bindings
    and unordered multiset comparison (exact or contains).
    """
    report = {
        'id': str(uuid4()), 'bundle_digest': bundle_digest, 'status': 'error',
        'engine': {'name': 'Apache Jena', 'version': JENA_VERSION, 'runner_version': RUNNER_VERSION},
        'profile': 'rdfs', 'validation_graph': 'asserted_plus_inferred',
        'stages': [], 'cases': [], 'limitations': [
            'No fallback validator is used when Apache Jena is unavailable.',
            'RDFS checks are not a complete OWL DL consistency proof.',
        ], 'started_at': _now(), 'finished_at': None,
    }

    def fail(message: str, status: str = 'error') -> dict:
        report['status'] = status
        report['stages'].append({'name': 'runner', 'status': status, 'message': message})
        report['finished_at'] = _now()
        return report

    try:
        if not re.fullmatch(r'(?:sha256:)?[a-f0-9]{64}', bundle_digest):
            return fail('Bundle digest must be a SHA-256 hexadecimal value')
        if not isinstance(tests, (list, type(None))) or len(tests or []) > 100:
            return fail('Tests must be a list with at most 100 cases')
        if not RUNNER_JAR.is_file() or not JAVA_EXECUTABLE.is_file():
            return fail('Jena runner or Java executable is missing; build services/jena-runner with Java 21+')
        profile_text = PROFILE_FILE.read_text()
        report['limitations'] = json.loads(profile_text)['limitations']
        inputs = {'ontology': ontology_ttl, 'shapes': shapes_ttl, 'fixtures': fixtures_ttl,
                  'tests': json.dumps(tests or [], ensure_ascii=False, allow_nan=False), 'profile': profile_text}
        if any(not isinstance(value, str) or len(value.encode('utf-8')) > MAX_INPUT_BYTES for value in inputs.values()):
            return fail('Each runner input must be UTF-8 text no larger than 1 MiB')
        with tempfile.TemporaryDirectory(prefix='oe-jena-') as temporary:
            directory = Path(temporary)
            artifacts = {}
            for name, value in inputs.items():
                content = value.encode('utf-8')
                filename = name + ('.json' if name in ('tests', 'profile') else '.ttl')
                (directory / filename).write_bytes(content)
                artifacts[name] = {'path': filename, 'sha256': hashlib.sha256(content).hexdigest()}
            manifest = {'schema_version': 1, 'bundle_digest': bundle_digest,
                        'expected_runner_version': RUNNER_VERSION,
                        'inference_mode': 'rdfs', 'validation_graph': 'asserted_plus_inferred',
                        'limits': {'timeout_seconds': TIMEOUT_SECONDS, 'heap_mib': 256,
                                   'max_input_bytes': MAX_INPUT_BYTES, 'max_select_rows': 10_000},
                        'artifacts': artifacts}
            manifest_path = directory / 'manifest.json'
            manifest_path.write_text(json.dumps(manifest, sort_keys=True))
            command = [str(JAVA_EXECUTABLE.resolve()), '-Xmx256m', '-XX:MaxMetaspaceSize=128m',
                       '-XX:ActiveProcessorCount=2', '-Xss512k', '-jar', str(RUNNER_JAR.resolve()),
                       '--manifest', str(manifest_path)]
            command, isolation = isolated_command(command, workdir=directory,
                                                   readable=[JAVA_EXECUTABLE.resolve().parent.parent, RUNNER_JAR])
            report['engine']['isolation'] = isolation
            # Remove JVM injection knobs; credentials are not copied into the isolated runner.
            environment = {key: os.environ[key] for key in ('PATH', 'LANG', 'LC_ALL', 'TMPDIR', 'SYSTEMROOT') if key in os.environ}
            limits = {'wall_seconds': TIMEOUT_SECONDS, 'rss_bytes': MAX_RSS_BYTES,
                      'tasks': MAX_TASKS, 'output_bytes': MAX_OUTPUT_BYTES, 'enforcement': ENFORCEMENT}
            report['engine']['limits'] = limits
            process = run_engine(command, cwd=directory, timeout=TIMEOUT_SECONDS, env=environment,
                                 max_rss_bytes=MAX_RSS_BYTES, max_tasks=MAX_TASKS,
                                 max_output_bytes=MAX_OUTPUT_BYTES,
                                 output_paths=[directory / name for name in
                                               ('report.json', 'shacl-report.ttl', 'query-results.json')])
            output = directory / 'report.json'
            if not output.is_file():
                return fail(f'Jena exited with code {process.returncode} without a structured report')
            if output.stat().st_size > MAX_REPORT_BYTES:
                return fail('Jena report exceeds the output limit')
            actual = json.loads(output.read_text())
            status = actual.get('status')
            expected_codes = {'passed': {0}, 'failed': {2}, 'unsupported': {3}, 'error': {3, 4}, 'timeout': {4}}
            if status not in expected_codes or process.returncode not in expected_codes[status]:
                return fail('Jena exit code and report status disagree')
            if actual.get('bundle_digest', bundle_digest) != bundle_digest:
                return fail('Jena report references a different bundle')
            if actual.get('engine', {}).get('version') != JENA_VERSION:
                return fail('Jena report engine version does not match the pinned environment')
            if not isinstance(actual.get('stages'), list) or not isinstance(actual.get('cases'), list):
                return fail('Jena report has an invalid stage/case schema')
            if status == 'passed':
                expected_ids = {case.get('test_id', case.get('id')) for case in tests or []}
                actual_ids = {case.get('id') for case in actual['cases']}
                required_stages = {'integrity_and_syntax', 'admitted_profile', 'materialization',
                                   'data_constraints', 'executable_expectations'}
                passed_stages = {stage.get('name') for stage in actual['stages'] if stage.get('status') == 'passed'}
                if (expected_ids != actual_ids or len(actual['cases']) != len(tests or []) or
                        not required_stages <= passed_stages or
                        any(case.get('status') != 'passed' for case in actual['cases'])):
                    return fail('Successful Jena report is missing required stages or case outcomes')
            report.update(actual)
            report['engine']['isolation'] = isolation
            report['engine']['limits'] = limits
            report['bundle_digest'] = bundle_digest
            report['input_manifest'] = manifest
            report['engine']['jar_sha256'] = hashlib.sha256(RUNNER_JAR.read_bytes()).hexdigest()
            report['raw_artifacts'] = {}
            for name in ('shacl-report.ttl', 'query-results.json'):
                artifact = directory / name
                if not artifact.is_file() or artifact.stat().st_size > MAX_REPORT_BYTES:
                    return fail(f'Missing or oversized required report artifact: {name}')
                report['raw_artifacts'][name] = artifact.read_text()
            return report
    except subprocess.TimeoutExpired:
        return fail('Jena process exceeded its wall-clock limit and was terminated', 'timeout')
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError, subprocess.SubprocessError) as error:
        return fail(f'Validator input or process error: {type(error).__name__}: {error}')
