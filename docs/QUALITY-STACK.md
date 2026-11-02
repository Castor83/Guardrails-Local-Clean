# DeepEval, Guardrails AI und Promptfoo lokal

Der explizite Befehl `quality-check` verbindet die drei Rollen: DeepEval bewertet
eine vollständige Aufgabe und Antwort anhand angegebener Regeln. Guardrails AI
weist fehlgeschlagene oder offene Prüfergebnisse zurück. Promptfoo führt feste
Regressionen gegen dieselbe Produktpipeline aus. Dieser Anschluss aktiviert
keine abgeschalteten Chats oder globalen Hooks.

Seit der Nutzerfreigabe vom 23.10.2026 verwenden Critic, DeepEval und der
lokale Korrektor `gpt-oss:20b`, fest gebunden an Digest
`f38aa0c53da5f8c49d08c43a99df24ff53167fe68e24664a7777288e7656fdfe`.
Das vorherige Huihui-Prüfmodell ist laut Nutzer nicht mehr vorhanden.
Modellname und Digest des Ersatzes sind im lokalen Ollama-Katalog belegt;
ein neuer echter Bewertungs-/Korrekturlauf ist damit noch nicht nachgewiesen.
Historische Modellläufe gelten ausschließlich für ihre damalige Modellbindung.
NLI und die Regeln für Modell-Empfehlungen werden dadurch nicht geändert.

Die Auswahl der vorhandenen offiziellen Hub-Bausteine und die gezielt
geprüften Ergänzungen sind in `GUARDRAILS-HUB-AUSWAHL.md` begründet.

## Eine passende Metrik je Antwort

- `metric: "prompt_alignment"`: Native `PromptAlignmentMetric` prüft den Auftrag
  und die einzelnen Einträge in `instructions` und `criteria`. Formuliere pro
  Eintrag eine klare prüfbare Anforderung. Alle Urteile müssen `yes` sein.
- `metric: "g_eval"` oder fehlendes `metric`: Native `GEval` mit festen Schritten
  für Aufgabenerfüllung und allgemeinere Qualitätskriterien.

Beide verwenden DeepEval 4.3.1 und ausschließlich das vorhandene gepinnte lokale
Ollama-Modell. Es wird genau eine Metrik ausgeführt. Synchrone Ausführung,
binäre Bewertung und ein Modellaufruf je Antwort sind festgelegt. Prompt Alignment
verwendet ausdrücklich den LLM-Modus und lädt kein eigenes Jev-Modell.
`include_reason=false` verhindert einen zusätzlichen Begründungsaufruf; bei
Ablehnung werden vorhandene Einzelbegründungen verwendet. Fehlen sie, steht
dies ausdrücklich im Bericht.

