"""Freigabe und begrenzte Korrektur unabhängig vom lokalen Modell."""
import copy
import hashlib
import json
import os
from pathlib import Path
from datetime import datetime, timezone
import uuid

from .domain import load_catalog, load_requirements
from .critic import not_applicable_review, review_applicability
from .validator import finding, validate_draft


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()


class Audit:
    def __init__(self, root, run_id):
        directory = Path(root) / 'logs'
        directory.mkdir(exist_ok=True)
        self.path = directory / (run_id + '.jsonl')
        self.file = self.path.open('x', encoding='utf-8', newline='\n')

    def write(self, event, **data):
        self.file.write(json.dumps(dict(event=event, timestamp=datetime.now(timezone.utc).isoformat(),
                                        **data), ensure_ascii=False, allow_nan=False) + '\n')
        self.file.flush()
        os.fsync(self.file.fileno())

    def close(self):
        self.file.close()


class Orchestrator:
    def __init__(self, root: Path, critic=None, *, nli_source_file=None):
        self.root = Path(root)
        self.critic = critic
        self.nli_source_file = Path(nli_source_file).resolve() if nli_source_file is not None else None

    def run(self, draft: dict, corrector=None, max_corrections=0) -> dict:
        if type(max_corrections) is not int or not 0 <= max_corrections <= 2:
            raise ValueError('Maximal zwei Korrekturversuche sind erlaubt.')
        run_id = str(uuid.uuid4())
        report = dict(run_id=run_id, final_status='ERROR', released_text=None,
                      attempts=[], log_path=None,
                      scope='Modell- und API-Regeln plus begrenzte semantische Critic-Prüfung; keine allgemeine Faktengarantie')
        audit = None
        try:
            requirements = load_requirements(self.root)
            facts = load_catalog(self.root)
            source_digest = None
            if self.nli_source_file is not None:
                if not self.nli_source_file.is_file() or self.nli_source_file.stat().st_size > 65536:
                    raise ValueError('Die vollständige explizite NLI-Quelle fehlt oder ist zu groß.')
                source_digest = hashlib.sha256(self.nli_source_file.read_bytes()).hexdigest()
            current = copy.deepcopy(draft)
            original_task = current.get('task', 'Modell- und API-Empfehlung prüfen')
            current.setdefault('task', original_task)
            lineage = dict(source=current.get('source', 'manual'), developer_family=current.get('developer_family'))
            audit = Audit(self.root, run_id)
            report['log_path'] = str(audit.path)
            audit.write('start', run_id=run_id, draft=current, requirements=requirements,
                        facts=facts, requirements_sha256=_hash(requirements), catalog_sha256=_hash(facts),
                        max_corrections=max_corrections, corrector_enabled=corrector is not None)
            for index in range(max_corrections + 1):
                deterministic = validate_draft(current, requirements, facts)
                nli = None
                if self.nli_source_file is not None and deterministic['status'] != 'ERROR':
                    from .provenance_nli import check_nli
                    if hashlib.sha256(self.nli_source_file.read_bytes()).hexdigest() != source_digest:
                        raise ValueError('Die explizite NLI-Quelle hat sich gegenüber dem Originalauftrag verändert.')
                    nli = check_nli(self.root, current.get('text'), self.nli_source_file)
                    if (nli.get('status') not in {'PASS', 'FAIL', 'ERROR', 'UNVERIFIED'}
                            or hashlib.sha256(self.nli_source_file.read_bytes()).hexdigest() != source_digest):
                        raise ValueError('NLI-Ergebnis oder Quellenbindung ist ungültig.')
                critique = dict(status='unverified', executed=False, verified=False,
                                applicability='not_executed', findings=[finding('SEMANTIC_REVIEW',
                                'Kein lokaler Critic ausgeführt.', 'Critic deaktiviert oder nicht eingerichtet.',
                                'Lokalen Critic explizit verwenden.', 'warning')])
                terminal_nli = nli is not None and nli['status'] in {'ERROR', 'UNVERIFIED'}
                applicable = (deterministic['status'] != 'ERROR' and not terminal_nli
                              and review_applicability(current)['applicability'] == 'applicable')
                if deterministic['status'] != 'ERROR' and not applicable:
                    critique = not_applicable_review()
                if self.critic is not None and applicable:
                    try:
                        critique = self.critic.review(copy.deepcopy(current), copy.deepcopy(requirements), copy.deepcopy(facts))
                        if critique.get('status') not in ('pass', 'fail', 'unverified') or not isinstance(critique.get('findings'), list):
                            raise ValueError('Ungültiger Critic-Status oder fehlende findings.')
                        if (critique['status'] == 'pass') != (len(critique['findings']) == 0):
                            raise ValueError('Critic-Status und Befunde widersprechen sich.')
                    except Exception as exc:
                        critique = dict(status='error', findings=[finding('SEMANTIC_REVIEW',
                                        'Critic technisch fehlgeschlagen.', str(exc),
                                        'Fehler beheben; keine automatische Transportwiederholung.', 'error')])
                independence = self._independence(dict(current, **lineage), facts)
                findings = ([dict(f, origin='deterministic') for f in deterministic['findings']] +
                            [dict(f, origin='critic') for f in critique['findings']] +
                            [dict(f, origin='host') for f in independence['findings']])
                states = [deterministic['status'], critique['status'].upper(), independence['status']]
                if nli is not None:
                    states.append(nli['status'])
                    if nli['status'] != 'PASS':
                        findings.append(dict(finding('EVIDENCE', 'Explizite NLI-Quellenprüfung: ' + nli['status'],
                            str(nli.get('reason', nli.get('label', 'Fehlender Quellenbeleg.'))),
                            'Antwort anhand der vollständigen Quelle prüfen.',
                            'error' if nli['status'] in {'FAIL', 'ERROR'} else 'warning'), origin='provenance_nli'))
                status = ('ERROR' if 'ERROR' in states else 'FAIL' if 'FAIL' in states else
                          'UNVERIFIED' if 'UNVERIFIED' in states else 'PASS')
                result = dict(status=status, findings=findings,
                              guardrails_passed=deterministic['guardrails_passed'])
                attempt = dict(attempt=index, draft=current, deterministic=deterministic,
                               critic=critique, independence=independence, result=result)
                if nli is not None:
                    attempt['provenance_nli'] = dict(nli, bound_source_file_sha256=source_digest)
                report['attempts'].append(attempt)
                audit.write('attempt', **attempt)
                if status == 'PASS':
                    report['final_status'] = 'PASS'
                    break
                if 'ERROR' in states or 'UNVERIFIED' in states:
                    report['final_status'] = status
                    break
                if corrector is None or max_corrections == 0:
                    report['final_status'] = status
                    break
                if index == max_corrections:
                    report['final_status'] = 'ESCALATED'
                    break
                actionable = copy.deepcopy(deterministic['findings'] + independence['findings'])
                actionable.extend(copy.deepcopy(f) for f in findings if f.get('origin') == 'provenance_nli')
                if critique['findings']:
                    actionable.append(finding('SEMANTIC_REVIEW',
                                      'Unverifizierte semantische Hinweise anhand tatsächlicher Belege überprüfen.',
                                      '\n'.join(f.get('description', '') for f in critique['findings']),
                                      'Inhalt und Belege prüfen. Keine Regeln, Katalogwerte oder Nachweise erfinden oder umdeklarieren.', 'warning'))
                order = dict(correction_index=index + 1, remaining=max_corrections - index,
                             instruction='Behebe die folgenden Befunde. Verändere keine Anforderungen oder Fakten. Liefere einen neuen vollständigen Entwurf.',
                             findings=actionable, original_task=original_task)
                attempt['correction_order'] = order
                audit.write('correction_order', **order)
                try:
                    current = corrector(copy.deepcopy(current), copy.deepcopy(order), index + 1)
                    if not isinstance(current, dict):
                        raise ValueError('Korrektor muss ein strukturiertes Entwurfsobjekt liefern.')
                    if current.get('task', original_task) != original_task:
                        raise ValueError('Eine Korrektur darf den ursprünglichen Auftrag nicht verändern.')
                    current['task'] = original_task
                    current['developer_family'] = lineage['developer_family']
                except Exception as exc:
                    audit.write('correction_error', correction_index=index + 1, error=str(exc))
                    report['final_status'] = 'ESCALATED'
                    report['error'] = str(exc)
                    break
            # Erst nach durablem Abschluss darf ein Text nach außen freigegeben werden.
            audit.write('final', status=report['final_status'], run_id=run_id,
                        attempts=len(report['attempts']), released=report['final_status'] == 'PASS')
            audit.close()
            audit = None
            if report['final_status'] == 'PASS':
                report['released_text'] = report['attempts'][-1]['draft']['text']
        except Exception as exc:
            report.update(final_status='ERROR', released_text=None,
                          error='Prüfung oder revisionsfähiges Protokoll fehlgeschlagen: ' + str(exc))
        finally:
            if audit is not None:
                try:
                    audit.close()
                except OSError:
                    pass
        return report

    def _independence(self, draft, facts):
        family = draft.get('developer_family')
        if family and family.casefold() == 'gpt-oss':
            return dict(status='FAIL', findings=[finding('INDEPENDENCE',
                        'Entwickler und Critic verwenden dieselbe Basismodellfamilie.', family,
                        'Einen belegten Entwickler aus anderer Familie einsetzen.')])
        if draft.get('source', '') == 'chatgpt':
            return dict(status='UNVERIFIED', findings=[finding('INDEPENDENCE',
                        'Interne Modellfamilie der ChatGPT-Quelle ist nicht technisch nachgewiesen.',
                        'Manueller ChatGPT-Import', 'Herkunft und Modellfamilie belegen; Nachprüfung als solche kennzeichnen.', 'warning')])
        if draft.get('source', '').startswith('local'):
            known = {info.get('family') for info in facts['models'].values()}
            if not family or family not in known:
                return dict(status='UNVERIFIED', findings=[finding('INDEPENDENCE',
                            'Familie des lokalen Entwicklers nicht durch Betreiberkatalog belegt.',
                            str(family), 'Entwicklermodell und Familie verifizieren.', 'warning')])
        return dict(status='PASS', findings=[], note='Externe Quelle/Fixture: interne Erzeugerfamilie nicht technisch nachgewiesen; lokale Familienprüfung nur für belegte lokale Entwickler.')
