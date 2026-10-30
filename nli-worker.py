"""Fixed dedicated-runtime entry for the bounded native NLI worker."""

import argparse
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description="Lokaler CPU-/Offline-NLI-Worker")
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--response", required=True, type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    sys.path.insert(0, str(root / "src"))
    from guardrails_local.provenance_nli import worker_main
    return worker_main(root, args.request, args.response)


if __name__ == "__main__":
    raise SystemExit(main())
