#!/usr/bin/env python3
"""Create isolated local smoke secrets without printing them or changing host config."""
from pathlib import Path
import secrets

runtime = Path(__file__).resolve().parent / "runtime"
runtime.mkdir(exist_ok=True)
env_file = runtime / ".env"
if not env_file.exists():
    env_file.write_text(
        f"OE_PORTAL_BUS_PASSWORD={secrets.token_urlsafe(32)}\n"
        f"OE_PORTAL_BOOTSTRAP_TOKEN=tg_{secrets.token_urlsafe(40)}\n"
    )
    env_file.chmod(0o600)
print(f"Local-only smoke environment ready: {env_file}")
