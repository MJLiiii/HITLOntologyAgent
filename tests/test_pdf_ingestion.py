import hashlib
import io
import json

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject


def pdf_bytes(texts=('Payroll service has an owner.',), *, encrypted=False, broken_page=None, scanned=False):
    writer = PdfWriter()
    font = writer._add_object(DictionaryObject({NameObject('/Type'): NameObject('/Font'),
        NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica'),
        NameObject('/Encoding'): NameObject('/WinAnsiEncoding')}))
    for number, text in enumerate(texts, 1):
        page = writer.add_blank_page(width=612, height=792)
        if text is not None:
            page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'):
                DictionaryObject({NameObject('/F1'): font})})
            stream = DecodedStreamObject()
            escaped = text.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
            stream.set_data(b'BT /F1 12 Tf (unterminated' if number == broken_page else
                ('BT /F1 12 Tf 40 700 Td (' + escaped + ') Tj ET').encode('latin-1'))
            page[NameObject('/Contents')] = writer._add_object(stream)
        elif scanned:
            from pypdf.generic import NumberObject
            image = DecodedStreamObject()
            image.set_data(b'\xff\xff\xff')
            image.update({NameObject('/Type'): NameObject('/XObject'), NameObject('/Subtype'): NameObject('/Image'),
                          NameObject('/Width'): NumberObject(1), NameObject('/Height'): NumberObject(1),
                          NameObject('/ColorSpace'): NameObject('/DeviceRGB'), NameObject('/BitsPerComponent'): NumberObject(8)})
            page[NameObject('/Resources')] = DictionaryObject({NameObject('/XObject'):
                DictionaryObject({NameObject('/Im0'): writer._add_object(image)})})
            content = DecodedStreamObject()
            content.set_data(b'q 600 0 0 700 0 0 cm /Im0 Do Q')
            page[NameObject('/Contents')] = writer._add_object(content)
    if encrypted:
        writer.encrypt('secret')
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def test_pdf_extracts_every_page_and_preserves_exact_source_hash_and_offsets():
    from oe_studio.pdf_ingestion import extract_pdf
    source = pdf_bytes(('Payroll service has an owner.', 'Operations team owns Payroll.'))
    report = extract_pdf(source)
    assert report['status'] == 'completed', report
    assert report['source_sha256'] == hashlib.sha256(source).hexdigest()
    assert report['source_bytes'] == len(source)
    assert report['page_count'] == 2
    assert report['text'] == 'Payroll service has an owner.\n\nOperations team owns Payroll.'
    assert report['text_sha256'] == hashlib.sha256(report['text'].encode()).hexdigest()
    for number, page in enumerate(report['pages'], 1):
        assert page['page'] == number and page['status'] == 'completed'
        assert report['text'][page['char_start']:page['char_end']] == page['text']
        assert page['text_sha256'] == hashlib.sha256(page['text'].encode()).hexdigest()
    assert report['engine']['version'] == '6.21.4'
    assert report['engine']['isolation']['network'] == 'kernel-denied'
    assert report['engine']['limits']['cpu_seconds'] == 10
    assert report['engine']['limits']['rss_bytes'] == 512 * 1024 * 1024


@pytest.mark.parametrize('source', [b'', b'not a PDF', b'%PDF-1.7\nbroken\n%%EOF', pdf_bytes(())])
def test_empty_or_malformed_pdf_never_completes(source):
    from oe_studio.pdf_ingestion import extract_pdf
    report = extract_pdf(source)
    assert report['status'] in {'unsupported', 'error'}, report
    assert report['text'] == ''
    assert report['diagnostics']


def test_encrypted_pdf_is_not_accepted_even_if_a_text_layer_exists():
    from oe_studio.pdf_ingestion import extract_pdf
    report = extract_pdf(pdf_bytes(encrypted=True))
    assert report['status'] == 'unsupported', report
    assert any(item['code'] == 'encrypted_pdf' for item in report['diagnostics'])


def test_partial_extraction_is_retained_but_never_ingestible():
    from oe_studio.pdf_ingestion import extract_pdf
    report = extract_pdf(pdf_bytes(('Readable first page.', None)))
    assert report['status'] == 'unsupported', report
    assert report['text'] == '' and report['text_sha256'] is None
    assert report['pages'][0]['text'] == 'Readable first page.'
    assert report['pages'][1]['status'] == 'unsupported'
    assert report['pages'][1]['diagnostics'][0]['code'] == 'empty_or_scanned_page'


def test_page_count_and_upload_size_limits_are_not_truncation():
    from oe_studio.pdf_ingestion import MAX_INPUT_BYTES, extract_pdf
    assert extract_pdf(b'%PDF-' + b' ' * MAX_INPUT_BYTES)['status'] == 'unsupported'
    report = extract_pdf(pdf_bytes(['Page'] * 201))
    assert report['status'] == 'unsupported', report
    assert report['text'] == ''


def test_extracted_text_limit_never_returns_a_partial_success():
    from oe_studio.pdf_ingestion import MAX_TEXT_BYTES, extract_pdf
    report = extract_pdf(pdf_bytes(('x' * (MAX_TEXT_BYTES + 1),)))
    assert report['status'] == 'unsupported', report
    assert report['text'] == ''
    assert report['diagnostics']
    assert report['pages'][0]['diagnostics'][0]['code'] == 'text_limit'


