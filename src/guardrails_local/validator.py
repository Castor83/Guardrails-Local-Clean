"""Harte Freigaberegeln außerhalb des Critic; Guardrails führt sie lokal aus."""
import json
import os
import hashlib

# Vor Guardrails/OpenTelemetry-Import; die Benutzerkonfiguration bleibt unberührt.
os.environ['OTEL_SDK_DISABLED'] = 'true'
from guardrails import Guard
from guardrails.validators import Validator, register_validator, PassResult, FailResult
from .domain import CORE_METHODS, Draft, analyze_text
from .python_api import check_python_apis


def finding(rule, description, evidence, correction, severity='critical'):
    return dict(requirement_id=rule, severity=severity, description=description,
                evidence=evidence, correction=correction)


def _evaluate(draft: dict, requirements: list, facts: dict) -> dict:
    failures, pending = [], []
    try:
        d = Draft.model_validate(draft)
        if not isinstance(requirements, list) or not isinstance(facts.get('models'), dict):
            raise ValueError('Regeln oder Modellkatalog fehlen.')
        ids = [r['requirement_id'] for r in requirements]
        if len(set(ids)) != len(ids):
            raise ValueError('Doppelte Regel-ID.')
        for rid, method in CORE_METHODS.items():
            rule = next((r for r in requirements if r['requirement_id'] == rid), None)
            if not rule or rule.get('status') != 'active' or rule.get('verification_method') != method:
                raise ValueError('Pflichtregel fehlt oder wurde abgeschwächt: ' + rid)
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        return dict(status='ERROR', findings=[finding('EVIDENCE', 'Ungültige Eingabe oder Regelablage.',
                    str(exc), 'Eingabeschema und aktive Pflichtregeln wiederherstellen.', 'error')])
    parsed = analyze_text(d.text)
    api_findings = check_python_apis(d.text, facts)
    # API-Nichtexistenz ist belegbar, aber ein bewusst falsches Negativbeispiel
    # ist deshalb noch kein Anforderungsverstoß. Die Rolle muss separat belegt sein.
    reviewed_examples = facts.get('software_evidence', {}).get('reviewed_code_examples', {})
    reviewed = reviewed_examples.get(hashlib.sha256(d.text.encode('utf-8')).hexdigest(), {})
    if (isinstance(reviewed, dict) and reviewed.get('intent') == 'recommended_executable'
            and reviewed.get('evidence_quote') and reviewed['evidence_quote'] in d.text):
        failures.extend(api_findings)
    else:
        pending.extend(dict(f, severity='warning', description=f['description'] +
                            ' Die Rolle des Fragments im Gesamttext ist nicht bestätigt.') for f in api_findings)
    if parsed['rename']:
        failures.append(finding('ABLITERATED', 'Umbenennung belegt keine Abliteration.', d.text,
                                'Eine dokumentierte echte Abliterationsvariante verwenden.'))
    if parsed['unknown']:
        pending.append(finding('EVIDENCE', 'Text liegt teilweise außerhalb der belegten Extraktionsregeln.',
                               '\n'.join(parsed['unknown']), 'Strukturierte Fakten prüfen und Extraktion ergänzen; keine Freigabe erfinden.', 'warning'))
    supplied = [r.model_dump() for r in d.recommendations]
    # Alle belegten Textangaben prüfen, auch mehrere Kontexte desselben Modells.
    # Strukturierte Daten können den Originaltext ergänzen, nie verdrängen.
    recs = parsed['recommendations'] + [r for r in supplied if r not in parsed['recommendations']]
    for rec in recs:
        model = rec['model']
        quote = rec['evidence_quote']
        if quote not in d.text or model.lower() not in quote.lower():
            pending.append(finding('EVIDENCE', 'Empfehlung hat keine passende Belegstelle im Originaltext.',
                                   quote, 'Modell mit wortgetreuer Belegstelle binden.', 'warning'))
            continue
        # Eine per Eingabe erfundene positive Empfehlung darf eine negative Erwähnung nicht umdeuten.
        parsed_models = {r['model'] for r in parsed['recommendations']}
        if model not in parsed_models:
            pending.append(finding('EVIDENCE', 'Empfehlungsrolle im Text nicht unabhängig bestätigt.', model,
                                   'Empfehlung und Textzuordnung überprüfen.', 'warning'))
            continue
        info = facts['models'].get(model)
        if not info:
            pending.append(finding('ABLITERATED', 'Modellherkunft und Abliteration sind unbekannt.', model,
                                   'Quellen und exakte Variante im Betreiberkatalog belegen.', 'warning'))
            continue
        if info.get('execution') != 'local' or rec['execution'] == 'cloud_api':
            failures.append(finding('LOCAL_ONLY', 'Empfohlenes Modell wird über eine Cloud-API ausgeführt.',
                                    quote, 'Ein belegtes lokales Modell über Ollama einsetzen.'))
        elif rec['execution'] != 'local':
            pending.append(finding('LOCAL_ONLY', 'Lokale Ausführungsart nicht belegt.', quote,
                                   'Ausführung explizit lokal angeben.', 'warning'))
        if info.get('api_cost_required') is True:
            failures.append(finding('NO_PAID_API', 'Empfehlung benötigt eine potenziell kostenpflichtige Modell-API.',
                                    quote, 'Ohne externe Modell-API lokal ausführen.'))
        if info.get('abliterated_verified') is not True or not info.get('sources'):
            failures.append(finding('ABLITERATED', 'Geforderte Abliterationsvariante nicht nachgewiesen.', model,
                                    'Belegte Abliterationsvariante statt regulärer Cloud-API wählen.'))
        if info.get('execution') == 'cloud_api' and ('lokal' in d.text.lower() or 'kostenlos' in d.text.lower()):
            failures.append(finding('EVIDENCE', 'Cloud-Empfehlung widerspricht behaupteter lokaler/kostenloser Ausführung.',
                                    d.text, 'Falsche Ausführungs- und Kostenbehauptung korrigieren.'))
        if rec['estimated_vram_gb'] is not None and rec['estimated_vram_gb'] > min(16, facts.get('hardware_vram_gb', 16)):
            failures.append(finding('HARDWARE', 'Angegebener Speicherbedarf überschreitet 16 GB VRAM.',
                                    str(rec['estimated_vram_gb']), 'Messbare passende Konfiguration wählen.'))
        if info.get('execution') == 'local':
            measurement = info.get('hardware_evidence', {})
            context = rec['context_tokens']
            measured_memory = measurement.get('ollama_reported_size_gb')
            if type(measured_memory) not in (int, float) or measured_memory <= 0:
                pending.append(finding('HARDWARE', 'Dokumentierter Laufzeitspeicher fehlt.', model,
                                       'Speicherbedarf für die konkrete Konfiguration belegen.', 'warning'))
            elif measured_memory > min(16, facts.get('hardware_vram_gb', 16)):
                failures.append(finding('HARDWARE', 'Dokumentierter Laufzeitspeicher überschreitet das VRAM-Limit.',
                                        str(measured_memory), 'Eine gemessene passende Konfiguration wählen.'))
            if not context or context > measurement.get('context_tokens', 0) or measurement.get('processor') != '100% GPU':
                pending.append(finding('HARDWARE', 'Hardwareeignung für diesen Kontext ist nicht nachgewiesen.',
                                       str(context), 'Konkrete Konfiguration messen oder belegten Kontext verwenden.', 'warning'))
        for rule in requirements:
            if rule.get('status') == 'active' and rule.get('verification_method') == 'deny_model' and model in rule.get('models', []):
                failures.append(finding(rule['requirement_id'], rule['description'], quote,
                                        'Projektausschluss einhalten.'))
    for rule in requirements:
        if rule.get('status') == 'active' and rule['requirement_id'] not in CORE_METHODS and rule.get('verification_method') != 'deny_model':
            pending.append(finding(rule['requirement_id'], 'Zusatzregel hat keinen implementierten deterministischen Prüfer.',
                                   rule.get('description', ''), 'Prüfer implementieren oder fachlich eskalieren.', 'warning'))
    return dict(status='FAIL' if failures else 'UNVERIFIED' if pending else 'PASS', findings=failures + pending)


