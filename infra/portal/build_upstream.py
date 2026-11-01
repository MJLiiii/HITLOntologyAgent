#!/usr/bin/env python3
"""Download hash-checked upstream pins and build without changing source or locks."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile
from urllib.request import urlopen

HERE = Path(__file__).resolve().parent
UPSTREAM = HERE / "upstream"
RUNTIME = HERE / "runtime"
PINS = json.loads((HERE / "source-pins.json").read_text())
UPSTREAM.mkdir(exist_ok=True)
RUNTIME.mkdir(exist_ok=True)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fetch(name):
    pin = PINS[name]
    repo = pin["repository"].split("/")[1]
    archive = RUNTIME / f"{repo}-{pin['commit']}.tar.gz"
    if not archive.exists():
        with urlopen(f"https://codeload.github.com/{pin['repository']}/tar.gz/{pin['commit']}") as source:
            archive.write_bytes(source.read())
    if digest(archive) != pin["archive_sha256"]:
        raise RuntimeError(f"{name}: archive checksum mismatch")
    checkout = UPSTREAM / f"{repo}-{pin['commit']}"
    with tarfile.open(archive) as tar:
        if not checkout.exists():
            tar.extractall(UPSTREAM, filter="data")
        changed = [entry.name for entry in tar if entry.isfile() and (
            not (UPSTREAM / entry.name).exists() or
            tar.extractfile(entry).read() != (UPSTREAM / entry.name).read_bytes())]
    if changed:
        raise RuntimeError(f"{name}: upstream source changed: {changed}")
    if "lock_sha256" in pin and digest(checkout / "package-lock.json") != pin["lock_sha256"]:
        raise RuntimeError(f"{name}: package lock checksum mismatch")
    return checkout


def run(checkout, command, label, environment=None):
    print(f"{label}: {' '.join(command)}", flush=True)
    result = subprocess.run(command, cwd=checkout, env=environment, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (RUNTIME / f"{label}.log").write_text(result.stdout)
    print(result.stdout, flush=True)
    result.check_returncode()


ui, template = fetch("ui"), fetch("template")
fetch("backend")
for name, checkout in (("ui", ui), ("template", template)):
    run(checkout, ["npm", "ci", "--ignore-scripts", "--no-audit", "--no-fund"], f"{name}-install")
run(ui, ["npm", "run", "build"], "ui-build")
# The template's upstream package omits tsc. Supply the exact compiler from the
# UI's verified lock as a build tool; do not edit its package or source.
environment = os.environ | {"PATH": f"{ui / 'node_modules/.bin'}{os.pathsep}{os.environ['PATH']}"}
run(template, ["npm", "run", "build"], "template-build", environment)
for name in PINS:
    fetch(name)  # Verify every original source file again after the builds.
print("Pinned sources and locks unchanged; real portal and template builds passed.")