def test_pdf_timeout_is_not_an_extraction_result(monkeypatch):
    import oe_studio.pdf_ingestion as ingestion
    monkeypatch.setattr(ingestion, 'WALL_SECONDS', 0.001)
    report = ingestion.extract_pdf(pdf_bytes())
    assert report['status'] == 'timeout', report
    assert report['text'] == ''


def test_pdf_cpu_signal_through_sandbox_is_a_timeout(monkeypatch, tmp_path):
    import oe_studio.pdf_ingestion as ingestion
    worker = tmp_path / 'cpu_timeout.py'
    worker.write_text('import os, signal; os.kill(os.getpid(), signal.SIGXCPU)')
    monkeypatch.setattr(ingestion, 'WORKER', worker)
    report = ingestion.extract_pdf(pdf_bytes())
    assert report['status'] == 'timeout', report
    assert report['diagnostics'][0]['code'] == 'cpu_timeout'
    assert report['text'] == ''


def test_pdf_rss_watchdog_terminates_worker(monkeypatch):
    import oe_studio.pdf_ingestion as ingestion
    monkeypatch.setattr(ingestion, 'MAX_RSS_BYTES', 1)
    report = ingestion.extract_pdf(pdf_bytes())
    assert report['status'] == 'error', report
    assert any(item['code'] == 'memory_limit' for item in report['diagnostics'])


def test_pdf_rss_limit_includes_descendant_workers(monkeypatch, tmp_path):
    """A lightweight launcher must not hide the actual parser's allocation."""
    import sys
    import oe_studio.pdf_ingestion as ingestion
    worker = tmp_path / 'launcher.py'
    worker.write_text('''import subprocess, sys, time
child = subprocess.Popen([sys.executable, '-c',
    'import time; allocation = bytearray(80 * 1024 * 1024); time.sleep(1)'])
try:
    child.wait()
finally:
    child.kill()
print('{}')
''')
    # Exercise real process accounting with only the OS sandbox boundary replaced.
    monkeypatch.setattr(ingestion, 'isolated_command', lambda *args, **kwargs:
                        ([sys.executable, str(worker)], {'mode': 'controlled-test'}))
    monkeypatch.setattr(ingestion, 'MAX_RSS_BYTES', 48 * 1024 * 1024)
    report = ingestion.extract_pdf(pdf_bytes())
    assert report['status'] == 'error', report
    assert any(item['code'] == 'memory_limit' for item in report['diagnostics']), report


def test_pdf_report_with_wrong_input_identity_is_rejected(monkeypatch, tmp_path):
    import oe_studio.pdf_ingestion as ingestion
    source = pdf_bytes()
    valid = ingestion.extract_pdf(source)
    assert valid['status'] == 'completed', valid
    valid['source_sha256'] = '0' * 64
    worker = tmp_path / 'wrong_report.py'
    worker.write_text('print(' + repr(json.dumps(valid)) + ')')
    monkeypatch.setattr(ingestion, 'WORKER', worker)
    report = ingestion.extract_pdf(source)
    assert report['status'] == 'error', report
    assert report['text'] == ''


def test_missing_pdf_worker_is_an_error(monkeypatch, tmp_path):
    import oe_studio.pdf_ingestion as ingestion
    monkeypatch.setattr(ingestion, 'WORKER', tmp_path / 'absent.py')
    report = ingestion.extract_pdf(pdf_bytes())
    assert report['status'] == 'error', report


def test_image_only_page_is_marked_as_needing_preprocessing():
    from oe_studio.pdf_ingestion import extract_pdf
    report = extract_pdf(pdf_bytes((None,), scanned=True))
    assert report['status'] == 'unsupported', report
    assert report['pages'][0]['diagnostics'][0]['code'] == 'empty_or_scanned_page'


def test_broken_later_page_cannot_silently_disappear():
    from oe_studio.pdf_ingestion import extract_pdf
    report = extract_pdf(pdf_bytes(('Readable.', 'Broken.'), broken_page=2))
    assert report['status'] == 'unsupported', report
    assert len(report['pages']) == 2
    assert report['pages'][1]['diagnostics'][0]['code'] == 'page_extraction_failed'
    assert report['text'] == ''


def test_unicode_offsets_are_characters_and_hashes_cover_utf8_bytes():
    from oe_studio.pdf_ingestion import extract_pdf
    report = extract_pdf(pdf_bytes(('Équipe opérations.', 'Second page.')))
    assert report['status'] == 'completed', report
    assert report['text'].startswith('Équipe opérations.')
    assert report['pages'][1]['char_start'] == len('Équipe opérations.') + 2
    assert report['text_sha256'] == hashlib.sha256(report['text'].encode('utf-8')).hexdigest()


def test_worker_verifies_original_pdf_bytes_against_manifest(tmp_path):
    import subprocess
    import sys
    from oe_studio.engine_isolation import isolated_command, python_runtime_paths
    from oe_studio.pdf_ingestion import WORKER
    source = pdf_bytes()
    (tmp_path / 'source.pdf').write_bytes(source)
    request = tmp_path / 'manifest.json'
    request.write_text(json.dumps({'source_bytes': len(source), 'source_sha256': '0' * 64}))
    command, _ = isolated_command([sys.executable, '-I', str(WORKER), str(request)],
                                 workdir=tmp_path, readable=[WORKER, *python_runtime_paths(sys.executable)])
    process = subprocess.run(command, capture_output=True, text=True, timeout=15)
    assert process.returncode == 0, process.stderr
    report = json.loads(process.stdout)
    assert report['status'] == 'error', report
    assert report['diagnostics'][0]['code'] == 'source_integrity'
