"""Explicit project-only dependency/model setup with fixed actions and artifacts."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import uuid

from .workflow import ensure_contract
from .codex_hook import _state, _atomic_json, _config

OPERATOR_RULE = ('Vorhandene Infrastruktur zuerst nutzen. Zusätzliche lokale Pakete, Dienste oder Modelle '
    'sind nur für beauftragte Einrichtungen zulässig, wenn vorhandene Komponenten nachweislich nicht '
    'ausreichen. Keine zusätzlichen Cloud-Prüfer oder kostenpflichtigen Modell-APIs; keine ungefragten Providerwechsel.')
ACTIONS = ('inspect', 'resolve', 'install', 'download-model', 'smoke-nli', 'smoke-deepeval', 'check')
TORCH_URL = ('https://download-r2.pytorch.org/whl/cpu/torch-2.12.1%2Bcpu-cp312-cp312-win_amd64.whl'
             '#sha256=51c6c6e26eaa0d64ed439ebdc9ce3b8cc2d5cfcc7cdd4e72f17831d80886b7f4')
REQUIREMENTS = ('guardrails-ai==0.11.0', 'pydantic==2.14.1', 'deepeval==4.3.1',
    'guardrails-ai-provenance-nli==0.1.0', 'click==8.3.1', 'huggingface-hub==0.36.0',
    'transformers==4.57.6', 'tokenizers==0.22.2', 'sentence-transformers==5.2.0',
    'nltk==3.10.3', 'safetensors==0.8.0', 'torch @ ' + TORCH_URL)
MODEL_REPO = 'MoritzLaurer/multilingual-MiniLMv2-L6-mnli-xnli'
MODEL_REVISION = '0a71e92a985b6e1ad1828cf67ce9c459639c1dca'
MODEL_SHA256 = '91b323ccf247ec1e3b5925d566230bae7c52de8147e6062b42e250089a3fc80b'
MODEL_FILES = ('config.json', 'tokenizer.json', 'tokenizer_config.json',
               'special_tokens_map.json', 'sentencepiece.bpe.model', 'model.safetensors', 'README.md')


def runtime_python(root):
    base = Path(root).resolve() / 'work' / 'evals-runtime'
    target = (base / '.venv' / 'Scripts' / 'python.exe').resolve()
    if not target.is_relative_to(base.resolve()) or target == Path(sys.executable).resolve():
        raise ValueError('Evaluation runtime must be a separate environment inside project work/.')
    return target


def locked_requirements(plan):
    records = plan.get('install') if isinstance(plan, dict) else None
    if not isinstance(records, list) or not records or len(records) > 256:
        raise ValueError('A nonempty bounded resolver artifact list is required.')
    names, lines = set(), []
    for record in records:
        metadata, info = record.get('metadata', {}), record.get('download_info', {})
        name, version = metadata.get('name'), metadata.get('version')
        if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', name):
            raise ValueError('Invalid distribution name.')
        normalized = re.sub(r'[-_.]+', '-', name).lower()
        if normalized in names or not isinstance(version, str) or not re.fullmatch(r'[A-Za-z0-9.+_-]+', version):
            raise ValueError('Duplicate or invalid distribution record.')
        names.add(normalized)
        url = info.get('url', '')
        parsed = urllib.parse.urlsplit(url)
        digest = info.get('archive_info', {}).get('hashes', {}).get('sha256', '')
        if (parsed.scheme != 'https' or parsed.hostname not in {
                'files.pythonhosted.org', 'download.pytorch.org', 'download-r2.pytorch.org'}
                or parsed.username or parsed.password or any(c.isspace() for c in url)
                or parsed.query or parsed.port not in (None, 443)
                or not parsed.path.lower().endswith('.whl')
                or not isinstance(digest, str) or not re.fullmatch(r'[a-fA-F0-9]{64}', digest)):
            raise ValueError('Only hashed official HTTPS wheel artifacts are allowed.')
        clean = urllib.parse.urlunsplit(parsed._replace(fragment=''))
        lines.append(f'{name} @ {clean} --hash=sha256:{digest.lower()}')
    return '\n'.join(lines) + '\n'


def _run(root, command, label, *, timeout=900):
    from .deepeval_adapter import build_worker_environment
    env = build_worker_environment(os.environ)
    env['PIP_CONFIG_FILE'] = os.devnull
    directory = Path(root) / 'work' / 'evals-runtime'
    directory.mkdir(parents=True, exist_ok=True)
    log = directory / (label + '-' + uuid.uuid4().hex + '.txt')
    options = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
    with log.open('wb') as stream:
        completed = subprocess.run(command, cwd=root, env=env, stdin=subprocess.DEVNULL,
            stdout=stream, stderr=subprocess.STDOUT, timeout=timeout, check=False, **options)
    if completed.returncode:
        raise RuntimeError(f'{label} failed with exit {completed.returncode}; log: {log}')
    return str(log)


def _inventory():
    return {dist.metadata['Name']: dist.version for dist in importlib.metadata.distributions()}


def _resolve(root):
    python = runtime_python(root)
    directory = python.parents[2]
    directory.mkdir(parents=True, exist_ok=True)
    _atomic_json(directory / 'controller-packages-before.json', _inventory())
    if not python.is_file():
        _run(root, [sys.executable, '-m', 'venv', str(python.parents[1])], 'create-environment')
    report = directory / 'pip-resolution.json'
    log = _run(root, [str(python), '-m', 'pip', '--isolated', '--disable-pip-version-check',
        '--no-input', '--retries', '0', '--timeout', '30', 'install', '--dry-run',
        '--report', str(report), '--only-binary=:all:', '--index-url', 'https://pypi.org/simple',
        *REQUIREMENTS], 'resolve')
    plan = json.loads(report.read_text(encoding='utf-8'))
    locked = locked_requirements(plan)
    lock = directory / 'requirements.lock.txt'
    lock.write_bytes(locked.encode('utf-8'))
    _atomic_json(directory / 'resolution-binding.json', dict(
        report_sha256=hashlib.sha256(report.read_bytes()).hexdigest(),
        lock_sha256=hashlib.sha256(lock.read_bytes()).hexdigest(),
        requirements=list(REQUIREMENTS)))
    return dict(status='RESOLVED', artifact_count=len(plan['install']), log_path=log,
                report_path=str(report), lock_path=str(lock))


def _install(root):
    python = runtime_python(root)
    directory = python.parents[2]
    binding = json.loads((directory / 'resolution-binding.json').read_text(encoding='utf-8'))
    report, lock = directory / 'pip-resolution.json', directory / 'requirements.lock.txt'
    if (binding.get('requirements') != list(REQUIREMENTS)
            or hashlib.sha256(report.read_bytes()).hexdigest() != binding['report_sha256']
            or hashlib.sha256(lock.read_bytes()).hexdigest() != binding['lock_sha256']
            or locked_requirements(json.loads(report.read_bytes())).encode('utf-8') != lock.read_bytes()):
        raise ValueError('Resolved dependency artifacts changed; no installation.')
    log = _run(root, [str(python), '-m', 'pip', '--isolated', '--disable-pip-version-check',
        '--no-input', '--retries', '0', '--timeout', '30', 'install', '--no-index',
        '--no-deps', '--only-binary=:all:', '--require-hashes', '--require-virtualenv',
        '-r', str(lock)], 'install')
    check = _run(root, [str(python), '-m', 'pip', '--isolated', 'check'], 'dependency-check')
    if _inventory() != json.loads((directory / 'controller-packages-before.json').read_bytes()):
        raise RuntimeError('Controller package inventory changed; investigate before proceeding.')
    return dict(status='INSTALLED', runtime_python=str(python), log_path=log, pip_check_log=check,
                controller_packages_unchanged=True)


def _download_model(root):
    directory = runtime_python(root).parents[2] / 'model'
    directory.mkdir(parents=True, exist_ok=True)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    hashes = {}
    for name in MODEL_FILES:
        target = directory / name
        if name == 'model.safetensors' and target.is_file() and _file_hash(target) == MODEL_SHA256:
            hashes[name] = MODEL_SHA256
            continue
        url = f'https://huggingface.co/{MODEL_REPO}/resolve/{MODEL_REVISION}/{name}'
        temporary = target.with_name(target.name + '.' + uuid.uuid4().hex + '.partial')
        total, started = 0, time.monotonic()
        digest = hashlib.sha256()
        try:
            with opener.open(url, timeout=30) as response, temporary.open('xb') as output:
                while chunk := response.read(1024 * 1024):
                    total += len(chunk)
                    if total > 512 * 1024 * 1024 or time.monotonic() - started > 600:
                        raise ValueError('Model artifact exceeds download bound.')
                    digest.update(chunk)
                    output.write(chunk)
            if name == 'model.safetensors' and digest.hexdigest() != MODEL_SHA256:
                raise ValueError('NLI weight SHA256 differs from the pinned publisher artifact.')
            os.replace(temporary, target)
            hashes[name] = digest.hexdigest()
        finally:
            temporary.unlink(missing_ok=True)
    _atomic_json(directory / 'manifest.json', dict(repo=MODEL_REPO, revision=MODEL_REVISION,
        weights_sha256=MODEL_SHA256, files=hashes,
        downloaded_at=datetime.now(timezone.utc).isoformat()))
    return dict(status='DOWNLOADED', model_path=str(directory), revision=MODEL_REVISION,
                weights_sha256=MODEL_SHA256, inference_executed=False)


def _file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def run_action(root, state, action):
    if action not in ACTIONS:
        raise ValueError('Unknown setup action.')
    root = Path(root).resolve()
    config = _config(root, state['session_id'], required=True)
    if state['session_id'] not in config.get('workflow_session_ids', []):
        raise ValueError('Setup action requires current explicit workflow permission for this session.')
    contract = ensure_contract(root, state)
    rule = next((d['description'] for d in contract['decisions'] if d['id'] == 'NO_NEW_RUNTIME'), None)
    if action != 'inspect' and rule != OPERATOR_RULE:
        raise ValueError('Necessary local setup requires the actual operator-approved conditional rule.')
    if action == 'inspect':
        result = dict(status='INSPECTED', runtime_python=str(runtime_python(root)),
            runtime_exists=runtime_python(root).is_file(), requirements=list(REQUIREMENTS),
            installed_controller_packages=_inventory(), model_repo=MODEL_REPO)
    elif action == 'resolve':
        result = _resolve(root)
    elif action == 'install':
        result = _install(root)
    elif action == 'download-model':
        result = _download_model(root)
    elif action == 'smoke-nli':
        from .provenance_nli import smoke_nli
        result = smoke_nli(root)
    elif action == 'smoke-deepeval':
        from .deepeval_adapter import run_deepeval_smoke
        result = run_deepeval_smoke(root)
    else:
        result = dict(status='CHECKED', pip_check_log=_run(root,
            [str(runtime_python(root)), '-m', 'pip', '--isolated', 'check'], 'dependency-check'))
    result.update(action=action, session_id=state['session_id'], task_id=state['task_id'],
        policy_sha256=contract['policy_sha256'], checked_at=datetime.now(timezone.utc).isoformat())
    directory = root / 'work' / 'codex' / 'sessions' / state['session_id'] / 'tasks' / state['task_id']
    _atomic_json(directory / ('evals-' + action + '.json'), result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session-id', required=True)
    parser.add_argument('--action', required=True, choices=ACTIONS)
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[2]
    try:
        session = str(uuid.UUID(args.session_id))
        state = _state(root / 'work' / 'codex' / 'sessions' / session)
        if state is None:
            raise ValueError('An actual native task binding is required.')
        result = run_action(root, state, args.action)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 3 if result['status'] in {'ERROR', 'FAIL', 'UNVERIFIED'} else 0
    except Exception as exc:
        print(json.dumps(dict(status='ERROR', action=args.action, error=str(exc)), ensure_ascii=False))
        return 3
