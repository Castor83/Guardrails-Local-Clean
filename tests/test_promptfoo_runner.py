"""Bounded Promptfoo runner contracts; no models or global package operations."""
import json
import copy
import hashlib
import os
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
import shutil
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
try:
    from guardrails_local import promptfoo_runner as runner
except ImportError:
    runner = None


class PromptfooRunnerTests(unittest.TestCase):
    def summary(self):
        cases = json.loads((ROOT / 'regressions/promptfoo/cases.json').read_text(encoding='utf-8'))
        config = json.loads((ROOT / 'regressions/promptfoo/config.json').read_text(encoding='utf-8'))
        calls = [(0, 0, 1), (0, 0, 1), (1, 0, 1), (0, 0, 1), (2, 1, 2), (1, 0, 1), (1, 0, 1), (3, 2, 3)]
        rows = []
        for case, entry, (evaluations, corrections, attempts) in zip(cases, config['tests'], calls):
            case_hash = hashlib.sha256(json.dumps(case, ensure_ascii=False, sort_keys=True,
                separators=(',', ':')).encode('utf-8')).hexdigest()
            output = dict(case_id=case['id'], case_sha256=case_hash, final_status=case['expected_status'],
                evaluator_calls=evaluations, corrector_calls=corrections, attempt_count=attempts,
                fixture=True, native_metric=False, model_called=False, released_text=None, verified=False,
                original_contract_preserved=True, pipeline_framework='guardrails_local.quality_pipeline', pipeline_error=None)
            assertions = config['defaultTest']['assert'] + entry.get('assert', [])
            rows.append(dict(vars=copy.deepcopy(entry['vars']), testCase=dict(vars=copy.deepcopy(entry['vars']),
                assert_=assertions), prompt=dict(raw=case['id']), success=True,
                gradingResult=dict(pass_=True, score=1, componentResults=[dict(pass_=True, assertion=a) for a in assertions]),
                response=dict(output=json.dumps(output))))
            rows[-1]['testCase']['assert'] = rows[-1]['testCase'].pop('assert_')
            grading = rows[-1]['gradingResult']
            grading['pass'] = grading.pop('pass_')
            for component in grading['componentResults']:
                component['pass'] = component.pop('pass_')
        return dict(results=dict(stats=dict(successes=8, failures=0, errors=0), results=rows))

    def test_eight_duplicate_pass_cases_are_not_complete(self):
        result = self.summary()
        result['results']['results'] = [result['results']['results'][0]] * 8
        with self.assertRaises(ValueError):
            runner.checked_summary(result)

    def test_fixed_case_contract_and_result_ids_must_match(self):
        valid = self.summary()
        self.assertEqual(8, runner.checked_summary(valid)['passed'])
        for mutation in ('unknown', 'missing', 'extra', 'status', 'output-id', 'calls', 'hash', 'assertion'):
            result = copy.deepcopy(valid)
            row = result['results']['results'][0]
            if mutation == 'unknown':
                row['vars']['case_id'] = 'unknown'
            elif mutation == 'missing':
                result['results']['results'].pop()
            elif mutation == 'extra':
                result['results']['results'].append(copy.deepcopy(row))
            elif mutation == 'status':
                row['testCase']['vars']['expected_status'] = 'PASS'
            elif mutation == 'assertion':
                row['gradingResult']['componentResults'] = []
            else:
                output = json.loads(row['response']['output'])
                output[{'output-id': 'case_id', 'calls': 'evaluator_calls', 'hash': 'case_sha256'}[mutation]] = 'wrong'
                row['response']['output'] = json.dumps(output)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                runner.checked_summary(result)

    def test_artifact_drift_invalidates_regression_proof(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shutil.copytree(ROOT / 'regressions/promptfoo', root / 'regressions/promptfoo')
            cli = root / 'work/promptfoo-runtime/node_modules/promptfoo/dist/src/entrypoint.js'
            cli.parent.mkdir(parents=True)
            cli.touch()
            cases_path = root / 'regressions/promptfoo/cases.json'
            def drifting_run(_root, command, label, **kwargs):
                cases_path.write_text('[]', encoding='utf-8')
                Path(command[command.index('--output') + 1]).write_text(json.dumps(self.summary()), encoding='utf-8')
                return 0, 'synthetic-cli.log'
            with patch.object(runner, '_validate_lock', return_value='synthetic-lock'), \
                    patch.object(runner, '_run', side_effect=drifting_run) as execute:
                report = runner.run_regressions(root)
            self.assertEqual(1, execute.call_count)
            self.assertEqual('ERROR', report['status'])
            with patch.object(runner, '_validate_lock', return_value='synthetic-lock'), \
                    patch.object(runner, '_run', return_value=(1, 'not-run')) as execute:
                runner.run_regressions(root)
            execute.assert_not_called()

    def setUp(self):
        self.assertIsNotNone(runner, 'The real Promptfoo regression runner is missing.')

    def test_environment_has_no_keys_or_global_home_and_disables_remote_features(self):
        with tempfile.TemporaryDirectory() as area:
            env = runner.build_environment(Path(area), {'PATH': os.environ.get('PATH', ''),
                'SystemRoot': os.environ.get('SystemRoot', ''), 'OPENAI_API_KEY': 'never-propagate',
                'PROMPTFOO_API_KEY': 'never-propagate', 'NODE_OPTIONS': '--require evil.js',
                'PYTHONPATH': 'foreign path', 'HTTPS_PROXY': 'http://proxy:1234'})
            self.assertNotIn('OPENAI_API_KEY', env)
            self.assertNotIn('PROMPTFOO_API_KEY', env)
            self.assertNotIn('PYTHONPATH', env)
            self.assertNotIn('HTTPS_PROXY', env)
            self.assertNotIn('--require', env.get('NODE_OPTIONS', ''))
            self.assertEqual('1', env['PROMPTFOO_DISABLE_TELEMETRY'])
            self.assertEqual('true', env['PROMPTFOO_DISABLE_UPDATE'])
            self.assertEqual('false', env['PROMPTFOO_CACHE_ENABLED'])
            self.assertEqual('true', env['PROMPTFOO_DISABLE_REMOTE_GENERATION'])
            self.assertEqual(sys.executable, env['PROMPTFOO_PYTHON'])
            self.assertTrue(Path(env['USERPROFILE']).is_relative_to(Path(area)))

    def test_eval_command_is_fixed_single_concurrency_without_cache_share_or_database(self):
        with tempfile.TemporaryDirectory() as area:
            command = runner.evaluation_command(Path(area), Path(area) / 'runs/result.json')
            self.assertIn('eval', command)
            self.assertEqual('1', command[command.index('--max-concurrency') + 1])
            for option in ('--no-cache', '--no-share', '--no-write', '--no-progress-bar'):
                self.assertIn(option, command)
            self.assertNotIn('npx', command)
            self.assertNotIn('--remote', command)

    def test_locked_installation_is_local_and_refuses_scripts_or_floating_dependencies(self):
        package = json.loads((ROOT / 'tools/promptfoo/package.json').read_bytes())
        self.assertEqual('0.124.1', package['dependencies']['promptfoo'])
        command = runner.installation_command(ROOT)
        for argument in ('ci', '--ignore-scripts', '--omit=optional', '--no-audit', '--no-fund'):
            self.assertIn(argument, command)
        self.assertNotIn('-g', command)
        self.assertNotIn('--global', command)

    def test_no_zero_case_or_failed_report_can_be_reported_as_passing(self):
        for report in ({'results': {'stats': {'successes': 0, 'failures': 0, 'errors': 0}}},
                       {'results': {'stats': {'successes': 8, 'failures': 1, 'errors': 0}}},
                       {'results': {'stats': {'successes': 8, 'failures': 0, 'errors': 1}}}):
            with self.subTest(report=report), self.assertRaises(ValueError):
                runner.checked_summary(report, expected=8)
        with self.assertRaises(ValueError):
            runner.checked_summary({'results': {'stats': {'successes': 8, 'failures': 0, 'errors': 0}}}, expected=8)

    def test_missing_installation_is_reported_without_implicit_install(self):
        with tempfile.TemporaryDirectory() as area:
            report = runner.run_regressions(Path(area))
        self.assertEqual('ERROR', report['status'])
        self.assertFalse(report['model_called'])
        self.assertFalse(report['global_installation'])

    def test_python_provider_exercises_real_pipeline_with_all_fixed_expected_outcomes(self):
        program = '''import importlib.util,json,pathlib
p=pathlib.Path("regressions/promptfoo/provider.py").resolve()
s=importlib.util.spec_from_file_location("fixture_provider",p)
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
cases=json.loads(p.with_name("cases.json").read_text(encoding="utf-8"))
outputs=[]
for c in cases:
 r=json.loads(m.call_api(c["id"],{}, {"vars":{"case_id":c["id"]}})["output"])
 outputs.append({"case":c["id"],"expected":c["expected_status"],"actual":r["final_status"],"binding":r["original_contract_preserved"],"released":r["released_text"]})
print(json.dumps(outputs))'''
        completed = subprocess.run([sys.executable, '-c', program], cwd=ROOT,
                                  capture_output=True, text=True, check=False, timeout=45)
        self.assertEqual(0, completed.returncode, completed.stderr)
        results = json.loads(completed.stdout)
        self.assertEqual(8, len(results))
        for result in results:
            with self.subTest(case=result['case']):
                self.assertEqual(result['expected'], result['actual'])
                self.assertTrue(result['binding'])
                self.assertIsNone(result['released'])


if __name__ == '__main__':
    unittest.main()
