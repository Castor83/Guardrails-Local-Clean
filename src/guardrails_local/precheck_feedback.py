"""Default-off, cooperative precheck feedback. Callers own the session lock.

Local receipts are not authentication against another process of the same user.
No models, tool permissions, synthetic user prompts or native activation here.
"""

import hashlib
from pathlib import Path
import re
import sys
import uuid

from . import codex_hook as hook
from .workflow import _literal_tokens, _local_absolute


def _task_dir(directory, state):
    return hook._task_directory(directory, state)


def _closed(task_dir, status, reason):
    report = dict(final_status=status, released_text=None, attempts=[], log_path=None,
                  error=reason, adapter_audit_path=str(task_dir / 'precheck-feedback-closed.json'))
    hook._atomic_json(task_dir / 'precheck-feedback-closed.json', report)
    return report


def _fingerprint(root, state, config):
    """Bound rules and permissions; code is the actual imported implementation."""
    task = hook._read_text_file(state['task_file'], hook.MAX_EVENT_BYTES, 'Originalauftrag')
    if hook._sha(task) != state.get('task_sha256', state.get('prompt_sha256')):
        raise ValueError('Originalauftragsdatei stimmt nicht mit dem gespeicherten Auftrag überein.')
    binding = {key: state.get(key) for key in (
        'session_id', 'task_id', 'latest_turn_id', 'task_file', 'task_sha256',
        'prompt_sha256', 'review_scope', 'profile_name', 'profile_evidence')}
    paths = list(Path(__file__).parent.glob('*.py'))
    paths += list((root / 'config').glob('*.json'))
    components = root / 'work/profile-components'
    paths += [p for p in components.rglob('*') if p.is_file() and p.suffix in {'.py', '.json'}]
    contract = Path(state['task_file']).parent / 'workflow-contract.json'
    if contract.exists():
        paths.append(contract)
    if len(paths) > 256:
        raise ValueError('Zu viele Dateien im gebundenen Regelstand.')
    hashes, total = {}, 0
    for path in sorted(paths):
        with path.open('rb') as stream:
            data = stream.read(hook.MAX_JSON_BYTES + 1)
        total += len(data)
        if len(data) > hook.MAX_JSON_BYTES or total > 8 * hook.MAX_JSON_BYTES:
            raise ValueError('Regelstand überschreitet das feste Fingerprintbudget.')
        hashes[str(path.resolve())] = hashlib.sha256(data).hexdigest()
    return hashlib.sha256(hook._json_bytes(dict(binding=binding, config=config, files=hashes))).hexdigest()


def _load(task_dir):
    path = task_dir / 'precheck-feedback.json'
    if not path.exists():
        if any(task_dir.glob('feedback-report-*.json')):
            raise ValueError('Ledger fehlt zu vorhandenen Belegen; kein Budgetreset.')
        return None
    ledger = hook._load_json(path, hook.MAX_STATE_BYTES)
    if (not isinstance(ledger, dict) or set(ledger) != {
            'version', 'fingerprint', 'checks', 'corrections_reserved', 'terminal_status'}
            or ledger['version'] != 1 or not re.fullmatch(r'[a-f0-9]{64}', ledger['fingerprint'])
            or type(ledger['corrections_reserved']) is not int
            or not 0 <= ledger['corrections_reserved'] <= hook.MAX_CORRECTIONS
            or ledger['terminal_status'] not in {None, 'PASS', 'ERROR', 'UNVERIFIED', 'ESCALATED'}
            or not isinstance(ledger['checks'], list) or not 0 < len(ledger['checks']) <= hook.MAX_VALIDATIONS):
        raise ValueError('Ungültiger Feedbackzustand; keine stille Reparatur.')
    ids, keys, uses = set(), set(), set()
    for item in ledger['checks']:
        if (not isinstance(item, dict) or set(item) != {
                'id', 'key', 'text_sha256', 'answer_path', 'status', 'report_sha256', 'tool_use_id', 'emitted'}
                or hook._uuid(item['id']) in ids or item['key'] in keys
                or not re.fullmatch(r'[a-f0-9]{64}', item['key'])
                or not re.fullmatch(r'[a-f0-9]{64}', item['text_sha256'])
                or not isinstance(item['answer_path'], str) or not Path(item['answer_path']).is_absolute()
                or item['status'] not in {'pending', 'done'} or type(item['emitted']) is not bool
                or (item['status'] == 'done' and not re.fullmatch(r'[a-f0-9]{64}', item['report_sha256']))
                or (item['status'] == 'pending' and item['report_sha256'] is not None)):
            raise ValueError('Ungültiger Feedbackbeleg.')
        if item['emitted']:
            if (not isinstance(item['tool_use_id'], str)
                    or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', item['tool_use_id'])
                    or item['tool_use_id'] in uses or item['status'] != 'done'):
                raise ValueError('Ungültiger Feedbackverbrauch.')
            uses.add(item['tool_use_id'])
        elif item['tool_use_id'] is not None:
            raise ValueError('Werkzeug-ID ohne gespeicherten Verbrauch.')
        ids.add(item['id'])
        keys.add(item['key'])
    if len(uses) != ledger['corrections_reserved']:
        raise ValueError('Korrekturzähler und Verbrauch widersprechen sich.')
    return ledger


