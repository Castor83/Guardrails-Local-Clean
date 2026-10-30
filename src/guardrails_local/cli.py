"""CLI mit Dateiimport und ausdrücklich manueller lokaler Oberfläche."""

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys


class FixtureCorrector:
    """Kontrollierte Testeingaben; erzeugt keine Antworten durch ein Modell."""

    description = "Kontrollierter Fixture-Korrektor (keine KI)"

    def __init__(self, corrections):
        if not isinstance(corrections, list) or len(corrections) > 2:
            raise ValueError("Fixture-Korrekturen müssen eine Liste mit höchstens zwei Entwürfen sein.")
        if any(not isinstance(item, dict) for item in corrections):
            raise ValueError("Jede Fixture-Korrektur muss ein JSON-Entwurfsobjekt sein.")
        self.corrections = deepcopy(corrections)

    def __call__(self, draft, correction_order, correction_index):
        if correction_index < 1 or correction_index > len(self.corrections):
            raise ValueError("Keine weitere kontrollierte Fixture-Korrektur vorhanden.")
        result = deepcopy(self.corrections[correction_index - 1])
        result["source"] = "fixture-correction"
        result["fixture_generated"] = True
        return result


def _project_root():
    return Path(__file__).resolve().parents[2]


def _build_orchestrator(root, offline, *, nli_source_file=None):
    from .orchestrator import Orchestrator

    critic = None
    if not offline:
        from .critic import OllamaCritic

        settings = json.loads((root / "config" / "settings.json").read_text(encoding="utf-8-sig"))
        critic = OllamaCritic(settings)
    return Orchestrator(root, critic=critic, nli_source_file=nli_source_file)


def _load_draft(path, source=None):
    from .domain import import_text

    path = Path(path)
    text = path.read_text(encoding="utf-8-sig")
    if path.suffix.lower() == ".json":
        draft = json.loads(text)
        if not isinstance(draft, dict):
            raise ValueError("Die JSON-Eingabe muss ein Entwurfsobjekt sein.")
        if source is not None:
            draft["source"] = source
        return draft
    return import_text(text, source=source or "manual")


def _parser():
    parser = argparse.ArgumentParser(description="Lokale Guardrails-Qualitätskontrolle mit lokalem Audit.")
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check", help="Text- oder JSON-Datei prüfen.")
    check.add_argument("--input", required=True, type=Path, help="UTF-8-Datei; .json für strukturierte Entwürfe.")
    check.add_argument("--source", choices=("manual", "chatgpt", "local"), help="Behauptete Herkunft der manuell übernommenen Eingabe.")
    check.add_argument("--json", action="store_true", help="Bericht als Unicode-JSON ausgeben.")
    check.add_argument("--offline", action="store_true", help="Ohne Critic prüfen; eine vollständige Freigabe ist ausgeschlossen.")
    check.add_argument("--nli-source", type=Path, help="Vollständige lokale UTF-8-Quelle zusätzlich einmal pro Entwurf mit Provenance NLI prüfen.")
    check.add_argument("--corrections", type=Path, help="JSON-Liste mit höchstens zwei kontrollierten Fixture-Korrekturen (keine KI).")
    profile = commands.add_parser('profile-check', help='Passende Gesprächsregeln mit expliziten Belegen prüfen.')
    profile.add_argument('--input', required=True, type=Path)
    profile.add_argument('--task-file', required=True, type=Path)
    profile.add_argument('--profile', choices=('auto', 'conversation', 'explanation', 'research',
                         'recommendation', 'project', 'source'), default='auto')
    profile.add_argument('--evidence', type=Path, help='Strukturierte lokale Belege; kein Werkzeugausführungsnachweis.')
    profile.add_argument('--nli-source', type=Path, help='Vollständige explizite lokale Quelle; aktiviert nur Quellen-NLI.')
    profile.add_argument('--json', action='store_true')
    quality = commands.add_parser('quality-check', help='Expliziten JSON-Auftrag lokal mit DeepEval und Guardrails prüfen.')
    quality.add_argument('--input', required=True, type=Path, help='JSON mit task, answer, instructions und criteria; lokales Audit enthält Eingaben.')
    quality.add_argument('--offline', action='store_true', help='Nur Hostregeln, ohne Modell; keine semantische Bewertung.')
    quality.add_argument('--correct', action='store_true', help='Höchstens einen lokalen Korrekturkandidaten erzeugen und nachprüfen.')
    quality.add_argument('--json', action='store_true')
    serve = commands.add_parser("serve", help="Lokale Oberfläche ausschließlich auf 127.0.0.1 starten.")
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--offline", action="store_true", help="Ohne Critic; keine vollständige Freigabe.")
    return parser


