"""Install or run the fixed local Promptfoo regression harness."""
import argparse
import json
from pathlib import Path
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install', action='store_true', help='Explicitly install the locked project-local npm runtime.')
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parent
    sys.path.insert(0, str(root / 'src'))
    from guardrails_local.promptfoo_runner import install_runtime, run_regressions
    try:
        report = install_runtime(root) if args.install else run_regressions(root)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report['status'] in {'PASS', 'INSTALLED'} else 3
    except Exception as exc:
        print(json.dumps(dict(status='ERROR', error=type(exc).__name__ + ': ' + str(exc)), ensure_ascii=False))
        return 3


if __name__ == '__main__':
    raise SystemExit(main())
