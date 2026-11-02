"""Offline feedback contracts; no native hooks, network or model execution."""

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from guardrails_local import codex_hook, workflow

SESSION = '11111111-1111-4111-8111-111111111111'
TURN = '22222222-2222-4222-8222-222222222222'
OTHER = '33333333-3333-4333-8333-333333333333'
TASK = 'Antworte mit höchstens 3 Zeichen.'


class FeedbackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copytree(ROOT / 'config', self.root / 'config')
        shutil.copytree(ROOT / 'work/profile-components', self.root / 'work/profile-components')
        self.config_path = self.root / 'work/codex/config.json'
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config = dict(enabled=True, critic_enabled=False, session_ids=[SESSION],
                           precheck_feedback_session_ids=[SESSION])
        self.configure()
        self.session_dir = self.root / 'work/codex/sessions' / SESSION
        self.answer = self.root / 'answer.txt'
        self.prompt()
        self.addCleanup(patch.stopall)
        patch.object(codex_hook, '_run_worker', side_effect=AssertionError('No model')).start()
        patch('guardrails_local.provenance_nli.check_nli', side_effect=AssertionError('No NLI')).start()

    def configure(self, **changes):
        self.config.update(changes)
        self.config_path.write_text(json.dumps(self.config), encoding='utf-8')

    def event(self, name, **fields):
        payload = dict(hook_event_name=name, session_id=SESSION, turn_id=TURN, **fields)
        return codex_hook.handle_event(payload, root=self.root)

    def prompt(self, text=TASK, turn=TURN):
        return codex_hook.handle_event(dict(hook_event_name='UserPromptSubmit',
            session_id=SESSION, turn_id=turn, prompt=text), root=self.root)

    def state(self):
        return codex_hook._state(self.session_dir)

    def ledger_path(self):
        return Path(self.state()['task_file']).parent / 'precheck-feedback.json'

    def precheck(self, text='LANG', turn=TURN, task_file=None):
        self.answer.write_text(text, encoding='utf-8')
        return codex_hook.precheck(self.answer, SESSION,
            task_file or self.state()['task_file'], turn, root=self.root)

    def payload(self, report, tool_id='call_one'):
        values = [sys.executable, str(self.root / 'codex-hook.py'),
                  '--precheck', str(self.answer), '--session-id', SESSION,
                  '--task-file', self.state()['task_file'], '--turn-id', TURN]
        command = '& ' + ' '.join('"' + value + '"' for value in values)
        status = report['final_status']
        return dict(hook_event_name='PostToolUse', session_id=SESSION, turn_id=TURN,
            tool_name='Bash', tool_use_id=tool_id, tool_input=dict(command=command),
            tool_response=dict(stdout=json.dumps(report, ensure_ascii=False),
                               exit_code=0 if status in {'PASS', 'SKIPPED'} else 3 if status == 'ERROR' else 2))

    def consume(self, report, tool_id='call_one'):
        return codex_hook.handle_event(self.payload(report, tool_id), root=self.root)

    def feedback(self, output):
        return output.get('hookSpecificOutput', {}).get('additionalContext', '')

    def test_actual_length_failure_emits_bound_feedback_once(self):
        report = self.precheck()
        self.assertEqual('FAIL', report['final_status'])
        self.assertIn('feedback_receipt_id', report)
        output = self.consume(report)
        self.assertIn('Korrektur 1/2', self.feedback(output))
        self.assertNotIn('continue', output)
        self.assertNotIn('decision', output)
        self.assertIn(self.state()['task_id'], self.feedback(output))
        self.assertEqual({}, self.consume(report))
        self.assertEqual({}, self.consume(report, 'another_id'))

    def test_two_corrections_persist_and_third_failure_escalates(self):
        for index, text in enumerate(('LANG', 'LANGER'), start=1):
            report = self.precheck(text)
            self.assertIn(f'Korrektur {index}/2', self.feedback(self.consume(report, f'call_{index}')))
        report = self.precheck('NOCHLANGER')
        self.assertEqual('ESCALATED', report['final_status'])
        self.assertEqual('', self.feedback(self.consume(report, 'call_three')))
        ledger = codex_hook._load_json(self.ledger_path())
        self.assertEqual(2, ledger['corrections_reserved'])
        self.assertEqual('ESCALATED', self.precheck('ANDERS')['final_status'])

    def test_corrected_actual_length_pass_never_emits_feedback(self):
        self.consume(self.precheck())
        report = self.precheck('JA')
        self.assertEqual('PASS', report['final_status'])
        self.assertEqual('', self.feedback(self.consume(report, 'pass_call')))

    def test_default_off_keeps_existing_precheck_and_no_ledger(self):
        self.configure(precheck_feedback_session_ids=[])
        report = self.precheck()
        self.assertNotIn('feedback_receipt_id', report)
        self.assertEqual({}, self.consume(report))
        self.assertFalse(self.ledger_path().exists())

    def test_missing_or_foreign_turn_never_creates_receipt(self):
        for turn in (None, OTHER):
            with self.subTest(turn=turn):
                report = self.precheck(turn=turn)
                self.assertEqual('ERROR', report['final_status'])
                self.assertNotIn('feedback_receipt_id', report)
        self.assertFalse(self.ledger_path().exists())

    def test_same_text_new_task_rejects_old_task_file(self):
        old_task = self.state()['task_file']
        self.prompt(TASK, OTHER)
        self.assertNotEqual(old_task, self.state()['task_file'])
        report = self.precheck(turn=OTHER, task_file=old_task)
        self.assertEqual('ERROR', report['final_status'])
        self.assertNotIn('feedback_receipt_id', report)

    def test_terminal_error_unverified_and_skipped_do_not_repeat_check(self):
        for status in ('ERROR', 'UNVERIFIED', 'SKIPPED'):
            with self.subTest(status=status):
                self.prompt('Neuer Auftrag ' + status, OTHER)
                with patch.object(codex_hook, '_conversation_check', return_value=dict(
                        final_status=status, released_text=None)) as check:
                    first = self.precheck(turn=OTHER)
                    second = self.precheck('ANDERS', turn=OTHER)
                self.assertEqual(1, check.call_count)
                self.assertNotEqual('PASS', second['final_status'])
                self.assertEqual('', self.feedback(codex_hook.handle_event(self.payload(first), root=self.root)))

    def test_critic_only_fail_and_component_error_do_not_correct(self):
        for extra in ({}, {'profile_check': dict(status='ERROR', findings=[dict(description='error')])}):
            with self.subTest(extra=extra):
                self.prompt('Freie Antwort ' + str(extra))
                with patch.object(codex_hook, '_conversation_check', return_value=dict(
                        final_status='FAIL', released_text=None, **extra)):
                    report = self.precheck()
                self.assertEqual('', self.feedback(self.consume(report)))

    def test_rule_change_closes_old_ledger_without_rebinding(self):
        report = self.precheck()
        policy = self.root / 'config/workflow-policy.json'
        policy.write_bytes(policy.read_bytes() + b' ')
        self.assertEqual('', self.feedback(self.consume(report)))
        self.assertNotEqual('FAIL', self.precheck('ANDERS')['final_status'])

    def test_rights_change_and_revocation_cannot_consume(self):
        report = self.precheck()
        self.configure(precheck_feedback_session_ids=[])
        self.assertEqual({}, self.consume(report))
        self.configure(precheck_feedback_session_ids=[SESSION], action_evidence_session_ids=[SESSION])
        self.assertEqual('', self.feedback(self.consume(report)))

    def test_changed_answer_cannot_consume_old_receipt(self):
        report = self.precheck()
        self.answer.write_text('ANDERS', encoding='utf-8')
        self.assertEqual('', self.feedback(self.consume(report)))

    def test_stdout_status_and_forged_receipt_do_not_suffice(self):
        report = self.precheck()
        for replacement in (dict(final_status='FAIL'), dict(report, feedback_receipt_id=OTHER),
                            dict(report, final_status='PASS')):
            with self.subTest(replacement=replacement.get('final_status')):
                output = codex_hook.handle_event(self.payload(replacement), root=self.root)
                self.assertEqual('', self.feedback(output))

    def test_foreign_tools_commands_session_turn_and_task_are_no_feedback(self):
        report = self.precheck()
        original = self.payload(report)
        variations = [dict(tool_name='web.run'), dict(session_id=OTHER), dict(turn_id=OTHER)]
        for command in (original['tool_input']['command'] + '; echo ok',
                        original['tool_input']['command'].replace(sys.executable, 'other-python'),
                        original['tool_input']['command'].replace(self.state()['task_file'], str(self.root / 'foreign.txt')),
                        original['tool_input']['command'] + ' --turn-id ' + TURN):
            variations.append(dict(tool_input=dict(command=command)))
        for changes in variations:
            with self.subTest(changes=changes):
                output = codex_hook.handle_event(dict(original, **changes), root=self.root)
                self.assertEqual('', self.feedback(output))

    def test_unsupported_output_shape_does_not_correct(self):
        report = self.precheck()
        payload = self.payload(report)
        payload['tool_response'] = dict(output=payload['tool_response']['stdout'], exit_code=2)
        self.assertEqual('', self.feedback(codex_hook.handle_event(payload, root=self.root)))

    def test_pending_reservation_after_crash_is_not_reexecuted(self):
        with patch.object(codex_hook, '_conversation_check', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.precheck()
        with patch.object(codex_hook, '_conversation_check', side_effect=AssertionError('No repeat')):
            self.assertEqual('ERROR', self.precheck('NEU')['final_status'])

    def test_crash_after_feedback_consumption_never_reemits(self):
        report = self.precheck()
        original_atomic = codex_hook._atomic_json

        def persisted_crash(path, value):
            original_atomic(path, value)
            if Path(path) == self.ledger_path() and value.get('corrections_reserved') == 1:
                raise KeyboardInterrupt

        with patch.object(codex_hook, '_atomic_json', side_effect=persisted_crash):
            with self.assertRaises(KeyboardInterrupt):
                self.consume(report)
        self.assertEqual({}, self.consume(report, 'after_restart'))

    def test_parallel_consumers_emit_at_most_once(self):
        report = self.precheck()
        with ThreadPoolExecutor(max_workers=2) as pool:
            outputs = list(pool.map(lambda i: self.consume(report, 'parallel_' + str(i)), range(2)))
        self.assertEqual(1, sum(bool(self.feedback(output)) for output in outputs))
        self.assertEqual(1, codex_hook._load_json(self.ledger_path())['corrections_reserved'])

    def test_new_user_copy_of_feedback_is_reachable_and_new_task(self):
        report = self.precheck()
        original_task = self.state()['task_id']
        text = self.feedback(self.consume(report))
        self.assertTrue(text)
        output = self.prompt(text, OTHER)
        self.assertNotEqual(original_task, self.state()['task_id'])
        self.assertNotIn('continue', output)
        self.assertFalse(self.ledger_path().exists())
        self.assertEqual({}, self.consume(report, 'late_old_event'))

    def test_new_draft_before_feedback_consumption_is_not_checked(self):
        self.precheck()
        with patch.object(codex_hook, '_conversation_check', side_effect=AssertionError('No unchecked step')):
            self.assertNotEqual('FAIL', self.precheck('ANDERS')['final_status'])

    def test_allowlist_shape_is_strict_and_context_gives_turn_binding(self):
        context = self.prompt()['hookSpecificOutput']['additionalContext']
        self.assertIn('--turn-id', context)
        self.assertIn(TURN, context)
        for value in ([SESSION, SESSION], [OTHER], 'all'):
            self.configure(precheck_feedback_session_ids=value)
            self.assertIn('ERROR', self.prompt()['systemMessage'])

    def test_workflow_accepts_only_exact_bound_turn_variant(self):
        state = self.state()
        command = self.payload(dict(final_status='FAIL'))['tool_input']['command']
        self.assertTrue(workflow._shell_allowed(self.root, state, command))
        self.assertFalse(workflow._shell_allowed(self.root, state, command.replace(TURN, OTHER)))
        self.assertFalse(workflow._shell_allowed(self.root, state, command + ' --turn-id ' + TURN))

    def test_same_precheck_returns_exact_report_without_second_callback(self):
        first = self.precheck()
        with patch.object(codex_hook, '_conversation_check', side_effect=AssertionError('No repeat')):
            second = self.precheck()
        self.assertEqual(first, second)

    def test_changed_rules_during_check_never_create_usable_receipt(self):
        original_check = codex_hook._conversation_check

        def changed(*args):
            report = original_check(*args)
            policy = self.root / 'config/workflow-policy.json'
            policy.write_bytes(policy.read_bytes() + b' ')
            return report

        with patch.object(codex_hook, '_conversation_check', side_effect=changed):
            report = self.precheck()
        self.assertEqual('UNVERIFIED', report['final_status'])
        self.assertNotIn('feedback_receipt_id', report)
        self.assertEqual('', self.feedback(self.consume(report)))

    def test_modified_local_report_closes_without_aborting_user_communication(self):
        report = self.precheck()
        path = self.ledger_path().parent / ('feedback-report-' + report['feedback_receipt_id'] + '.json')
        changed = dict(report, final_status='PASS')
        codex_hook._atomic_json(path, changed)
        output = self.consume(report)
        self.assertEqual('', self.feedback(output))
        self.assertNotIn('continue', output)
        self.assertEqual('UNVERIFIED', self.precheck('ANDERS')['final_status'])

    def test_malformed_ledger_remains_visible_without_reset(self):
        self.precheck()
        path = self.ledger_path()
        path.write_text('{"version":1,"version":2}', encoding='utf-8')
        original = path.read_bytes()
        with patch.object(codex_hook, '_conversation_check', side_effect=AssertionError('No reset')):
            self.assertEqual('ERROR', self.precheck('ANDERS')['final_status'])
        self.assertEqual(original, path.read_bytes())

    def test_one_tool_id_cannot_deliver_two_receipts(self):
        self.assertTrue(self.feedback(self.consume(self.precheck(), 'same_call')))
        report = self.precheck('LANGER')
        self.assertEqual('', self.feedback(self.consume(report, 'same_call')))
        self.assertEqual(1, codex_hook._load_json(self.ledger_path())['corrections_reserved'])

    def test_unknown_tool_output_closes_future_automatic_checks(self):
        report = self.precheck()
        payload = self.payload(report)
        payload['tool_response'] = {'unknown': 'shape'}
        codex_hook.handle_event(payload, root=self.root)
        with patch.object(codex_hook, '_conversation_check', side_effect=AssertionError('No retry')):
            self.assertEqual('UNVERIFIED', self.precheck('ANDERS')['final_status'])

    def test_missing_feedback_gate_field_is_inactive(self):
        del self.config['precheck_feedback_session_ids']
        self.configure()
        report = self.precheck()
        self.assertNotIn('feedback_receipt_id', report)
        self.assertEqual({}, self.consume(report))

    def test_posttool_lock_error_has_no_continue_false(self):
        report = self.precheck()
        with patch.object(codex_hook, '_session_lock', side_effect=OSError('lock unavailable')):
            output = self.consume(report)
        self.assertNotIn('continue', output)
        self.assertEqual('', self.feedback(output))

    def project_report(self):
        return dict(final_status='FAIL', released_text=None, attempts=[],
                    workflow=dict(status='FAIL', findings=[dict(description='Bound host failure')]))

    def test_project_task_file_change_invalidates_cache_and_consumption(self):
        for operation in ('cache', 'consume'):
            with self.subTest(operation=operation):
                self.prompt('Guardrails: Projekt\nOriginal ' + operation)
                with patch.object(codex_hook, '_validate', return_value=(self.project_report(), None)):
                    report = self.precheck()
                Path(self.state()['task_file']).write_text('Geänderter Auftrag', encoding='utf-8')
                if operation == 'cache':
                    self.assertEqual('ERROR', self.precheck()['final_status'])
                else:
                    output = self.consume(report)
                    self.assertEqual('', self.feedback(output))
                    self.assertNotIn('continue', output)

    def test_changed_tool_duplicate_with_both_gates_permanently_closes_feedback(self):
        self.configure(action_evidence_session_ids=[SESSION])
        first = self.precheck()
        self.assertTrue(self.feedback(self.consume(first, 'same_call')))
        duplicate = self.payload(first, 'same_call')
        duplicate['tool_response']['stdout'] += ' '
        output = codex_hook.handle_event(duplicate, root=self.root)
        self.assertNotIn('continue', output)
        with patch.object(codex_hook, '_conversation_check', side_effect=AssertionError('No retry after error')) as check:
            self.assertEqual('ERROR', self.precheck('ANDERS')['final_status'])
        check.assert_not_called()

    def test_damaged_closed_state_never_releases_text_or_unstructured_value(self):
        for bad in (dict(final_status='PASS', released_text='x'), [],
                    dict(final_status='ERROR', released_text='x'), dict(final_status='SKIPPED')):
            with self.subTest(bad=bad):
                self.prompt('Geschlossener Auftrag ' + str(bad))
                report = self.precheck()
                payload = self.payload(report)
                payload['tool_response'] = {'unknown': 'shape'}
                codex_hook.handle_event(payload, root=self.root)
                closed = self.ledger_path().parent / 'precheck-feedback-closed.json'
                codex_hook._atomic_json(closed, bad)
                original = closed.read_bytes()
                result = self.precheck('ANDERS')
                self.assertIsInstance(result, dict)
                self.assertEqual('ERROR', result['final_status'])
                self.assertIsNone(result.get('released_text'))
                self.assertEqual(original, closed.read_bytes())

    def test_existing_evidence_only_error_behavior_is_preserved(self):
        self.configure(precheck_feedback_session_ids=[], action_evidence_session_ids=[SESSION])
        with patch('guardrails_local.action_evidence.record_tool_result', side_effect=ValueError('bad evidence')):
            output = self.consume(dict(final_status='FAIL'))
        self.assertIs(output.get('continue'), False)

    def test_feedback_command_rejects_unc_and_ntfs_stream_like_workflow(self):
        from guardrails_local import precheck_feedback
        report = self.precheck()
        payload = self.payload(report)
        for path in (r'\\server\share\answer.txt', r'C:\local\answer.txt:stream'):
            with self.subTest(path=path):
                changed = dict(payload, tool_input=dict(command=payload['tool_input']['command'].replace(str(self.answer), path)))
                self.assertFalse(workflow._shell_allowed(self.root, self.state(), changed['tool_input']['command']))
                self.assertIsNone(precheck_feedback._command(self.root, self.state(), changed))


if __name__ == '__main__':
    unittest.main()
