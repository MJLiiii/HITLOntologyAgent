# PDF text extraction contract

`oe_studio.pdf_ingestion.extract_pdf(content: bytes)` runs a separate worker using pinned **pypdf 6.21.4**. `pyproject.toml` and `uv.lock` pin the official PyPI distribution and its hashes. The release is BSD-3-Clause; the [official package record](https://pypi.org/project/pypdf/6.21.4/) identifies the source and release artifacts. No Poppler/Homebrew executable, OCR service, optional cryptography package or runtime download is required.

The adapter returns `id`, `status` (`completed`, `unsupported`, `error`, `timeout`), `source_sha256`, `source_bytes`, `page_count`, `pages`, `text`, `text_sha256`, `diagnostics` and `engine`. A page record includes one-based `page`, `status`, `text`, `text_sha256`, `char_start`, `char_end` and structured `diagnostics` (`code`, `message`).

Only a `completed` report may become an ingestible corpus text artifact. It contains every page, each with nonempty extracted text and no parser warnings/errors. Text is stripped at each page boundary and joined by two newline characters. Page offsets are Python Unicode character offsets into that exact joined text; hashes cover UTF-8 bytes. This is extracted text, not a claim that the original PDF's visual order or semantics have been verified. [pypdf's extraction documentation](https://pypdf.readthedocs.io/en/6.21.4/user/extract-text.html) describes text-layer and layout limitations.

Any empty/image-only page, malformed later page, unsupported encoding, warning, resource failure or encryption prevents completion. Partially extracted page text remains in diagnostic page records, while top-level `text` is empty, `text_sha256` is null and page offsets are null. The workflow must persist that report as incomplete and prevent corpus freezing; it must not discard the diagnostics or silently ingest only the successful pages. Scanned documents need separately reviewed OCR/preprocessing. Encrypted documents are rejected without attempting supplied passwords. Active PDF scripts/actions are never executed by this extractor.

## Integrity and limits

The API-facing adapter accepts immutable bytes and rejects a missing `%PDF-` header, empty input or more than **20 MiB**. It writes only a private run directory and passes an original-byte SHA-256/length manifest. The worker verifies both before parsing; the parent verifies the source file again after extraction and validates the returned source identity, engine version, complete page count, page hashes, concatenated text hash and offsets. A forged success report cannot become an ingestion result.

| Limit | Enforcement |
|---|---|
| 200 pages | Strict page-tree parsing plus explicit page-count check; no truncation |
| 2 MiB extracted UTF-8 text | Cumulative text bytes, including page separators; over-limit extraction is unsupported |
| 15 seconds wall time | Parent watchdog terminates the whole worker process group |
| 10 seconds CPU | POSIX `RLIMIT_CPU`, 10-second soft and 11-second hard limits |
| 512 MiB resident memory | Parent samples the child via macOS `/bin/ps` at approximately 50 ms intervals and terminates an over-limit process; this permits transient allocation between samples |
| Address space | `RLIMIT_AS` attempted; macOS 27.2 rejected it, recorded explicitly in `engine.limits`; no claim of a verified instantaneous address-space cap |
| 8 MiB report/worker file | Worker `RLIMIT_FSIZE` plus parent output-size checks |
| Expanded content streams | Pinned pypdf configuration: 8 MiB common decompressor outputs, 32 MiB accumulated stream decoding, 1 million content parsing operations; other page-tree bounds recorded |

The worker uses the same fail-closed macOS Seatbelt launcher and file/network profile as Jena/OntoCheck. Its read roots are the Python runtime/environment, the worker script and its run directory. Writes stay in the run directory; no project state or home credentials are allowed. A supplementary Python audit hook denies network operations and subprocess creation. It is not the kernel boundary. See `integration-spike.md` for the verified OS tests, deprecated-launcher limitation and unsupported Linux deployment status. Failure to sample a still-running worker's memory is an error, not permission to run unbounded.

## Verification

Run from a normal macOS operator shell, outside another sandbox:

```sh
uv sync --frozen
.venv/bin/python -m pytest tests/test_pdf_ingestion.py -q
```

On 1 November 2026, **17 tests passed in 2.23 seconds** using real confined workers. Fixtures cover two-page text/hash/offset integrity, Unicode character versus byte accounting, malformed/empty PDFs, encrypted PDFs, an image-only page, a malformed later page, incomplete extraction, 201 pages, oversized uploads, exact extracted-text limit rejection, wall timeout, resident-memory termination, original input manifest mismatch, forged returned identity and a missing worker. The fixtures are generated as small PDFs through the pinned library; no silently skipped engine or external dependency substitutes for execution.
