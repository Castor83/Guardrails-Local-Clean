import contextlib
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from guardrails_local import cli


class QualityCLITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copytree(ROOT / 'work/profile-components', self.root / 'work/profile-components')
        self.input = self.root / 'request.json'
        self.input.write_text(json.dumps(dict(task='Antworte kurz.', answer='Viel zu lang',
            instructions=[], criteria=[], constraints=dict(max_chars=4))), encoding='utf-8')

    def invoke(self, *args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(cli, '_project_root', return_value=self.root):
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                try:
                    code = cli.main(['quality-check', '--input', str(self.input), '--json', *args])
                except SystemExit as exc:
                    code = exc.code
        text = stdout.getvalue()
        return code, json.loads(text) if text else {}

    def test_offline_cli_really_holds_a_host_violation_without_a_model(self):
        code, report = self.invoke('--offline')
        self.assertEqual(2, code)
        self.assertEqual('FAIL', report.get('final_status'))
        self.assertIsNone(report.get('released_text'))

    def test_offline_correction_cannot_start_a_model_as_a_side_effect(self):
        code, report = self.invoke('--offline', '--correct')
        self.assertEqual(3, code)
        self.assertEqual('ERROR', report.get('final_status'))

    def test_duplicate_request_keys_are_rejected_before_evaluation(self):
        self.input.write_text('{"task":"Original", "task":"Ersetzt", "answer":"a"}', encoding='utf-8')
        code, report = self.invoke('--offline')
        self.assertEqual(3, code)
        self.assertEqual('ERROR', report.get('final_status'))


if __name__ == '__main__':
    unittest.main()
