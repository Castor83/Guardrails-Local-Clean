# Lokale Quellenprüfung und DeepEval

Der zusätzliche Prüfteil verwendet die getrennte Projektumgebung
`E:\Guardrails-Local\work\evals-runtime\.venv`. Die bisherige
Umgebung `C:\Users\REDACTED_USER\.venv` steuert weiterhin Guardrails; ihre Pakete
werden durch die Einrichtung nicht ersetzt.

Der feste, auf den aktuellen Aufgabenvertrag gebundene Einrichtungsaufruf ist:

```powershell
& 'C:\Users\REDACTED_USER\.venv\Scripts\python.exe' 'E:\Guardrails-Local\setup-local-evals.py' --session-id '<aktuelle Sitzungs-ID>' --action inspect
```

Weitere feste Aktionen: `resolve`, `install`, `download-model`, `check`,
`smoke-nli`, `smoke-deepeval`. Es gibt keine freien Paket-, Modell- oder
Shellargumente. Auflösung und Installation verwenden gepinnte Versionen und
offizielle, per SHA256 gebundene Wheels. Nur die ausdrücklich vom Betreiber
korrigierte bedingte Installationsregel erlaubt diese Einrichtung.

## Provenance NLI

Der vorhandene Prüfablauf unterstützt eine explizite vollständige Quelldatei:

```powershell
& 'C:\Users\REDACTED_USER\.venv\Scripts\python.exe' 'E:\Guardrails-Local\main.py' check --input '<Antwortdatei>' --nli-source '<Quelldatei>' --json
```

NLI wird einmal je tatsächlichem Antwortentwurf ausgeführt. Die Quelldatei
bleibt über ihren SHA256 an den ursprünglichen Lauf gebunden. Ohne Critic ist
auch bei NLI-PASS keine vollständige Gesamtfreigabe möglich (`--offline`).

Der native Guardrails-Validator wird als Projekt-Unterklasse verwendet;
installierte globale Paketdateien werden nicht gepatcht. Das gepinnte Modell
ist `MoritzLaurer/multilingual-MiniLMv2-L6-mnli-xnli`, Revision
`0a71e92a985b6e1ad1828cf67ce9c459639c1dca`, mit drei tatsächlichen Klassen.
Nur CPU, lokale Safetensors und lokaler Fast-Tokenizer sind zugelassen.
Neutral und Widerspruch gelten als nicht durch die Quelle gestützt.

Der begrenzte Modus bewertet ein vollständiges Quellen-/Antwortpaar mit
höchstens 512 Tokens einschließlich Sondertokens. Überlänge, fehlende Quellen
oder ein anderer Checkpoint führen zu UNVERIFIED; es gibt keine stille
Kürzung, keine Embeddingsuche und keine behauptete satzweise Qualitätsabnahme.

Ohne ausdrücklich gebundene Quelle wird NLI im automatischen Codex-Anschluss
übersprungen (SKIPPED). Cache-/Stabilitätsprüfungen dürfen keine Modellaufrufe
wiederholen. Für einen automatischen NLI-Anschluss fehlen dort noch explizite
Quellenbindung und reservierte Ausführung. Ein einzelnes NLI-PASS beweist keine
allgemeine Wahrheit. Der ausdrückliche Profilaufruf ist separat möglich:
`main.py profile-check --task-file <Auftrag> --input <Antwort> --profile source --nli-source <Quelle> --json`.

## DeepEval

DeepEval 4.3.1 verwendet einen eigenen Adapter zum bereits festgelegten
lokalen Ollama-Critic. Digest- und Fremdmodellsperre, 4096 Kontexttokens,
höchstens 1200 Ausgabetokens, vollständige 8500 UTF-8-Bytes, keine Wiederholung
und eine harte Worker-Gesamtfrist von 180 Sekunden bleiben erhalten.
Die vier vorbereiteten synthetischen Fälle verwenden insgesamt höchstens
vier Modellaufrufe seriell. Diese Auswertung ist eine explizite Einrichtung-
und Integrationsprüfung und wird nicht zusätzlich in jeden Antwort-Hook eingebaut.

Die Worker erhalten nur geprüfte Umgebungswerte, ein privates Projektprofil,
deaktivierte Telemetrie, keine Cloud-Zugangsdaten, keinen Login und keine
dotenv-/Legacy-Key-Dateien. Python-Socket-Auditregeln blockieren externe
Verbindungen. Das ist keine Betriebssystem-Sandbox. Fremde geladene Modelle
werden weder entladen noch ersetzt; eine belegte Fremdbelegung blockiert den Lauf.

Tatsächliche Ergebnisse stehen getrennt von diesem Nutzungsdokument in den
auftragsgebundenen `evals-*.json`-Belegen. Installation, CPU-Vertragstests,
synthetische Modellfälle und allgemeine Qualitätsabnahme sind unterschiedliche Nachweise.
# Review-Reparatur 20.10.2026: feste synthetische Fälle

Die Standardfälle liegen versioniert in `examples/evals/deepeval-smoke.json`
und `examples/evals/nli-smoke.json`. Ein frischer Checkout enthält alle vier
DeepEval- und beide NLI-Fälle. Ihre vollständigen kanonischen Inhalte samt
Schema, IDs, Reihenfolge, Quellen, Antworten und Sollurteilen sind separat im
Code gepinnt. Änderungen oder Duplikate werden vor dem ersten Messaufruf
zurückgewiesen; auch ein alternativer NLI-Fallpfad muss denselben Vertrag
erfüllen. Private frühere Dateien unter `work/` werden nicht verändert.

CPU-/Double-Regressionsfälle weisen diese Eingangsverträge nach. Sie sind
kein echter Modell-Smoke und keine allgemeine Qualitätsabnahme. Historische
NLI-/DeepEval-Laufresultate bleiben an ihren damaligen Stand gebunden.