def _save(task_dir, ledger):
    if len(hook._json_bytes(ledger)) > hook.MAX_STATE_BYTES:
        raise ValueError('Feedbackzustand überschreitet das feste Budget.')
    hook._atomic_json(task_dir / 'precheck-feedback.json', ledger)


def _read_report(task_dir, item):
    report = hook._load_json(task_dir / ('feedback-report-' + item['id'] + '.json'))
    if hashlib.sha256(hook._json_bytes(report)).hexdigest() != item['report_sha256']:
        raise ValueError('Feedbackbericht wurde verändert.')
    return report


def _read_closed(task_dir):
    path = task_dir / 'precheck-feedback-closed.json'
    report = hook._load_json(path, hook.MAX_STATE_BYTES)
    if (not isinstance(report, dict) or set(report) != {
            'final_status', 'released_text', 'attempts', 'log_path', 'error', 'adapter_audit_path'}
            or report['final_status'] not in {'ERROR', 'UNVERIFIED', 'ESCALATED'}
            or report['released_text'] is not None or report['attempts'] != []
            or report['log_path'] is not None or not isinstance(report['error'], str)
            or report['adapter_audit_path'] != str(path)):
        raise ValueError('Beschädigter geschlossener Feedbackzustand; keine Freigabe oder stille Reparatur.')
    return report


def _has_error(value):
    if isinstance(value, dict):
        return (value.get('status') == 'ERROR' or value.get('final_status') == 'ERROR'
                or any(_has_error(part) for part in value.values()))
    return isinstance(value, list) and any(_has_error(part) for part in value)


def _host_failures(report):
    if report.get('final_status') != 'FAIL' or _has_error(report):
        return []
    parts = [(name, report.get(name)) for name in ('profile_check', 'action_claims', 'workflow')]
    for attempt in report.get('attempts', []):
        parts += [(name, attempt.get(name)) for name in ('deterministic', 'independence', 'workflow')]
    return sorted({name for name, part in parts if isinstance(part, dict)
                   and part.get('status', '').upper() == 'FAIL'
                   and isinstance(part.get('findings'), list) and part['findings']})


