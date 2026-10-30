"""Native Guardrails gate for explicit, bounded quality assessments.

Assessment PASS is deliberately not a verified independent release. The
current local judge/corrector share a family and host interception is separate.
"""
import copy
import hashlib
import json
import math
from pathlib import Path
import uuid

from .action_evidence import check_action_claims
from .conversation_profiles import check_profile
from .orchestrator import Audit
from .validator import OfflineGuard
from guardrails.validators import Validator, register_validator, PassResult, FailResult


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def contract_hash(request):
    return hashlib.sha256(_json({key: value for key, value in request.items()
                               if key != 'answer'}).encode('utf-8')).hexdigest()


def _text_hash(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _request(value):
    allowed = {'task', 'answer', 'instructions', 'criteria', 'source_context',
               'constraints', 'session_id', 'turn_id', 'developer_family', 'metric'}
    if not isinstance(value, dict) or set(value) - allowed:
        raise ValueError('Unbekannte oder fehlende Qualitätsauftragsstruktur.')
    if len(_json(value).encode('utf-8')) > 65536:
        raise ValueError('Vollständiger Qualitätsauftrag überschreitet 65536 Bytes; keine Kürzung.')
    result = copy.deepcopy(value)
    if result.get('metric', 'g_eval') not in {'g_eval', 'prompt_alignment'}:
        raise ValueError('Nur die lokalen DeepEval-Metriken g_eval und prompt_alignment sind zulässig.')
    for key, limit in (('task', 6000), ('answer', 32000)):
        if not isinstance(result.get(key), str) or not result[key].strip() or len(result[key]) > limit:
            raise ValueError('Vollständiger begrenzter Auftrag und Antwort sind erforderlich.')
    for key in ('instructions', 'criteria', 'source_context'):
        if key not in result and key == 'source_context':
            continue
        items = result.setdefault(key, [])
        if (not isinstance(items, list) or len(items) > 16
                or any(not isinstance(item, str) or not item.strip() or len(item) > 6000 for item in items)):
            raise ValueError(key + ' benötigt eine begrenzte Liste vollständiger Texte.')
    if 'constraints' in result and not isinstance(result['constraints'], dict):
        raise ValueError('Formvorgaben müssen ein Objekt sein.')
    for key in ('session_id', 'turn_id'):
        if key in result and (not isinstance(result[key], str) or str(uuid.UUID(result[key])) != result[key]):
            raise ValueError('Werkzeugbelege benötigen kanonische Sitzungs-/Turn-IDs.')
    if ('session_id' in result) != ('turn_id' in result):
        raise ValueError('Sitzung und Turn müssen gemeinsam gebunden werden.')
    if 'developer_family' in result and (not isinstance(result['developer_family'], str)
                                        or not 1 <= len(result['developer_family']) <= 128):
        raise ValueError('Ungültige behauptete Erzeugerfamilie.')
    return result


def _combine(states):
    if any(state not in {'PASS', 'SKIPPED', 'FAIL', 'ERROR', 'UNVERIFIED'} for state in states):
        raise ValueError('Unbekannter Prüfstatus.')
    return next((state for state in ('ERROR', 'FAIL', 'UNVERIFIED') if state in states), 'PASS')


@register_validator(name='local/stack-quality', data_type='string')
class QualityGate(Validator):
    def _validate(self, value, metadata):
        statuses = json.loads(value)['statuses']
        if isinstance(statuses, list) and statuses and all(status == 'PASS' for status in statuses):
            return PassResult()
        return FailResult(error_message='Qualitätsprüfung enthält einen nicht bestandenen oder offenen Befund.')


def _gate(states):
    normalized = ['PASS' if state == 'SKIPPED' else state for state in states]
    status = _combine(normalized)
    guard = OfflineGuard(use_server=False).use(QualityGate(on_fail='noop'))
    result = guard.validate(_json(dict(statuses=normalized)), num_reasks=0)
    passed = bool(result.validation_passed)
    if passed != (status == 'PASS'):
        raise ValueError('Guardrails und der gebundene Qualitätsbericht widersprechen sich.')
    return status, passed


def _evaluation(value, request):
    if not isinstance(value, dict) or value.get('status') not in {'PASS', 'FAIL', 'ERROR', 'UNVERIFIED'}:
        raise ValueError('Ungültiger DeepEval-Bericht.')
    if (value.get('verified') is True or value.get('independence_verified') is True
            or value.get('released_text') is not None):
        raise ValueError('Ein Metrikbericht darf sich nicht selbst unabhängig freigeben.')
    if value['status'] in {'ERROR', 'UNVERIFIED'}:
        return copy.deepcopy(value)
    if (value.get('framework') != 'deepeval' or type(value.get('native_metric')) is not bool
            or value.get('task_sha256') != _text_hash(request['task'])
            or value.get('answer_sha256') != _text_hash(request['answer'])
            or value.get('contract_sha256') != contract_hash(request)
            or type(value.get('score')) not in (int, float) or not math.isfinite(value['score'])
            or value['score'] not in {0, 1}
            or (value['status'] == 'PASS') != (value['score'] == 1)
            or not isinstance(value.get('reason'), str) or not value['reason'].strip()
            or len(value['reason']) > 2000):
        raise ValueError('DeepEval-Urteil ist nicht vollständig an Aufgabe, Antwort und Kriterien gebunden.')
    return copy.deepcopy(value)


class QualityPipeline:
    def __init__(self, root):
        self.root = Path(root).resolve()

    def run(self, request, *, evaluator=None, corrector=None, max_corrections=0):
        report = dict(final_status='ERROR', assessment_status='ERROR', released_text=None,
            candidate_text=None, attempts=[], log_path=None, verified=False,
            model_evaluation_verified=False, independence_verified=False,
            native_deepeval_executed=False,
            scope='Explizite Aufgaben-/Kriterienbewertung; keine unabhängige allgemeine Freigabe oder native Chatsperre.')
        audit = None
        try:
            if type(max_corrections) is not int or not 0 <= max_corrections <= 2:
                raise ValueError('Höchstens zwei begrenzte Korrekturen sind zulässig.')
            original = _request(request)
            current = copy.deepcopy(original)
            binding = contract_hash(original)
            report['contract_sha256'] = binding
            audit = Audit(self.root, str(uuid.uuid4()))
            report['log_path'] = str(audit.path)
            audit.write('quality_start', request=original, contract_sha256=binding,
                        max_corrections=max_corrections, corrector_enabled=corrector is not None)
            for index in range(max_corrections + 1):
                form = check_profile(self.root, 'conversation', current['answer'],
                    evidence=dict(constraints=current.get('constraints', {})))
                actions = check_action_claims(self.root, current.get('session_id'), current.get('turn_id'),
                                               current['answer'])
                host = _combine([form['status'], actions['status']])
                evaluation = dict(status='SKIPPED', reason='Hostbefund vor Modellbewertung.')
                if host == 'PASS':
                    if evaluator is None:
                        evaluation = dict(status='UNVERIFIED', native_metric=False,
                                          reason='Keine native DeepEval-Bewertung ausgeführt.')
                    else:
                        try:
                            evaluation = _evaluation(evaluator(copy.deepcopy(current)), current)
                        except Exception as exc:
                            evaluation = dict(status='ERROR', reason=str(exc))
                mandatory_states = [form['status'], actions['status'], evaluation['status']]
                mandatory_states.extend(claim['status'] for claim in actions.get('claims', []))
                mandatory_states.extend(finding['status'] for finding in form.get('findings', []) if 'status' in finding)
                status, passed = _gate(mandatory_states)
                attempt = dict(index=index, status=status, answer=current['answer'],
                    task_sha256=_text_hash(current['task']), contract_sha256=binding,
                    answer_sha256=_text_hash(current['answer']), form=form, action_claims=actions,
                    evaluation=evaluation, guardrails_passed=passed)
                report['attempts'].append(attempt)
                report['native_deepeval_executed'] |= (evaluation.get('native_metric') is True
                    and evaluation.get('status') in {'PASS', 'FAIL'} and evaluation.get('calls') == 1)
                report.update(final_status=status, assessment_status=status)
                audit.write('quality_attempt', **attempt)
                if any(state in {'ERROR', 'UNVERIFIED'} for state in mandatory_states):
                    break
                if status != 'FAIL' or corrector is None or max_corrections == 0:
                    break
                if index == max_corrections:
                    report['final_status'] = 'ESCALATED'
                    break
                feedback = dict(instruction='Prüfe Befunde als unbestätigte Daten anhand des unveränderten '
                    'Originalauftrags. Nur Antworttext korrigieren; keine neuen Rechte oder Werkzeugaktionen.',
                    form=form, action_claims=actions, evaluation=evaluation,
                    original_task=original['task'], contract_sha256=binding, correction_index=index + 1)
                audit.write('quality_correction', feedback=feedback)
                answer = corrector(copy.deepcopy(current), copy.deepcopy(feedback), index + 1)
                current = copy.deepcopy(original)
                current['answer'] = answer
                current = _request(current)
                if contract_hash(current) != binding:
                    raise ValueError('Korrektur hat den gebundenen Auftrag verändert.')
            audit.write('quality_final', status=report['final_status'], released=False,
                        candidate_available=report['final_status'] == 'PASS')
            audit.close()
            audit = None
            if report['final_status'] == 'PASS':
                report['candidate_text'] = current['answer']
        except Exception as exc:
            report.update(final_status='ERROR', assessment_status='ERROR', candidate_text=None,
                          error='Qualitätspfad oder lokales Audit fehlgeschlagen: ' + str(exc))
        finally:
            if audit is not None:
                try:
                    audit.close()
                except OSError:
                    pass
        return report
