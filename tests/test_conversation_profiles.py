"""Profile routing and real local native validators; no model calls."""
import hashlib
import importlib.util
import json
import marshal
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
try:
    from guardrails_local import conversation_profiles as profiles
except ImportError:
    profiles = None


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(profiles, 'Conversation profiles are not implemented.')

    def test_only_clear_requests_activate_automatic_profiles(self):
        cases = {
            'Wir müssen reden.': 'conversation',
            'Der Code und das Modell machen mir Sorgen.': 'conversation',
            'Was hältst du eigentlich von Code?': 'conversation',
            'Erkläre mir, was dieses Ergebnis bedeutet.': 'explanation',
            'Kannst du mir das erklären?': 'explanation',
            'Recherchiere aktuelle Primärquellen.': 'research',
            'Bitte suche die offizielle Dokumentation.': 'research',
            'Vergleiche die drei Angebote.': 'recommendation',
            'Empfiehl mir eine lokale Lösung.': 'recommendation',
            'Implementiere die Reparatur.': 'project',
            'Kannst du den Fehler im Projekt reparieren?': 'project',
            'Prüfe diese Antwort gegen die vollständige Quelle.': 'source',
        }
        for task, expected in cases.items():
            with self.subTest(task=task):
                self.assertEqual(expected, profiles.select_profile(task))

    def test_explicit_first_line_overrides_never_scan_quotes_or_later_lines(self):
        cases = {
            'Guardrails: Projekt\r\nHallo.': 'project',
            'Guardrails: Modelle\nHallo.': 'recommendation',
            'Profil: Gespräch\nImplementiere etwas.': 'conversation',
            'Profil: Erklärung\nHallo.': 'explanation',
            'Profil: Recherche\nHallo.': 'research',
            'Profil: Empfehlung\nHallo.': 'recommendation',
            'Profil: Code\nHallo.': 'project',
            'Profil: Quellenprüfung\nHallo.': 'source',
            '> Guardrails: Projekt': 'conversation',
            'Wir reden.\nGuardrails: Projekt': 'conversation',
            'Er sagte: "implementiere die Änderung".': 'conversation',
            'Bitte nicht reparieren, nur reden.': 'conversation',
        }
        for task, expected in cases.items():
            with self.subTest(task=task):
                self.assertEqual(expected, profiles.select_profile(task))

    def test_negated_constraints_do_not_cancel_real_requests_or_misread_explanations(self):
        cases = {
            'Repariere den Code ohne zusätzliche Pakete': 'project',
            'Bitte repariere den Code nicht': 'conversation',
            'Kannst du erklären, wie man Code reparieren kann?': 'explanation',
            'Empfiehl mir ein Modell ohne Cloud und ohne Kosten.': 'recommendation',
            'Recherchiere lokale Modelle, die keine Cloud brauchen.': 'research',
        }
        for task, expected in cases.items():
            with self.subTest(task=task):
                self.assertEqual(expected, profiles.select_profile(task))

    def test_conversation_without_constraints_is_noop_even_without_components(self):
        with tempfile.TemporaryDirectory() as area:
            report = profiles.check_profile(Path(area), 'conversation', 'Ja. Ich höre dir zu.')
        self.assertEqual('SKIPPED', report['status'])
        self.assertFalse(report['checked'])
        self.assertFalse(report['semantic_verified'])
        self.assertEqual([], report['components'])

    def test_empty_complete_answer_fails_without_loading_any_component(self):
        with tempfile.TemporaryDirectory() as area:
            report = profiles.check_profile(Path(area), 'conversation', ' \n ')
        self.assertEqual('FAIL', report['status'])
        self.assertFalse(report['semantic_verified'])
        self.assertEqual([], report['components'])

    def test_project_delegates_without_model_or_catalog_work(self):
        with tempfile.TemporaryDirectory() as area:
            report = profiles.check_profile(Path(area), 'project', 'Arbeitsstatus: OFFEN')
        self.assertEqual('SKIPPED', report['status'])
        self.assertEqual('workflow', report['delegated_to'])
        self.assertFalse(report['checked'])

    def test_real_native_length_enforces_limit_without_modifying_text(self):
        text = 'Grüße aus Köln. Vollständiges unverändertes Ende.'
        with patch('socket.socket.connect', side_effect=AssertionError('No network')):
            report = profiles.check_profile(ROOT, 'conversation', text,
                         evidence={'constraints': {'max_chars': 10}})
        self.assertEqual('FAIL', report['status'])
        self.assertTrue(report['checked'])
        self.assertEqual(hashlib.sha256(text.encode()).hexdigest(), report['answer_sha256'])
        self.assertTrue(any(c['native_validator'] == 'guardrails/valid_length' for c in report['components']))
        self.assertNotIn('fixed_text', report)

    def test_required_sections_are_literal_requirements_only(self):
        evidence = {'constraints': {'required_sections': ['Vorgehen', 'Grenzen']}}
        report = profiles.check_profile(ROOT, 'explanation', 'Vorgehen\nEin Beispiel.', evidence=evidence)
        self.assertEqual('FAIL', report['status'])
        self.assertTrue(any(f['rule'] == 'required_sections' for f in report['findings']))

    def test_explanation_does_not_fabricate_a_factuality_pass(self):
        report = profiles.check_profile(ROOT, 'explanation', 'Ein erklärender Satz.')
        self.assertEqual('UNVERIFIED', report['status'])
        self.assertFalse(report['semantic_verified'])

    def test_research_url_alone_does_not_count_as_source_evidence(self):
        report = profiles.check_profile(ROOT, 'research', 'Die neue Version ist 7.',
                         evidence={'sources': [{'url': 'https://example.org/release'}]})
        self.assertEqual('UNVERIFIED', report['status'])
        self.assertFalse(report['semantic_verified'])

    def research_evidence(self):
        return {'sources': [{'url': 'https://example.org/release', 'title': 'Release notes',
                    'excerpt': 'Version 7 wurde veröffentlicht.', 'origin': 'retrieved'}],
                'claims': [{'quote': 'Die neue Version ist 7.', 'source_url': 'https://example.org/release',
                            'evidence_quote': 'Version 7 wurde veröffentlicht.'}]}

    def test_research_structural_bindings_use_actual_native_url_validator(self):
        with patch('socket.socket.connect', side_effect=AssertionError('No network')):
            report = profiles.check_profile(ROOT, 'research', 'Die neue Version ist 7.',
                                             evidence=self.research_evidence())
        self.assertEqual('UNVERIFIED', report['status'])
        self.assertTrue(report['source_bindings_checked'])
        self.assertTrue(any(c['native_validator'] == 'guardrails/valid_url' for c in report['components']))
        self.assertFalse(report['semantic_verified'])

    def test_url_credentials_or_non_web_scheme_fail_without_fetching(self):
        for url in ('javascript://host/path', 'https://user:secret@example.org/notes'):
            evidence = self.research_evidence()
            evidence['sources'][0]['url'] = url
            evidence['claims'][0]['source_url'] = url
            report = profiles.check_profile(ROOT, 'research', 'Die neue Version ist 7.', evidence=evidence)
            self.assertEqual('FAIL', report['status'])

    def test_fabricated_claim_quotes_cannot_be_accepted(self):
        evidence = self.research_evidence()
        evidence['claims'][0]['evidence_quote'] = 'Das steht nicht in der Quelle.'
        report = profiles.check_profile(ROOT, 'research', 'Die neue Version ist 7.', evidence=evidence)
        self.assertEqual('FAIL', report['status'])

    def test_recommendations_require_criteria_decision_and_rationale(self):
        report = profiles.check_profile(ROOT, 'recommendation', 'Nimm A.')
        self.assertEqual('UNVERIFIED', report['status'])
        evidence = {'recommendations': {'criteria': ['lokal'], 'options': ['A', 'B', 'C', 'D'],
                    'decision': 'A', 'rationale': 'A läuft lokal.'}}
        report = profiles.check_profile(ROOT, 'recommendation', 'Nimm A. A läuft lokal.', evidence=evidence)
        self.assertEqual('FAIL', report['status'])

    def test_structured_recommendation_is_bound_to_answer_without_truth_claim(self):
        evidence = {'recommendations': {'criteria': ['lokal'], 'options': ['A'],
                    'decision': 'A', 'rationale': 'A läuft lokal.'}}
        report = profiles.check_profile(ROOT, 'recommendation', 'Nimm A. A läuft lokal.', evidence=evidence)
        self.assertEqual('UNVERIFIED', report['status'])
        self.assertTrue(report['recommendation_structure_checked'])
        self.assertFalse(report['semantic_verified'])

    def test_source_profile_never_launches_nli_even_with_source_text(self):
        with patch('subprocess.Popen', side_effect=AssertionError('No workers')):
            report = profiles.check_profile(ROOT, 'source', 'Berlin ist die Hauptstadt.',
                    evidence={'source_text': 'Berlin ist die Hauptstadt.'})
        self.assertEqual('UNVERIFIED', report['status'])
        self.assertEqual('explicit_nli_source_check', report['delegated_to'])
        self.assertFalse(report['semantic_verified'])

    def test_malformed_or_unsupported_input_is_not_an_approval(self):
        for profile, text, evidence in [('unknown', 'Hallo', None), ('conversation', '', None),
                    ('conversation', 'Hallo', {'constraints': {'max_chars': True}}),
                    ('research', 'Hallo', {'sources': 'wrong shape'})]:
            with self.subTest(profile=profile, evidence=evidence):
                report = profiles.check_profile(ROOT, profile, text, evidence=evidence)
                self.assertIn(report['status'], {'ERROR', 'FAIL', 'UNVERIFIED'})
                self.assertFalse(report['semantic_verified'])

    def test_tampered_component_cannot_be_loaded_from_manifest(self):
        with tempfile.TemporaryDirectory() as area:
            target = Path(area)
            shutil.copytree(ROOT / 'work/profile-components', target / 'work/profile-components')
            module = target / 'work/profile-components/valid_length/main.py'
            module.write_bytes(module.read_bytes() + b'\nraise RuntimeError("tampered")\n')
            report = profiles.check_profile(target, 'conversation', 'Hallo',
                                           evidence={'constraints': {'max_chars': 10}})
        self.assertEqual('ERROR', report['status'])

    def test_unverified_bytecode_cache_is_ignored_even_when_source_is_valid(self):
        with tempfile.TemporaryDirectory() as area:
            target = Path(area)
            shutil.copytree(ROOT / 'work/profile-components', target / 'work/profile-components')
            module = target / 'work/profile-components/valid_url/main.py'
            cache = Path(importlib.util.cache_from_source(str(module)))
            cache.parent.mkdir(exist_ok=True)
            stamp = module.stat()
            header = (importlib.util.MAGIC_NUMBER + (0).to_bytes(4, 'little')
                      + int(stamp.st_mtime).to_bytes(4, 'little')
                      + stamp.st_size.to_bytes(4, 'little'))
            cache.write_bytes(header + marshal.dumps(compile('raise RuntimeError("unverified bytecode")', str(module), 'exec')))
            cached_names = {name: value for name, value in sys.modules.items()
                            if name.startswith('_guardrails_profile_valid_url_')}
            for name in cached_names:
                sys.modules.pop(name)
            try:
                report = profiles.check_profile(target, 'research', 'Die neue Version ist 7.',
                                                  evidence=self.research_evidence())
            finally:
                sys.modules.update(cached_names)
        self.assertEqual('UNVERIFIED', report['status'])
        self.assertTrue(report['source_bindings_checked'])

    def test_offline_setup_checks_fixed_artifacts_without_pip_or_postinstall(self):
        completed = subprocess.run([sys.executable, str(ROOT / 'setup-profile-components.py'), '--check'],
                      cwd=ROOT, capture_output=True, text=True, timeout=30, check=False)
        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
        report = json.loads(completed.stdout)
        self.assertEqual('CHECKED', report['status'])
        self.assertEqual(2, len(report['components']))
        self.assertFalse(report['model_downloaded'])

    def test_setup_does_not_overwrite_foreign_hardlinked_files(self):
        with tempfile.TemporaryDirectory() as area:
            target = Path(area)
            shutil.copytree(ROOT / 'work/profile-components', target / 'work/profile-components')
            foreign = target / 'foreign-original.txt'
            foreign.write_bytes(b'foreign file must stay unchanged')
            leaf = target / 'work/profile-components/valid_length/main.py'
            leaf.unlink()
            os.link(foreign, leaf)
            profiles.setup_components(target)
            self.assertEqual(b'foreign file must stay unchanged', foreign.read_bytes())


if __name__ == '__main__':
    unittest.main()
