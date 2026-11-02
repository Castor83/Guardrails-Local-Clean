"""Guardrails-native checks with explicit mechanical coverage, no new models."""
import json
import os
from pathlib import Path

os.environ['OTEL_SDK_DISABLED'] = 'true'
from guardrails.validators import Validator, register_validator, PassResult, FailResult
from .validator import OfflineGuard, _evaluate
from .domain import import_text, load_requirements, load_catalog
from .workflow import ensure_contract, completion_report, _shell_allowed, _patch_allowed, work_status


def instruction_compliance(value, metadata):
    ensure_contract(metadata['root'], metadata['state'])
    status = 'PASS' if work_status(value)[1] else 'UNVERIFIED'
    return dict(status=status, findings=[] if status == 'PASS' else [dict(
                description='Vorgeschriebene strukturierte Arbeitsstatusdeklaration fehlt.')],
                scope='Exakte Auftrags-/Quellenbindung und vorgeschriebener Arbeitsstatus; '
                      'keine vollständige semantische Auftragsprüfung.')


def decision_consistency(value, metadata):
    root, state = Path(metadata['root']).resolve(), metadata['state']
    ensure_contract(root, state)
    if metadata.get('action') is True:
        payload = json.loads(value)
        allowed = (payload.get('turn_id') == state.get('latest_turn_id') and (
            payload.get('tool_name') == 'Bash' and _shell_allowed(root, state, payload.get('tool_input', {}).get('command'))
            or payload.get('tool_name') == 'apply_patch' and _patch_allowed(root, payload)))
        return dict(status='PASS' if allowed else 'FAIL', findings=[] if allowed else [dict(
                    description='Arbeitsaktion ist nicht durch die feste Workflow-Policy freigegeben.')],
                    scope='Feste Arbeitsbereichs-, Schreibschutz- und positiv erkannte Befehlsregeln.')
    if state.get('review_scope', 'project') != 'model':
        return dict(status='PASS', findings=[],
                    scope='Unveränderte auftragsgebundene Projektpolicy; keine Modell-/API- oder Prosa-Bewertung.')
    report = _evaluate(import_text(value, source='chatgpt', task=state['task']),
                       load_requirements(root), load_catalog(root))
    report['scope'] = ('Unveränderte bestätigte Policy plus bestehende Modell-/API-Entscheidungsregeln; '
                       'beliebige frühere Gesprächsentscheidungen werden nicht vollständig semantisch geprüft.')
    return report


def completion_evidence(value, metadata):
    return completion_report(metadata['root'], metadata['state'], value)


def _report(checker, value, metadata):
    try:
        return checker(value, metadata)
    except Exception as exc:
        return dict(status='ERROR', findings=[dict(description=str(exc))])


@register_validator(name='local/instruction-compliance', data_type='string')
class InstructionCompliance(Validator):
    def _validate(self, value, metadata):
        result = _report(instruction_compliance, value, metadata)
        return PassResult() if result['status'] == 'PASS' else FailResult(error_message=json.dumps(result, ensure_ascii=False))


@register_validator(name='local/decision-consistency', data_type='string')
class DecisionConsistency(Validator):
    def _validate(self, value, metadata):
        result = _report(decision_consistency, value, metadata)
        return PassResult() if result['status'] == 'PASS' else FailResult(error_message=json.dumps(result, ensure_ascii=False))


@register_validator(name='local/completion-evidence', data_type='string')
class CompletionEvidence(Validator):
    def _validate(self, value, metadata):
        result = _report(completion_evidence, value, metadata)
        return PassResult() if result['status'] == 'PASS' else FailResult(error_message=json.dumps(result, ensure_ascii=False))


def checked(validator, checker, value, metadata):
    report = _report(checker, value, metadata)
    try:
        result = OfflineGuard(use_server=False).use(validator(on_fail='noop')).validate(
                     value, metadata=metadata, num_reasks=0)
        report['guardrails_passed'] = bool(result.validation_passed)
        if report['guardrails_passed'] != (report['status'] == 'PASS'):
            return dict(status='ERROR', findings=[dict(description='Guardrails und Workflow-Fachprüfer widersprechen sich.')])
    except Exception as exc:
        return dict(status='ERROR', findings=[dict(description='Guardrails-Workflow-Prüfung fehlgeschlagen: ' + str(exc))])
    return report


def validate_answer(root, state, value):
    metadata = dict(root=str(root), state=state)
    reports = {
        'InstructionCompliance': checked(InstructionCompliance, instruction_compliance, value, metadata),
        'DecisionConsistency': checked(DecisionConsistency, decision_consistency, value, metadata),
        'CompletionEvidence': checked(CompletionEvidence, completion_evidence, value, metadata),
        'ProvenanceNLI': dict(status='SKIPPED', findings=[], scope=(
            'Diese wiederholbare Antwort-Momentaufnahme führt kein NLI-Modell aus. '
                        'Explizite Quellenprüfung ist im Prüfablauf über check --nli-source verfügbar; '
                        'kein expliziter Quellenprüfauftrag in diesem Hook.'))}
    statuses = [r['status'] for r in reports.values()]
    status = next((s for s in ('ERROR', 'FAIL', 'UNVERIFIED') if s in statuses), 'PASS')
    return dict(status=status, validators=reports,
                findings=[dict(item, validator=name) for name, report in reports.items() for item in report.get('findings', [])],
                scope='Ausgewiesene deterministische Prüfumfänge; keine allgemeine semantische Richtigkeitsfreigabe.')