def _emit_report(report, as_json):
    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    print(f"Ergebnis: {report.get('final_status', 'ERROR')}")
    if report.get("fixture_corrector"):
        print(report["fixture_corrector"])
    if report.get("error"):
        print(report["error"])
    for number, attempt in enumerate(report.get("attempts", []), start=1):
        result = attempt.get("result", {'status': attempt.get('status', 'ERROR')})
        print(f"Versuch {number}: {result.get('status', 'ERROR')}")
        for finding in result.get("findings", []):
            origin = 'Critic-Hinweis (unverifiziert): ' if finding.get('origin') == 'critic' else ''
            print(f"  {finding.get('requirement_id', '?')}: {origin}{finding.get('description', '')}")
    if report.get("log_path"):
        print(f"Lokales Audit: {report['log_path']}")
    if report.get("released_text") is not None:
        print("Freigegebenes Ergebnis:")
        print(report["released_text"])
    elif report.get('candidate_text') is not None:
        print('Bewerteter Kandidat; keine unabhängige allgemeine Freigabe:')
        print(report['candidate_text'])


def main(argv=None):
    args = _parser().parse_args(argv)
    try:
        root = _project_root()
        if args.command == 'quality-check':
            if args.offline and args.correct:
                raise ValueError('Offline-Prüfung darf keine Modellkorrektur starten.')
            from .codex_hook import _load_json
            request = _load_json(args.input, 65536)
            if args.offline:
                from .quality_pipeline import QualityPipeline
                report = QualityPipeline(root).run(request)
            else:
                from .quality_evaluation import run_quality_worker
                report = run_quality_worker(root, request, max_corrections=1 if args.correct else 0)
            _emit_report(report, args.json)
            return 0 if report['final_status'] == 'PASS' else 3 if report['final_status'] == 'ERROR' else 2
        if args.command == 'profile-check':
            from .codex_hook import _read_text_file, _load_json
            from .profile_checks import check_answer
            task = _read_text_file(args.task_file, 262144, 'Vollständiger Profilauftrag')
            text = _read_text_file(args.input, 32000, 'Vollständige Antwort')
            evidence = _load_json(args.evidence, 262144) if args.evidence else None
            report = check_answer(root, task, text, evidence=evidence, source_file=args.nli_source,
                                 profile=None if args.profile == 'auto' else args.profile)
            _emit_report(report, args.json)
            return 0 if report['status'] in {'PASS', 'SKIPPED'} else 3 if report['status'] == 'ERROR' else 2
        if args.command == "check":
            draft = _load_draft(args.input, args.source)
            corrector = None
            if args.corrections:
                corrections = json.loads(args.corrections.read_text(encoding="utf-8-sig"))
                corrector = FixtureCorrector(corrections)
            orchestrator = _build_orchestrator(root, args.offline, nli_source_file=args.nli_source)
            report = orchestrator.run(draft, corrector=corrector, max_corrections=len(corrector.corrections) if corrector else 0)
            if corrector:
                report["fixture_corrector"] = corrector.description
            _emit_report(report, args.json)
            return 0 if report.get("final_status") == "PASS" else 3 if report.get("final_status") == "ERROR" else 2

        if not 1 <= args.port <= 65535:
            raise ValueError("Der Port muss zwischen 1 und 65535 liegen.")
        from .webapp import create_server

        server = create_server(_build_orchestrator(root, args.offline), port=args.port)
        print("Manuelle lokale ChatGPT-Übernahme. Diese URL enthält den privaten Zugriffstoken:")
        print(f"http://127.0.0.1:{server.server_port}/#token={server.access_token}", flush=True)
        print("Antwort selbst einfügen. Keine Übertragung an ChatGPT. Audit enthält den Eingabetext im Klartext.")
        print("Beenden mit Strg+C. Der Browser wird nicht automatisch geöffnet.", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nLokale Oberfläche beendet.")
        finally:
            server.server_close()
        return 0
    except (OSError, ValueError, TypeError, RuntimeError, ImportError) as exc:
        report = {"final_status": "ERROR", "released_text": None, "error": str(exc)}
        _emit_report(report, getattr(args, "json", False))
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
