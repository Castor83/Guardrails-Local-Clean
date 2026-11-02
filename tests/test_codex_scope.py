"""Reproduce conversational false alarms without starting an actual model."""
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
from guardrails_local import codex_hook

SESSION = '11111111-1111-4111-8111-111111111111'
OTHER = '22222222-2222-4222-8222-222222222222'
TURN = '33333333-3333-4333-8333-333333333333'
NEXT = '44444444-4444-4444-8444-444444444444'


class ScopedHookTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copytree(ROOT / 'config', self.root / 'config')
        (self.root / 'docs').mkdir()
        shutil.copyfile(ROOT / 'docs/ORIGINALAUFTRAG.txt', self.root / 'docs/ORIGINALAUFTRAG.txt')
        self.config_path = self.root / 'work/codex/config.json'
        self.config_path.parent.mkdir(parents=True)
        self.configure()
        self.directory = self.root / 'work/codex/sessions' / SESSION
        worker = patch.object(codex_hook, '_run_worker',
                              side_effect=AssertionError('Scope tests must never start a model worker'))
        worker.start()
        self.addCleanup(worker.stop)

    def configure(self, **changes):
        value = dict(enabled=True, critic_enabled=True, session_ids=[SESSION],
                     workflow_session_ids=[SESSION])
        value.update(changes)
        self.config_path.write_text(json.dumps(value), encoding='utf-8')

    def event(self, name, turn=TURN, **extra):
        return codex_hook.handle_event(dict(hook_event_name=name, session_id=SESSION,
                                          turn_id=turn, **extra), root=self.root)

    def activate(self, scope='Projekt'):
        prompt = 'Guardrails: ' + scope + '\nPrüfe diese konkrete Änderung vollständig.'
        result = self.event('UserPromptSubmit', prompt=prompt)
        state = json.loads((self.directory / 'state.json').read_text(encoding='utf-8'))
        return result, state

    def precheck(self, text='Arbeitsstatus: OFFEN\nDie Änderung wird geprüft.'):
        state = json.loads((self.directory / 'state.json').read_text(encoding='utf-8'))
        answer = self.root / 'answer.txt'
        answer.write_bytes(text.encode('utf-8'))
        return codex_hook.precheck(answer, SESSION, state['task_file'], TURN, root=self.root)

    def test_conversation_only_binds_core_evidence_without_a_model_or_workflow_review(self):
        for prompt in ('hallo', 'wir müssen reden', 'Was ist mit dem Code und dem Modell?',
                       '"Guardrails: Projekt" ist nur ein Zitat.', 'x' * 20000):
            with self.subTest(prompt=prompt[:50]):
                with patch.object(codex_hook, '_run_worker', side_effect=AssertionError('No model for conversation')):
                    result = self.event('UserPromptSubmit', prompt=prompt)
                    context = result['hookSpecificOutput']['additionalContext']
                    self.assertIn('Belegpflicht', context)
                    self.assertNotIn('Workflow aktiv:', context)
                    self.assertNotIn('Beginne finale Texte mit Arbeitsstatus:', context)
                    self.assertEqual({}, self.event('Stop', last_assistant_message='Ich höre dir zu.'))
                    self.assertEqual({}, self.event('PreToolUse', tool_name='Bash',
                        tool_input=dict(command='whoami')))

    def test_disabled_or_unregistered_precheck_skips_before_reading_files(self):
        missing = self.root / 'missing.txt'
        for changes in (dict(enabled=False), dict(session_ids=[OTHER], workflow_session_ids=[OTHER])):
            with self.subTest(changes=changes):
                self.configure(**changes)
                report = codex_hook.precheck(missing, SESSION, missing, root=self.root)
                self.assertEqual('SKIPPED', report['final_status'])
                self.assertIs(False, report['checked'])
                self.assertEqual([], report['attempts'])
                self.assertIsNone(report['released_text'])
                self.assertFalse(self.directory.exists())

    def test_skipped_cli_is_a_successful_noop_and_not_a_pass(self):
        self.configure(enabled=False)
        output = io.StringIO()
        with patch.object(codex_hook, '_project_root', return_value=self.root):
            with contextlib.redirect_stdout(output):
                code = codex_hook.main(['--precheck', str(self.root / 'absent'),
                    '--session-id', SESSION, '--task-file', str(self.root / 'absent-task')])
        self.assertEqual(0, code)
        self.assertEqual('SKIPPED', json.loads(output.getvalue())['final_status'])

    def test_explicit_project_checks_do_not_require_model_catalog_or_worker(self):
        result, state = self.activate()
        self.assertIn('workflow-check.py', result['hookSpecificOutput']['additionalContext'])
        self.assertEqual('Guardrails: Projekt\nPrüfe diese konkrete Änderung vollständig.',
                         Path(state['task_file']).read_text(encoding='utf-8'))
        for name in ('catalog.json', 'settings.json', 'requirements.json'):
            (self.root / 'config' / name).unlink()
        with patch.object(codex_hook, '_run_worker', side_effect=AssertionError('No model/catalog in project check')):
            report = self.precheck()
        self.assertEqual('PASS', report['final_status'], report)
        self.assertEqual('project', report['review_scope'])
        self.assertIsNone(report['released_text'])
        self.assertIs(False, report['attempts'][0]['critic']['executed'])

    def test_project_still_denies_foreign_edits_and_unproven_completion(self):
        self.activate()
        denied = self.event('PreToolUse', tool_name='apply_patch', cwd=str(self.root),
            tool_input=dict(command='*** Begin Patch\n*** Add File: ../foreign.py\n+x\n*** End Patch'))
        self.assertEqual('deny', denied['hookSpecificOutput']['permissionDecision'])
        with patch.object(codex_hook, '_run_worker', side_effect=AssertionError('Host evidence only')):
            report = self.precheck('Arbeitsstatus: ABGESCHLOSSEN\nErledigt.')
        self.assertEqual('FAIL', report['final_status'])
        self.assertIsNone(report['released_text'])

    def test_conversation_replaces_old_project_scope_but_preserves_its_record(self):
        _, old = self.activate()
        result = self.event('UserPromptSubmit', turn=NEXT, prompt='wir müssen reden')
        self.assertIn('Belegpflicht', result['hookSpecificOutput']['additionalContext'])
        missing = self.root / 'not-read.txt'
        report = codex_hook.precheck(missing, SESSION, old['task_file'], root=self.root)
        self.assertEqual('SKIPPED', report['final_status'])
        self.assertEqual({}, self.event('Stop', turn=NEXT, last_assistant_message='Ich höre zu.'))
        saved = Path(old['task_file']).parent / 'state-final.json'
        self.assertTrue(saved.is_file())
        self.assertEqual(old['task'], json.loads(saved.read_text(encoding='utf-8'))['task'])

    def test_modified_scope_cannot_activate_a_different_review_or_reuse_a_pass(self):
        self.activate()
        with patch.object(codex_hook, '_run_worker', side_effect=AssertionError('No model')):
            self.assertEqual('PASS', self.precheck()['final_status'])
        path = self.directory / 'state.json'
        state = json.loads(path.read_text(encoding='utf-8'))
        state['review_scope'] = 'model'
        path.write_text(json.dumps(state), encoding='utf-8')
        with patch.object(codex_hook, '_run_worker', side_effect=AssertionError('Tampered scope must fail before inference')):
            report = self.precheck()
        self.assertEqual('ERROR', report['final_status'])

    def test_project_cache_cannot_fabricate_a_successful_completion(self):
        self.activate()
        first = self.precheck('Arbeitsstatus: ABGESCHLOSSEN\nErledigt.')
        path = Path(first['adapter_audit_path'])
        first['final_status'] = 'PASS'
        path.write_text(json.dumps(first), encoding='utf-8')
        repeated = self.precheck('Arbeitsstatus: ABGESCHLOSSEN\nErledigt.')
        self.assertEqual('ERROR', repeated['final_status'])
        self.assertIsNone(repeated['released_text'])

    def test_late_stop_does_not_check_the_previous_task_again(self):
        self.activate()
        with patch.object(codex_hook, '_run_worker', side_effect=AssertionError('Late stop must not infer')):
            result = self.event('Stop', turn=NEXT, last_assistant_message='Veraltete Antwort')
        self.assertEqual({}, result)

    def test_project_without_a_configured_workflow_stays_unverified_when_cached(self):
        self.configure(workflow_session_ids=[])
        self.activate()
        first = self.precheck()
        repeated = self.precheck()
        self.assertEqual('UNVERIFIED', first['final_status'])
        self.assertEqual('UNVERIFIED', repeated['final_status'])
        self.assertIs(True, repeated['cached'])

    def test_scope_binding_edge_crlf_original_stays_exact_in_workflow(self):
        prompt = 'Guardrails: Projekt\r\nPrüfe den vollständigen Auftrag.\r\n'
        result = self.event('UserPromptSubmit', prompt=prompt)
        self.assertNotIn('systemMessage', result)
        state = json.loads((self.directory / 'state.json').read_text(encoding='utf-8'))
        self.assertEqual(prompt.encode('utf-8'), Path(state['task_file']).read_bytes())
        self.assertEqual('PASS', self.precheck()['final_status'])

    def test_scope_binding_edge_missing_turn_cannot_consume_or_change_project_state(self):
        self.activate()
        before = (self.directory / 'state.json').read_bytes()
        result = self.event('Stop', turn=None, last_assistant_message='Arbeitsstatus: OFFEN\nAntwort')
        self.assertEqual({}, result)
        self.assertEqual(before, (self.directory / 'state.json').read_bytes())


if __name__ == '__main__':
    unittest.main()
