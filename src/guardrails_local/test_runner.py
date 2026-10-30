"""Structured cooperative unittest result; not an adversarial trust boundary."""
import argparse
import json
import os
from pathlib import Path
import unittest
import uuid


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start-dir', required=True)
    parser.add_argument('--result', required=True, type=Path)
    parser.add_argument('--invocation-id', required=True)
    args = parser.parse_args(argv)
    if len(args.invocation_id) != 32 or uuid.UUID(args.invocation_id).hex != args.invocation_id:
        raise ValueError('Canonical invocation identifier required.')
    suite = unittest.defaultTestLoader.discover(args.start_dir, pattern='test*.py')
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    skipped = len(result.skipped)
    report = dict(schema_version=1, completed=True, invocation_id=args.invocation_id,
                  tests_run=result.testsRun, test_count=result.testsRun - skipped,
                  failures=len(result.failures), errors=len(result.errors), skipped=skipped,
                  expected_failures=len(result.expectedFailures),
                  unexpected_successes=len(result.unexpectedSuccesses),
                  evidence_scope='cooperative-unit-tests', tamper_resistant=False)
    temporary = args.result.with_name('.' + args.result.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temporary.open('x', encoding='utf-8', newline='\n') as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, args.result)
    finally:
        temporary.unlink(missing_ok=True)
    return 0 if result.wasSuccessful() and result.testsRun > 0 else 3


if __name__ == '__main__':
    raise SystemExit(main())
