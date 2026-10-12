"""Cross-platform task runner mirroring the Makefile (for machines without `make`).

Usage: python tasks.py <dev|test|lint|demo|bench|seed|api|web>
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"


def _python() -> str:
    """Prefer the repo venv so `python tasks.py` works from any shell."""
    for candidate in (ROOT / ".venv" / "Scripts" / "python.exe", ROOT / ".venv" / "bin" / "python"):
        if candidate.exists():
            return str(candidate)
    return sys.executable


def _npm() -> str:
    return shutil.which("npm") or "npm"


def run(cmd: list[str], cwd: Path = ROOT) -> int:
    print("$", " ".join(cmd))
    return subprocess.call(cmd, cwd=cwd)


def seed() -> int:
    return run([_python(), "-m", "mocks.seed"])


def test() -> int:
    return run([_python(), "-m", "pytest"])


def lint() -> int:
    return run([_python(), "-m", "ruff", "check", "."]) or run(
        [_python(), "-m", "ruff", "format", "--check", "."]
    )


def bench() -> int:
    return run([_python(), "-m", "bench.runner"])


def api() -> int:
    return run([_python(), "-m", "uvicorn", "kavach.api.main:app", "--port", "8000", "--reload"])


def web() -> int:
    if not (WEB / "node_modules").exists():
        run([_npm(), "install"], cwd=WEB)
    return run([_npm(), "run", "dev"], cwd=WEB)


def dev(open_browser: bool = False) -> int:
    """Start API and dashboard together; Ctrl+C stops both."""
    if not (WEB / "node_modules").exists():
        run([_npm(), "install"], cwd=WEB)
    env = {**os.environ, "LLM_PROVIDER": os.environ.get("LLM_PROVIDER", "scripted")}
    procs = [
        subprocess.Popen(
            [_python(), "-m", "uvicorn", "kavach.api.main:app", "--port", "8000"], cwd=ROOT, env=env
        ),
        subprocess.Popen([_npm(), "run", "dev"], cwd=WEB, env=env, shell=os.name == "nt"),
    ]
    try:
        if open_browser:
            time.sleep(6)
            webbrowser.open("http://localhost:3000")
        for p in procs:
            p.wait()
    except KeyboardInterrupt:
        pass
    finally:
        for p in procs:
            p.terminate()
    return 0


def demo() -> int:
    """Seed deterministic data, then start everything in offline scripted mode."""
    os.environ["LLM_PROVIDER"] = "scripted"
    return seed() or dev(open_browser=True)


TASKS = {
    "dev": dev,
    "test": test,
    "lint": lint,
    "demo": demo,
    "bench": bench,
    "seed": seed,
    "api": api,
    "web": web,
}

if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else ""
    if name not in TASKS:
        print(__doc__)
        sys.exit(2)
    sys.exit(TASKS[name]())
