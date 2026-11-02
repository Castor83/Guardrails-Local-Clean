"""Fixed entry point for the explicitly requested local quality worker."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from guardrails_local.quality_evaluation import worker_main


if __name__ == "__main__":
    raise SystemExit(worker_main())
