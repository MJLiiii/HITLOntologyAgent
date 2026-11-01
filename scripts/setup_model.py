"""Install the hash-pinned optional local model; never writes outside .runtime."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def verify_file(path, expected):
    with Path(path).open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual != expected:
        raise ValueError(f"SHA-256 mismatch for {Path(path).name}")


def download(url, destination, sha):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        verify_file(destination, sha)
        return
    temporary = destination.with_suffix(destination.suffix + ".partial")
    try:
        with urllib.request.urlopen(url, timeout=60) as response, temporary.open("wb") as output:
            shutil.copyfileobj(response, output, 1024 * 1024)
        verify_file(temporary, sha)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def setup():
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise SystemExit("This optional pinned runtime targets macOS arm64. Use a separately installed Ollama on other platforms.")
    lock = json.loads((ROOT / "infra/model.lock.json").read_text())
    runtime = ROOT / ".runtime"
    archive = runtime / "downloads/ollama-darwin.tgz"
    print("Downloading/verifying Ollama " + lock["runtime"]["version"], flush=True)
    download(lock["runtime"]["url"], archive, lock["runtime"]["sha256"])
    target = runtime / "ollama"
    target.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive) as package:
        package.extractall(target, filter="data")
    model = lock["model"]
    manifest = runtime / "models/manifests/registry.ollama.ai/library/qwen3/1.7b"
    print("Downloading/verifying model manifest", flush=True)
    download(model["manifest_url"], manifest, model["manifest_sha256"])
    specification = json.loads(manifest.read_text())
    for layer in [specification["config"], *specification["layers"]]:
        sha = layer["digest"].removeprefix("sha256:")
        print("Verifying model layer " + sha[:12], flush=True)
        destination = runtime / "models/blobs" / ("sha256-" + sha)
        download(model["blob_base_url"] + layer["digest"], destination, sha)
        if destination.stat().st_size != layer["size"]:
            raise ValueError("Model layer size mismatch")
    print("Pinned local runtime and model are ready. Run: make model-serve", flush=True)


def serve():
    candidates = [ROOT / ".runtime/ollama/bin/ollama", ROOT / ".runtime/ollama/ollama"]
    binary = next((p for p in candidates if p.is_file()), None)
    if not binary:
        raise SystemExit("Run make setup-model first")
    environment = {**os.environ, "OLLAMA_HOST": "127.0.0.1:11434", "OLLAMA_MODELS": str(ROOT / ".runtime/models"),
                   "OLLAMA_NO_CLOUD": "1", "OLLAMA_KEEP_ALIVE": "5m", "OLLAMA_MAX_LOADED_MODELS": "1"}
    os.execve(binary, [str(binary), "serve"], environment)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["setup", "serve"], default="setup", nargs="?")
    args = parser.parse_args()
    setup() if args.action == "setup" else serve()
