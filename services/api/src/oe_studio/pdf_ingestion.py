"""Bounded PDF extraction; incomplete pages never become an ingestible text artifact."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
from uuid import uuid4

from .engine_isolation import isolated_command, python_runtime_paths
from .engine_process import ENFORCEMENT, EngineResourceLimit, run_engine

VERSION = '6.21.4'
MAX_INPUT_BYTES = 20 * 1024 * 1024
MAX_TEXT_BYTES = 2 * 1024 * 1024
MAX_RSS_BYTES = 512 * 1024 * 1024
MAX_REPORT_BYTES = 8 * 1024 * 1024
MAX_TASKS = 32
WALL_SECONDS = 15
WORKER = Path(__file__).with_name('pdf_worker.py')


def _verify(result, source_hash, source_bytes):
    if (not isinstance(result, dict) or result.get('status') not in {'completed', 'unsupported', 'error'}
            or result.get('source_sha256') != source_hash or result.get('source_bytes') != source_bytes
            or result.get('engine', {}).get('version') != VERSION):
        raise ValueError('PDF report identity or engine does not match the frozen input')
    if result['status'] != 'completed':
        result['text'], result['text_sha256'] = '', None
        return
    pages = result.get('pages')
    text = result.get('text')
    if (not isinstance(pages, list) or not 0 < len(pages) <= 200
            or result.get('page_count') != len(pages) or not isinstance(text, str)
            or len(text.encode()) > MAX_TEXT_BYTES
            or text != '\n\n'.join(page.get('text', '') for page in pages)
            or result.get('text_sha256') != hashlib.sha256(text.encode()).hexdigest()
            or result.get('diagnostics')):
        raise ValueError('PDF success report is incomplete or exceeds the extraction limit')
    offset = 0
    for number, page in enumerate(pages, 1):
        value = page['text']
        if (page.get('status') != 'completed' or page.get('page') != number or not value.strip()
                or page.get('diagnostics') or page.get('char_start') != offset
                or page.get('char_end') != offset + len(value)
                or page.get('text_sha256') != hashlib.sha256(value.encode()).hexdigest()):
            raise ValueError('PDF page text, identity or offsets are invalid')
        offset += len(value) + 2


def extract_pdf(content: bytes) -> dict:
    report = {'id': str(uuid4()), 'status': 'error', 'source_sha256': None, 'source_bytes': 0,
              'page_count': None, 'pages': [], 'text': '', 'text_sha256': None, 'diagnostics': [],
              'engine': {'name': 'pypdf', 'version': VERSION,
                         'limits': {'wall_seconds': WALL_SECONDS, 'rss_bytes': MAX_RSS_BYTES,
                                    'tasks': MAX_TASKS, 'output_bytes': MAX_REPORT_BYTES,
                                    'enforcement': ENFORCEMENT,
                                    'input_bytes': MAX_INPUT_BYTES, 'text_bytes': MAX_TEXT_BYTES, 'pages': 200}}}

    def fail(code, message, status='error'):
        report['status'] = status
        report['text'], report['text_sha256'] = '', None
        report['diagnostics'].append({'code': code, 'message': str(message)[:2000]})
        return report

    if not isinstance(content, bytes):
        return fail('invalid_input', 'PDF input must be immutable bytes', 'unsupported')
    source_hash = hashlib.sha256(content).hexdigest()
    report.update(source_sha256=source_hash, source_bytes=len(content))
    if not 0 < len(content) <= MAX_INPUT_BYTES or not content.startswith(b'%PDF-'):
        return fail('invalid_input', 'PDF must have a PDF header and contain at most 20 MiB', 'unsupported')
    try:
        with tempfile.TemporaryDirectory(prefix='oe-pdf-') as work:
            directory = Path(work)
            source = directory / 'source.pdf'
            source.write_bytes(content)
            manifest = directory / 'manifest.json'
            manifest.write_text(json.dumps({'source_sha256': source_hash, 'source_bytes': len(content)}))
            command, isolation = isolated_command(
                [sys.executable, '-I', str(WORKER), str(manifest)], workdir=directory,
                readable=[WORKER, *python_runtime_paths(sys.executable)],
            )
            report['engine']['isolation'] = isolation
            process = run_engine(
                command, cwd=directory, timeout=WALL_SECONDS, max_rss_bytes=MAX_RSS_BYTES,
                max_tasks=MAX_TASKS, max_output_bytes=MAX_REPORT_BYTES,
                env={'PATH': str(Path(sys.executable).parent), 'LANG': 'C.UTF-8', 'TMPDIR': work},
            )
            if process.returncode:
                if process.returncode in {-signal.SIGXCPU, 128 + signal.SIGXCPU}:
                    return fail('cpu_timeout', 'PDF extraction exceeded its CPU-time limit', 'timeout')
                return fail('worker_failure', f'PDF worker exit {process.returncode}: {process.stderr[-1000:]}')
            result = json.loads(process.stdout)
            if hashlib.sha256(source.read_bytes()).hexdigest() != source_hash:
                return fail('source_integrity', 'PDF source bytes changed during extraction')
            _verify(result, source_hash, len(content))
            limits = {**result['engine'].get('limits', {}), **report['engine']['limits']}
            report.update(result)
            report['engine'].update(isolation=isolation, limits=limits)
    except subprocess.TimeoutExpired:
        return fail('wall_timeout', 'PDF extraction exceeded its wall-clock deadline', 'timeout')
    except EngineResourceLimit as exc:
        return fail(exc.code, str(exc))
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError, subprocess.SubprocessError) as exc:
        return fail('extraction_error', f'{type(exc).__name__}: {exc}')
    return report
