"""The original failure: claiming a verified chat lookup without a real result."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from guardrails_local import codex_hook

SESSION = '11111111-1111-4111-8111-111111111111'
TURN = '22222222-2222-4222-8222-222222222222'
OTHER = '33333333-3333-4333-8333-333333333333'
TITLE = 'Chat zu Rechercheverhalten finden'


class ClaimHookTests(unittest.TestCase):
    def test_unapproved_posttool_event_has_no_files_or_lock(self):
        config_path = self.root / 'work/codex/config.json'
        config = json.loads(config_path.read_text(encoding='utf-8'))
        config.update(session_ids=[SESSION, OTHER], action_evidence_session_ids=[SESSION])
        config_path.write_text(json.dumps(config), encoding='utf-8')
        result = codex_hook.handle_event(dict(hook_event_name='PostToolUse', session_id=OTHER,
            turn_id=TURN, tool_name='mcp__codex_app__list_threads', tool_use_id='other-call',
            tool_input={}, tool_response={}), root=self.root)
        self.assertEqual({}, result)
        self.assertFalse((self.root / 'work/codex/sessions' / OTHER).exists())

    def test_revoked_session_cannot_reuse_receipts(self):
        config_path = self.root / 'work/codex/config.json'
        config = json.loads(config_path.read_text(encoding='utf-8'))
        config['action_evidence_session_ids'] = [SESSION]
        config_path.write_text(json.dumps(config), encoding='utf-8')
        self.receipt()
        text = f'Ich habe den Chat „{TITLE}“ in deiner Chatliste gefunden.'
        self.assertEqual('PASS', self.check(text)['action_claims']['status'])
        config['action_evidence_session_ids'] = []
        config_path.write_text(json.dumps(config), encoding='utf-8')
        with patch('guardrails_local.action_evidence.check_action_claims') as checker:
            report = self.check(text)
            self.event('Stop', last_assistant_message=text)
        checker.assert_not_called()
        self.assertEqual('SKIPPED', report['action_claims']['status'])
        self.assertIsNone(report['released_text'])

    def test_malformed_evidence_allowlist_is_closed(self):
        config_path = self.root / 'work/codex/config.json'
        config = json.loads(config_path.read_text(encoding='utf-8'))
        for value in ('all', [OTHER], [SESSION, SESSION], [None], [SESSION] * 17):
            with self.subTest(value=value):
                config['action_evidence_session_ids'] = value
                config_path.write_text(json.dumps(config), encoding='utf-8')
                with self.assertRaises((ValueError, TypeError, AttributeError)):
                    codex_hook._config(self.root, SESSION, required=True)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copytree(ROOT / 'config', self.root / 'config')
        shutil.copytree(ROOT / 'work/profile-components', self.root / 'work/profile-components')
        path = self.root / 'work/codex/config.json'
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(dict(enabled=True, critic_enabled=True,
            session_ids=[SESSION], workflow_session_ids=[], action_evidence_session_ids=[SESSION])), encoding='utf-8')
        self.directory = path.parent / 'sessions' / SESSION
        self.prompt = 'Finde den Chat über mein Rechercheverhalten.'
        self.event('UserPromptSubmit', prompt=self.prompt)
        self.worker = patch.object(codex_hook, '_run_worker',
            side_effect=AssertionError('A lookup claim needs receipts, never a language-model judge'))
        self.worker.start()
        self.addCleanup(self.worker.stop)

    def event(self, kind, **extra):
        return codex_hook.handle_event(dict(hook_event_name=kind, session_id=SESSION,
            turn_id=TURN, **extra), root=self.root)

    def check(self, text):
        answer = self.root / 'answer.txt'
        answer.write_bytes(text.encode('utf-8'))
        state = json.loads((self.directory / 'state.json').read_text(encoding='utf-8'))
        task = Path(state.get('task_file', self.root / 'original-task.txt'))
        if not task.exists():
            task.write_bytes(self.prompt.encode('utf-8'))
        return codex_hook.precheck(answer, SESSION, task, TURN, root=self.root)

    def receipt(self, *, tool='mcp__codex_app__list_threads', turn=TURN):
        response = dict(content=[dict(type='text', text=json.dumps(dict(
            schemaVersion=4, threads=[dict(id=OTHER, title=TITLE)], pinnedThreads=[])))], isError=False)
        return codex_hook.handle_event(dict(hook_event_name='PostToolUse', session_id=SESSION,
            turn_id=turn, tool_name=tool, tool_use_id='native-call-1',
            tool_input=dict(limit=10), tool_response=response), root=self.root)

    def test_the_reported_false_lookup_is_rejected_without_a_tool_receipt(self):
        report = self.check(f'Ich habe den Chat „{TITLE}“ in deiner Chatliste gefunden und verifiziert.')
        self.assertEqual('FAIL', report['final_status'])
        self.assertIsNone(report['released_text'])
        self.assertTrue(Path(report['adapter_audit_path']).is_file())

    def test_a_real_native_chat_result_can_support_only_its_actual_title(self):
        self.receipt()
        supported = self.check(f'Ich habe den Chat „{TITLE}“ in deiner Chatliste gefunden.')
        wrong = self.check('Ich habe den Chat „Erfundener anderer Titel“ in deiner Chatliste gefunden.')
        self.assertEqual('PASS', supported['action_claims']['status'])
        self.assertEqual('UNVERIFIED', supported['final_status'])
        self.assertIsNone(supported['released_text'])
        self.assertEqual('FAIL', wrong['final_status'])

    def test_an_old_result_or_bash_printout_does_not_prove_a_chat_search(self):
        for tool, turn in (('mcp__codex_app__list_threads', OTHER), ('Bash', TURN)):
            with self.subTest(tool=tool):
                self.receipt(tool=tool, turn=turn)
                report = self.check(f'Ich habe den Chat „{TITLE}“ in deiner Chatliste gefunden.')
                self.assertEqual('FAIL', report['final_status'])

    def test_the_host_requests_correction_instead_of_a_false_successful_release(self):
        text = f'Ich habe den Chat „{TITLE}“ in deiner Chatliste gefunden.'
        self.check(text)
        stopped = self.event('Stop', last_assistant_message=text)
        self.assertIs(stopped.get('continue'), False)
        self.assertNotIn('decision', stopped)
        self.assertIn('Herkunft', stopped['systemMessage'])

    def test_an_honest_unconfirmed_statement_is_not_a_proven_lookup(self):
        report = self.check(f'Der Titel „{TITLE}“ ist eine unbestätigte Vermutung. Ich habe nicht gesucht.')
        self.assertEqual('SKIPPED', report['action_claims']['status'])
        self.assertEqual('UNVERIFIED', report['final_status'])
        self.assertIsNone(report['released_text'])

    def test_new_receipt_is_rechecked_without_repeating_a_model_worker(self):
        text = f'Ich habe den Chat „{TITLE}“ in deiner Chatliste gefunden.'
        self.assertEqual('FAIL', self.check(text)['final_status'])
        self.receipt()
        self.assertEqual('PASS', self.check(text)['action_claims']['status'])

    def test_project_rejection_links_the_actual_claim_report_without_poisoning_the_base_cache(self):
        self.prompt = 'Guardrails: Projekt\nPrüfe die konkrete Änderung.'
        self.event('UserPromptSubmit', prompt=self.prompt)
        text = f'Ich habe den Chat „{TITLE}“ in deiner Chatliste gefunden.'
        rejected = self.check(text)
        self.assertEqual('FAIL', rejected['final_status'])
        audit = json.loads(Path(rejected['adapter_audit_path']).read_text(encoding='utf-8'))
        self.assertEqual('FAIL', audit['final_status'])
        self.assertEqual('FAIL', audit['action_claims']['status'])
        base_path = Path(audit['base_adapter_audit_path'])
        before = base_path.read_bytes()
        self.receipt()
        supported = self.check(text)
        self.assertEqual('PASS', supported['action_claims']['status'])
        self.assertEqual('UNVERIFIED', supported['final_status'])
        self.assertEqual(before, base_path.read_bytes())

    def test_duplicate_prompt_cannot_reset_the_correction_budget_or_replace_task(self):
        text = f'Ich habe den Chat „{TITLE}“ in deiner Chatliste gefunden.'
        self.assertIs(self.event('Stop', last_assistant_message=text)['continue'], False)
        path = self.directory / 'state.json'
        before = path.read_bytes()
        self.event('UserPromptSubmit', prompt=self.prompt)
        self.assertEqual(before, path.read_bytes())

    def test_claim_failure_cannot_turn_a_technical_error_into_an_automatic_retry(self):
        self.prompt = 'Guardrails: Modelle\nPrüfe den tatsächlichen Modellvorschlag.'
        self.event('UserPromptSubmit', prompt=self.prompt)
        text = f'Ich habe den Chat „{TITLE}“ in deiner Chatliste gefunden.'
        with patch.object(codex_hook, '_run_worker', return_value=codex_hook._error('Worker fehlgeschlagen')) as worker:
            report = self.check(text)
            self.assertEqual('ERROR', report['final_status'])
            self.assertEqual('FAIL', report['action_claims']['status'])
            stopped = self.event('Stop', last_assistant_message=text)
        self.assertEqual(1, worker.call_count)
        self.assertIs(False, stopped['continue'])
        self.assertNotIn('decision', stopped)


if __name__ == '__main__':
    unittest.main()