Quelle: [DeepEval Prompt Alignment](https://deepeval.com/docs/metrics-prompt-alignment),
[G-Eval](https://deepeval.com/docs/metrics-llm-evals),
[eigene lokale Modelle](https://deepeval.com/guides/guides-using-custom-llms).

Die im Arbeitsplan zusätzlich genannte native `TaskCompletionMetric` ist ein
eigener offener Anschluss. Sie benötigt einen tatsächlich erfassten vollständigen
Assistentenablauf und hat im LLM-Modus ein anderes Aufrufbudget. G-Eval wird
hier nicht als bereits umgesetzte Task-Completion-Prüfung ausgegeben. Quelle:
[DeepEval Task Completion](https://deepeval.com/docs/metrics-task-completion).

## Prüfen und begrenzt korrigieren

Eine vollständige Beispieldatei liegt unter `examples/quality-alignment.json`.
`task`, `answer`, `instructions` und `criteria` gehören in denselben Auftrag.
Optional sind vollständiger `source_context`, explizite `constraints`, eine
behauptete `developer_family` sowie zusammengehörige `session_id`/`turn_id`.
Letztere ordnen tatsächliche Werkzeugbelege zu; das Eintragen einer ID erzeugt
keinen Beleg.

```powershell
Set-Location 'E:\Guardrails-Local'
& 'C:\Users\REDACTED_USER\.venv\Scripts\python.exe' main.py quality-check --input examples/quality-alignment.json --json
```

Der Aufruf kann das vorhandene Modell laden und führt höchstens einen
Bewertungsaufruf aus. Fremde geladene Ollama-Modelle blockieren ihn; sie werden
nicht entladen. Modell und Digest werden vor jedem Aufruf geprüft.

Mit zusätzlich `--correct` wird nach einem `FAIL` höchstens ein lokaler
Korrekturkandidat erzeugt und erneut bewertet: insgesamt maximal drei
Modellaufrufe und 180 Sekunden für den Worker. Nur der Antworttext darf sich
ändern; ursprüngliche Aufgabe, Regeln und Quellen bleiben gebunden.
`ERROR` oder `UNVERIFIED` stoppen ohne automatische Wiederholung. Der
Fixturepfad für Regressionen prüft getrennt auch das äußere Limit von zwei
Korrekturen. Für eine Prüfung ohne Modell `--offline` verwenden; ohne
semantische Bewertung entsteht dabei kein semantischer Erfolgsnachweis.

Exitcodes: `0` bestandenes Assessment, `2` abgelehnt/offen/eskaliert,
`3` technischer Fehler. `PASS` stellt einen bewerteten `candidate_text` bereit.
`released_text` bleibt leer. Judge und Korrektor nutzen dieselbe Modellfamilie;
eine unabhängige Abnahme oder allgemeine Wahrheitsgarantie ist damit nicht
belegt. Deshalb bleiben die Verifizierungsflags `false`.

Hostregeln prüfen explizite Formgrenzen und ausgewählte, an tatsächliche
Werkzeugereignisse gebundene Aktionsbehauptungen vor dem Modell. Die sechs
Gesprächsprofile sind weiterhin über `profile-check` verfügbar; dieser
Qualitätsauftrag ersetzt keine allgemeine automatische Regelerkennung.

## Regressionen mit echter Promptfoo-CLI

Promptfoo 0.124.1 ist unter `work/promptfoo-runtime` projektlokal installiert.
Node 24.20.0 war bereits vorhanden; globale Pakete und die Controller-Python-
Pakete wurden nicht ergänzt. Paketversionen und Integrität sind unter
`tools/promptfoo/package-lock.json` festgehalten. Installationsskripte wurden
nicht ausgeführt. Der Windows-TLS-Vertrauensspeicher wird nur für diese
Prozesse genutzt; Zertifikatsprüfung bleibt eingeschaltet.

```powershell
& 'C:\Users\REDACTED_USER\.venv\Scripts\python.exe' 'E:\Guardrails-Local\run-regressions.py'
```

Der Befehl installiert nichts und ruft kein Modell auf. Acht feste Fälle
prüfen unbelegte Suchbehauptungen, falsche Chattitel, ehrlich markierte
Unsicherheit, Längengrenzen, Auftragserhalt bei Korrekturen, Fehlerstopp,
Unverifiziert-Stopp und das Korrekturbudget. Der Pythonprovider nutzt die echte
Guardrails-Pipeline mit ausdrücklich synthetischen semantischen Urteilen.
Das belegt den Ablauf, keine echte Modellqualität. Quelle:
[Promptfoo Pythonprovider](https://www.promptfoo.dev/docs/providers/python/).

Ergebnisse: `work/promptfoo-runtime/latest-run.json` verweist auf CLI-Log und
vollständiges Ergebnis. `final-source-binding.json` bindet den dokumentierten
Abschlusslauf an die relevanten acht Quelldateien. Neuinstallation ist ein
separater expliziter `--install`-Aufruf und für reguläre Tests unnötig.

## Daten und Nachweisgrenzen

Eingaben und Korrekturen stehen lokal im Klartext in `logs/<UUID>.jsonl`;
Workeraufträge in `work/quality/<UUID>/request.json`. Der Vertragshash bindet
sämtliche Auftragsfelder außer dem veränderbaren Antworttext. Berichte werden
beim Rückweg auf Auftrag, Versuchskette und Kandidaten geprüft.

Private Prozessumgebung, abgeschaltete Telemetrie und lokale Netzwerksperren
begrenzen die Auswertung. Dies ist keine Betriebssystem-Sandbox. DeepEval
darf ausschließlich zum festen numerischen Ollama-Loopback verbinden;
Promptfoo-Regressionen benötigen keine externen Verbindungen. Es werden keine
Cloudprüfer, Bezahl-APIs oder neuen Modelle eingerichtet.

Der Qualitätsworker verwendet bereits vorhandene lokale Punkt-Daten über einen
expliziten internen Ressourcenpfad und setzt Guardrails auf synchrone Validierung.
Bibliotheksmeldungen gehen in den Diagnosekanal; der Ergebnisrückweg enthält
genau ein JSON-Objekt. Fehlt ein lesbarer Workerbericht, bleiben unbekannte
Modellaufrufzahlen ausdrücklich unbekannt und werden nicht als null ausgegeben.

Der konkrete Verifikationsstand steht in
`work/quality-stack-20261018/verification.json` und der getrennten nativen
Funktionsprüfung `live-prompt-alignment.json`. Eine native automatische
Abnahme jedes Chats, allgemeine Entscheidungsprüfung und unabhängige
Fehlerkorrektur bleiben eigene offene Projektkriterien. Der Gesamtstatus
bleibt bis zu deren tatsächlichem Nachweis `NOT_ACCEPTED`.
