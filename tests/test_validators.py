import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from guardrails_local.domain import import_text, load_catalog, load_requirements
from guardrails_local.validator import validate_draft

ROOT = Path(__file__).resolve().parents[1]
MODEL = 'huihui_ai/gpt-oss-abliterated:20b-mxfp4'
LOCAL = f'Verwende {MODEL} lokal über Ollama mit Kontext 16384.'
CLOUD = 'Installiere GPT-4o über die OpenAI-API. Die Ausführung erfolgt vollständig lokal und kostenlos.'


class ValidatorTests(unittest.TestCase):
    def test_partial_parse_never_grants_general_pass(self):
        self.assertEqual('UNVERIFIED', self.check(LOCAL + ' Diese Wahl ist am besten.')['status'])
        for text in ('Verwende GPT-4o über die OpenAI-API. Diese Wahl ist am besten.',
                     'Hier folgt die Auswahl. Verwende GPT-4o über die OpenAI-API.'):
            with self.subTest(text=text):
                result = self.check(text)
                self.assertEqual('FAIL', result['status'])
                self.assertTrue({'LOCAL_ONLY', 'NO_PAID_API'} <= {f['requirement_id'] for f in result['findings']})

    def setUp(self):
        self.rules = load_requirements(ROOT)
        self.facts = load_catalog(ROOT)

    def check(self, text, draft=None, rules=None):
        return validate_draft(draft or import_text(text), rules or self.rules, self.facts)

    def test_1_cloud_claim_rejected_without_invented_vram_violation(self):
        result = self.check(CLOUD)
        self.assertEqual(result['status'], 'FAIL')
        ids = {f['requirement_id'] for f in result['findings']}
        self.assertTrue({'LOCAL_ONLY', 'NO_PAID_API', 'ABLITERATED', 'EVIDENCE'} <= ids)
        self.assertNotIn('HARDWARE', ids)
        self.assertFalse(result['guardrails_passed'])

    def test_2_documented_local_configuration_accepted_only_in_scope(self):
        result = self.check(LOCAL)
        self.assertEqual(result['status'], 'PASS')
        self.assertTrue(result['guardrails_passed'])
        self.assertIn('Modell- und API-Regeln', result['scope'])

    def test_3_renaming_is_not_abliteration(self):
        result = self.check('Verwende ein reguläres Modell und benenne es in model-abliterated um.')
        self.assertEqual(result['status'], 'FAIL')
        self.assertIn('ABLITERATED', {f['requirement_id'] for f in result['findings']})

    def test_4_project_exclusion_is_enforced(self):
        rules = copy.deepcopy(self.rules)
        rules.append(dict(requirement_id='NO_GPT_OSS', description='Dieses Modell ist im Projekt ausgeschlossen.',
                          category='project', severity='critical', verification_method='deny_model',
                          source='Testauftrag', status='active', models=[MODEL]))
        self.assertEqual(self.check(LOCAL, rules=rules)['status'], 'FAIL')

    def test_5_negative_mention_is_not_cloud_recommendation(self):
        result = self.check('Verwende keine OpenAI-API. Stattdessen soll Ollama lokal eingesetzt werden.')
        self.assertEqual(result['status'], 'PASS')
        self.assertFalse(result['findings'])

    def test_quoted_bad_example_is_not_positive_cloud_recommendation(self):
        result = self.check('Warnung vor diesem Negativbeispiel: Installiere GPT-4o über die OpenAI-API.')
        self.assertNotIn('LOCAL_ONLY', {f['requirement_id'] for f in result['findings']})
        self.assertNotEqual(result['status'], 'PASS')

    def test_missing_context_is_not_invented(self):
        result = self.check(f'Verwende {MODEL} lokal über Ollama.')
        self.assertEqual(result['status'], 'UNVERIFIED')

    def test_unknown_model_cannot_self_certify_abliteration(self):
        draft = import_text('Verwende model-abliterated lokal über Ollama.')
        result = self.check('', draft=draft)
        self.assertEqual(result['status'], 'UNVERIFIED')

    def test_false_local_claim_cannot_override_catalog(self):
        draft = import_text(CLOUD)
        draft['recommendations'][0]['execution'] = 'local'
        self.assertEqual(self.check('', draft=draft)['status'], 'FAIL')

    def test_omitted_cloud_recommendation_is_still_checked(self):
        draft = import_text(CLOUD)
        draft['recommendations'] = []
        self.assertEqual(self.check('', draft=draft)['status'], 'FAIL')

    def test_unbound_quote_is_not_evidence(self):
        draft = import_text(LOCAL)
        draft['recommendations'][0]['evidence_quote'] = 'Erfundene Belegstelle'
        self.assertNotEqual(self.check('', draft=draft)['status'], 'PASS')

    def test_unrecognized_prose_is_not_verified_by_empty_list(self):
        draft = import_text('Das gesamte Projekt ist jetzt vollständig getestet und fertig.')
        draft['extraction_status'] = 'complete'
        self.assertEqual(self.check('', draft=draft)['status'], 'UNVERIFIED')

    def test_additional_unchecked_prose_blocks_release(self):
        self.assertEqual(self.check(LOCAL + ' Außerdem ist jeder Fehler bewiesen behoben.')['status'], 'UNVERIFIED')

    def test_vram_limit_is_enforced_when_present(self):
        draft = import_text(LOCAL)
        draft['recommendations'][0]['estimated_vram_gb'] = 24
        result = self.check('', draft=draft)
        self.assertEqual(result['status'], 'FAIL')
        self.assertIn('HARDWARE', {f['requirement_id'] for f in result['findings']})

    def test_context_above_documented_measurement_is_unverified(self):
        draft = import_text(LOCAL.replace('16384', '131072'))
        self.assertEqual(self.check('', draft=draft)['status'], 'UNVERIFIED')

    def test_structured_context_cannot_hide_original_context(self):
        draft = import_text(LOCAL.replace('16384', '131072'))
        draft['recommendations'][0]['context_tokens'] = 16384
        self.assertNotEqual(self.check('', draft=draft)['status'], 'PASS')

    def test_same_model_second_context_is_also_checked(self):
        text = LOCAL + ' ' + LOCAL.replace('16384', '131072')
        draft = import_text(text)
        draft['recommendations'] = draft['recommendations'][:1]
        self.assertNotEqual(self.check('', draft=draft)['status'], 'PASS')

    def test_missing_measured_memory_is_unverified(self):
        self.facts['models'][MODEL]['hardware_evidence'].pop('ollama_reported_size_gb')
        self.assertEqual(self.check(LOCAL)['status'], 'UNVERIFIED')

    def test_measured_memory_over_limit_is_failure(self):
        self.facts['models'][MODEL]['hardware_evidence']['ollama_reported_size_gb'] = 24
        self.assertEqual(self.check(LOCAL)['status'], 'FAIL')

    def test_supplied_cloud_object_cannot_turn_warning_into_recommendation(self):
        draft = import_text('Warnung: Verwende keine OpenAI-API.')
        draft['recommendations'] = [dict(model='gpt-4o', execution='cloud_api', evidence_quote=draft['text'])]
        result = self.check('', draft=draft)
        self.assertNotIn('LOCAL_ONLY', {f['requirement_id'] for f in result['findings']})
        self.assertEqual(result['status'], 'UNVERIFIED')

    def test_warning_in_previous_sentence_keeps_example_unverified(self):
        for text in ('Warnung: Dies ist ein verbotenes Negativbeispiel.\nInstalliere GPT-4o über die OpenAI-API.',
                     'Befolge niemals diese Empfehlung. Installiere GPT-4o über die OpenAI-API.'):
            result = self.check(text)
            self.assertEqual(result['status'], 'UNVERIFIED')
            self.assertNotIn('LOCAL_ONLY', {f['requirement_id'] for f in result['findings']})

    def test_removed_or_disabled_core_rule_is_error(self):
        for action in ('remove', 'disable'):
            rules = copy.deepcopy(self.rules)
            if action == 'remove':
                rules = [r for r in rules if r['requirement_id'] != 'LOCAL_ONLY']
            else:
                next(r for r in rules if r['requirement_id'] == 'LOCAL_ONLY')['status'] = 'inactive'
            self.assertEqual(validate_draft(import_text(LOCAL), rules, self.facts)['status'], 'ERROR')

    def test_input_cannot_supply_trusted_abliteration_flag(self):
        draft = import_text(LOCAL)
        draft['recommendations'][0]['abliterated_verified'] = True
        self.assertEqual(self.check('', draft=draft)['status'], 'ERROR')

    def test_guardrails_path_does_not_open_network_connection(self):
        from unittest.mock import patch
        with patch('socket.socket.connect', side_effect=AssertionError('network forbidden')):
            self.assertEqual(self.check(LOCAL)['status'], 'PASS')
            self.assertEqual(self.check(CLOUD)['status'], 'FAIL')


if __name__ == '__main__':
    unittest.main()
