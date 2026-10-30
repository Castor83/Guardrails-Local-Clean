"""Project-local genuine Promptfoo CLI regressions over the real quality pipeline.

All semantic evaluators in this regression corpus are labelled synthetic fixtures.
The harness tests control flow, never real model quality or live hook trust.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

VERSION = '0.124.1'
EXPECTED_CASES = 8
_ARTIFACT_PINS = {
    'cases.json': '50de4743f7c9e49c299259e848edd5d44a5352c8c162fbcc98b5cf08d39d2357',
    'config.json': 'e1dd0a47c3cf7c63f923316a231b8204c1fd6104ec8897584689990881a5adb3',
    'provider.py': '30897a58606969c7c6c779e831ffda47e0011a8b95ae82fab234ed221ec2553a',
    'offline.cjs': '7c02c0c3a7941606ce82a7f3815e367bb54a0dddcbeb0a956f5c4576b1af1fee',
}
_EXPECTED_CALLS = {
    'unbacked_chat_search': (0, 0, 1), 'wrong_chat_title': (0, 0, 1),
    'honest_uncertainty': (1, 0, 1), 'explicit_length_bound': (0, 0, 1),
    'preserve_contract_on_correction': (2, 1, 2), 'error_has_no_retry': (1, 0, 1),
    'unverified_has_no_retry': (1, 0, 1), 'correction_budget': (3, 2, 3),
}


def _canonical_hash(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


def _fixed_cases(root):
    path = Path(root) / 'regressions/promptfoo/cases.json'
    if path.stat().st_size > 65536:
        raise ValueError('Fixed cases exceed the input budget.')
    cases = json.loads(path.read_text(encoding='utf-8'))
    if _canonical_hash(cases) != _ARTIFACT_PINS['cases.json']:
        raise ValueError('Fixed case identities, inputs or expected outcomes changed.')
    return cases


def _artifact_contract(root):
    _fixed_cases(root)
    hashes = {}
    for name, expected in _ARTIFACT_PINS.items():
        path = Path(root) / 'regressions/promptfoo' / name
        if path.stat().st_size > 131072:
            raise ValueError('Regression artifact exceeds its budget.')
        content = path.read_text(encoding='utf-8')
        digest = (_canonical_hash(json.loads(content)) if name.endswith('.json') else
                  hashlib.sha256(content.encode('utf-8')).hexdigest())
        if digest != expected:
            raise ValueError('Pinned regression artifact changed: ' + name)
        hashes[name] = digest
    return hashes


def _runtime(root):
    root = Path(root).resolve()
    target = root / 'work/promptfoo-runtime'
    if not target.resolve().is_relative_to(root):
        raise ValueError('Promptfoo runtime must stay inside the project.')
    return target


def build_environment(root, parent=None):
    parent = os.environ if parent is None else parent
    runtime = _runtime(root)
    allowed = {'path', 'systemroot', 'windir', 'comspec', 'pathext', 'systemdrive',
               'processor_architecture', 'number_of_processors', 'temp', 'tmp'}
    env = {key: value for key, value in parent.items() if key.lower() in allowed and isinstance(value, str)}
    home = runtime / 'home'
    env.update(HOME=str(home), USERPROFILE=str(home), APPDATA=str(home / 'AppData/Roaming'),
        LOCALAPPDATA=str(home / 'AppData/Local'), CI='true', NO_COLOR='1', FORCE_COLOR='0',
        PROMPTFOO_DISABLE_TELEMETRY='1', PROMPTFOO_DISABLE_UPDATE='true',
        PROMPTFOO_CACHE_ENABLED='false', PROMPTFOO_DISABLE_REMOTE_GENERATION='true',
        PROMPTFOO_DISABLE_REDTEAM_REMOTE_GENERATION='true', PROMPTFOO_SELF_HOSTED='true',
        PROMPTFOO_DISABLE_TEMPLATE_ENV_VARS='true', PROMPTFOO_ENABLE_OTEL='false',
        PROMPTFOO_PYTHON=sys.executable, PYTHONIOENCODING='utf-8', PYTHONNOUSERSITE='1',
        OTEL_SDK_DISABLED='true', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
        PROMPTFOO_CONFIG_DIR=str(runtime / 'config'), PROMPTFOO_CACHE_PATH=str(runtime / 'cache'),
        PROMPTFOO_LOG_DIR=str(runtime / 'logs'), PROMPTFOO_ASSERTIONS_MAX_CONCURRENCY='1',
        PROMPTFOO_EVAL_TIMEOUT_MS='30000', PROMPTFOO_MAX_EVAL_TIME_MS='120000',
        PROMPTFOO_DISABLE_VAR_EXPANSION='true', NODE_OPTIONS='--use-system-ca --max-old-space-size=1536',
        DOTENV_PATH=str(runtime / 'empty.env'), DOTENV_CONFIG_PATH=str(runtime / 'empty.env'),
        NPM_CONFIG_USERCONFIG=str(runtime / 'empty.npmrc'),
        NPM_CONFIG_GLOBALCONFIG=str(runtime / 'empty-global.npmrc'),
        NPM_CONFIG_CACHE=str(runtime / 'npm-cache'), NPM_CONFIG_REGISTRY='https://registry.npmjs.org/',
        NPM_CONFIG_IGNORE_SCRIPTS='true', NPM_CONFIG_AUDIT='false', NPM_CONFIG_FUND='false',
        NPM_CONFIG_FETCH_RETRIES='0', NPM_CONFIG_FETCH_TIMEOUT='30000')
    return env


def _node_tools():
    node = shutil.which('node')
    npm = shutil.which('npm.cmd') or shutil.which('npm')
    if not node or not npm:
        raise ValueError('Existing Node and npm are required; this runner does not install them.')
    npm_cli = Path(npm).parent / 'node_modules/npm/bin/npm-cli.js'
    if not npm_cli.is_file():
        raise ValueError('Installed npm CLI JavaScript entrypoint is missing.')
    return str(Path(node).resolve()), str(npm_cli.resolve())


def installation_command(root):
    node, npm_cli = _node_tools()
    return [node, npm_cli, 'ci', '--prefix', str(_runtime(root)), '--ignore-scripts',
            '--omit=optional', '--no-audit', '--no-fund', '--registry=https://registry.npmjs.org/']


def evaluation_command(root, result_path):
    node, _ = _node_tools()
    cli = _runtime(root) / 'node_modules/promptfoo/dist/src/entrypoint.js'
    return [node, '--require', str(Path(root).resolve() / 'regressions/promptfoo/offline.cjs'), str(cli),
            'eval', '--config', str(Path(root).resolve() / 'regressions/promptfoo/config.json'),
            '--max-concurrency', '1', '--no-cache', '--no-share', '--no-write', '--no-progress-bar',
            '--no-table', '--output', str(result_path)]


def _json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def _run(root, command, label, *, timeout):
    runtime = _runtime(root)
    runtime.mkdir(parents=True, exist_ok=True)
    env = build_environment(root)
    for name in ('empty.env', 'empty.npmrc', 'empty-global.npmrc'):
        (runtime / name).write_bytes(b'')
    log = runtime / (label + '-' + uuid.uuid4().hex + '.txt')
    options = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
    with log.open('wb') as stream:
        done = subprocess.run(command, cwd=runtime, env=env, stdin=subprocess.DEVNULL,
            stdout=stream, stderr=subprocess.STDOUT, check=False, timeout=timeout, **options)
    return done.returncode, str(log)


def _validate_lock(root):
    tools = Path(root).resolve() / 'tools/promptfoo'
    package = json.loads((tools / 'package.json').read_bytes())
    lock_bytes = (tools / 'package-lock.json').read_bytes()
    lock = json.loads(lock_bytes)
    if package.get('dependencies', {}).get('promptfoo') != VERSION:
        raise ValueError('Promptfoo must have the fixed published version.')
    for path, info in lock.get('packages', {}).items():
        if path:
            if (not isinstance(info.get('integrity'), str)
                    or not str(info.get('resolved', '')).startswith('https://registry.npmjs.org/')):
                raise ValueError('Lock artifacts must have npm registry URLs and integrity hashes.')
    if lock.get('packages', {}).get('node_modules/promptfoo', {}).get('version') != VERSION:
        raise ValueError('The lock does not bind the fixed Promptfoo version.')
    return hashlib.sha256(lock_bytes).hexdigest()


def install_runtime(root):
    root = Path(root).resolve()
    runtime = _runtime(root)
    runtime.mkdir(parents=True, exist_ok=True)
    tools = root / 'tools/promptfoo'
    if not (tools / 'package-lock.json').is_file():
        # Generate the complete integrity lock before installation; no scripts.
        shutil.copyfile(tools / 'package.json', runtime / 'package.json')
        node, npm_cli = _node_tools()
        command = [node, npm_cli, 'install', '--package-lock-only', '--ignore-scripts',
                   '--omit=optional', '--no-audit', '--no-fund', '--registry=https://registry.npmjs.org/']
        code, log = _run(root, command, 'resolve', timeout=600)
        if code:
            raise RuntimeError('npm lock resolution failed; log: ' + log)
        shutil.copyfile(runtime / 'package-lock.json', tools / 'package-lock.json')
    lock_sha256 = _validate_lock(root)
    for filename in ('package.json', 'package-lock.json'):
        shutil.copyfile(tools / filename, runtime / filename)
    code, log = _run(root, installation_command(root), 'install', timeout=900)
    if code:
        raise RuntimeError('Project-local npm ci failed; log: ' + log)
    package = json.loads((runtime / 'node_modules/promptfoo/package.json').read_bytes())
    if package.get('version') != VERSION:
        raise ValueError('Installed Promptfoo version differs from locked version.')
    report = dict(status='INSTALLED', version=VERSION, runtime=str(runtime), lock_sha256=lock_sha256,
        install_log=log, ignore_scripts=True, optional_dependencies_omitted=True,
        global_installation=False, model_called=False, python_packages_installed=False,
        installed_at=datetime.now(timezone.utc).isoformat())
    _json(runtime / 'installation.json', report)
    return report


def checked_summary(result, *, expected=EXPECTED_CASES):
    if type(expected) is not int or expected != EXPECTED_CASES or not isinstance(result, dict):
        raise ValueError('Only the eight fixed regression cases can prove completion.')
    stats = result.get('results', {}).get('stats', {})
    successes, failures, errors = (stats.get(key) for key in ('successes', 'failures', 'errors'))
    if (type(successes) is not int or successes != expected or type(failures) is not int
            or failures or type(errors) is not int or errors):
        raise ValueError('Promptfoo regression count or failure/error totals do not prove a passing run.')
    root = Path(__file__).resolve().parents[2]
    cases = {case['id']: case for case in _fixed_cases(root)}
    config = json.loads((root / 'regressions/promptfoo/config.json').read_text(encoding='utf-8'))
    entries = {entry['vars']['case_id']: entry for entry in config['tests']}
    rows = result.get('results', {}).get('results')
    if not isinstance(rows, list) or len(rows) != EXPECTED_CASES:
        raise ValueError('Every fixed regression requires an individual result.')
    seen = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get('vars'), dict):
            raise ValueError('Invalid individual regression result.')
        case_id = row['vars'].get('case_id')
        if not isinstance(case_id, str) or case_id not in cases or case_id in seen:
            raise ValueError('Missing, duplicate or unknown regression identity.')
        case = cases[case_id]
        expected_vars = dict(case_id=case_id, expected_status=case['expected_status'])
        assertions = config['defaultTest']['assert'] + entries[case_id].get('assert', [])
        test_case, grading = row.get('testCase', {}), row.get('gradingResult', {})
        components = grading.get('componentResults', [])
        if (row['vars'] != expected_vars or test_case.get('vars') != expected_vars
                or row.get('prompt', {}).get('raw') != case_id or row.get('success') is not True
                or grading.get('pass') is not True or type(grading.get('score')) not in (int, float)
                or grading['score'] != 1 or test_case.get('assert') != assertions
                or not isinstance(components, list) or len(components) != len(assertions)
                or any(not isinstance(component, dict) or component.get('pass') is not True
                       or component.get('assertion') != assertion
                       for component, assertion in zip(components, assertions))):
            raise ValueError('Regression vars, prompt or assertion evidence differs from its contract.')
        output = json.loads(row.get('response', {}).get('output', ''))
        if (not isinstance(output, dict) or output.get('case_id') != case_id
                or output.get('case_sha256') != _canonical_hash(case)
                or output.get('final_status') != case['expected_status']
                or output.get('fixture') is not True or output.get('native_metric') is not False
                or output.get('model_called') is not False or output.get('verified') is not False
                or output.get('released_text') is not None or output.get('pipeline_error') is not None
                or output.get('original_contract_preserved') is not True
                or output.get('pipeline_framework') != 'guardrails_local.quality_pipeline'
                or any(type(output.get(key)) is not int for key in
                       ('evaluator_calls', 'corrector_calls', 'attempt_count'))
                or tuple(output[key] for key in ('evaluator_calls', 'corrector_calls', 'attempt_count'))
                   != _EXPECTED_CALLS[case_id]):
            raise ValueError('Provider result identity, outcome or execution counts do not match the fixed case.')
        seen.append(case_id)
    return dict(passed=successes, failed=failures, errors=errors, case_ids=seen)


def run_regressions(root):
    report = dict(status='ERROR', framework='promptfoo', version=VERSION,
        synthetic_fixtures=True, live_model_quality_verified=False, model_called=False,
        global_installation=False)
    try:
        root = Path(root).resolve()
        runtime = _runtime(root)
        cli = runtime / 'node_modules/promptfoo/dist/src/entrypoint.js'
        if not cli.is_file():
            raise ValueError('Project-local Promptfoo is missing; explicitly run --install first.')
        artifacts = _artifact_contract(root)
        lock_sha256 = _validate_lock(root)
        result_path = runtime / 'runs' / (uuid.uuid4().hex + '.json')
        result_path.parent.mkdir(parents=True, exist_ok=True)
        code, log = _run(root, evaluation_command(root, result_path), 'eval', timeout=180)
        report.update(exit_code=code, log_path=log, result_path=str(result_path), lock_sha256=lock_sha256)
        if _artifact_contract(root) != artifacts:
            raise ValueError('Regression artifacts changed during execution.')
        report['artifact_sha256'] = artifacts
        if code:
            raise ValueError('The real Promptfoo CLI did not pass every fixed regression case.')
        report.update(checked_summary(json.loads(result_path.read_bytes())))
        report.update(status='PASS', checked_at=datetime.now(timezone.utc).isoformat(),
                      scope='Echte Promptfoo-CLI und Produktpipeline mit explizit synthetischen semantischen Testurteilen.')
    except Exception as exc:
        report['error'] = type(exc).__name__ + ': ' + str(exc)
    _json(_runtime(root) / 'latest-run.json', report)
    return report