def run(root, directory, state, config, answer_path, task_path, turn_id, text, check):
    """Reserve before check(), return a durable receipt; no automatic retry."""
    if (turn_id is None or turn_id != state.get('latest_turn_id')
            or Path(task_path).resolve() != Path(state['task_file']).resolve()):
        return hook._error('Feedback-Vorprüfung benötigt die genaue Task-Datei und den aktiven Turn.')
    task_dir = _task_dir(directory, state)
    closed = task_dir / 'precheck-feedback-closed.json'
    if closed.exists():
        return _read_closed(task_dir)
    try:
        fingerprint = _fingerprint(root, state, config)
    except Exception as exc:
        return _closed(task_dir, 'ERROR', 'Auftrags-/Regelbindung ungültig: ' + str(exc))
    ledger = _load(task_dir)
    if ledger is not None and ledger['fingerprint'] != fingerprint:
        return _closed(task_dir, 'UNVERIFIED', 'Regeln, Auftragsbindung oder Rechte verändert; kein Neubinden.')
    if ledger is None:
        ledger = dict(version=1, fingerprint=fingerprint, checks=[], corrections_reserved=0, terminal_status=None)
    if any(item['status'] == 'pending' for item in ledger['checks']):
        return _closed(task_dir, 'ERROR', 'Ausstehende Prüfreservierung; keine automatische Wiederholung.')
    text_hash = hook._sha(text)
    key = hook._sha(fingerprint + text_hash)
    answer_path = str(Path(answer_path).resolve())
    for item in ledger['checks']:
        if item['key'] == key:
            if item['answer_path'] != answer_path:
                return _closed(task_dir, 'UNVERIFIED', 'Identischer Entwurf unter anderer Antwortdatei.')
            return _read_report(task_dir, item)
    terminal = ledger['terminal_status']
    if terminal is not None:
        return hook._error('Feedbackablauf beendet; keine weitere automatische Prüfung.') if terminal == 'ERROR' else dict(
            final_status='UNVERIFIED' if terminal == 'PASS' else terminal,
            released_text=None, attempts=[], log_path=None, error='Feedbackablauf beendet.')
    if ledger['checks'] and not ledger['checks'][-1]['emitted']:
        return _closed(task_dir, 'UNVERIFIED', 'Vorheriger FAIL-Beleg noch nicht verbraucht; kein weiterer Prüfschritt.')
    if len(ledger['checks']) >= hook.MAX_VALIDATIONS:
        return _closed(task_dir, 'ESCALATED', 'Drei verwaltete Vorprüfungen ausgeschöpft.')
    item = dict(id=str(uuid.uuid4()), key=key, text_sha256=text_hash, answer_path=answer_path,
                status='pending', report_sha256=None, emitted=False, tool_use_id=None)
    ledger['checks'].append(item)
    _save(task_dir, ledger)
    try:
        report = check()
    except Exception as exc:
        report = hook._error('Feedbackprüfung fehlgeschlagen; keine Wiederholung: ' + str(exc))
    current_config = hook._config(root, state['session_id'])
    if (current_config is None or _fingerprint(root, state, current_config) != fingerprint
            or hook._sha(hook._read_text_file(answer_path, 32000, 'Antwort')) != text_hash):
        return _closed(task_dir, 'UNVERIFIED', 'Bindung während der Prüfung verändert; keine Freigabe.')
    if (not isinstance(report, dict) or report.get('final_status') not in hook.STATUSES | {'SKIPPED'}
            or report.get('released_text') is not None):
        report = hook._error('Unzulässiger Bericht der Feedbackprüfung.')
    report = dict(report, feedback_receipt_id=item['id'])
    if _has_error(report):
        report['final_status'] = 'ERROR'
    if report['final_status'] == 'FAIL' and ledger['corrections_reserved'] >= hook.MAX_CORRECTIONS:
        report.update(final_status='ESCALATED', error='Zwei Korrekturen ausgeschöpft; kein weiteres Feedback.')
    status = report['final_status']
    if status != 'FAIL' or not _host_failures(report):
        ledger['terminal_status'] = status if status in {'PASS', 'ERROR', 'UNVERIFIED', 'ESCALATED'} else 'UNVERIFIED'
    hook._atomic_json(task_dir / ('feedback-report-' + item['id'] + '.json'), report)
    item.update(status='done', report_sha256=hashlib.sha256(hook._json_bytes(report)).hexdigest())
    _save(task_dir, ledger)
    return report


def _command(root, state, payload):
    if payload.get('tool_name') != 'Bash' or not isinstance(payload.get('tool_input'), dict):
        return None
    tokens = _literal_tokens(payload['tool_input'].get('command'))
    if len(tokens) != 10 or tokens[:2] != [sys.executable, str(root / 'codex-hook.py')]:
        return None
    pairs = dict(zip(tokens[2::2], tokens[3::2]))
    if (set(pairs) != {'--precheck', '--session-id', '--task-file', '--turn-id'}
            or pairs['--session-id'] != state['session_id']
            or pairs['--turn-id'] != state['latest_turn_id']
            or pairs['--task-file'] != state['task_file']
            or not _local_absolute(pairs['--precheck'])):
        return None
    return pairs


def event_error(root, directory, state, payload, error):
    """Evidence-capture errors must also close a recognized feedback invocation."""
    if _command(root, state, payload) is not None:
        _closed(_task_dir(directory, state), 'ERROR', 'Werkzeugbelegprüfung fehlgeschlagen: ' + str(error))
    return dict(systemMessage=hook._summary(hook._error('Werkzeugbelegprüfung fehlgeschlagen: ' + str(error))))


