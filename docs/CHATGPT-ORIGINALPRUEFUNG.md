# Prüfung des vom Benutzer eingefügten ChatGPT-Originaltexts

Der Benutzer hat den angefragten unveränderten ChatGPT-Antwortausschnitt direkt
in diesem Chat bereitgestellt. Die Übernahme erfolgte manuell, ohne Browser-
Scraping. Diese Herkunft ist durch die ausdrückliche Benutzerangabe dokumentiert;
eine unabhängige Authentifizierung des erzeugenden Modells ist damit nicht verbunden.

Der Wortlaut liegt in `examples/chatgpt-original.txt`, als strukturierter
Prüfentwurf zusätzlich in `examples/chatgpt-original.json`. Das Feld `text`
wurde direkt als UTF-8 gespeichert, ohne zusätzliche Endzeile oder Änderungen.

- Länge: 756 Zeichen / 756 UTF-8-Bytes.
- SHA256: `655505061310237da782c5387de66d3cddc7f254282c243dfb54d313e62923bd`.
- Herkunft und Übernahmemethode: `examples/chatgpt-original.provenance.json`.
- Keiner der enthaltenen Installations-, Hub- oder Konfigurationsbefehle wurde ausgeführt.

## Erster tatsächlicher Prüflauf

```powershell
& 'C:\Users\REDACTED_USER\.venv\Scripts\python.exe' main.py check --input examples\chatgpt-original.json --json
```

Gesamtstatus `UNVERIFIED`, Prozess-Exitcode 2, kein freigegebener Text.
Der natürliche Text liegt außerhalb der engen deterministischen Modellregeln,
und die interne ChatGPT-Modellfamilie ist nicht nachgewiesen.

Der echte lokale gpt-oss-Critic lieferte `pass` ohne Befunde, obwohl die
verifizierten lokalen Softwarefakten beigefügt waren. Modell-Digest unverändert,
4096 Kontexttoken, 1708 Prompttoken, 32 Ausgabetoken. Der Ollama-Aufruf benötigte
etwa 4,87 Sekunden laut dessen `total_duration`. Kein automatischer Retry.
Audit: `8bec85e4-948f-410f-a599-11dcd6766e1f.jsonl`.

## Unabhängig festgestellte technische Fehler und Grenzen

1. `Guard.from_string` existiert in der installierten Version 0.11.0 nicht.
   Die lokale `hasattr`-Prüfung ergibt `False`; `Guard.for_string` ist vorhanden.
   Das Codefragment ist dadurch mit dieser Version nicht ausführbar, auch wenn
   ein Regex-Validator später bereitgestellt würde. Der Benutzertext wurde für
   diese Feststellung nicht ausgeführt.
2. Der spezifische RegexMatch-Validator ist nicht installiert. Das vorhandene
   Paket `regex` ist kein Guardrails-RegexMatch-Validator. Die im Beispiel
   enthaltene Installation wurde nicht nachgeholt.
3. `guardrails configure` ist laut aktueller offizieller Hub-Dokumentation keine
   Voraussetzung mehr. Der Befehl existiert historisch noch; er wurde nicht ausgeführt.
4. Der frühere Hub-Installations- und Importweg ist in 0.11.0 als veraltet
   markiert. Dies allein bedeutet keinen sicheren Laufzeitfehler, wenn passende
   Kompatibilitätspakete vorhanden wären. Hier sind sie nicht installiert.

Das derzeitige offizielle Regex-Beispiel darf ebenfalls nicht ungeprüft kopiert
werden: Seine Form `Guard().use(RegexMatch, regex=..., on_fail=...)` passt nicht
zur lokal inspizierten `Guard.use`-Signatur in 0.11.0. Die reine Signaturbindung
weist das Argument `regex` zurück. Eine neue Installation ist zur Lösung der
Projektaufgabe nicht erforderlich: Der bereits vorhandene `LocalModelPolicy`
wird korrekt als Validatorinstanz an `OfflineGuard.use` übergeben.

Primärquellen: [Konfiguration/API-Keys](https://guardrailsai.com/hub/keys),
[RegexMatch](https://guardrailsai.com/hub/validator/guardrails/regex_match),
[Guard-API](https://guardrailsai.com/guardrails/docs/api_reference_markdown/guards),
[Version 0.11.0](https://github.com/guardrails-ai/guardrails/releases/tag/v0.11.0),
[Quelltext des Versions-Tags](https://raw.githubusercontent.com/guardrails-ai/guardrails/v0.11.0/guardrails/guard.py).

Die aktuelle Online-Dokumentation und die tatsächlich installierte API wurden
getrennt betrachtet; lokale Signatur- und Verfügbarkeitstests geben hier den
Ausschlag. Der Critic hat diese belegten Probleme im ersten Lauf übersehen.

## Abschließende Prüfung mit ergänztem deterministischem API-Prüfer

Der Originaltext blieb bytegleich. Ein kleiner statischer AST-Prüfer wurde
ergänzt und mit zunächst fehlschlagenden Tests belegt. Er führt den Text nicht
aus. Für dieses Beispiel ist die positive Ausführungsempfehlung anhand der
Einleitung „You can then import Guardrails in your Python script:“ manuell
geprüft und im Betreiberkatalog an den exakten Texthash gebunden. Damit wird
ein negativer oder unklarer Beispielkontext nicht als Empfehlung fehlinterpretiert.

Der abschließende echte lokale Gesamtlauf ergab **FAIL**, CLI-Exitcode2,
`released_text=null`. Der eigene Guardrails-Validator benennt den fehlenden
Aufruf `gd.Guard.from_string(...)` in Zeile19 anhand des lokalen0.11.0-Belegs.
Audit: `b545b301-1e4f-4f0a-b6be-fe855c67ac67.jsonl`.

Der Critic meldete in diesem zweiten Lauf `fail`. Wegen des ergänzten
Betreiberbelegs im Faktenkontext ist dies kein identischer Wiederholungsversuch
und kein Nachweis einer jetzt zuverlässigen Modellbeurteilung. Die Ablehnung
ist unabhängig vom Critic durch den deterministischen Befund gesichert.
Auch die zweite Modellantwort enthält pauschale Befunde zu sämtlichen acht
Regeln; sie wird ausdrücklich nicht als verifizierter Fehlernachweis behandelt.
Der gesicherte konkrete Ablehnungsgrund ist die statisch belegte fehlende API.

Die abschließende Suite besteht mit **87 Tests**, darunter11 neue statische
API-Tests und zwei neue Orchestrator-Regressionsfälle. Die gezielte unabhängige
Codeprüfung fand im gelesenen Änderungsumfang keine weiteren wichtigen Bugs.
Das bedeutet keine vollständige allgemeine Pythonanalyse: Nicht erkannte
Aufrufmuster, unbestätigte Rollen und die allgemeine Textqualität bleiben offen.

Der technische Abnahmepunkt „echte manuell übernommene ChatGPT-Ausgabe lokal
prüfen“ ist damit erfüllt. Interne ChatGPT-Vorabkontrolle, allgemeine
Critic-Qualität und echte KI-generierte Korrektur werden dadurch nicht behauptet.
