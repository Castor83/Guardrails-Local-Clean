"""Local entry point for scoped Codex hooks and explicit final-text prechecks."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
for stream in (sys.stdin, sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="strict")

from guardrails_local.codex_hook import main


if __name__ == "__main__":
    raise SystemExit(main())
