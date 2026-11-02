"""Conversation-profile entry point; model execution requires explicit source binding."""
import hashlib
from pathlib import Path

from .conversation_profiles import check_profile, select_profile, PROFILES


def check_answer(root, task, text, *, evidence=None, source_file=None, profile=None):
    selected = select_profile(task) if profile is None else profile
    report = dict(status='ERROR', profile=selected, released_text=None, checked=False,
                  findings=[], components=[], semantic_verified=False)
    try:
        if selected not in PROFILES or not isinstance(task, str) or not isinstance(text, str):
            raise ValueError('Vollständiger Auftrag, Antwort und bekanntes Profil sind erforderlich.')
        if len(task) > 262144 or len(text) > 32000:
            raise ValueError('Vollständige Eingabe überschreitet das feste Profilbudget; keine Kürzung.')
        if source_file is not None and selected != 'source':
            raise ValueError('Eine NLI-Quelle gehört ausschließlich in einen ausdrücklichen Quellenprüfauftrag.')
        base_profile = 'explanation' if source_file is not None else selected
        report = check_profile(root, base_profile, text, evidence=evidence)
        report.update(profile=selected, released_text=None,
                      task_sha256=hashlib.sha256(task.encode('utf-8')).hexdigest())
        if source_file is not None and report['status'] not in {'FAIL', 'ERROR'}:
            from .provenance_nli import check_nli
            source = Path(source_file)
            result = check_nli(Path(root), text, source)
            status = result.get('status')
            if status not in {'PASS', 'FAIL', 'ERROR', 'UNVERIFIED'}:
                raise ValueError('Unbekannter Status der expliziten Quellenprüfung.')
            if status == 'PASS' and not (
                    result.get('native_validator') is True and result.get('truncation') is False
                    and result.get('source_sha256') == hashlib.sha256(source.read_bytes()).hexdigest()
                    and result.get('answer_sha256') == hashlib.sha256(text.encode('utf-8')).hexdigest()):
                raise ValueError('Positives NLI-Ergebnis ist nicht an vollständige Quelle und Antwort gebunden.')
            report.update(status=status, checked=True, provenance_nli=result,
                source_entailment_checked=result.get('native_validator') is True,
                scope='Expliziter lokaler Quellenbezug und ausgewiesene Formregeln; keine allgemeine Tatsachenfreigabe.')
        report['final_status'] = report['status']
        return report
    except (OSError, ValueError, TypeError, ImportError) as exc:
        report.update(status='ERROR', final_status='ERROR', released_text=None,
                      error=str(exc), semantic_verified=False)
        return report
