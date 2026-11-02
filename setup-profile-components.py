"""Fixed two-component setup; no pip, postinstall, service or model operations."""
import argparse
import json
from pathlib import Path
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Verify local component hashes without network.')
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parent
    sys.path.insert(0, str(root / 'src'))
    from guardrails_local.conversation_profiles import setup_components, verify_components
    try:
        report = (dict(status='CHECKED', components=verify_components(root), model_downloaded=False,
                       package_installed=False, postinstall_executed=False)
                  if args.check else setup_components(root, download=True))
        print(json.dumps(report, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps(dict(status='ERROR', error=type(exc).__name__ + ': ' + str(exc)), ensure_ascii=False))
        return 3


if __name__ == '__main__':
    raise SystemExit(main())
