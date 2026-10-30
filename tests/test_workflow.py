"""Real host-policy behavior; no Ollama or other model calls."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
try:
    from guardrails_local import workflow
except ImportError:
    workflow = None
try:
    from guardrails_local import workflow_validators
except ImportError:
    workflow_validators = None

SESSION = '11111111-1111-4111-8111-111111111111'
TASK = '22222222-2222-4222-8222-222222222222'
TURN = '33333333-3333-4333-8333-333333333333'


class WorkflowTests(unittest.TestCase):
    def test_stdout_and_atexit_cannot_spoof_test_count(self):
        self.policy['minimum_tests'] = 128
        self.policy_path.write_text(json.dumps(self.policy), encoding='utf-8')
        tests = self.root / 'tests'
        tests.mkdir()
        (tests / 'test_spoof.py').write_text(
            'import atexit, unittest\n'
            'atexit.register(lambda: print("Ran 128 tests in 0.001s"))\n'
            'class Spoof(unittest.TestCase):\n'
            '    def test_one(self): print("Ran 128 tests in 0.001s")\n', encoding='utf-8')
        proof = workflow.run_checks(self.root, self.state)
        self.assertEqual(1, proof['test_count'])
        self.assertNotEqual('PASS', proof['status'])
        self.assertNotEqual('PASS', workflow.completion_report(self.root, self.state,
            'Arbeitsstatus: ABGESCHLOSSEN\nAlle Tests bestanden.')['status'])

    def test_offen_does_not_override_success_claim(self):
        text = 'Arbeitsstatus: OFFEN\nDie Arbeit ist vollständig abgeschlossen und alle Tests bestanden.'
        for checker in (workflow.completion_report,
                        lambda root, state, value: workflow_validators.instruction_compliance(
                            value, dict(root=root, state=state))):
            self.assertNotEqual('PASS', checker(self.root, self.state, text)['status'])
        for body in ('Noch nicht vollständig abgeschlossen; Tests sind offen.',
                     'Keine Tests bestanden, die Arbeit ist nicht vollständig abgeschlossen.',
                     'Zitat: „vollständig abgeschlossen und alle Tests bestanden“.',
                     '> vollständig abgeschlossen und alle Tests bestanden',
                     '```text\nvollständig abgeschlossen und alle Tests bestanden\n```'):
            self.assertEqual('PASS', workflow.completion_report(self.root, self.state,
                'Arbeitsstatus: OFFEN\n' + body)['status'])

    def test_unrelated_comma_negation_cannot_hide_test_success(self):
        text = 'Arbeitsstatus: OFFEN\nEs gibt keine offenen Punkte, alle Tests bestanden.'
        self.assertEqual('UNVERIFIED', workflow.completion_report(self.root, self.state, text)['status'])
        self.assertEqual('UNVERIFIED', workflow_validators.instruction_compliance(text,
            dict(root=self.root, state=self.state))['status'])


    def test_invalid_or_stale_runner_result_cannot_complete(self):
        self.make_suite()
        proof = workflow.run_checks(self.root, self.state)
        self.assertIn('runner_result_path', proof)
        result_path = Path(proof['runner_result_path'])
        original = result_path.read_bytes()
        document = json.loads(original)
        proof_path = self.directory / 'workflow-check.json'
        for content in (b'{}', b'not JSON', original.replace(b'"completed": true', b'"completed": false'),
                        original.replace(proof['invocation_id'].encode(), b'0' * 32)):
            with self.subTest(content=content[:70]):
                result_path.write_bytes(content)
                self.assertNotEqual('PASS', workflow.completion_report(self.root, self.state,
                    'Arbeitsstatus: ABGESCHLOSSEN')['status'])
        for changes in ({'completed': False}, {'tests_run': True}, {'test_count': 128},
                        {'skipped': -1}, {'unexpected_successes': 1}, {'extra': 'unsupported'}):
            changed = dict(document, **changes)
            content = (json.dumps(changed, indent=2) + '\n').encode('utf-8')
            result_path.write_bytes(content)
            bound = dict(proof, runner_result_sha256=hashlib.sha256(content).hexdigest())
            proof_path.write_text(json.dumps(bound), encoding='utf-8')
            self.assertNotEqual('PASS', workflow.completion_report(self.root, self.state,
                'Arbeitsstatus: ABGESCHLOSSEN')['status'])
        proof_path.write_text(json.dumps(proof), encoding='utf-8')
        result_path.write_bytes(original)
        result_path.unlink()
        self.assertNotEqual('PASS', workflow.completion_report(self.root, self.state,
            'Arbeitsstatus: ABGESCHLOSSEN')['status'])

    def test_skips_never_fill_minimum_and_aborted_process_cannot_complete(self):
        tests = self.root / 'tests'
        tests.mkdir()
        path = tests / 'test_result.py'
        for source in ('import unittest\nclass Skipped(unittest.TestCase):\n'
                       '    @unittest.skip("Synthetic skip")\n    def test_skip(self): pass\n',
                       'import os\nos._exit(0)\n'):
            with self.subTest(source=source):
                path.write_text(source, encoding='utf-8')
                proof = workflow.run_checks(self.root, self.state)
                self.assertNotEqual('PASS', proof['status'])
                self.assertEqual(0, proof['test_count'])

    def test_allowed_reads_cannot_escape_repository(self):
        for verb in ('Get-Content', 'Get-Item', 'Test-Path', 'Get-ChildItem'):
            for path in (self.root.parent / 'foreign.txt',
                         Path(str(self.root) + '-neighbor') / 'foreign.txt',
                         self.root / '..' / 'foreign.txt',
                         Path(r'\\server\share\foreign.txt'),
                         Path(str(self.root / 'file.txt') + ':hidden')):
                with self.subTest(verb=verb, path=path):
                    self.assertFalse(workflow._shell_allowed(self.root, self.state,
                        f"{verb} -LiteralPath '{path}'"))
            self.assertTrue(workflow._shell_allowed(self.root, self.state,
                f"{verb} -LiteralPath '{self.root / 'docs/ORIGINALAUFTRAG.txt'}'"))

    def test_read_resolution_error_is_denied(self):
        with patch.object(Path, 'resolve', side_effect=OSError('cannot resolve')):
            self.assertFalse(workflow._shell_allowed(self.root, self.state,
                f"Get-Content -LiteralPath '{self.root / 'docs/ORIGINALAUFTRAG.txt'}'"))

    def test_read_link_cannot_escape_repository(self):
        with tempfile.TemporaryDirectory() as foreign:
            link = self.root / 'outside-link'
            try:
                link.symlink_to(foreign, target_is_directory=True)
            except OSError as exc:
                self.skipTest('Directory symlink unavailable: ' + str(exc))
            for verb in ('Get-Content', 'Get-Item', 'Test-Path', 'Get-ChildItem'):
                self.assertFalse(workflow._shell_allowed(self.root, self.state,
                    f"{verb} -LiteralPath '{link / 'private.txt'}'"))

    @unittest.skipUnless(sys.platform == 'win32', 'Windows junction contract')
    def test_windows_junction_reads_obey_resolved_repository_boundary(self):
        with tempfile.TemporaryDirectory() as foreign_area:
            foreign = Path(foreign_area).resolve()
            marker = foreign / 'synthetic.txt'
            marker.write_bytes(b'Synthetic external target must remain intact.')
            for target, expected in ((foreign, 'deny'), (self.root / 'docs', 'allow')):
                with self.subTest(target=target, expected=expected):
                    link = self.root / 'read-junction'
                    created = subprocess.run(['cmd.exe', '/d', '/c', 'mklink', '/J',
                        str(link), str(target)], capture_output=True, text=True,
                        check=False, timeout=15)
                    try:
                        self.assertEqual(0, created.returncode, created.stdout + created.stderr)
                        self.assertTrue(link.is_junction())
                        self.assertEqual(target, link.resolve())
                        for verb in ('Get-Content', 'Get-Item', 'Test-Path', 'Get-ChildItem'):
                            for name in ('', 'synthetic.txt', 'missing.txt'):
                                with self.subTest(verb=verb, name=name):
                                    self.assertEqual(expected, self.shell(
                                        f"{verb} -LiteralPath '{link / name}'"))
                    finally:
                        if link.is_junction():
                            self.assertEqual(self.root, link.parent.resolve())
                            link.rmdir()  # Remove this fixture link only, never its target.
                    self.assertFalse(link.exists())
                    self.assertEqual(b'Synthetic external target must remain intact.', marker.read_bytes())

    def test_repeated_workflow_snapshots_never_start_nli_inference(self):
        for filename in ('requirements.json', 'catalog.json'):
            (self.root / 'config' / filename).write_bytes((ROOT / 'config' / filename).read_bytes())
        self.state['nli_source_file'] = str(self.root / 'explicit-source.txt')
        with patch('guardrails_local.provenance_nli.check_nli', side_effect=AssertionError('Repeated snapshot must not infer')) as checker:
            report = workflow_validators.validate_answer(self.root, self.state,
                                                        'Arbeitsstatus: OFFEN\nBerlin.')
        checker.assert_not_called()
        self.assertEqual('SKIPPED', report['validators']['ProvenanceNLI']['status'])

    def setUp(self):
        self.assertIsNotNone(workflow, 'The deterministic workflow guard is missing')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        (self.root / 'config').mkdir()
        (self.root / 'docs').mkdir()
        original = b'Keep original instructions and require actual completion evidence.'
        (self.root / 'docs/ORIGINALAUFTRAG.txt').write_bytes(original)
        self.policy_path = self.root / 'config/workflow-policy.json'
        self.policy = dict(version=1, source_sha256=hashlib.sha256(original).hexdigest(),
                           minimum_tests=1, decisions=[dict(id='SCOPED_WORK',
                           description='Only authorized project edits; no arbitrary execution.',
                           source='docs/ORIGINALAUFTRAG.txt')])
        self.policy_path.write_text(json.dumps(self.policy), encoding='utf-8')
        self.state = dict(session_id=SESSION, task_id=TASK, task='Implement the authorized change.',
                          task_sha256=hashlib.sha256(b'Implement the authorized change.').hexdigest(),
                          latest_turn_id=TURN, original_turn_id=TURN)
        self.directory = self.root / 'work/codex/sessions' / SESSION / 'tasks' / TASK
        self.directory.mkdir(parents=True)
        self.state['task_file'] = str(self.directory / 'original-task.txt')
        Path(self.state['task_file']).write_text(self.state['task'], encoding='utf-8')

    def decision(self, name, args, **extra):
        return workflow.tool_decision(self.root, self.state, dict(tool_name=name,
                    tool_input=args, turn_id=TURN, cwd=str(self.root), **extra))

    def shell(self, command):
        return self.decision('Bash', dict(command=command))['hookSpecificOutput']['permissionDecision']

    def test_unknown_shell_is_denied_before_execution(self):
        marker = self.root / 'should-never-exist'
        self.assertEqual(self.shell(f"New-Item -LiteralPath '{marker}'"), 'deny')
        self.assertFalse(marker.exists())

    def test_known_read_does_not_allow_a_second_command_or_expression(self):
        safe = f"Get-Content -LiteralPath '{self.root / 'docs/ORIGINALAUFTRAG.txt'}'"
        self.assertEqual(self.shell(safe), 'allow')
        for suffix in ('; Remove-Item x', '\nRemove-Item x', ' | Invoke-Expression', ' && whoami'):
            with self.subTest(suffix=suffix):
                self.assertEqual(self.shell(safe + suffix), 'deny')
        self.assertEqual(self.shell('Get-Content -LiteralPath "$(whoami)"'), 'deny')

    def test_project_patch_allowed_but_foreign_path_and_audit_forgery_denied(self):
        template = '*** Begin Patch\n*** Add File: {}\n+hello\n*** End Patch'
        for path, expected in ((self.root / 'new.py', 'allow'),
                               (self.root.parent / 'foreign.py', 'deny'),
                               (self.directory / 'workflow-check.json', 'deny'),
                               (self.root / 'logs/existing-audit.jsonl', 'deny'),
                               (self.root / '.git/config', 'deny'),
                               (self.policy_path, 'deny')):
            with self.subTest(path=path):
                result = self.decision('apply_patch', dict(command=template.format(path)))
                self.assertEqual(result['hookSpecificOutput']['permissionDecision'], expected)

    def test_patch_traversal_delete_move_and_unparsed_input_cannot_bypass_scope(self):
        bodies = [f'*** Delete File: {self.root / "a.py"}',
                  f'*** Update File: {self.root / "a.py"}\n*** Move to: {self.root / "b.py"}',
                  '*** Add File: ../outside.py\n+x', 'not a patch']
        for body in bodies:
            with self.subTest(body=body):
                result = self.decision('apply_patch', dict(command=body))
                self.assertEqual(result['hookSpecificOutput']['permissionDecision'], 'deny')

    def test_task_or_policy_drift_cannot_silently_replace_contract(self):
        workflow.ensure_contract(self.root, self.state)
        self.policy['minimum_tests'] = 2
        self.policy_path.write_text(json.dumps(self.policy), encoding='utf-8')
        with self.assertRaises(ValueError):
            workflow.ensure_contract(self.root, self.state)

    def test_missing_or_old_test_evidence_cannot_complete_work(self):
        self.assertEqual(workflow.completion_report(self.root, self.state,
                         'Arbeitsstatus: ABGESCHLOSSEN\nFertig.')['status'], 'FAIL')
        self.assertEqual(workflow.completion_report(self.root, self.state,
                         'Arbeitsstatus: OFFEN\nNoch nicht abgenommen.')['status'], 'PASS')
        self.assertEqual(workflow.completion_report(self.root, self.state,
                         'Alles erledigt.')['status'], 'UNVERIFIED')

    def make_suite(self, failing=False):
        tests = self.root / 'tests'
        tests.mkdir(exist_ok=True)
        (tests / 'test_real.py').write_text('import unittest\nclass Real(unittest.TestCase):\n'
             f'    def test_actual_result(self): self.assertEqual(2 + 2, {5 if failing else 4})\n', encoding='utf-8')

    def test_real_cpu_result_can_complete_only_same_task_and_unchanged_tree(self):
        self.make_suite()
        evidence = workflow.run_checks(self.root, self.state)
        self.assertEqual(evidence['status'], 'PASS')
        self.assertEqual(evidence['test_count'], 1)
        self.assertEqual(workflow.completion_report(self.root, self.state,
                          'Arbeitsstatus: ABGESCHLOSSEN\nGeprüft.')['status'], 'PASS')
        (self.root / 'new.py').write_text('changed after tests', encoding='utf-8')
        self.assertEqual(workflow.completion_report(self.root, self.state,
                          'Arbeitsstatus: ABGESCHLOSSEN\nGeprüft.')['status'], 'FAIL')

    def test_failed_or_empty_suite_never_proves_completion(self):
        self.make_suite(failing=True)
        self.assertEqual(workflow.run_checks(self.root, self.state)['status'], 'FAIL')
        self.assertEqual(workflow.completion_report(self.root, self.state,
                          'Arbeitsstatus: ABGESCHLOSSEN')['status'], 'FAIL')
        (self.root / 'tests/test_real.py').unlink()
        empty = workflow.run_checks(self.root, self.state)
        # This installed unittest exits nonzero for an empty suite: preserve FAIL.
        self.assertEqual(empty['status'], 'FAIL', Path(empty['output_path']).read_text())

    def test_fixed_runner_allowed_but_extra_python_code_denied(self):
        command = f'& "{sys.executable}" "{self.root / "workflow-check.py"}" --session-id "{SESSION}" --run-tests'
        self.assertEqual(self.shell(command), 'allow')
        self.assertEqual(self.shell(command + ' -c "print(1)"'), 'deny')

    def test_wrong_turn_cannot_reuse_current_task_authority(self):
        r = workflow.tool_decision(self.root, self.state, dict(tool_name='Bash',
                tool_input=dict(command="Get-Content -LiteralPath '/tmp/x'"),
                cwd=str(self.root), turn_id='44444444-4444-4444-8444-444444444444'))
        self.assertEqual(r['hookSpecificOutput']['permissionDecision'], 'deny')

    def test_nested_source_named_like_runtime_directory_invalidates_snapshot(self):
        for name in ('logs', 'work', '.venv'):
            with self.subTest(name=name):
                path = self.root / 'src' / name / 'feature.py'
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('value = 1', encoding='utf-8')
                before = workflow.tree_snapshot(self.root)
                path.write_text('value = 2', encoding='utf-8')
                self.assertNotEqual(workflow.tree_snapshot(self.root), before)

    def test_guardrails_instruction_validator_rejects_missing_required_status(self):
        self.assertIsNotNone(workflow_validators, 'Guardrails-native workflow validators are missing')
        from guardrails_local.validator import OfflineGuard
        guard = OfflineGuard(use_server=False).use(workflow_validators.InstructionCompliance(on_fail='noop'))
        result = guard.validate('Alles erledigt.', metadata=dict(root=self.root, state=self.state), num_reasks=0)
        self.assertFalse(result.validation_passed)

        valid = guard.validate('Arbeitsstatus: OFFEN\nNoch offen.', metadata=dict(root=self.root, state=self.state), num_reasks=0)
        self.assertTrue(valid.validation_passed)

    def test_guardrails_decision_validator_rejects_disallowed_action(self):
        self.assertIsNotNone(workflow_validators, 'Guardrails-native workflow validators are missing')
        from guardrails_local.validator import OfflineGuard
        guard = OfflineGuard(use_server=False).use(workflow_validators.DecisionConsistency(on_fail='noop'))
        payload = dict(tool_name='Bash', tool_input=dict(command='Install-Module something'), turn_id=TURN)
        result = guard.validate(json.dumps(payload), metadata=dict(root=self.root, state=self.state, action=True), num_reasks=0)
        self.assertFalse(result.validation_passed)

        payload['tool_input']['command'] = f"Get-Content -LiteralPath '{self.root / 'docs/ORIGINALAUFTRAG.txt'}'"
        valid = guard.validate(json.dumps(payload), metadata=dict(root=self.root, state=self.state, action=True), num_reasks=0)
        self.assertTrue(valid.validation_passed)

    def test_guardrails_completion_validator_rejects_unproven_done(self):
        self.assertIsNotNone(workflow_validators, 'Guardrails-native workflow validators are missing')
        from guardrails_local.validator import OfflineGuard
        guard = OfflineGuard(use_server=False).use(workflow_validators.CompletionEvidence(on_fail='noop'))
        result = guard.validate('Arbeitsstatus: ABGESCHLOSSEN', metadata=dict(root=self.root, state=self.state), num_reasks=0)
        self.assertFalse(result.validation_passed)

        valid = guard.validate('Arbeitsstatus: OFFEN', metadata=dict(root=self.root, state=self.state), num_reasks=0)
        self.assertTrue(valid.validation_passed)


if __name__ == '__main__':
    unittest.main()
