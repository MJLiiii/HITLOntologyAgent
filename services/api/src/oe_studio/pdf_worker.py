"""Strict text-layer extraction in a resource-limited, OS-confined process."""
from __future__ import annotations

import hashlib
import io
import json
import logging
from pathlib import Path
import resource
import sys
import warnings

VERSION = '6.21.4'
MAX_INPUT_BYTES = 20 * 1024 * 1024
MAX_TEXT_BYTES = 2 * 1024 * 1024
MAX_PAGES = 200


def diagnostic(code, message):
    return {'code': code, 'message': str(message)[:1000]}


def restrict_process():
    resource.setrlimit(resource.RLIMIT_CPU, (10, 11))
    resource.setrlimit(resource.RLIMIT_FSIZE, (8 * 1024 * 1024, 8 * 1024 * 1024))
    limits = {'cpu_seconds': 10, 'file_bytes': 8 * 1024 * 1024,
              'rss_bytes': 512 * 1024 * 1024,
              'rss_enforcement': 'parent watchdog at approximately 50 ms intervals; not an instantaneous allocation cap'}
    try:
        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
        limits['address_space_bytes'] = 512 * 1024 * 1024
    except (ValueError, OSError) as exc:
        limits['address_space_bytes'] = None
        limits['address_space_limit_reason'] = str(exc)

    def audit(event, args):
        if event in {'socket.connect', 'socket.getaddrinfo', 'socket.sendto', 'socket.sendmsg',
                     'subprocess.Popen', 'os.system', 'os.exec', 'os.posix_spawn', 'os.fork'}:
            raise PermissionError('PDF extraction prohibits network access and child processes')

    sys.addaudithook(audit)
    return limits


class ParseWarnings(logging.Handler):
    def __init__(self):
        super().__init__(logging.WARNING)
        self.items = []

    def emit(self, record):
        if len(self.items) < 100:
            self.items.append(diagnostic('parser_warning', record.getMessage()))


def extract(request):
    limits = restrict_process()
    payload = json.loads(request.read_text())
    source = request.parent / 'source.pdf'
    content = source.read_bytes()
    report = {'status': 'error', 'source_sha256': hashlib.sha256(content).hexdigest(),
              'source_bytes': len(content), 'page_count': None, 'pages': [],
              'text': '', 'text_sha256': None, 'diagnostics': [],
              'engine': {'name': 'pypdf', 'version': VERSION, 'limits': limits,
                         'limitations': ['Text-layer extraction does not verify visual reading order or OCR accuracy.']}}
    if (len(content) > MAX_INPUT_BYTES or len(content) != payload['source_bytes']
            or report['source_sha256'] != payload['source_sha256']):
        report['diagnostics'].append(diagnostic('source_integrity', 'Original PDF bytes differ from the manifest'))
        return report
    import pypdf
    if pypdf.__version__ != VERSION:
        report['diagnostics'].append(diagnostic('engine_version', 'The exact pinned pypdf release is required'))
        return report
    configuration = {
        'maximum_declared_stream_length': MAX_INPUT_BYTES,
        'array_based_stream_maximum_output_length': 8 * 1024 * 1024,
        'zlib_maximum_output_length': 8 * 1024 * 1024,
        'lzw_maximum_output_length': 8 * 1024 * 1024,
        'run_length_maximum_output_length': 8 * 1024 * 1024,
        'brotli_maximum_output_length': 8 * 1024 * 1024,
        'stream_decoding_work_maximum_length': 32 * 1024 * 1024,
        'stream_parsing_work_maximum_count': 1_000_000,
        'page_tree_maximum_entries': 2000, 'page_tree_maximum_depth': 30,
        'page_tree_maximum_page_entries': 201, 'jbig2dec_binary': None,
    }
    report['engine']['configuration'] = configuration
    captured = ParseWarnings()
    logger = logging.getLogger('pypdf')
    logger.addHandler(captured)
    logger.propagate = False
    warnings.simplefilter('error')
    total_bytes = 0
    try:
        with pypdf.apply_configuration(**configuration):
            reader = pypdf.PdfReader(io.BytesIO(content), strict=True,
                                     root_object_recovery_limit=0, xref_stream_maximum_entries=100_000)
            if reader.is_encrypted:
                report['status'] = 'unsupported'
                report['diagnostics'].append(diagnostic('encrypted_pdf', 'Encrypted PDFs require preprocessing'))
                return report
            report['page_count'] = len(reader.pages)
            if not 0 < report['page_count'] <= MAX_PAGES:
                report['status'] = 'unsupported'
                report['diagnostics'].append(diagnostic('page_limit', 'PDF must contain 1–200 text-bearing pages'))
                return report
            if captured.items:
                report['status'] = 'unsupported'
                report['diagnostics'].extend(captured.items)
                return report
            report['status'] = 'completed'
            for index, page in enumerate(reader.pages, 1):
                item = {'page': index, 'status': 'completed', 'text': '', 'text_sha256': None,
                        'char_start': None, 'char_end': None, 'diagnostics': []}
                warning_count = len(captured.items)
                try:
                    text = (page.extract_text(extraction_mode='plain') or '').strip()
                    if not text:
                        item['diagnostics'].append(diagnostic('empty_or_scanned_page',
                            'Page has no extractable text; OCR or preprocessing is required'))
                    elif '\x00' in text or '\ufffd' in text:
                        item['diagnostics'].append(diagnostic('unreliable_encoding',
                            'Page contains missing or invalid character mappings'))
                    elif total_bytes + len(text.encode()) + (2 if index > 1 else 0) > MAX_TEXT_BYTES:
                        item['diagnostics'].append(diagnostic('text_limit', 'Extracted text exceeds 2 MiB UTF-8'))
                    else:
                        item['text'] = text
                        item['text_sha256'] = hashlib.sha256(text.encode()).hexdigest()
                        total_bytes += len(text.encode()) + (2 if index > 1 else 0)
                    item['diagnostics'].extend(captured.items[warning_count:])
                except (pypdf.errors.PyPdfError, ValueError, TypeError, KeyError, Warning) as exc:
                    item['diagnostics'].append(diagnostic('page_extraction_failed', f'{type(exc).__name__}: {exc}'))
                if item['diagnostics']:
                    item['status'] = 'unsupported'
                    report['status'] = 'unsupported'
                report['pages'].append(item)
    except (pypdf.errors.PyPdfError, ValueError, TypeError, KeyError, Warning) as exc:
        report['status'] = 'unsupported'
        report['diagnostics'].append(diagnostic('malformed_or_limited_pdf', f'{type(exc).__name__}: {exc}'))
    if report['status'] == 'completed':
        report['text'] = '\n\n'.join(page['text'] for page in report['pages'])
        report['text_sha256'] = hashlib.sha256(report['text'].encode()).hexdigest()
        offset = 0
        for page in report['pages']:
            page['char_start'], page['char_end'] = offset, offset + len(page['text'])
            offset = page['char_end'] + 2
    elif report['pages']:
        report['diagnostics'].append(diagnostic('incomplete_extraction',
            'At least one page was not completely extracted; partial text is diagnostic only'))
    return report


if __name__ == '__main__':
    try:
        result = extract(Path(sys.argv[1]))
    except Exception as exc:
        result = {'status': 'error', 'diagnostics': [diagnostic('worker_error', f'{type(exc).__name__}: {exc}')]}
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))
