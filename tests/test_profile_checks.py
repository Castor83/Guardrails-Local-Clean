"""Profile entry-point boundaries; explicit sources alone may invoke NLI."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from guardrails_local import cli
try:
    from guardrails_local.profile_checks import check_answer
except ImportError:
    check_answer = None


class ProfileEntryTests(unittest.TestCase):
    def test_plain_conversation_does_not_invoke_any_model_or_require_evidence(self):
        self.assertIsNotNone(check_answer, 'Integrated conversation profile entry point missing')
        with patch('guardrails_local.provenance_nli.check_nli', side_effect=AssertionError('No source request')):
            result = check_answer(ROOT, 'hallo', 'Hallo!')
        self.assertEqual('conversation', result['profile'])
        self.assertEqual('SKIPPED', result['status'])
        self.assertIsNone(result['released_text'])

    def test_a_source_profile_without_a_file_does_not_fake_an_inference(self):
        self.assertIsNotNone(check_answer, 'Integrated profile entry point missing')
        with patch('guardrails_local.provenance_nli.check_nli', side_effect=AssertionError('Missing source binding')):
            result = check_answer(ROOT, 'Prüfe die Quelle.', 'Berlin ist die Hauptstadt Deutschlands.')
        self.assertEqual('source', result['profile'])
        self.assertEqual('UNVERIFIED', result['status'])
        self.assertFalse(result['semantic_verified'])

    def test_an_explicit_source_for_another_profile_is_rejected_before_inference(self):
        self.assertIsNotNone(check_answer, 'Integrated profile entry point missing')
        with patch('guardrails_local.provenance_nli.check_nli', side_effect=AssertionError('Wrong profile')):
            result = check_answer(ROOT, 'hallo', 'Hallo!', source_file=ROOT / 'unrequested-source')
        self.assertEqual('ERROR', result['status'])

    def test_explicit_source_checks_original_answer_once_and_preserves_contradiction(self):
        self.assertIsNotNone(check_answer, 'Integrated profile entry point missing')
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'source.txt'
            source.write_bytes('Berlin ist die Hauptstadt Deutschlands.'.encode('utf-8'))
            answer = 'Bonn ist die Hauptstadt Deutschlands.'
            calls = []
            def native(root, value, source_file, **kwargs):
                calls.append((root, value, source_file))
                return dict(status='FAIL', reason='Bound native contradiction',
                    native_validator=True, truncation=False, label='contradiction')
            with patch('guardrails_local.provenance_nli.check_nli', side_effect=native):
                result = check_answer(ROOT, 'Prüfe die Quelle.', answer, source_file=source)
        self.assertEqual([(ROOT, answer, source)], calls)
        self.assertEqual('FAIL', result['status'])
        self.assertIsNone(result['released_text'])

    def test_cli_profile_check_is_available_without_chat_registration(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base / 'task.txt').write_text('hallo', encoding='utf-8')
            (base / 'answer.txt').write_text('Hallo!', encoding='utf-8')
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = cli.main(['profile-check', '--input', str(base / 'answer.txt'),
                    '--task-file', str(base / 'task.txt'), '--json'])
        self.assertEqual(0, code)
        report = json.loads(output.getvalue())
        self.assertEqual('SKIPPED', report['final_status'])
        self.assertIsNone(report['released_text'])


if __name__ == '__main__':
    unittest.main()
