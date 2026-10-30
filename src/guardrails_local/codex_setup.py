"""Installiert den begrenzten Codex-Anschluss, ohne Hook-Vertrauen zu setzen."""

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid


def _read_object(path):
    value = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(value, dict):
        raise ValueError(f'JSON-Objekt erwartet: {path}')
    return value


def _atomic_bytes(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temporary.open('xb') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')


def configure(root, codex_home, session_id, *, critic_enabled, workflow_enabled=False,
              action_evidence_enabled=False):
    """Ergänzt gewählte Handler und erhält vorhandene Hookdefinitionen."""
    root, codex_home = Path(root).resolve(), Path(codex_home).resolve()
    try:
        canonical_session = str(uuid.UUID(session_id))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError('Eine gültige Sitzungs-UUID ist erforderlich.') from exc
    if (canonical_session != session_id or type(critic_enabled) is not bool
            or type(workflow_enabled) is not bool or type(action_evidence_enabled) is not bool):
        raise ValueError('Kanonische Sitzungs-ID und ausdrückliche Critic-Auswahl erforderlich.')
    adapter = root / 'codex-hook.py'
    if not adapter.is_file() or not codex_home.is_dir():
        raise ValueError('Vorhandener Adapter und vorhandenes Codex-Verzeichnis erforderlich.')
    if workflow_enabled:
        if not (root / 'workflow-check.py').is_file():
            raise ValueError('Der feste Workflow-Runner fehlt; keine Einrichtung.')
        from .workflow import _policy
        _policy(root)
    hooks_path = codex_home / 'hooks.json'
    before = hooks_path.read_bytes() if hooks_path.exists() else None
    definition = _read_object(hooks_path) if before is not None else {'hooks': {}}
    hooks = definition.setdefault('hooks', {})
    if not isinstance(hooks, dict):
        raise ValueError('Vorhandenes hooks-Feld ist kein Objekt; keine Änderung.')
    updated = deepcopy(definition)
    command = subprocess.list2cmdline([sys.executable, str(adapter)])
    evidence_handler = {'type': 'command', 'command': command, 'timeout': 10,
                        'statusMessage': 'Guardrails Local: tatsächliches Werkzeugergebnis binden'}
    definitions = [
        ('UserPromptSubmit', 10, 'Guardrails Local: Auftrag und Vorprüfung binden'),
        ('Stop', 190, 'Guardrails Local: Antwort und lokalen Critic prüfen'),
    ]
    if workflow_enabled:
        definitions.append(('PreToolUse', 10, 'Guardrails Local: Arbeitsaktion vor Ausführung prüfen'))
    if action_evidence_enabled:
        definitions.append(('PostToolUse', evidence_handler['timeout'], evidence_handler['statusMessage']))
    for event, timeout, message in definitions:
        groups = updated['hooks'].setdefault(event, [])
        if not isinstance(groups, list):
            raise ValueError(f'Vorhandene {event}-Definition ist keine Liste; keine Änderung.')
        matches = []
        for group in groups:
            if not isinstance(group, dict) or not isinstance(group.get('hooks'), list):
                raise ValueError(f'Vorhandene {event}-Gruppe ist ungültig; keine Änderung.')
            for handler in group['hooks']:
                if not isinstance(handler, dict):
                    raise ValueError('Vorhandener Hookhandler ist ungültig; keine Änderung.')
                if handler.get('command') == command:
                    if event == 'PreToolUse' and group.get('matcher') != '^(Bash|apply_patch)$':
                        raise ValueError('Abweichender Workflow-Matcher; keine automatische Ersetzung.')
                    if event == 'PostToolUse' and 'matcher' in group:
                        raise ValueError('Abweichender Beleg-Matcher; vollständige Werkzeugerfassung erforderlich.')
                    matches.append(handler)
                elif (isinstance(handler.get('command'), str)
                      and str(adapter).casefold() in handler['command'].casefold()):
                    raise ValueError('Derselbe Adapter ist mit einem anderen Aufruf eingerichtet; keine Verdoppelung.')
        expected = {'type': 'command', 'command': command, 'timeout': timeout, 'statusMessage': message}
        if matches:
            if len(matches) != 1 or matches[0] != expected:
                raise ValueError('Abweichender vorhandener Guardrails-Handler; keine automatische Ersetzung.')
        else:
            group = {'hooks': [expected]}
            if event == 'PreToolUse':
                group['matcher'] = '^(Bash|apply_patch)$'
            groups.append(group)

    config_path = root / 'work' / 'codex' / 'config.json'
    old_config_bytes = config_path.read_bytes() if config_path.exists() else None
    local = _read_object(config_path) if old_config_bytes is not None else {}
    if set(local) - {'enabled', 'session_ids', 'critic_enabled', 'workflow_session_ids',
                     'action_evidence_session_ids'}:
        raise ValueError('Unbekannte lokale Adaptereinstellungen; keine Änderung.')
    sessions = local.get('session_ids', [])
    if not isinstance(sessions, list) or any(not isinstance(item, str) for item in sessions):
        raise ValueError('Lokale session_ids müssen eine Liste von Sitzungs-UUIDs sein.')
    for item in sessions:
        if str(uuid.UUID(item)) != item:
            raise ValueError('Ungültige vorhandene Sitzungs-ID.')
    evidence_sessions = local.get('action_evidence_session_ids', [])
    if (not isinstance(evidence_sessions, list) or len(evidence_sessions) > 16
            or any(not isinstance(item, str) or item not in sessions for item in evidence_sessions)
            or len(set(evidence_sessions)) != len(evidence_sessions)):
        raise ValueError('Ungültige vorhandene Beleg-Sitzungsliste; keine Änderung.')
    if sessions and set(sessions) != {session_id}:
        if local.get('critic_enabled') is not critic_enabled or local.get('enabled') is False:
            raise ValueError('Die Auswahl darf den Critic oder die Aktivierung anderer Chats nicht ändern.')
    local.update(enabled=True, critic_enabled=critic_enabled,
                 session_ids=list(dict.fromkeys(sessions + [session_id])))
    workflow_sessions = local.get('workflow_session_ids', [])
    if (not isinstance(workflow_sessions, list) or len(workflow_sessions) > 16
            or any(item not in local['session_ids'] for item in workflow_sessions)):
        raise ValueError('Ungültige vorhandene Workflow-Sitzungsliste; keine Änderung.')
    if workflow_enabled:
        local['workflow_session_ids'] = list(dict.fromkeys(workflow_sessions + [session_id]))
    if action_evidence_enabled:
        local['action_evidence_session_ids'] = list(dict.fromkeys(evidence_sessions + [session_id]))
    if len(local['session_ids']) > 16:
        raise ValueError('Höchstens 16 Sitzungs-IDs; abgeschlossene Chats zuerst ausdrücklich aus der lokalen Liste entfernen.')
    backup_path = None
    changed = updated != definition
    if changed and before is not None:
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        backup_path = root / 'work' / 'codex' / 'backups' / ('hooks-' + stamp + '.json')
        _atomic_bytes(backup_path, before)
    try:
        local_bytes = _json_bytes(local)
        if ((hooks_path.read_bytes() if hooks_path.exists() else None) != before
                or (config_path.read_bytes() if config_path.exists() else None) != old_config_bytes):
            raise ValueError('Konfiguration wurde gleichzeitig geändert; Einrichtung abgebrochen.')
        if old_config_bytes != local_bytes:
            _atomic_bytes(config_path, local_bytes)
        if changed:
            if (hooks_path.read_bytes() if hooks_path.exists() else None) != before:
                raise ValueError('Hookdefinition wurde gleichzeitig geändert; fremde Änderung bleibt erhalten.')
            _atomic_bytes(hooks_path, _json_bytes(updated))
    except (OSError, ValueError):
        # Roll back only our own bytes; never erase a concurrent foreign edit.
        if config_path.exists() and config_path.read_bytes() == local_bytes:
            if old_config_bytes is None:
                config_path.unlink()
            else:
                _atomic_bytes(config_path, old_config_bytes)
        raise
    evidence_groups = updated['hooks'].get('PostToolUse', [])
    evidence_installed = isinstance(evidence_groups, list) and sum(
        1 for group in evidence_groups
        if isinstance(group, dict) and 'matcher' not in group and isinstance(group.get('hooks'), list)
        for handler in group['hooks'] if handler == evidence_handler) == 1
    return {'configured': True, 'session_id': session_id, 'critic_enabled': critic_enabled,
            'workflow_enabled': session_id in local.get('workflow_session_ids', []),
            'action_evidence_enabled': evidence_installed and session_id in local.get('action_evidence_session_ids', []),
            'hooks_changed': changed, 'backup_path': str(backup_path) if backup_path else None,
            'hooks_path': str(hooks_path), 'config_path': str(config_path),
            'trust_changed': False, 'live_hook_execution_verified': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description='Vorhandene Guardrails-Installation an Codex anschließen.')
    parser.add_argument('--session-id', required=True)
    parser.add_argument('--codex-home', type=Path, default=Path.home() / '.codex')
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument('--critic', action='store_true')
    selection.add_argument('--offline', action='store_true')
    parser.add_argument('--workflow', action='store_true', help='Shell-/Dateiaktionen und strukturierte Abschlüsse nur für diese Sitzung prüfen.')
    parser.add_argument('--action-evidence', action='store_true',
                        help='Tatsächliche lokale Werkzeugergebnisse über PostToolUse erfassen; setzt kein Hook-Vertrauen.')
    args = parser.parse_args(argv)
    try:
        result = configure(Path(__file__).resolve().parents[2], args.codex_home,
                           args.session_id, critic_enabled=args.critic, workflow_enabled=args.workflow,
                           action_evidence_enabled=args.action_evidence)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, TypeError) as exc:
        print(json.dumps({'configured': False, 'error': str(exc)}, ensure_ascii=False))
        return 3
