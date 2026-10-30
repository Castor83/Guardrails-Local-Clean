"""Deterministic, scoped work checks; no general shell parser or OS sandbox."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid

from .codex_hook import _atomic_json, _load_json, _json_bytes, _session_lock


def _digest(value):
    return hashlib.sha256(_json_bytes(value)).hexdigest()


def _task_dir(root, state):
    for field in ('session_id', 'task_id'):
        if str(uuid.UUID(state[field])) != state[field]:
            raise ValueError('Nichtkanonische Aufgaben- oder Sitzungs-ID.')
    return Path(root) / 'work/codex/sessions' / state['session_id'] / 'tasks' / state['task_id']


def _policy(root):
    policy = _load_json(Path(root) / 'config/workflow-policy.json')
    if (not isinstance(policy, dict) or set(policy) != {'version', 'source_sha256', 'minimum_tests', 'decisions'}
            or policy['version'] != 1 or type(policy['minimum_tests']) is not int
            or not 1 <= policy['minimum_tests'] <= 10000
            or not isinstance(policy['decisions'], list) or not 1 <= len(policy['decisions']) <= 32):
        raise ValueError('Workflow-Policy ist ungültig.')
    ids = []
    for decision in policy['decisions']:
        if (not isinstance(decision, dict) or set(decision) != {'id', 'description', 'source'}
                or any(not isinstance(v, str) or not v.strip() or len(v) > 1000 for v in decision.values())
                or decision['source'] != 'docs/ORIGINALAUFTRAG.txt'):
            raise ValueError('Bestätigte Entscheidung benötigt ID, Beschreibung und Originalquelle.')
        ids.append(decision['id'])
    if len(set(ids)) != len(ids):
        raise ValueError('Doppelte Entscheidungs-ID.')
    source = Path(root) / 'docs/ORIGINALAUFTRAG.txt'
    if source.stat().st_size > 2 * 1024 * 1024 or hashlib.sha256(source.read_bytes()).hexdigest() != policy['source_sha256']:
        raise ValueError('Originalauftrag hat sich gegenüber der bestätigten Policy verändert.')
    return policy


def ensure_contract(root, state):
    root = Path(root).resolve()
    directory = _task_dir(root, state)
    task = state['task']
    if hashlib.sha256(task.encode('utf-8')).hexdigest() != state['task_sha256']:
        raise ValueError('Originalauftrag stimmt nicht mit seinem Hash überein.')
    expected_task_file = directory / 'original-task.txt'
    if Path(state['task_file']).resolve() != expected_task_file.resolve() or expected_task_file.read_bytes().decode('utf-8') != task:
        raise ValueError('Workflow benötigt den unveränderten tatsächlich gebundenen Auftrag.')
    policy = _policy(root)
    contract = dict(version=1, session_id=state['session_id'], task_id=state['task_id'],
                    task_sha256=state['task_sha256'], root=str(root), policy_sha256=_digest(policy),
                    decisions=policy['decisions'], minimum_tests=policy['minimum_tests'])
    if 'review_scope' in state:
        from .codex_hook import _review_scope
        contract['review_scope'] = _review_scope(state)
        contract['scope_sha256'] = state.get('scope_sha256')
    path = directory / 'workflow-contract.json'
    if path.exists():
        if _load_json(path) != contract:
            raise ValueError('Auftrag oder Regeln weichen vom gespeicherten Workflow-Vertrag ab.')
    else:
        _atomic_json(path, contract)
    return contract


def tree_snapshot(root):
    """Content, names and modes; ignored runtime paths cannot prove code changes."""
    root = Path(root).resolve()
    entries, total = [], 0
    for parent, dirs, files in os.walk(root, followlinks=False):
        excluded = {'__pycache__'}
        if Path(parent) == root:
            excluded.update({'.git', 'work', 'logs', '.venv', '.superpowers'})
        dirs[:] = sorted(d for d in dirs if d not in excluded)
        for directory in dirs:
            if (Path(parent) / directory).is_symlink():
                raise ValueError('Verlinktes Quellverzeichnis kann nicht als aktueller Stand bestätigt werden.')
        for name in sorted(files):
            path = Path(parent) / name
            if name.endswith('.pyc'):
                continue
            if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root):
                raise ValueError('Quellpfad verlässt den bestätigten Arbeitsbereich.')
            size = path.stat().st_size
            total += size
            if size > 2 * 1024 * 1024 or total > 64 * 1024 * 1024 or len(entries) >= 10000:
                raise ValueError('Dateistand überschreitet das feste Prüfbudget.')
            entries.append((path.relative_to(root).as_posix(), path.stat().st_mode,
                            hashlib.sha256(path.read_bytes()).hexdigest()))
    return _digest(entries)


def _literal_tokens(command):
    if not isinstance(command, str) or len(command) > 16000 or any(c in command for c in '\r\n\x00`$'):
        return []
    text = command.strip()
    if text.startswith('& '):
        text = text[2:].lstrip()
    pattern = re.compile(r"'([^']*)'|\"([^\"]*)\"|([A-Za-z0-9_./:\\\-]+)")
    result, pos = [], 0
    while pos < len(text):
        match = pattern.match(text, pos)
        if not match or (match.end() < len(text) and not text[match.end()].isspace()):
            return []
        result.append(next(v for v in match.groups() if v is not None))
        pos = match.end()
        while pos < len(text) and text[pos].isspace():
            pos += 1
    return result


def _local_absolute(value):
    return (isinstance(value, str) and Path(value).is_absolute()
            and not value.startswith(('\\\\', '//')) and ':' not in value[2:])


def _shell_allowed(root, state, command):
    tokens = _literal_tokens(command)
    if not tokens:
        return False
    if tokens[0].casefold() in {'get-content', 'get-item', 'test-path', 'get-childitem'}:
        if not (len(tokens) == 3 and tokens[1].casefold() == '-literalpath' and _local_absolute(tokens[2])):
            return False
        try:
            target = Path(tokens[2])
            return '..' not in target.parts and target.resolve().is_relative_to(Path(root).resolve())
        except (OSError, ValueError, RuntimeError):
            return False
    if tokens[:2] == [sys.executable, str(root / 'workflow-check.py')]:
        return tokens[2:] in (["--session-id", state['session_id'], '--inspect'],
                               ["--session-id", state['session_id'], '--run-tests'])
    if tokens[:2] == [sys.executable, str(root / 'setup-local-evals.py')]:
        return (len(tokens) == 6 and tokens[2:5] == ['--session-id', state['session_id'], '--action']
                and tokens[5] in {'inspect', 'resolve', 'install', 'download-model',
                                  'smoke-nli', 'smoke-deepeval', 'check'})
    if tokens[:2] == [sys.executable, str(root / 'codex-hook.py')] and len(tokens) in {8, 10}:
        pairs = dict(zip(tokens[2::2], tokens[3::2]))
        options = {'--precheck', '--session-id', '--task-file'}
        if len(tokens) == 10:
            options.add('--turn-id')
            if state.get('latest_turn_id') is None or pairs.get('--turn-id') != state['latest_turn_id']:
                return False
        return (set(pairs) == options and len(pairs) == (len(tokens) - 2) // 2
                and pairs['--session-id'] == state['session_id']
                and pairs['--task-file'] == state['task_file'] and _local_absolute(pairs['--precheck']))
    return False


def _patch_allowed(root, payload):
    body = payload.get('tool_input', {}).get('command')
    if not isinstance(body, str) or not body.startswith('*** Begin Patch\n') or not body.rstrip().endswith('*** End Patch'):
        return False
    if any(line.startswith(('*** Delete File:', '*** Move to:')) for line in body.splitlines()):
        return False
    paths = re.findall(r'^\*\*\* (?:Add|Update) File: (.+)$', body, re.MULTILINE)
    if not paths:
        return False
    cwd = Path(payload.get('cwd', str(root)))
    for name in paths:
        path = Path(name)
        path = (path if path.is_absolute() else cwd / path).resolve()
        if not path.is_relative_to(root):
            return False
        relative = path.relative_to(root).as_posix().casefold()
        if (relative == 'docs/originalauftrag.txt' or relative.startswith(('config/', 'work/codex/', 'logs/', '.git/'))
                or relative in {'config', 'work/codex', 'logs', '.git'}):
            return False
    return True


def tool_decision(root, state, payload):
    """The supported event receives an actual deny even if auditing fails."""
    root = Path(root).resolve()
    allowed, reason = False, 'Nicht positiv erkannter Werkzeugaufruf; keine Freigabe.'
    try:
        contract = ensure_contract(root, state)
        if payload.get('turn_id') != state.get('latest_turn_id'):
            raise ValueError('Werkzeugaufruf gehört nicht zum tatsächlich gebundenen Turn.')
        if payload.get('tool_name') == 'Bash':
            allowed = _shell_allowed(root, state, payload.get('tool_input', {}).get('command'))
        elif payload.get('tool_name') == 'apply_patch':
            allowed = _patch_allowed(root, payload)
        from .workflow_validators import checked, DecisionConsistency, decision_consistency
        validation = checked(DecisionConsistency, decision_consistency, json.dumps(payload, ensure_ascii=False),
                             dict(root=str(root), state=state, action=True))
        allowed = allowed and validation['status'] == 'PASS'
        reason = ('Workflow-Regeln für diesen unterstützten Aufruf geprüft.' if allowed else reason)
        _atomic_json(_task_dir(root, state) / ('tool-' + str(uuid.uuid4()) + '.json'),
                     dict(event='PreToolUse', allowed=allowed, reason=reason, contract_sha256=_digest(contract),
                          tool_name=payload.get('tool_name'), input_sha256=_digest(payload.get('tool_input'))))
    except Exception as exc:
        allowed, reason = False, 'Workflow-Prüfung fehlgeschlagen: ' + str(exc)
    return dict(hookSpecificOutput=dict(hookEventName='PreToolUse',
                permissionDecision='allow' if allowed else 'deny', permissionDecisionReason=reason))


def run_checks(root, state):
    root = Path(root).resolve()
    with _session_lock(root / 'work/codex/sessions' / state['session_id']):
        contract = ensure_contract(root, state)
        directory = _task_dir(root, state)
        before = tree_snapshot(root)
        path = directory / 'workflow-check.json'
        runner = Path(__file__).with_name('test_runner.py').resolve()
        runner_hash = hashlib.sha256(runner.read_bytes()).hexdigest()
        if path.exists():
            prior = _load_json(path)
            if (prior.get('version') == 2 and prior.get('runner_sha256') == runner_hash
                    and prior.get('tree_before') == before and prior.get('contract_sha256') == _digest(contract)):
                if prior.get('status') == 'PASS':
                    try:
                        _runner_result(root, state, prior)
                    except (OSError, ValueError, KeyError, TypeError) as exc:
                        return dict(prior, cached=True, status='ERROR', error=str(exc))
                return dict(prior, cached=True, status=prior['status'] if prior['status'] != 'PENDING' else 'ERROR')
        invocation = uuid.uuid4().hex
        result_path = directory / ('workflow-result-' + invocation + '.json')
        command = [sys.executable, '-B', str(runner), '--start-dir', str(root / 'tests'),
                   '--result', str(result_path), '--invocation-id', invocation]
        evidence = dict(version=2, status='PENDING', task_sha256=state['task_sha256'],
                        contract_sha256=_digest(contract), tree_before=before, command=command,
                        invocation_id=invocation, runner_result_path=str(result_path), runner_sha256=runner_hash,
                        evidence_scope='cooperative-unit-tests', tamper_resistant=False,
                        exit_code=None, test_count=0)
        _atomic_json(path, evidence)
        output = directory / ('workflow-tests-' + str(uuid.uuid4()) + '.txt')
        options = dict(cwd=root, stdin=subprocess.DEVNULL, timeout=120, check=False)
        if os.name == 'nt':
            options['creationflags'] = subprocess.CREATE_NO_WINDOW
        try:
            with output.open('xb') as stream:
                process = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, **options)
            evidence.update(exit_code=process.returncode, output_path=str(output),
                            output_sha256=_file_digest(output))
            if result_path.is_file():
                evidence['runner_result_sha256'] = _file_digest(result_path)
            result = _runner_result(root, state, evidence, check_count=False)
            count = result['test_count']
            after = tree_snapshot(root)
            success = (process.returncode == 0 and result['failures'] == result['errors'] ==
                       result['unexpected_successes'] == 0 and count >= contract['minimum_tests'] and before == after)
            evidence.update(status='PASS' if success else 'FAIL' if process.returncode else 'UNVERIFIED',
                            exit_code=process.returncode, test_count=count, tree_after=after,
                            runner_result=result)
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            evidence.update(status='ERROR', error=str(exc), output_path=str(output))
        _atomic_json(path, evidence)
        return evidence


def _file_digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def _runner_result(root, state, proof, *, check_count=True):
    directory = _task_dir(root, state).resolve()
    result_path = Path(proof.get('runner_result_path', ''))
    output = Path(proof.get('output_path', ''))
    runner = Path(__file__).with_name('test_runner.py').resolve()
    if (proof.get('version') != 2 or proof.get('evidence_scope') != 'cooperative-unit-tests'
            or proof.get('tamper_resistant') is not False or proof.get('runner_sha256') != _file_digest(runner)
            or not result_path.is_file() or not result_path.resolve().is_relative_to(directory)
            or not output.is_file() or not output.resolve().is_relative_to(directory)
            or _file_digest(result_path) != proof.get('runner_result_sha256')
            or _file_digest(output) != proof.get('output_sha256')):
        raise ValueError('Runner/log evidence missing, changed or outside the bound task.')
    result = _load_json(result_path, 65536)
    fields = {'schema_version', 'completed', 'invocation_id', 'tests_run', 'test_count',
              'failures', 'errors', 'skipped', 'expected_failures', 'unexpected_successes',
              'evidence_scope', 'tamper_resistant'}
    counts = ('tests_run', 'test_count', 'failures', 'errors', 'skipped',
              'expected_failures', 'unexpected_successes')
    if (not isinstance(result, dict) or set(result) != fields
            or type(result['schema_version']) is not int or result['schema_version'] != 1
            or result['completed'] is not True or result['evidence_scope'] != 'cooperative-unit-tests'
            or result['tamper_resistant'] is not False
            or not isinstance(proof.get('invocation_id'), str)
            or not re.fullmatch(r'[0-9a-f]{32}', proof['invocation_id'])
            or result['invocation_id'] != proof['invocation_id']
            or any(type(result[key]) is not int or not 0 <= result[key] <= 1000000 for key in counts)
            or result['test_count'] != result['tests_run'] - result['skipped']
            or (check_count and (type(proof.get('test_count')) is not int
                                 or proof['test_count'] != result['test_count']))):
        raise ValueError('Invalid or stale structured unittest result.')
    return result


def work_status(text):
    """Bounded declaration/claim consistency, shared by both workflow validators."""
    from .action_evidence import _mask_examples, _QUOTES, _QUALIFIED
    first = text.splitlines()[0] if text else ''
    narrative = _QUOTES.sub(lambda m: ' ' * len(m.group(0)), _mask_examples(text))
    success = re.compile(r'\b(?:(?:vollständig|komplett|erfolgreich)\s+(?:abgeschlossen|erledigt|fertig)|'
                         r'(?:alle|sämtliche)\s+tests?\s+(?:(?:sind|wurden)\s+)?bestanden|'
                         r'alles\s+(?:erledigt|abgeschlossen)|fertiggestellt)\b', re.I)
    asserted = any(success.search(clause) and not _QUALIFIED.search(clause)
                   for clause in re.split(r'[,.;!?\n]|\b(?:und|aber|sondern)\b', narrative, flags=re.I))
    valid = first in {'Arbeitsstatus: OFFEN', 'Arbeitsstatus: ABGESCHLOSSEN'}
    return first, valid and not (first == 'Arbeitsstatus: OFFEN' and asserted)


def completion_report(root, state, text):
    try:
        contract = ensure_contract(root, state)
        first, consistent = work_status(text)
        if not consistent:
            return dict(status='UNVERIFIED', findings=[dict(description='Arbeitsstatus fehlt oder widerspricht einer Erfolgsbehauptung.')])
        if first == 'Arbeitsstatus: OFFEN':
            return dict(status='PASS', findings=[], scope='Strukturierter offener Arbeitsstand; keine Abschlussbehauptung.')
        if first != 'Arbeitsstatus: ABGESCHLOSSEN':
            return dict(status='UNVERIFIED', findings=[dict(description='Strukturierter Arbeitsstatus fehlt.')])
        path = _task_dir(root, state) / 'workflow-check.json'
        proof = _load_json(path) if path.exists() else {}
        if not proof:
            return dict(status='FAIL', findings=[dict(description='Kein aktueller Runnerbeleg.')])
        result = _runner_result(root, state, proof)
        output = Path(proof.get('output_path', ''))
        verified = (proof.get('status') == 'PASS' and proof.get('exit_code') == 0
                    and proof.get('task_sha256') == state['task_sha256']
                    and proof.get('contract_sha256') == _digest(contract)
                    and proof.get('tree_before') == proof.get('tree_after') == tree_snapshot(root)
                    and type(proof.get('test_count')) is int and proof['test_count'] >= contract['minimum_tests']
                    and result['failures'] == result['errors'] == result['unexpected_successes'] == 0
                    and output.is_file() and output.resolve().is_relative_to(_task_dir(root, state).resolve())
                    and _file_digest(output) == proof.get('output_sha256'))
        return dict(status='PASS' if verified else 'FAIL', proof_path=str(path),
                    findings=[] if verified else [dict(description='Abschlussbeleg fehlt, ist fehlgeschlagen oder nicht mehr aktuell.')],
                    evidence_scope='cooperative-unit-tests', tamper_resistant=False,
                    general_completion_verified=False,
                    scope='Kooperativer CPU-Suitennachweis für Auftrag, Regeln und Dateistand; keine adversariale Beleggarantie oder allgemeine Abschlussfreigabe.')
    except Exception as exc:
        return dict(status='ERROR', findings=[dict(description=str(exc))])


def main(argv=None):
    import argparse
    from .codex_hook import _config, _state
    parser = argparse.ArgumentParser(description='Festgelegte lokale Workflow-Prüfung, keine freie Kommandoausführung.')
    parser.add_argument('--session-id', required=True)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--inspect', action='store_true')
    action.add_argument('--run-tests', action='store_true')
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[2]
    try:
        config = _config(root, args.session_id, required=True)
        if args.session_id not in config.get('workflow_session_ids', []):
            raise ValueError('Workflow ist für diese Sitzung nicht aktiviert.')
        state = _state(root / 'work/codex/sessions' / args.session_id)
        if state is None:
            raise ValueError('Keine echte gebundene Aufgabe vorhanden.')
        report = run_checks(root, state) if args.run_tests else ensure_contract(root, state)
        print(json.dumps(report, ensure_ascii=False))
        return 0 if report.get('status', 'PASS') == 'PASS' else 2
    except Exception as exc:
        print(json.dumps(dict(status='ERROR', error=str(exc)), ensure_ascii=False))
        return 3