@register_validator(name='local-model-policy', data_type='string')
class LocalModelPolicy(Validator):
    def _validate(self, value, metadata):
        report = _evaluate(json.loads(value), metadata['requirements'], metadata['facts'])
        if report['status'] == 'PASS':
            return PassResult()
        return FailResult(error_message=json.dumps(report, ensure_ascii=False))


class OfflineGuard(Guard):
    def configure(self, *, num_reasks=None, allow_metrics_collection=None):
        super().configure(num_reasks=num_reasks, allow_metrics_collection=False)


def validate_draft(draft: dict, requirements: list, facts: dict) -> dict:
    # Report wird mit demselben reinen Prüfer erzeugt; Guardrails muss ihn ebenfalls passieren lassen.
    report = _evaluate(draft, requirements, facts)
    try:
        guard = OfflineGuard(use_server=False).use(LocalModelPolicy(on_fail='noop'))
        result = guard.validate(json.dumps(draft, ensure_ascii=False),
                                metadata=dict(requirements=requirements, facts=facts), num_reasks=0)
        report['guardrails_passed'] = bool(result.validation_passed)
        if report['status'] == 'PASS' and not result.validation_passed:
            report = dict(status='ERROR', guardrails_passed=False, findings=[finding('EVIDENCE',
                          'Guardrails und Fachprüfer widersprechen sich.', str(result.error),
                          'Validierung technisch untersuchen.', 'error')])
    except Exception as exc:
        report = dict(status='ERROR', guardrails_passed=False, findings=[finding('EVIDENCE',
                      'Guardrails-Prüfung fehlgeschlagen.', str(exc), 'Prüfinfrastruktur reparieren.', 'error')])
    report['scope'] = 'Modell- und API-Regeln; keine allgemeine Qualitäts- oder Faktengarantie'
    return report