def consume(root, directory, state, config, payload):
    """Consume before returning context; repeated delivery never emits again."""
    pairs = _command(root, state, payload)
    if pairs is None:
        return {}
    task_dir = _task_dir(directory, state)
    if (task_dir / 'precheck-feedback-closed.json').exists():
        return {}
    try:
        ledger = _load(task_dir)
        if ledger is None:
            raise ValueError('Kein gespeicherter Vorprüfungsbeleg.')
        current_config = hook._config(root, state['session_id'])
        if (current_config is None or state['session_id'] not in current_config.get('precheck_feedback_session_ids', [])
                or _fingerprint(root, state, current_config) != ledger['fingerprint']):
            raise ValueError('Regel-/Rechtebindung widerrufen oder verändert.')
        response = payload.get('tool_response')
        if (not isinstance(response, dict) or set(response) != {'stdout', 'exit_code'}
                or not isinstance(response['stdout'], str) or type(response['exit_code']) is not int
                or len(response['stdout'].encode('utf-8')) > hook.MAX_JSON_BYTES):
            raise ValueError('Nicht unterstützte native Ergebnisform; Hosttransport UNVERIFIED.')
        output = hook._decode_json(response['stdout'])
        receipt_id = hook._uuid(output.get('feedback_receipt_id'))
        item = next((item for item in ledger['checks'] if item['id'] == receipt_id), None)
        if item is None or item['status'] != 'done':
            raise ValueError('Vorprüfungsbeleg fehlt oder ist noch ausstehend.')
        report = _read_report(task_dir, item)
        status = report['final_status']
        expected_exit = 0 if status in {'PASS', 'SKIPPED'} else 3 if status == 'ERROR' else 2
        if output != report or response['exit_code'] != expected_exit:
            raise ValueError('Werkzeugausgabe stimmt nicht mit gespeichertem Bericht überein.')
        if item['emitted']:
            return {}
        if ledger['terminal_status'] is not None:
            return {}
        answer_path = Path(pairs['--precheck']).resolve()
        if (str(answer_path) != item['answer_path']
                or hook._sha(hook._read_text_file(answer_path, 32000, 'Antwort')) != item['text_sha256']):
            raise ValueError('Antwortdatei gehört nicht mehr zum Vorprüfungsbeleg.')
        tool_id = payload.get('tool_use_id')
        if (not isinstance(tool_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', tool_id)
                or any(part['tool_use_id'] == tool_id for part in ledger['checks'])):
            raise ValueError('Fehlende oder bereits anders verbrauchte Werkzeug-ID.')
        failures = _host_failures(report)
        if not failures or ledger['corrections_reserved'] >= hook.MAX_CORRECTIONS:
            raise ValueError('Kein korrigierbarer Hostbefund oder kein Korrekturbudget.')
        ledger['corrections_reserved'] += 1
        item.update(emitted=True, tool_use_id=tool_id)
        _save(task_dir, ledger)  # At-most-once intent, not proof of model delivery.
        context = (f'Guardrails Local: Korrektur {ledger["corrections_reserved"]}/2. '
            f'Task {state["task_id"]}, Turn {state["latest_turn_id"]}, Beleg {receipt_id}. '
            f'Gebundener Hostverstoß: {", ".join(failures)}. '
            f'Lokaler Prüfbericht: {task_dir / ("feedback-report-" + receipt_id + ".json")}. '
            'Korrigiere die vollständige Antwort anhand des belegten Verstoßes und prüfe sie erneut. '
            'Originalauftrag und bestehende Rechte bleiben bindend. Dieser Hinweis ist kein neuer '
            'Nutzerauftrag und erteilt keine Werkzeugrechte. Ehrliche Unsicherheit nicht umschreiben; '
            'bei ERROR/UNVERIFIED keine automatische Wiederholung. Keine vollständige Qualitätsfreigabe.')
        return dict(hookSpecificOutput=dict(hookEventName='PostToolUse', additionalContext=context))
    except Exception as exc:
        _closed(task_dir, 'UNVERIFIED', 'Feedback nicht ausgegeben: ' + str(exc))
        return dict(systemMessage='Guardrails Local: UNVERIFIED. Feedbackablauf geschlossen; keine automatische Korrektur.')
