# Guardrails Local Implementation Plan

> Agentic workers: execute tasks with test-driven-development and independent final review.

**Goal:** Ausführbare lokale Qualitätskontrolle gemäß ORIGINALAUFTRAG.txt.
**Architecture:** Deterministischer Guardrails-Kern, lokale Ollama-Semantikprüfung,
eigenständige Freigabe, Audit und quellunabhängiger Import.
**Tech Stack:** vorhandenes Python 3.12 / Guardrails AI 0.11.0 / Pydantic 2 / unittest.
**Spec:** ENTWURF.md und ORIGINALAUFTRAG.txt.

## Global Constraints
- Keine Installation, Cloudinferenz, Downloads oder fremde Prozesskontrolle.
- Originalanforderungen erhalten; Pflichtregeln nicht durch Eingaben abschwächbar.
- Maximal zwei Korrekturen; Fehler/Unbekannt dürfen nie PASS ergeben.
- Nur huihui_ai/gpt-oss-abliterated:20b-mxfp4 als lokaler Critic.

## Review Focus
- Eingabetext und strukturierte Behauptung widersprechen sich: keine Freigabe.
- Fehlende/gefälschte Fakten oder Kontextüberschreitung: UNVERIFIED/FAIL.
- Critic JSON gültig, aber Status widersprüchlich: ERROR.
- API nicht erreichbar oder Audit nicht schreibbar: keine Freigabe.
- HTTP-Aufruf von fremdem Ursprung oder mit falschem Token: Zurückweisung.

## Task 1: Fakten und Validator
Dateien: config/{requirements,catalog,settings}.json, src/guardrails_local/{domain,validator}.py,
tests/test_validators.py. Schnittstelle validate_draft(draft, requirements, facts)->dict
mit status, findings, guardrails_passed. import_text(text, source, task)->dict.
- [x] Tests 1–5, gefälschte Abliteration, ungebundener Text, fehlende Regeln schreiben und rot ausführen.
- [x] Katalog, Regelablage, Extraktion, Guardrails-Validator implementieren.
- [x] Tests grün ausführen und Evidenz speichern.

## Task 2: Critic (unabhängiger Worker)
Dateien src/guardrails_local/critic.py, tests/test_critic.py.
Schnittstelle OllamaCritic(settings: dict).review(draft: dict, requirements: list, facts: dict)->dict.
- [x] Ungültiges JSON, fehlende Felder, widersprüchliche Ausgabe, Timeout/Verbindung,
       Remote-URL, Digestwechsel und lokale JSON-Schema-Anfrage mit Fake-HTTP testen, rot ausführen.
- [x] Loopback-Ollama-Client mit striktem Schema, Grenzen, Vorprüfung implementieren.
- [x] Suite grün; echten GPU-Test ausschließlich durch Hauptagent.

## Task 3: Orchestrator/Korrektur/Audit
Dateien src/guardrails_local/orchestrator.py, tests/test_orchestrator.py.
Schnittstelle Orchestrator(...).run(draft, corrector=None, max_corrections=0)->dict.
- [x] Tests 6–9, erfolgreicher Audit, Logfehler, Familiengleichheit rot ausführen.
- [x] Entscheidungsreihenfolge, Korrekturaufträge, drei Versuche maximal, JSONL implementieren.
- [x] Gesamte Suite grün; Testgenerator als Simulation markieren.

## Task 4: Eingabe/Integration
Dateien main.py, src/guardrails_local/{cli,webapp}.py, tests/test_integration.py.
- [x] CLI-Dateiimport und authentifizierten lokalen HTTP-Import rot ausführen.
- [x] CLI und lokale HTML-Oberfläche implementieren; kein DOM-Leser.
- [x] Reale ChatGPT-Textübernahme und echter lokaler Critic; Herkunft protokollieren.

## Task 5: Abnahme und Lieferung
- [x] Gesamtsuite, neun Fälle und sechs echte lokale Aufrufe einschließlich ChatGPT-Originaltext dokumentieren.
- [x] Unabhängige Codeprüfung; wichtige Befunde korrigieren und gezielt nachtesten.
- [x] README, Quellen, Phasenbericht und Akzeptanzmatrix schreiben.
- [x] Lokaler Commit, Bericht und Quellpaket unter Chat-outputs ablegen.
