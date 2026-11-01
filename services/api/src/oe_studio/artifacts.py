import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5


def canonical_json(value) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()


def digest(value) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value)).hexdigest()


class ArtifactStore:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, content: bytes, media_type: str) -> dict:
        sha = hashlib.sha256(content).hexdigest()
        ref = {"id": str(uuid5(NAMESPACE_URL, "urn:oe-artifact:" + sha + ":" + media_type)),
               "sha256": sha, "byte_length": len(content), "media_type": media_type, "schema_version": 1}
        path = self.root / sha
        if path.exists():
            self.get_verified(ref)
            return ref
        fd, name = tempfile.mkstemp(dir=self.root)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, path)
        finally:
            Path(name).unlink(missing_ok=True)
        return ref

    def get_verified(self, ref: dict) -> bytes:
        sha = ref.get("sha256", "")
        if not re.fullmatch(r"[a-f0-9]{64}", sha):
            raise ValueError("Invalid artifact identifier")
        content = (self.root / sha).read_bytes()
        if hashlib.sha256(content).hexdigest() != sha or len(content) != ref["byte_length"]:
            raise ValueError("Artifact integrity mismatch")
        return content
