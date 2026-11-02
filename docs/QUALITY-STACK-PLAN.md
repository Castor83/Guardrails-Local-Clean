# Lokaler Qualitätsstack: Umsetzungsplan

Ziel: Den ausdrücklich beauftragten vorhandenen Prüfpfad um native DeepEval-
Qualitätsbewertung und echte Promptfoo-Regression ergänzen. Guardrails AI führt
die Zurückweisung aus. Keine erneute allgemeine Freigaberunde; die konkreten
Rollen und lokale Umsetzung sind vom Nutzer beauftragt.

Entscheidung: Bestehender Checkout und getrennte Eval-Laufzeit bleiben erhalten.
Pro Antwort wird genau eine native synchrone Metrik gewählt: GEval mit festen
evaluation_steps für allgemeinere Qualitätskriterien oder PromptAlignmentMetric
für einzelne Anweisungen. Prompt Alignment nutzt eval_mode=llm, strict_mode=true
und include_reason=false; vorhandene Einzelbegründungen werden übernommen.
Ein Aufruf je Antwort; keine automatische Erzeugung von Bewertungsschritten.
Bestehender gepinnter Ollama-Adapter, keine
neuen Modelle oder Cloudprüfer. Expliziter eigener CLI-Aufruf; abgeschalteter
Chat-Hook bleibt abgeschaltet.

## Schnittstellen und Aufgaben

1. `quality_evaluation.py`, `quality-worker.py`: Native DeepEval-Bewertung und
   expliziter lokaler Korrekturkandidat in privatem Worker. Wiederverwendung von
   BoundedOllamaBridge, private-env und Loopback-Prüfung. Gesamtfrist 180s,
   höchstens eine Live-Korrektur, maximal drei Modellaufrufe. Gleiches Modell
   für Korrektur und Urteil ist ausdrücklich keine unabhängige Abnahme.
2. `quality_pipeline.py`, CLI `quality-check`: Request mit unveränderter Aufgabe,
   instructions, criteria, optional source_context/constraints/session_id/turn_id.
   `QualityPipeline(root).run(request, evaluator=None, corrector=None,
   max_corrections=0)` nutzt echte Guardrails ohne Reasks. Nur answer darf sich
   ändern. Vor jeder Korrektur sämtliche ERROR/UNVERIFIED prüfen und stoppen.
   Hostbefunde und Richterurteil bleiben Daten. Durable Audit vor Ergebnis.
   `released_text` bleibt None: Assessment-PASS ist keine unabhängige allgemeine
   Freigabe. candidate_text nur bei Assessment-PASS, verified=false.
3. `tools/promptfoo`, `regressions/promptfoo`, `promptfoo_runner.py`,
   `run-regressions.py`: Gepinnte tatsächliche Promptfoo-CLI projektlokal, native
   Pythonprovider-Schnittstelle gegen den echten Kern. Serielle Regressionen
   mit explizit synthetischen Richterurteilen, keine Modelle im Standardlauf.
   Telemetrie, Cloud, Updates, automatisches Teilen und Cache aus.

Evaluatorbericht: status, framework=deepeval, native_metric, task_sha256,
answer_sha256, contract_sha256, score (0/1 bei PASS/FAIL), reason.
`contract_hash(request)` bindet kanonisches JSON ohne answer. Korrektor:
`corrector(request, feedback, index) -> vollständiger Antworttext`.
Keine Reaktivierung, keine neuen Anbieterrechte aus einem Report.

## Gezielte Verifikation und Grenzen

- RED/GREEN: falsche/fehlende Belege, geänderte Kriterien, gebundene Urteile,
  Fehler-/Unverifiziert-Stopp, echte Guardrails-Zurückweisung, begrenzte Schleife.
- Echte Promptfoo-CLI ausführen, keine bloß vorbereitete Konfiguration melden.
- Native DeepEval-Metrik im vorhandenen Runtime prüfen; lokale Modellfälle nur
  bei erfolgreicher unveränderter Modell-/Fremdbelegungsprüfung, keine Entladung.
- Vollständige CPU-Suite einmal auf stabilem Stand, unabhängiger Review.
- Modellurteile, synthetische Fälle und native Chat-Abnahme getrennt ausweisen;
  das Gesamtziel bleibt ohne tatsächlichen Nachweis NOT_ACCEPTED.

Primärquellen: https://deepeval.com/docs/metrics-prompt-alignment,
https://deepeval.com/docs/metrics-llm-evals,
https://deepeval.com/guides/guides-using-custom-llms,
https://www.promptfoo.dev/docs/providers/python/.
