"""Offline integrity and extraction check for the frozen public DORA source packet.

Run with the repository's pinned Python environment. No downloads, model calls,
application state changes, or human decisions are performed.
"""
import hashlib
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

from pypdf import PdfReader


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def render(element):
    """Preserve words, list markers and table cells; normalize layout whitespace."""
    tag = element.tag.rsplit("}", 1)[-1]
    if tag in {"script", "style", "head"}:
        return ""
    if tag == "tr":
        cells = [" ".join(render(c).split()) for c in element
                 if c.tag.rsplit("}", 1)[-1] in {"td", "th"}]
        return " | ".join(cells) + "\n"
    text = element.text or ""
    for child in element:
        text += render(child) + (child.tail or "")
    if tag in {"p", "div", "li", "table", "br", "h1", "h2", "h3"}:
        text += "\n"
    return text


def normalized(element):
    lines = [re.sub(r"\s+", " ", line).strip() for line in render(element).splitlines()]
    return "\n".join(line for line in lines if line) + "\n"


def selected_text(source, selector):
    if selector["kind"] == "pdf_pages":
        reader = PdfReader(source)
        return "\n\n".join(reader.pages[n - 1].extract_text().strip()
                            for n in selector["pages"]) + "\n"
    root = ET.fromstring(source.read_bytes())
    nodes = {e.attrib["id"]: e for e in root.iter() if "id" in e.attrib}
    if selector["kind"] == "element":
        return normalized(nodes[selector["id"]])
    if selector["kind"] != "sibling_range":
        raise ValueError("Unknown selector kind")
    parent = nodes[selector["parent_id"]]
    children = list(parent)
    start = next(i for i, e in enumerate(children) if e.attrib.get("id") == selector["start_id"])
    end = next(i for i, e in enumerate(children) if e.attrib.get("id") == selector["end_id"])
    if end <= start:
        raise ValueError("Invalid source range")
    return "".join(normalized(e) for e in children[start:end])


def verify(root):
    manifest = json.loads((root / "manifest.json").read_text())
    documents = manifest["documents"]
    if len(documents) != 5 or any(d["classification"] != "public" for d in documents):
        raise ValueError("Expected five public source documents")
    source_files = {}
    for document in documents:
        for representation in document["representations"]:
            path = root / representation["path"]
            data = path.read_bytes()
            if sha256(data) != representation["sha256"] or len(data) != representation["bytes"]:
                raise ValueError(f"Source integrity mismatch: {path}")
            if path.suffix == ".pdf" and len(PdfReader(path).pages) != representation["pages"]:
                raise ValueError(f"PDF page count mismatch: {path}")
            source_files[representation["path"]] = (document["id"], representation["sha256"])
    extracts = manifest["extracts"]
    if len({e["id"] for e in extracts}) != len(extracts):
        raise ValueError("Duplicate extract IDs")
    for extract in extracts:
        path = root / extract["path"]
        if source_files[extract["source_path"]] != (extract["document_id"], extract["source_sha256"]):
            raise ValueError(f"Source lineage mismatch: {path}")
        data = path.read_bytes()
        if sha256(data) != extract["sha256"] or len(data) != extract["bytes"]:
            raise ValueError(f"Extract integrity mismatch: {path}")
        expected = selected_text(root / extract["source_path"], extract["selector"])
        if data.decode() != expected:
            raise ValueError(f"Extract differs from official source selection: {path}")
        if not expected.strip():
            raise ValueError(f"Empty extract: {path}")
    covered = {e["id"] for e in extracts}
    required = ({f"dora-art-{n}" for n in (2, 3, 28, 29, 30)}
                | {f"policy-art-{n}" for n in range(3, 11)}
                | {f"subcontracting-art-{n}" for n in range(3, 7)}
                | {f"register-{n}" for n in ("B_02.01", "B_02.02", "B_03.01", "B_03.02", "B_05.01", "B_05.02", "B_06.01")}
                | {"esma-qa-2646"})
    if not required <= covered:
        raise ValueError(f"Missing planned extracts: {sorted(required - covered)}")
    checksums = (root / "SHA256SUMS").read_text().splitlines()
    for line in checksums:
        expected, relative = line.split("  ", 1)
        if sha256((root / relative).read_bytes()) != expected:
            raise ValueError(f"Packet file changed: {relative}")
    print(f"PASS: {len(documents)} documents, {len(source_files)} official representations, "
          f"{len(extracts)} source-matched extracts, {len(checksums)} file hashes")


if __name__ == "__main__":
    verify(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent)
