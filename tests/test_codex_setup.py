import json
from contextlib import redirect_stdout
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
try:
    from guardrails_local import codex_setup
except ImportError:
    codex_setup = None

SESSION = '01a14629-82fe-7191-994d-1e5cef199406'


class CodexSetupTests(unittest.TestCase):
    def test_evidence_is_scoped_to_explicit_session(self):
        other = '33333333-3333-4333-8333-333333333333'
        codex_setup.configure(self.root, self.home, SESSION,
            critic_enabled=False, action_evidence_enabled=True)
        result = codex_setup.configure(self.root, self.home, other, critic_enabled=False)
        config = json.loads((self.root / 'work/codex/config.json').read_text(encoding='utf-8'))
        self.assertEqual([SESSION], config.get('action_evidence_session_ids'))
        self.assertIs(result['action_evidence_enabled'], False)
        self.assertEqual([SESSION, other], config['session_ids'])

    def test_optional_action_evidence_adds_unfiltered_handler_and_exact_backup(self):
        foreign_group = {'matcher': '^Bash$', 'hooks': [
            {'type': 'command', 'command': 'foreign recorder', 'timeout': 2}]}
        self.original['hooks']['PostToolUse'] = [foreign_group]
        self.hooks.write_text(json.dumps(self.original), encoding='utf-8')
        before = self.hooks.read_bytes()
        result = codex_setup.configure(self.root, self.home, SESSION,
            critic_enabled=False, action_evidence_enabled=True)
        hooks = json.loads(self.hooks.read_text(encoding='utf-8'))['hooks']
        self.assertEqual(hooks['PostToolUse'][0], foreign_group)
        self.assertEqual(len(hooks['PostToolUse']), 2)
        recorder = hooks['PostToolUse'][1]
        self.assertNotIn('matcher', recorder)
        self.assertEqual(len(recorder['hooks']), 1)
        self.assertEqual(recorder['hooks'][0]['command'],
                         hooks['UserPromptSubmit'][0]['hooks'][0]['command'])
        self.assertEqual(recorder['hooks'][0]['type'], 'command')
        self.assertIs(result['action_evidence_enabled'], True)
        self.assertIs(result['trust_changed'], False)
        self.assertIs(result['live_hook_execution_verified'], False)
        self.assertEqual(Path(result['backup_path']).read_bytes(), before)
        config = json.loads((self.root / 'work/codex/config.json').read_text(encoding='utf-8'))
        self.assertIs(config['critic_enabled'], False)
        self.assertNotIn('workflow_session_ids', config)

    def test_action_evidence_is_opt_in_and_repeat_install_is_idempotent(self):
        self.configure()
        self.assertNotIn('PostToolUse', json.loads(self.hooks.read_text(encoding='utf-8'))['hooks'])
        codex_setup.configure(self.root, self.home, SESSION,
            critic_enabled=True, action_evidence_enabled=True)
        before = self.hooks.read_bytes()
        stamp = self.hooks.stat().st_mtime_ns
        result = codex_setup.configure(self.root, self.home, SESSION,
            critic_enabled=True, action_evidence_enabled=True)
        self.assertEqual(self.hooks.read_bytes(), before)
        self.assertEqual(self.hooks.stat().st_mtime_ns, stamp)
        self.assertIs(result['hooks_changed'], False)
        self.assertIsNone(result['backup_path'])
        default_result = self.configure()
        self.assertEqual(self.hooks.read_bytes(), before)
        self.assertIs(default_result['action_evidence_enabled'], True)

    def test_scoped_existing_recorder_is_rejected_without_enrollment_or_hook_changes(self):
        codex_setup.configure(self.root, self.home, SESSION,
            critic_enabled=True, action_evidence_enabled=True)
        config = self.root / 'work/codex/config.json'
        config_before = config.read_bytes()
        original = json.loads(self.hooks.read_text(encoding='utf-8'))
        for matcher in ('^Bash$', '.*', '', None):
            with self.subTest(matcher=matcher):
                modified = json.loads(json.dumps(original))
                modified['hooks']['PostToolUse'][0]['matcher'] = matcher
                self.hooks.write_text(json.dumps(modified), encoding='utf-8')
                before = self.hooks.read_bytes()
                with self.assertRaises(ValueError):
                    codex_setup.configure(self.root, self.home,
                        '01a145a9-0a66-7320-8755-c78b5cbf17da',
                        critic_enabled=True, action_evidence_enabled=True)
                self.assertEqual(self.hooks.read_bytes(), before)
                self.assertEqual(config.read_bytes(), config_before)

    def test_duplicate_recorder_is_rejected_instead_of_multiplying_receipts(self):
        codex_setup.configure(self.root, self.home, SESSION,
            critic_enabled=True, action_evidence_enabled=True)
        hooks = json.loads(self.hooks.read_text(encoding='utf-8'))
        hooks['hooks']['PostToolUse'].append(hooks['hooks']['PostToolUse'][0])
        self.hooks.write_text(json.dumps(hooks), encoding='utf-8')
        before = self.hooks.read_bytes()
        with self.assertRaises(ValueError):
            codex_setup.configure(self.root, self.home, SESSION,
                critic_enabled=True, action_evidence_enabled=True)
        self.assertEqual(self.hooks.read_bytes(), before)

    def test_action_evidence_conflict_preserves_existing_config_and_foreign_hook(self):
        self.configure()
        config = self.root / 'work/codex/config.json'
        config_before = config.read_bytes()
        writer = codex_setup._atomic_bytes
        foreign = b'{"hooks": {}, "concurrent_change": true}'
        def conflicting_writer(path, content):
            writer(path, content)
            if path.name == 'config.json':
                self.hooks.write_bytes(foreign)
        with patch.object(codex_setup, '_atomic_bytes', side_effect=conflicting_writer):
            with self.assertRaises(ValueError):
                codex_setup.configure(self.root, self.home,
                    '01a145a9-0a66-7320-8755-c78b5cbf17da',
                    critic_enabled=True, action_evidence_enabled=True)
        self.assertEqual(self.hooks.read_bytes(), foreign)
        self.assertEqual(config.read_bytes(), config_before)

    def test_action_evidence_cli_installs_optional_recorder_into_temporary_home(self):
        configure = codex_setup.configure
        def isolated_configure(_root, codex_home, session_id, **options):
            return configure(self.root, codex_home, session_id, **options)
        output = io.StringIO()
        with patch.object(codex_setup, 'configure', side_effect=isolated_configure), redirect_stdout(output):
            exit_code = codex_setup.main(['--session-id', SESSION,
                '--codex-home', str(self.home), '--offline', '--action-evidence'])
        self.assertEqual(exit_code, 0)
        self.assertIs(json.loads(output.getvalue())['action_evidence_enabled'], True)
        self.assertIn('PostToolUse', json.loads(self.hooks.read_text(encoding='utf-8'))['hooks'])

    def test_workflow_setup_adds_scoped_guard_and_preserves_existing_mode(self):
        self.configure()
        self.prepare_workflow()
        codex_setup.configure(self.root, self.home,
            '01a145a9-0a66-7320-8755-c78b5cbf17da', critic_enabled=True, workflow_enabled=True)
        config = json.loads((self.root / 'work/codex/config.json').read_text(encoding='utf-8'))
        self.assertEqual(config['workflow_session_ids'], ['01a145a9-0a66-7320-8755-c78b5cbf17da'])
        hooks = json.loads(self.hooks.read_text(encoding='utf-8'))['hooks']
        self.assertEqual(hooks['PreToolUse'][0]['matcher'], '^(Bash|apply_patch)$')
        self.assertEqual(len(hooks['Stop']), 2)
        self.assertEqual(hooks['Stop'][0], self.original['hooks']['Stop'][0])
        before = self.hooks.read_bytes()
        codex_setup.configure(self.root, self.home,
            '01a145a9-0a66-7320-8755-c78b5cbf17da', critic_enabled=True, workflow_enabled=True)
        self.assertEqual(self.hooks.read_bytes(), before)

    def prepare_workflow(self):
        import shutil
        source = Path(__file__).resolve().parents[1]
        (self.root / 'config').mkdir(exist_ok=True)
        (self.root / 'docs').mkdir(exist_ok=True)
        shutil.copyfile(source / 'config/workflow-policy.json', self.root / 'config/workflow-policy.json')
        shutil.copyfile(source / 'docs/ORIGINALAUFTRAG.txt', self.root / 'docs/ORIGINALAUFTRAG.txt')
        (self.root / 'workflow-check.py').write_text('# fixed runner', encoding='utf-8')

    def test_workflow_missing_files_cannot_install_a_nonfunctional_gate(self):
        before = self.hooks.read_bytes()
        with self.assertRaises(ValueError):
            codex_setup.configure(self.root, self.home, SESSION, critic_enabled=True, workflow_enabled=True)
        self.assertEqual(self.hooks.read_bytes(), before)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'project with spaces'
        self.home = Path(self.temp.name) / 'codex'
        self.root.mkdir()
        self.home.mkdir()
        (self.root / 'codex-hook.py').write_text('# adapter', encoding='utf-8')
        self.original = {'description': 'keep me', 'hooks': {
            'SessionStart': [{'matcher': '^compact$', 'hooks': [
                {'type': 'command', 'command': 'existing handoff', 'timeout': 10}]}],
            'Stop': [{'hooks': [{'type': 'command', 'command': 'unrelated', 'timeout': 4}]}]}}
        self.hooks = self.home / 'hooks.json'
        self.hooks.write_text(json.dumps(self.original), encoding='utf-8')

    def configure(self, session=SESSION):
        self.assertIsNotNone(codex_setup, 'The Codex integration installer is missing')
        return codex_setup.configure(self.root, self.home, session, critic_enabled=True)

    def test_install_preserves_handoff_and_foreign_hooks_and_saves_exact_backup(self):
        before = self.hooks.read_bytes()
        result = self.configure()
        after = json.loads(self.hooks.read_text(encoding='utf-8'))
        self.assertEqual(after['description'], 'keep me')
        self.assertEqual(after['hooks']['SessionStart'], self.original['hooks']['SessionStart'])
        self.assertEqual(after['hooks']['Stop'][0], self.original['hooks']['Stop'][0])
        self.assertEqual(len(after['hooks']['Stop']), 2)
        self.assertEqual(len(after['hooks']['UserPromptSubmit']), 1)
        self.assertEqual(Path(result['backup_path']).read_bytes(), before)
        local = json.loads((self.root / 'work/codex/config.json').read_text(encoding='utf-8'))
        self.assertEqual(local['session_ids'], [SESSION])
        self.assertIs(local['critic_enabled'], True)
        self.assertIs(local['enabled'], True)

    def test_repeat_install_does_not_duplicate_hooks_or_rewrite_unchanged_file(self):
        self.configure()
        before = self.hooks.read_bytes()
        stamp = self.hooks.stat().st_mtime_ns
        self.configure()
        self.assertEqual(self.hooks.read_bytes(), before)
        self.assertEqual(self.hooks.stat().st_mtime_ns, stamp)

    def test_invalid_session_never_mutates_global_definition(self):
        self.assertIsNotNone(codex_setup, 'The Codex integration installer is missing')
        before = self.hooks.read_bytes()
        with self.assertRaises(ValueError):
            codex_setup.configure(self.root, self.home, '../another-project', critic_enabled=True)
        self.assertEqual(self.hooks.read_bytes(), before)
        self.assertFalse((self.root / 'work/codex/config.json').exists())

    def test_malformed_existing_hook_file_is_not_replaced(self):
        self.hooks.write_text('{broken', encoding='utf-8')
        self.assertIsNotNone(codex_setup, 'The Codex integration installer is missing')
        with self.assertRaises(ValueError):
            codex_setup.configure(self.root, self.home, SESSION, critic_enabled=True)
        self.assertEqual(self.hooks.read_text(encoding='utf-8'), '{broken')

    def test_invalid_existing_event_shape_is_not_silently_repaired(self):
        self.original['hooks']['Stop'] = {'unexpected': 'keep'}
        self.hooks.write_text(json.dumps(self.original), encoding='utf-8')
        self.assertIsNotNone(codex_setup, 'The Codex integration installer is missing')
        before = self.hooks.read_bytes()
        with self.assertRaises(ValueError):
            codex_setup.configure(self.root, self.home, SESSION, critic_enabled=True)
        self.assertEqual(self.hooks.read_bytes(), before)

    def test_other_interpreter_cannot_install_a_second_adapter(self):
        self.configure()
        before = self.hooks.read_bytes()
        with patch.object(codex_setup.sys, 'executable', r'C:\another-runtime\python.exe'):
            with self.assertRaises(ValueError):
                self.configure()
        self.assertEqual(self.hooks.read_bytes(), before)

    def test_adding_live_session_cannot_enable_critic_for_existing_offline_session(self):
        self.assertIsNotNone(codex_setup, 'The Codex integration installer is missing')
        codex_setup.configure(self.root, self.home, SESSION, critic_enabled=False)
        before = (self.root / 'work/codex/config.json').read_bytes()
        with self.assertRaises(ValueError):
            codex_setup.configure(self.root, self.home,
                                  '01a145a9-0a66-7320-8755-c78b5cbf17da', critic_enabled=True)
        self.assertEqual((self.root / 'work/codex/config.json').read_bytes(), before)

    def test_concurrent_hook_edit_is_preserved_and_our_config_write_is_rolled_back(self):
        self.assertIsNotNone(codex_setup, 'The Codex integration installer is missing')
        original_writer = codex_setup._atomic_bytes
        foreign = b'{"hooks": {}, "foreign_change": true}'
        def concurrent_writer(path, content):
            original_writer(path, content)
            if path.name == 'config.json':
                self.hooks.write_bytes(foreign)
        with patch.object(codex_setup, '_atomic_bytes', side_effect=concurrent_writer):
            with self.assertRaises(ValueError):
                self.configure()
        self.assertEqual(self.hooks.read_bytes(), foreign)
        self.assertFalse((self.root / 'work/codex/config.json').exists())

    def test_session_limit_cannot_install_an_unusable_adapter_configuration(self):
        self.assertIsNotNone(codex_setup, 'The Codex integration installer is missing')
        config = self.root / 'work/codex/config.json'
        config.parent.mkdir(parents=True)
        config.write_text(json.dumps({'enabled': True, 'critic_enabled': True,
                                      'session_ids': [str(uuid.uuid4()) for _ in range(16)]}), encoding='utf-8')
        before = config.read_bytes()
        with self.assertRaises(ValueError):
            self.configure()
        self.assertEqual(config.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
