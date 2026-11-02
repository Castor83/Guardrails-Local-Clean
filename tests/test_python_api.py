import importlib
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
FACTS = {'software_evidence': {
    'guardrails_ai_version': '0.11.0',
    'guard_from_string_available': False,
    'guard_for_string_available': True,
}}


class PythonApiTests(unittest.TestCase):
    def check(self, text, facts=None):
        spec = importlib.util.find_spec('guardrails_local.python_api')
        self.assertIsNotNone(spec, 'Statische Python-API-Prüfung fehlt.')
        module = importlib.import_module('guardrails_local.python_api')
        return module.check_python_apis(text, FACTS if facts is None else facts)

    def test_real_user_text_has_evidenced_missing_api(self):
        text = (ROOT / 'examples' / 'chatgpt-original.txt').read_text(encoding='utf-8')
        findings = self.check(text)
        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(finding['requirement_id'], 'EVIDENCE')
        self.assertEqual(finding['severity'], 'error')
        self.assertIn('Guard.from_string', finding['description'])
        self.assertIn('gd.Guard.from_string(', finding['evidence'])
        self.assertIn('0.11.0', finding['evidence'])
        self.assertIn('Guard.for_string', finding['correction'])

    def test_corrected_for_string_has_no_missing_api_finding(self):
        text = (ROOT / 'examples' / 'chatgpt-original.txt').read_text(encoding='utf-8')
        self.assertEqual(self.check(text.replace('Guard.from_string(', 'Guard.for_string(')), [])

    def test_prose_comments_and_strings_are_not_calls(self):
        examples = [
            'Guard.from_string ist nicht vorhanden.',
            'import guardrails as gd\n# gd.Guard.from_string()\n',
            'import guardrails as gd\nexample = "gd.Guard.from_string()"\n',
        ]
        for text in examples:
            with self.subTest(text=text):
                self.assertEqual(self.check(text), [])

    def test_fenced_direct_guard_alias_is_recognized(self):
        findings = self.check('Beispiel:\n```python\nfrom guardrails import Guard as G\ng = G.from_string(validators=[])\n```\nEnde.')
        self.assertEqual(len(findings), 1)
        self.assertIn('Zeile 4', findings[0]['evidence'])

    def test_direct_guard_import_without_alias_is_recognized(self):
        self.assertEqual(len(self.check('from guardrails import Guard\nGuard.from_string([])\n')), 1)

    def test_overwritten_or_reimported_alias_is_not_trusted(self):
        examples = [
            'import guardrails as gd\ngd = replacement\ngd.Guard.from_string([])',
            'import guardrails as gd\nimport replacement as gd\ngd.Guard.from_string([])',
            'from guardrails import Guard\nfrom replacement import Guard\nGuard.from_string([])',
            'from guardrails import Guard as G\nG.from_string = replacement\nG.from_string([])',
            'import guardrails as gd\ngd.Guard = replacement\ngd.Guard.from_string([])',
            'from guardrails import Guard\nfrom replacement import *\nGuard.from_string([])',
            'import guardrails as gd\nvalue = (gd := replacement)\ngd.Guard.from_string([])',
            'import guardrails as gd\nvalue: mutate_alias()\ngd.Guard.from_string([])',
        ]
        for text in examples:
            with self.subTest(text=text):
                self.assertEqual(self.check(text), [])

    def test_parseable_python_prefix_is_not_silently_discarded(self):
        text = ('import sys\nsys.modules["guardrails"] = replacement\n'
                'from guardrails import Guard\nGuard.from_string([])')
        self.assertEqual(self.check(text), [])

    def test_nested_or_ambiguous_scopes_are_not_verified(self):
        examples = [
            'import guardrails as gd\ndef example():\n    gd.Guard.from_string([])',
            'import guardrails as gd\nif condition:\n    gd = replacement\ngd.Guard.from_string([])',
            'import guardrails as gd\nwrapper(gd.Guard.from_string([]))',
            'import guardrails as gd\nunknown_call()\ngd.Guard.from_string([])',
        ]
        for text in examples:
            with self.subTest(text=text):
                self.assertEqual(self.check(text), [])

    def test_missing_or_inapplicable_facts_do_not_invent_violation(self):
        text = 'import guardrails as gd\ngd.Guard.from_string([])'
        for facts in ({}, {'software_evidence': {}},
                      {'software_evidence': {'guardrails_ai_version': '0.11.0'}},
                      {'software_evidence': {'guardrails_ai_version': '0.11.0', 'guard_from_string_available': True}},
                      {'software_evidence': {'guardrails_ai_version': 'other', 'guard_from_string_available': False}}):
            with self.subTest(facts=facts):
                self.assertEqual(self.check(text, facts), [])

    def test_invalid_or_unclosed_blocks_do_not_invent_violation(self):
        examples = [
            'import guardrails as gd\ngd.Guard.from_string(',
            '```python\nimport guardrails as gd\ngd.Guard.from_string([])',
            '```text\nimport guardrails as gd\ngd.Guard.from_string([])\n```',
            '```python\nimport guardrails as gd\ngd.Guard.from_string([])\n```\n```python\npass\n```',
        ]
        for text in examples:
            with self.subTest(text=text):
                self.assertEqual(self.check(text), [])

    def test_user_imports_calls_and_malicious_text_are_never_executed(self):
        text = ('import guardrails as gd\ngd.Guard.from_string([])\n'
                'import os\nos.system("must never run")\nraise AssertionError("executed")\n')
        with patch('os.system', side_effect=AssertionError('Benutzertext ausgeführt')):
            self.assertEqual(len(self.check(text)), 1)


if __name__ == '__main__':
    unittest.main()
