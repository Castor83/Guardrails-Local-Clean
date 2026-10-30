"""Installation admission and artifact locking, without installing anything."""
import importlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from guardrails_local import workflow
try:
    setup = importlib.import_module('guardrails_local.evals_setup')
except ModuleNotFoundError:
    setup = None


class EvalsSetupTests(unittest.TestCase):
    def test_setup_actions_require_current_workflow_permission(self):
        session = '11111111-1111-4111-8111-111111111111'
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config_path = root / 'work/codex/config.json'
            config_path.parent.mkdir(parents=True)
            state = dict(session_id=session, task_id='22222222-2222-4222-8222-222222222222')
            contract = dict(decisions=[dict(id='NO_NEW_RUNTIME', description=setup.OPERATOR_RULE)],
                            policy_sha256='a' * 64)
            for settings in ({}, dict(enabled=False, session_ids=[session], critic_enabled=False),
                    dict(enabled=True, session_ids=[session], critic_enabled=False, workflow_session_ids=[]),
                    dict(enabled=True, session_ids=[], critic_enabled=False, workflow_session_ids=[])):
                config_path.write_text(json.dumps(settings), encoding='utf-8')
                for action in setup.ACTIONS:
                    with self.subTest(settings=settings, action=action), \
                            patch.object(setup, 'ensure_contract', return_value=contract) as ensure, \
                            patch.object(setup, '_inventory', return_value={}) as inventory, \
                            patch.object(setup, '_resolve', return_value=dict(status='RESOLVED')) as resolve, \
                            patch.object(setup, '_install', return_value=dict(status='INSTALLED')) as install, \
                            patch.object(setup, '_download_model', return_value=dict(status='DOWNLOADED')) as download, \
                            patch.object(setup, '_run', return_value='log') as run, \
                            patch.object(setup, '_atomic_json') as write, \
                            patch('guardrails_local.provenance_nli.smoke_nli', return_value={}) as nli, \
                            patch('guardrails_local.deepeval_adapter.run_deepeval_smoke', return_value={}) as deepeval:
                        with self.assertRaises(ValueError):
                            setup.run_action(root, state, action)
                        for effect in (ensure, inventory, resolve, install, download, run, write, nli, deepeval):
                            effect.assert_not_called()
            self.assertFalse((config_path.parent / 'sessions').exists())

    def test_only_named_setup_actions_for_this_session_are_admitted(self):
        state = {'session_id': '11111111-1111-4111-8111-111111111111'}
        prefix = f'& "{sys.executable}" "{ROOT / "setup-local-evals.py"}" --session-id "{state["session_id"]}" --action '
        for action in ('inspect', 'resolve', 'install', 'download-model', 'smoke-nli', 'smoke-deepeval', 'check'):
            with self.subTest(action=action):
                self.assertTrue(workflow._shell_allowed(ROOT, state, prefix + action))
        for action in ('pip', 'install --user', 'install --target C:/foreign', 'install; whoami'):
            with self.subTest(action=action):
                self.assertFalse(workflow._shell_allowed(ROOT, state, prefix + action))
        self.assertFalse(workflow._shell_allowed(ROOT, state, (prefix + 'install').replace(state['session_id'], '22222222-2222-4222-8222-222222222222')))

    def test_existing_controller_is_never_an_install_target(self):
        self.assertIsNotNone(setup, 'Controlled evaluation setup is missing')
        with tempfile.TemporaryDirectory() as directory:
            target = setup.runtime_python(Path(directory))
            self.assertTrue(target.is_relative_to(Path(directory).resolve() / 'work' / 'evals-runtime'))
            self.assertNotEqual(target, Path(sys.executable))

    def test_resolved_artifacts_require_https_official_hosts_and_hashes(self):
        self.assertIsNotNone(setup, 'Controlled evaluation setup is missing')
        record = {'metadata': {'name': 'example-dependency', 'version': '1.2.3'},
                  'download_info': {'url': 'https://files.pythonhosted.org/packages/abc/example.whl',
                                    'archive_info': {'hashes': {'sha256': 'a' * 64}}}}
        locked = setup.locked_requirements({'install': [record]})
        self.assertIn('https://files.pythonhosted.org/packages/abc/example.whl', locked)
        self.assertIn('--hash=sha256:' + 'a' * 64, locked)
        for url in ('http://files.pythonhosted.org/example.whl', 'https://example.org/example.whl',
                    'https://files.pythonhosted.org.evil.invalid/example.whl', 'file:///C:/foreign.whl'):
            with self.subTest(url=url):
                changed = json.loads(json.dumps(record))
                changed['download_info']['url'] = url
                with self.assertRaises(ValueError):
                    setup.locked_requirements({'install': [changed]})
        del record['download_info']['archive_info']['hashes']['sha256']
        with self.assertRaises(ValueError):
            setup.locked_requirements({'install': [record]})

    def test_duplicate_or_injectable_distribution_records_are_rejected(self):
        self.assertIsNotNone(setup, 'Controlled evaluation setup is missing')
        record = {'metadata': {'name': 'example', 'version': '1.0'},
                  'download_info': {'url': 'https://files.pythonhosted.org/example.whl',
                                    'archive_info': {'hashes': {'sha256': 'b' * 64}}}}
        with self.assertRaises(ValueError):
            setup.locked_requirements({'install': [record, record]})
        record['metadata']['name'] = 'example\n--extra-index-url=https://example.org'
        with self.assertRaises(ValueError):
            setup.locked_requirements({'install': [record]})
