import os
from pathlib import Path
import subprocess


class GitStore:
    def __init__(self, root: Path):
        self.root = root
        if not root.exists():
            subprocess.run(["git", "init", "--bare", str(root)], check=True, capture_output=True)

    def run(self, *args, content=None):
        env = {**os.environ, "GIT_AUTHOR_NAME": "Ontology Studio", "GIT_AUTHOR_EMAIL": "studio@localhost",
               "GIT_COMMITTER_NAME": "Ontology Studio", "GIT_COMMITTER_EMAIL": "studio@localhost"}
        return subprocess.run(["git", "--git-dir", str(self.root), *args], input=content,
                              capture_output=True, check=True, env=env, timeout=20).stdout.decode().strip()

    def head(self, project_id):
        try:
            return self.run("rev-parse", "--verify", f"refs/heads/{project_id}-approved")
        except subprocess.CalledProcessError:
            return None

    def commit(self, files: dict[str, bytes], parent: str | None, message: str):
        entries = []
        for name, content in sorted(files.items()):
            if "/" in name or "\n" in name or "\t" in name:
                raise ValueError("Invalid release file")
            sha = self.run("hash-object", "-w", "--stdin", content=content)
            entries.append(f"100644 blob {sha}\t{name}\n")
        tree = self.run("mktree", content="".join(entries).encode())
        args = ["commit-tree", tree]
        if parent:
            args.extend(["-p", parent])
        return self.run(*args, content=message.encode())

    def advance(self, project_id, new, old):
        self.run("update-ref", f"refs/heads/{project_id}-approved", new, old or "0" * 40)
