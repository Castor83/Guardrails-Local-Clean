"""Dedicated, explicitly dispatched evaluation-worker entry point."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from guardrails_local.deepeval_adapter import worker_main


if __name__ == "__main__":
    raise SystemExit(worker_main())
