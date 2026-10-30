"""Scoped, bounded Codex after-check and explicit before-final precheck.

The host may already have displayed a response when Stop runs. Neither this
adapter nor a hook error provides a guarantee of pre-display interception.
Only the existing local orchestrator supplies validation results.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid


WORKER_TIMEOUT_SECONDS = 180
MAX_JSON_BYTES = 2 * 1024 * 1024
MAX_STATE_BYTES = 65536
MAX_EVENT_BYTES = 262144
MAX_VALIDATIONS = 3
MAX_CORRECTIONS = 2
STATUSES = {"PASS", "FAIL", "ERROR", "UNVERIFIED", "ESCALATED"}
REVIEW_PREFIXES = {"Guardrails: Projekt": "project", "Guardrails: Modelle": "model"}


def _project_root():
    return Path(__file__).resolve().parents[2]


def _sha(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _uuid(value):
    if not isinstance(value, str) or str(uuid.UUID(value)) != value.lower():
        raise ValueError("Eine kanonische UUID ist erforderlich.")
    return value.lower()


def _turn(value):
    return None if value is None else _uuid(value)


def _json_bytes(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def _load_json(path, maximum=MAX_JSON_BYTES):
    with Path(path).open("rb") as stream:
        data = stream.read(maximum + 1)
    if len(data) > maximum:
        raise ValueError("Lokale JSON-Datei überschreitet die zugelassene Größe.")
    return _decode_json(data.decode("utf-8-sig"))


def _decode_json(text):
    def unique(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Doppeltes JSON-Feld.")
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError("Nicht endliche JSON-Zahl.")

    return json.loads(text, object_pairs_hook=unique, parse_constant=invalid_constant)


def _atomic_bytes(path, data):
    path = Path(path)
    if len(data) > MAX_JSON_BYTES:
        raise ValueError("Lokales Audit überschreitet die zugelassene Größe.")
    temporary = path.with_name("." + path.name + "." + str(uuid.uuid4()) + ".tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _atomic_json(path, value):
    _atomic_bytes(path, _json_bytes(value))


def _error(message, **fields):
    return dict(final_status="ERROR", released_text=None, attempts=[], log_path=None,
                error=message, **fields)


def _skipped(reason):
    return dict(final_status="SKIPPED", checked=False, released_text=None,
                attempts=[], log_path=None, reason=reason)


def _prompt_scope(prompt):
    first = prompt.splitlines()[0] if prompt else ""
    if first in REVIEW_PREFIXES:
        return REVIEW_PREFIXES[first]
    from .conversation_profiles import select_profile
    return 'project' if select_profile(prompt) == 'project' else 'conversation'


def _review_scope(state):
    if not state or state.get("review_scope") in (None, "conversation"):
        return "conversation"
    scope = state["review_scope"]
    if (scope not in {"project", "model"} or _prompt_scope(state["task"]) != scope
            or state.get("scope_sha256") != _sha(state["task_sha256"] + "\0" + scope)):
        raise ValueError("Prüfbereich gehört nicht zum unveränderten Originalauftrag.")
    return scope


def _config(root, session_id, required=False):
    """No session directory or model work before this operator-owned gate."""
    try:
        session_id = _uuid(session_id)
    except (ValueError, TypeError, AttributeError):
        if required:
            raise ValueError("Ungültige Sitzungs-ID.")
        return None
    path = root / "work/codex/config.json"
    if not path.exists():
        if required:
            raise ValueError("Der Codex-Adapter ist nicht konfiguriert.")
        return None
    config = _load_json(path, MAX_STATE_BYTES)
    if not isinstance(config, dict) or type(config.get("enabled")) is not bool:
        raise ValueError("Codex-Konfiguration benötigt enabled als bool.")
    if not config['enabled']:
        if required:
            raise ValueError("Der Codex-Adapter ist abgeschaltet.")
        return None
    sessions = config.get("session_ids")
    if not isinstance(sessions, list) or len(sessions) > 16:
        raise ValueError("Codex-Konfiguration benötigt eine begrenzte UUID-Freigabeliste.")
    allowed = {_uuid(item) for item in sessions}
    if not config["enabled"] or session_id not in allowed:
        if required:
            raise ValueError("Diese Sitzung ist für den Codex-Adapter nicht freigegeben.")
        return None
    if type(config.get("critic_enabled")) is not bool:
        raise ValueError("Codex-Konfiguration benötigt critic_enabled als bool.")
    workflow_sessions = config.get('workflow_session_ids', [])
    if (not isinstance(workflow_sessions, list) or len(workflow_sessions) > 16
            or any(_uuid(item) not in allowed for item in workflow_sessions)):
        raise ValueError('Workflow benötigt ausdrücklich registrierte Sitzungs-UUIDs.')
    evidence_sessions = config.get('action_evidence_session_ids', [])
    if (not isinstance(evidence_sessions, list) or len(evidence_sessions) > 16
            or any(_uuid(item) not in allowed for item in evidence_sessions)
            or len(set(evidence_sessions)) != len(evidence_sessions)):
        raise ValueError('Belege benötigen eine begrenzte eindeutige Teilmenge registrierter Sitzungs-UUIDs.')
    feedback_sessions = config.get('precheck_feedback_session_ids', [])
    if (not isinstance(feedback_sessions, list) or len(feedback_sessions) > 16
            or any(_uuid(item) not in allowed for item in feedback_sessions)
            or len(set(feedback_sessions)) != len(feedback_sessions)):
        raise ValueError('Feedback benötigt eine begrenzte eindeutige Teilmenge registrierter Sitzungs-UUIDs.')
    return config


@contextmanager
def _session_lock(directory):
    """OS lock is released on process death; never steal another live lock."""
    directory.mkdir(parents=True, exist_ok=True)
    stream = (directory / "session.lock").open("a+b")
    locked = False
    try:
        if stream.seek(0, 2) == 0:
            stream.write(b"0")
            stream.flush()
            os.fsync(stream.fileno())
        stream.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        locked = True
        yield
    finally:
        if locked:
            stream.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        stream.close()


def _text(value, maximum, label):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f"{label} muss nichtleerer Text mit höchstens {maximum} Zeichen sein.")
    value.encode("utf-8", errors="strict")
    return value


def _state(directory):
    path = directory / "state.json"
    if not path.exists():
        return None
    state = _load_json(path, MAX_STATE_BYTES)
    if isinstance(state, dict) and state.get('review_scope') == 'conversation':
        allowed = {'version', 'session_id', 'review_scope', 'prompt_sha256', 'latest_turn_id',
                   'task_id', 'task_file', 'profile_name', 'profile_evidence',
                   'core_corrective_prompts', 'core_continuation_hashes', 'core_stop_keys'}
        legacy = {'version', 'session_id', 'review_scope', 'prompt_sha256', 'latest_turn_id'}
        if (set(state) not in (allowed, legacy)
                or state['version'] != 1 or _uuid(state['session_id']) != directory.name
                or not isinstance(state['prompt_sha256'], str) or len(state['prompt_sha256']) != 64):
            raise ValueError('Ungültige Gesprächsbindung.')
        _turn(state['latest_turn_id'])
        if 'task_id' in state:
            expected = _task_directory(directory, state) / 'original-task.txt'
            if (Path(state['task_file']).resolve() != expected.resolve()
                    or expected.stat().st_size > MAX_EVENT_BYTES
                    or hashlib.sha256(expected.read_bytes()).hexdigest() != state['prompt_sha256']
                    or type(state['core_corrective_prompts']) is not int
                    or not 0 <= state['core_corrective_prompts'] <= MAX_CORRECTIONS
                    or not isinstance(state['core_continuation_hashes'], list)
                    or len(state['core_continuation_hashes']) > MAX_CORRECTIONS
                    or not isinstance(state['core_stop_keys'], list)
                    or len(state['core_stop_keys']) > MAX_VALIDATIONS):
                raise ValueError('Gesprächsauftrag oder Belegprüfbudget wurde verändert.')
        return state
    if (not isinstance(state, dict) or state.get("version") != 1
            or _uuid(state.get("session_id")) != directory.name
            or not isinstance(state.get("validations"), list)
            or len(state["validations"]) > MAX_VALIDATIONS
            or type(state.get("corrective_prompts")) is not int
            or not 0 <= state["corrective_prompts"] <= MAX_CORRECTIONS
            or not isinstance(state.get("continuation_hashes"), list)
            or len(state["continuation_hashes"]) > MAX_CORRECTIONS):
        raise ValueError("Ungültiger oder unbegrenzt gewachsener Sitzungsstatus.")
    _uuid(state["task_id"])
    _text(state["task"], 6000, "Gespeicherter Originalauftrag")
    if state.get("task_sha256") != _sha(state["task"]):
        raise ValueError("Gespeicherter Originalauftrag und Hash widersprechen sich.")
    _review_scope(state)
    return state


def _save_state(directory, state):
    if len(_json_bytes(state)) > MAX_STATE_BYTES:
        raise ValueError("Sitzungsstatus überschreitet 65536 Bytes.")
    _atomic_json(directory / "state.json", state)


def _task_directory(directory, state):
    return directory / "tasks" / _uuid(state["task_id"])


def _archive_state(directory, state):
    if state and state.get('task_id'):
        _atomic_json(_task_directory(directory, state) / 'state-final.json', state)


def _new_conversation(directory, session_id, prompt, turn_id):
    from .conversation_profiles import select_profile
    task_id = str(uuid.uuid4())
    task_dir = directory / 'tasks' / task_id
    task_dir.mkdir(parents=True, exist_ok=False)
    task_file = task_dir / 'original-task.txt'
    raw = prompt.encode('utf-8')
    if len(raw) > MAX_EVENT_BYTES:
        raise ValueError('Vollständiger Gesprächsauftrag überschreitet das Ereignisbudget; keine Kürzung.')
    _atomic_bytes(task_file, raw)
    constraints = {}
    length = re.search(r'\b(?:maximal|höchstens|max\.?)\s*(\d+)\s*Zeichen\b', prompt, re.I)
    if length:
        constraints['max_chars'] = int(length[1])
    state = dict(version=1, session_id=session_id, review_scope='conversation',
        prompt_sha256=_sha(prompt), latest_turn_id=turn_id, task_id=task_id, task_file=str(task_file),
        profile_name=select_profile(prompt), profile_evidence=dict(constraints=constraints),
        core_corrective_prompts=0, core_continuation_hashes=[], core_stop_keys=[])
    _atomic_json(task_dir / 'task.json', dict(event='original_conversation_task', **state))
    _save_state(directory, state)
    return state


def _conversation_context(state, feedback_enabled=False):
    command = (f'& "{sys.executable}" "{_project_root() / "codex-hook.py"}" '
               f'--precheck "<absolute Antwortdatei>" --session-id "{state["session_id"]}" '
               f'--task-file "{state["task_file"]}"')
    if feedback_enabled:
        command += f' --turn-id "{state["latest_turn_id"]}"'
    return {'hookSpecificOutput': {'hookEventName': 'UserPromptSubmit', 'additionalContext': (
        'Gesprächsprofil: ' + state['profile_name'] + '. Belegpflicht für behauptete Such-, Prüf- und '
        'Verifikationserfolge: Solche Aussagen benötigen passende tatsächliche Werkzeugergebnisse; '
        'Kontextrekonstruktion und eigene Belegangaben sind kein Ausführungsnachweis. Vor Ausgabe solcher '
        'Behauptungen den vollständigen exakten Antworttext als UTF-8-Datei prüfen: ' + command +
        '. Normale Gespräche verlangen keine Modellprüfung und keinen Arbeitsstatus. '
        'Nicht belegte Ergebnisse als Vermutung oder ungeprüft kennzeichnen. '
        'Kein automatischer Wiederholungsversuch bei ERROR/UNVERIFIED; höchstens zwei echte Korrekturen.')}}


def _new_task(directory, session_id, task, turn_id):
    task_id = str(uuid.uuid4())
    task_directory = directory / "tasks" / task_id
    task_directory.mkdir(parents=True, exist_ok=False)
    task_file = task_directory / "original-task.txt"
    _atomic_bytes(task_file, task.encode("utf-8"))
    state = dict(version=1, session_id=session_id, task_id=task_id, task=task,
                 task_sha256=_sha(task), original_turn_id=turn_id, latest_turn_id=turn_id,
                 task_file=str(task_file), validations=[], corrective_prompts=0,
                 continuation_hashes=[], terminal_status=None)
    state['review_scope'] = _prompt_scope(task)
    state['scope_sha256'] = _sha(state['task_sha256'] + '\0' + state['review_scope'])
    _atomic_json(task_directory / "task.json", dict(event="original_task", **state))
    _save_state(directory, state)
    return state


def _context(state, feedback_enabled=False):
    wrapper = _project_root() / "codex-hook.py"
    command = (f'& "{sys.executable}" "{wrapper}" --precheck "<absolute Antwortdatei>" '
               f'--session-id "{state["session_id"]}" --task-file "{state["task_file"]}"')
    if feedback_enabled:
        command += f' --turn-id "{state["latest_turn_id"]}"'
    domain = 'Modell-/API-Prüfung' if _review_scope(state) == 'model' else 'mechanische Projektprüfung'
    return ("Auftragsgebundene lokale " + domain + " ist für diesen Auftrag aktiv. Vor der finalen Antwort den "
            "exakten vollständigen Antworttext als UTF-8-Datei speichern und prüfen: " + command +
            ". Genau den geprüften Text verwenden; jede Änderung braucht eine neue Prüfung. "
            "Originalauftrag bleibt in der angegebenen task-file erhalten. Behauptete Such- und Prüferfolge benötigen tatsächliche "
            "passende Werkzeugergebnisse; eigene Belegangaben sind kein Ausführungsnachweis. PASS gilt nur im "
            "ausgewiesenen Prüfumfang; FAIL/ERROR/UNVERIFIED/ESCALATED sind keine vollständige "
            "Freigabe. Bei Nicht-PASS Status und Auditpfad nennen, keine allgemeine Richtigkeit "
            "behaupten. Höchstens zwei Korrekturen; UNVERIFIED/ERROR nicht automatisch wiederholen. "
            "Stop prüft nachträglich und garantiert keine Sperre vor der Anzeige.")


def _prompt(root, session_id, turn_id, prompt, workflow_enabled=False, feedback_enabled=False):
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError('Benutzerbeitrag muss nichtleerer Text sein.')
    directory = root / "work/codex/sessions" / session_id
    with _session_lock(directory):
        state = _state(directory)
        legacy_match = state is not None and _sha(prompt) in (state.get("continuation_hashes", [])
                                                             + state.get('core_continuation_hashes', []))
        pending_origin = state is not None and (
            state.get('core_corrective_prompts', 0) > 0 or
            state.get('corrective_prompts', 0) > 0 and state.get('terminal_status') is None)
        if legacy_match and pending_origin:
            return dict(systemMessage='Guardrails Local: UNVERIFIED. Herkunft der alten Fortsetzung '
                'ist nicht eindeutig belegt; keine geerbte Autorität und kein neues Korrekturbudget.',
                **{'continue': False})
        duplicate = (state is not None and prompt == state.get("task")
                     and turn_id == state.get("original_turn_id"))
        if state and state.get('review_scope') == 'conversation':
            duplicate = (_sha(prompt) == state.get('prompt_sha256')
                         and turn_id == state.get('latest_turn_id'))
        if not duplicate:
            if _prompt_scope(prompt) == 'conversation':
                _archive_state(directory, state)
                state = _new_conversation(directory, session_id, prompt, turn_id)
                return _conversation_context(state, feedback_enabled)
            prompt = _text(prompt, 6000, 'Originalauftrag')
            _archive_state(directory, state)
            state = _new_task(directory, session_id, prompt, turn_id)
        else:
            state["latest_turn_id"] = turn_id
            _save_state(directory, state)
        if _review_scope(state) == 'conversation':
            return _conversation_context(state, feedback_enabled)
        context = _context(state, feedback_enabled)
        if workflow_enabled:
            from .workflow import ensure_contract
            contract = ensure_contract(root, state)
            context += (' Workflow aktiv: ' + json.dumps(contract['decisions'], ensure_ascii=False) +
                        '. Beginne finale Texte mit Arbeitsstatus: OFFEN oder Arbeitsstatus: ABGESCHLOSSEN. '
                        'ABGESCHLOSSEN benötigt einen aktuellen Beleg des festen CPU-Testrunners: '
                        f'& "{sys.executable}" "{root / "workflow-check.py"}" --session-id "{session_id}" --run-tests. '
                        'Shell und apply_patch werden positiv geprüft; unbekannte Befehle bleiben gesperrt. '
                        'Der Vertrag ist keine vollständige semantische Auswertung aller früheren Chats.')
        return {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
                                       "additionalContext": context}}


def _snapshots(root, review_scope='model'):
    snapshots = {}
    if review_scope == 'project':
        for name in ('codex_hook', 'workflow', 'workflow_validators'):
            snapshots[name + '_code_sha256'] = hashlib.sha256(
                Path(__file__).with_name(name + '.py').read_bytes()).hexdigest()
        return snapshots
    for name in ("requirements", "catalog", "settings"):
        path = root / "config" / (name + ".json")
        _load_json(path)  # Fail before model work on missing, oversized or malformed input.
        snapshots[name + "_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    # Bind cached checks and during-run stability to the implementation used by
    # our worker, not to a caller-supplied root that may only hold test configs.
    snapshots["critic_code_sha256"] = hashlib.sha256(
        Path(__file__).with_name("critic.py").read_bytes()).hexdigest()
    return snapshots


def _worker_command(request, response):
    return [sys.executable, str(_project_root() / "codex-hook.py"), "--worker",
            str(request), str(response)]


def _run_worker(root, draft, critic_enabled, directory):
    """One child only. A hard parent deadline kills our own worker, never Ollama."""
    request = directory / ("worker-request-" + str(uuid.uuid4()) + ".json")
    response = directory / ("worker-response-" + str(uuid.uuid4()) + ".json")
    _atomic_json(request, dict(root=str(root), draft=draft, critic_enabled=critic_enabled))
    options = dict(stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if os.name == "nt":
        options["creationflags"] = subprocess.CREATE_NO_WINDOW
    process = None
    try:
        process = subprocess.Popen(_worker_command(request, response), **options)
        try:
            process.wait(timeout=min(WORKER_TIMEOUT_SECONDS, 180))
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
            return _error("Lokaler Critic-Worker nach hartem 180-Sekunden-Limit beendet; "
                          "keine Wiederholung. Der Modellserver selbst ist keine abbrechbare OS-Sandbox.")
        if process.returncode != 0:
            return _error("Lokaler Prüf-Worker fehlgeschlagen; keine automatische Wiederholung.")
        report = _load_json(response)
        if not isinstance(report, dict):
            raise ValueError("Worker lieferte kein Berichtsobjekt.")
        return report
    except (OSError, ValueError, TypeError, subprocess.SubprocessError) as exc:
        if process is not None and process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        return _error("Lokaler Prüf-Worker oder sein Ergebnis fehlgeschlagen: " + str(exc))


def _worker(request, response):
    try:
        data = _load_json(request)
        if not isinstance(data, dict) or type(data.get("critic_enabled")) is not bool:
            raise ValueError("Ungültiger interner Worker-Auftrag.")
        root = Path(data["root"])
        from .orchestrator import Orchestrator
        critic = None
        if data["critic_enabled"]:
            from .critic import OllamaCritic
            critic = OllamaCritic(_load_json(root / "config/settings.json"))
        report = Orchestrator(root, critic=critic).run(data["draft"], max_corrections=0)
    except Exception as exc:
        report = _error("Lokaler Worker konnte Prüfung nicht ausführen: " + str(exc))
    _atomic_json(response, report)
    return 0


def _checked_report(report, draft, review_scope='model', workflow_report=None):
    if (not isinstance(report, dict) or report.get("final_status") not in STATUSES
            or report.get("released_text") is not None):
        return _error("Ungültiger Worker-Bericht oder unzulässige Freigabe.")
    if review_scope == 'project':
        if report['final_status'] == 'ERROR':
            return report
        attempts = report.get('attempts')
        if (report.get('review_scope') != 'project' or report.get('workflow') != workflow_report
                or report['final_status'] != workflow_report['status']
                or not isinstance(attempts, list) or len(attempts) != 1
                or attempts[0].get('draft') != draft or attempts[0].get('workflow') != workflow_report):
            return _error('Projektbericht stimmt nicht mit den aktuellen Hostbelegen überein.')
        return report
    if report["final_status"] == "PASS":
        return _error("PASS widerspricht der ungeprüften Modellfamilie der ChatGPT-Quelle.")
    attempts = report.get("attempts")
    if not isinstance(attempts, list) or len(attempts) > 1:
        return _error("Ungültige Anzahl interner Prüfversuche.")
    if report["final_status"] != "ERROR" and not attempts:
        return _error("Prüfversuch fehlt im Worker-Bericht.")
    if attempts:
        checked = attempts[0].get("draft", {})
        if any(checked.get(key) != draft[key] for key in ("text", "task", "source")):
            return _error("Worker-Bericht gehört nicht zum exakten Entwurf und Originalauftrag.")
        for component in ("deterministic", "critic", "independence") + (("workflow",) if 'workflow' in attempts[0] else ()):
            result = attempts[0].get(component)
            if not isinstance(result, dict) or not isinstance(result.get("status"), str):
                return _error("Prüfkomponente fehlt im Worker-Bericht.")
            if result["status"].upper() == "ERROR":
                # The existing orchestrator gives FAIL precedence over ERROR.
                # A technical failure must never schedule another model retry.
                report = dict(report, orchestrator_final_status=report["final_status"],
                              final_status="ERROR", released_text=None,
                              error="Prüfkomponente technisch fehlgeschlagen; keine automatische Wiederholung.")
                break
    return report


def _validate(root, directory, state, text, critic_enabled, workflow_enabled=False):
    """Caller owns the session lock throughout reservation, inference and commit."""
    review_scope = _review_scope(state)
    if review_scope == 'conversation':
        return _skipped('Kein ausdrücklich gebundener Fachprüfauftrag.'), None
    text = _text(text, 32000, "Antwort")
    if state.get("terminal_status") == "ESCALATED":
        return dict(final_status="ESCALATED", released_text=None, attempts=[], log_path=None,
                    error="Auftrag ist eskaliert; keine weiteren automatischen Prüfversuche."), None
    base_snapshots = _snapshots(root, review_scope)
    snapshots = dict(base_snapshots)
    workflow_report = None
    if workflow_enabled:
        from .workflow_validators import validate_answer
        workflow_report = validate_answer(root, state, text)
        snapshots['workflow_sha256'] = hashlib.sha256(_json_bytes(workflow_report)).hexdigest()
    elif review_scope == 'project':
        workflow_report = dict(status='UNVERIFIED', findings=[dict(
            description='Mechanische Projektprüfung ist für diese Sitzung nicht aktiviert.')])
        snapshots['workflow_sha256'] = hashlib.sha256(_json_bytes(workflow_report)).hexdigest()
    key = hashlib.sha256(_json_bytes(dict(task=state["task"], text=text, review_scope=review_scope,
                                         critic_enabled=critic_enabled, **snapshots))).hexdigest()
    task_directory = _task_directory(directory, state)
    if review_scope == 'project':
        draft = dict(text=text, source='chatgpt', task=state['task'])
    else:
        from .domain import import_text
        draft = import_text(text, source="chatgpt", task=state["task"])
    for item in state["validations"]:
        if item.get("status") == "pending":
            return _error("Eine reservierte Prüfung wurde nicht abgeschlossen. Keine stille "
                          "Wiederholung; Zustand und Audit müssen geprüft werden.",
                          adapter_audit_path=str(task_directory / ("reservation-" + item["key"] + ".json"))), item
    for item in state["validations"]:
        if item["key"] == key:
            report_path = task_directory / ("report-" + key + ".json")
            report = _checked_report(_load_json(report_path), draft, review_scope, workflow_report)
            report["adapter_audit_path"] = str(report_path)
            report["cached"] = True
            return report, item
    if len(state["validations"]) >= MAX_VALIDATIONS:
        state["terminal_status"] = "ESCALATED"
        _save_state(directory, state)
        return dict(final_status="ESCALATED", released_text=None, attempts=[], log_path=None,
                    error="Drei unterschiedliche Prüfversuche ausgeschöpft; keine Freigabe."), None
    item = dict(key=key, status="pending", text_sha256=_sha(text), stop_handled=False)
    state["validations"].append(item)
    _save_state(directory, state)  # Reserve BEFORE any potentially failing audit/model work.
    reservation = task_directory / ("reservation-" + key + ".json")
    _atomic_json(reservation, dict(event="reserved", session_id=state["session_id"],
                                   task_id=state["task_id"], original_turn_id=state["original_turn_id"],
                                   latest_turn_id=state["latest_turn_id"], draft=draft,
                                   snapshots=snapshots, critic_enabled=critic_enabled,
                                   timestamp=datetime.now(timezone.utc).isoformat()))
    try:
        if review_scope == 'project':
            mechanical = workflow_report or dict(status='UNVERIFIED', findings=[dict(
                description='Mechanische Projektprüfung ist für diese Sitzung nicht aktiviert.')])
            report = dict(final_status=mechanical['status'], released_text=None, log_path=None,
                review_scope='project', workflow=mechanical,
                scope='Nur auftragsgebundene mechanische Projekt-/Abschlussbelege; keine allgemeine Qualitätsfreigabe.',
                attempts=[dict(attempt=0, draft=draft, workflow=mechanical,
                    deterministic=mechanical, critic=dict(status='skipped', executed=False, findings=[]),
                    independence=dict(status='SKIPPED', findings=[]),
                    result=dict(status=mechanical['status'], findings=mechanical.get('findings', [])))])
        else:
            report = _checked_report(_run_worker(root, draft, critic_enabled, task_directory), draft)
        if (_snapshots(root, review_scope) != base_snapshots or (workflow_enabled
                and validate_answer(root, state, text) != workflow_report)):
            report = _error("Regeln, Katalog oder Einstellungen haben sich während der Prüfung geändert. "
                            "Ergebnis nicht unter dem früheren Stand zwischenspeichern; keine Freigabe.")
    except Exception as exc:
        report = _error("Prüf-Worker fehlgeschlagen; keine Wiederholung: " + str(exc))
    if workflow_report is not None:
        report['workflow'] = workflow_report
        for attempt in report.get('attempts', []):
            attempt['workflow'] = workflow_report
        if report['final_status'] != 'ERROR':
            if workflow_report['status'] == 'ERROR':
                report.update(final_status='ERROR', released_text=None, error='Workflow-Prüfung technisch fehlgeschlagen.')
            elif workflow_report['status'] == 'FAIL':
                report.update(final_status='FAIL', released_text=None)
            elif workflow_report['status'] == 'UNVERIFIED' and report['final_status'] == 'PASS':
                report.update(final_status='UNVERIFIED', released_text=None)
    report_path = task_directory / ("report-" + key + ".json")
    report["adapter_audit_path"] = str(report_path)
    report["cached"] = False
    report["adapter"] = dict(session_id=state["session_id"], task_id=state["task_id"],
                             task_sha256=state["task_sha256"], text_sha256=_sha(text),
                             snapshots=snapshots, critic_enabled=critic_enabled,
                             validation_number=len(state["validations"]),
                             scope="Automatische Nachprüfung und explizite Vorabprüfung; keine garantierte Anzeigesperre")
    _atomic_json(report_path, report)
    item.update(status="done", final_status=report["final_status"])
    _save_state(directory, state)
    return report, item


def _summary(report):
    message = "Guardrails Local: " + report["final_status"] + ". "
    if report.get("error"):
        message += report["error"] + " "
    message += "Keine vollständige Freigabe; begrenzter Prüfumfang."
    audit = report.get("adapter_audit_path") or report.get("log_path")
    if audit:
        message += " Lokales Audit: " + audit
    return message


def _claim_check(root, directory, state, text):
    config = _config(root, state['session_id'])
    if config is None or state['session_id'] not in config.get('action_evidence_session_ids', []):
        checked = dict(status='SKIPPED', checked=False, semantic_verified=False,
                       scope='action-claims', findings=[], reason='Keine aktuelle Belegfreigabe für diese Sitzung.')
    else:
        from .action_evidence import check_action_claims
        checked = check_action_claims(root, state['session_id'], state.get('latest_turn_id'), text)
    status = checked['status']
    report = dict(final_status=status, released_text=None, attempts=[], log_path=None,
        action_claims=checked, scope=checked.get('scope'), checked=checked.get('checked', False))
    if status != 'SKIPPED':
        key = hashlib.sha256(_json_bytes(dict(prompt=state.get('prompt_sha256', state.get('task_sha256')),
            turn=state.get('latest_turn_id'), text=text, evidence=checked))).hexdigest()
        path = _task_directory(directory, state) / ('claim-check-' + key + '.json')
        report['adapter_audit_path'] = str(path)
        _atomic_json(path, report)
    return report


def _with_action_claims(root, directory, state, text, base):
    """Fresh receipts augment the response, never the model/workflow cache."""
    claims = _claim_check(root, directory, state, text)
    report = dict(base, action_claims=claims['action_claims'])
    status = claims['final_status']
    if (report['final_status'] not in {'ERROR', 'ESCALATED'}
            and (status in {'FAIL', 'ERROR'}
                 or status == 'UNVERIFIED' and report['final_status'] == 'PASS')):
        report.update(final_status=status, released_text=None)
    if status != 'SKIPPED':
        report['base_adapter_audit_path'] = base.get('adapter_audit_path')
        report['action_audit_path'] = claims.get('adapter_audit_path')
        key = hashlib.sha256(_json_bytes(report)).hexdigest()
        path = _task_directory(directory, state) / ('combined-check-' + key + '.json')
        report['adapter_audit_path'] = str(path)
        _atomic_json(path, report)
    return report, claims


def _conversation_check(root, directory, state, text):
    from .profile_checks import check_answer
    task = _read_text_file(state['task_file'], MAX_EVENT_BYTES, 'Gesprächsauftrag')
    profile = check_answer(root, task, text, evidence=state['profile_evidence'], profile=state['profile_name'])
    claims = _claim_check(root, directory, state, text)
    states = [profile['status'], claims['final_status']]
    status = next((s for s in ('ERROR', 'FAIL', 'UNVERIFIED') if s in states),
                  'SKIPPED' if all(s == 'SKIPPED' for s in states) else 'PASS')
    report = dict(final_status=status, released_text=None, attempts=[], log_path=None,
                  profile_check=profile, action_claims=claims['action_claims'], semantic_verified=False,
                  scope='Gesprächsprofil und freigegebene Aktionsbelege; keine allgemeine Freigabe.')
    if status != 'SKIPPED':
        path = _task_directory(directory, state) / ('conversation-check-' +
            hashlib.sha256(_json_bytes(dict(report=report, turn=state['latest_turn_id'], text=text))).hexdigest() + '.json')
        report['adapter_audit_path'] = str(path)
        _atomic_json(path, report)
    return report


def _conversation_stop(root, directory, state, text):
    if 'task_id' not in state:
        return {}
    text = _text(text, 32000, 'Antwort')
    report = _conversation_check(root, directory, state, text)
    if report['final_status'] in {'FAIL', 'ERROR', 'UNVERIFIED'}:
        return dict(systemMessage=_summary(report) + ' Native automatische Korrektur bleibt ohne '
                    'eindeutige Herkunft des Folgeereignisses ausgesetzt.', **{'continue': False})
    return {}


def _stop(root, session_id, turn_id, text, config):
    directory = root / "work/codex/sessions" / session_id
    with _session_lock(directory):
        state = _state(directory)
        if _review_scope(state) == 'conversation':
            if state is None or turn_id != state.get('latest_turn_id'):
                return {}
            return _conversation_stop(root, directory, state, text)
        if turn_id != state.get('latest_turn_id'):
            return {}
        state["latest_turn_id"] = turn_id
        if isinstance(text, str) and not text.strip():
            path = _task_directory(directory, state) / ("empty-final-" + str(uuid.uuid4()) + ".json")
            report = dict(final_status="UNVERIFIED", released_text=None, attempts=[], log_path=None,
                          error="Leere finale Antwort: keine Inferenz ausgeführt.", adapter_audit_path=str(path))
            _atomic_json(path, report)
            return dict(systemMessage=_summary(report), **{'continue': False})
        report, item = _validate(root, directory, state, text, config["critic_enabled"],
                                 session_id in config.get('workflow_session_ids', []))
        report, claims = _with_action_claims(root, directory, state, text, report)
        if item is not None and item.get("stop_handled"):
            if report["final_status"] == "FAIL" and state["corrective_prompts"]:
                state["terminal_status"] = "ESCALATED"
                _save_state(directory, state)
                return dict(systemMessage="Guardrails Local: ESCALATED. Identischer abgelehnter Entwurf; "
                            "keine erneute Inferenz oder Korrekturschleife. " + _summary(report), **{"continue": False})
            return dict(systemMessage=_summary(report) + " Identischer Stop wurde bereits behandelt.",
                        **{"continue": False})
        output = dict(systemMessage=_summary(report))
        host_failure = any(
            attempt.get(component, {}).get("status", "").upper() == "FAIL"
            for attempt in report.get("attempts", [])
            for component in ("deterministic", "independence", "workflow")
        )
        host_failure = host_failure or claims['final_status'] == 'FAIL'
        if report["final_status"] == "FAIL" and not host_failure:
            output["systemMessage"] += (" Der ablehnende Critic-Befund ist nicht durch einen "
                                        "Hostverstoß belegt; keine automatische Umschreibeschleife.")
            output["continue"] = False
        elif report["final_status"] == "FAIL":
            state['terminal_status'] = 'FAIL'
            output['continue'] = False
            output['systemMessage'] += (' Native automatische Korrektur bleibt ohne eindeutige Herkunft '
                                        'des Folgeereignisses ausgesetzt; explizite Vorprüfung bleibt verfügbar.')
        elif report["final_status"] in ("ERROR", "UNVERIFIED", "ESCALATED"):
            output["continue"] = False
        if item is not None:
            item["stop_handled"] = True
        _atomic_json(_task_directory(directory, state) / ("stop-" + str(uuid.uuid4()) + ".json"),
                     dict(event="stop", check_status=report["final_status"], response=output))
        _save_state(directory, state)
        return output


def handle_event(payload, root=None):
    root = Path(root) if root is not None else _project_root()
    feedback_enabled = False
    try:
        if not isinstance(payload, dict):
            raise ValueError("Hook-Eingabe muss ein JSON-Objekt sein.")
        session_id = payload.get("session_id")
        config = _config(root, session_id)
        if config is None:
            return {}
        session_id = _uuid(session_id)
        event = payload.get("hook_event_name")
        if event not in ("UserPromptSubmit", "Stop", "PreToolUse", "PostToolUse"):
            return {}
        turn_id = _turn(payload.get("turn_id"))
        workflow_enabled = session_id in config.get('workflow_session_ids', [])
        feedback_enabled = session_id in config.get('precheck_feedback_session_ids', [])
        if event == 'PostToolUse':
            evidence_enabled = session_id in config.get('action_evidence_session_ids', [])
            if not evidence_enabled and not feedback_enabled:
                return {}
            directory = root / 'work/codex/sessions' / session_id
            with _session_lock(directory):
                state = _state(directory)
                if state is None or turn_id is None or turn_id != state.get('latest_turn_id'):
                    return {}
                if evidence_enabled:
                    from .action_evidence import record_tool_result
                    try:
                        record_tool_result(root, session_id, turn_id, payload.get('tool_name'),
                            payload.get('tool_use_id'), payload.get('tool_input'), payload.get('tool_response'))
                    except Exception as exc:
                        if feedback_enabled:
                            from .precheck_feedback import event_error
                            return event_error(root, directory, state, payload, exc)
                        raise
                if feedback_enabled:
                    from .precheck_feedback import consume
                    return consume(root, directory, state, config, payload)
            return {}
        if event == 'PreToolUse':
            if not workflow_enabled:
                return {}
            from .workflow import tool_decision
            directory = root / 'work/codex/sessions' / session_id
            with _session_lock(directory):
                state = _state(directory)
                if _review_scope(state) == 'conversation':
                    return {}
                return tool_decision(root, state, payload)
        if event == "UserPromptSubmit":
            return _prompt(root, session_id, turn_id, payload.get("prompt"), workflow_enabled, feedback_enabled)
        return _stop(root, session_id, turn_id, payload.get("last_assistant_message"), config)
    except Exception as exc:
        if feedback_enabled and isinstance(payload, dict) and payload.get('hook_event_name') == 'PostToolUse':
            return dict(systemMessage=_summary(_error('PostToolUse-Prüfung fehlgeschlagen: ' + str(exc))))
        if isinstance(payload, dict) and payload.get('hook_event_name') == 'PreToolUse':
            return dict(hookSpecificOutput=dict(hookEventName='PreToolUse', permissionDecision='deny',
                        permissionDecisionReason='Workflow-Prüfung fehlgeschlagen: ' + str(exc)))
        return dict(systemMessage=_summary(_error("Hook-Prüfung fehlgeschlagen: " + str(exc))),
                    **{"continue": False})


def _read_text_file(path, maximum, label):
    with Path(path).open("rb") as stream:
        data = stream.read(4 * maximum + 1)
    if len(data) > 4 * maximum:
        raise ValueError(label + " überschreitet die zugelassene Größe.")
    return _text(data.decode("utf-8", errors="strict"), maximum, label)


def precheck(answer_path, session_id, task_path, turn_id=None, root=None):
    root = Path(root) if root is not None else _project_root()
    try:
        session_id = _uuid(session_id)
        config = _config(root, session_id)
        if config is None:
            return _skipped('Adapter abgeschaltet oder Sitzung nicht registriert.')
        turn_id = _turn(turn_id)
        directory = root / "work/codex/sessions" / session_id
        with _session_lock(directory):
            state = _state(directory)
            config = _config(root, session_id)
            if config is None:
                return _skipped('Sitzungsfreigabe wurde widerrufen.')
            light = _review_scope(state) == 'conversation'
            if state is None or 'task_file' not in state:
                return _skipped('Kein aktiver auftragsgebundener Prüfbereich.')
            feedback_enabled = session_id in config.get('precheck_feedback_session_ids', [])
            if light and Path(task_path).resolve() != Path(state['task_file']).resolve():
                return _error('Feedback-Vorprüfung verweist auf abgelösten Auftrag.') if feedback_enabled else _skipped(
                    'Vorprüfung verweist auf einen abgelösten Auftrag.')
            text = _read_text_file(answer_path, 32000, 'Antwort')
            task = _read_text_file(task_path, MAX_EVENT_BYTES if light else 6000, 'Originalauftrag')

            def check():
                if light:
                    if _sha(task) != state.get('prompt_sha256'):
                        return _error('Gesprächsauftrag wurde verändert.')
                    if turn_id is not None and turn_id != state.get('latest_turn_id'):
                        return _error('Vorprüfung gehört nicht zum aktiven Turn.')
                    return _conversation_check(root, directory, state, text)
                if task != state['task']:
                    raise ValueError('task-file darf den gespeicherten Originalauftrag nicht ersetzen.')
                if turn_id is not None and turn_id != state.get('latest_turn_id'):
                    raise ValueError('Vorprüfung gehört nicht zum aktiven Turn.')
                report, _ = _validate(root, directory, state, text, config['critic_enabled'],
                                     session_id in config.get('workflow_session_ids', []))
                report, _ = _with_action_claims(root, directory, state, text, report)
                return report

            if feedback_enabled:
                from .precheck_feedback import run
                return run(root, directory, state, config, answer_path, task_path, turn_id, text, check)
            return check()
    except Exception as exc:
        return _error("Vorabprüfung fehlgeschlagen: " + str(exc))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Begrenzter lokaler Codex-Prüfadapter.")
    parser.add_argument("--precheck", type=Path)
    parser.add_argument("--session-id")
    parser.add_argument("--task-file", type=Path)
    parser.add_argument("--turn-id")
    parser.add_argument("--worker", nargs=2, metavar=("REQUEST", "RESPONSE"), help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.worker:
        return _worker(*args.worker)
    if args.precheck is not None:
        report = precheck(args.precheck, args.session_id, args.task_file, args.turn_id)
        print(json.dumps(report, ensure_ascii=False, allow_nan=False))
        return 0 if report["final_status"] in {"PASS", "SKIPPED"} else 3 if report["final_status"] == "ERROR" else 2
    try:
        # Stdin only. Never read transcript_path or arbitrary event-supplied files.
        stream = getattr(sys.stdin, "buffer", sys.stdin)
        data = stream.read(MAX_EVENT_BYTES + 1)
        if isinstance(data, bytes):
            data = data.decode("utf-8", errors="strict")
        if len(data.encode("utf-8")) > MAX_EVENT_BYTES:
            raise ValueError("Hook-Eingabe überschreitet 262144 Bytes.")
        output = handle_event(_decode_json(data))
    except Exception as exc:
        output = dict(systemMessage=_summary(_error("Ungültige Hook-Eingabe: " + str(exc))),
                      **{"continue": False})
    print(json.dumps(output, ensure_ascii=False, allow_nan=False))
    # Host receives a structured failure, not an accidental fail-open process code.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
