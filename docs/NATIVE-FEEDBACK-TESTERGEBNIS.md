# Nativer Feedbacktest: erster Vorbereitungsversuch, 23.10.2026

**Gesamtstatus dieses Versuchs: ERROR in der Vorbereitung.** Die native
Transport- und Korrekturabnahme bleibt UNVERIFIED; Gesamtprojekt NOT_ACCEPTED.
Die konkrete Nutzerfreigabe „los“ lag vor. Nach dem Fehler wurde entsprechend
der vereinbarten Abbruchregel kein weiterer Live-Aufruf versucht.

## Tatsächlich erfolgt

- T0-Aufnahme mit Originalbytes und SHA256 für globale `hooks.json`, globalen
  Trustspeicher `config.toml` und Projekt-Betreiberdatei. Temporärer Handler ABSENT.
- Genau ein lokaler Testchat erstellt:
  `01a16997-5905-72f0-8537-a4a1b3f2bc4e`. Sein erster Auftrag verlangte ohne
  Werkzeuge ausschließlich BEREIT; diese Antwort wurde tatsächlich geliefert.
- Ein eigener kurzlebiger lokaler Codex-Verwaltungsprozess führte `hooks/list`
  und `config/read` aus. Kein lokaler Modellaufruf, keine Installation, kein
  Neustart oder Eingriff in den laufenden Desktop-Server.
- `hooks/list` antwortete; die Ergebnisdaten sind lokal erhalten. Der Helfer
  brach danach beim Vergleich von `user-layer.config` mit dem lokal durch
  `tomllib` gelesenen Inhalt ab: `AssertionError: Inconsistent config/version snapshot`.
- Weder Handlerregistrierung noch Truständerung oder Test-Sitzungsfreigabe
  wurde erreicht. Der eigene Verwaltungsprozess wurde im finally-Pfad beendet.

Die genaue Darstellungsabweichung der alten API-Antwort ist **UNVERIFIED**:
Die vollständige `config/read`-Antwort wurde nicht gesichert. Eine falsche
Gleichheitsannahme des Helfers ist durch den tatsächlichen Abbruch und die
anschließende Offline-Reproduktion belegt; daraus folgt kein Nachweis eines
Codex-, DeepEval- oder Modellfehlers.

## Abnahmematrix

| Bereich | Ergebnis | Begründung |
| --- | --- | --- |
| Verwaltungsvorbereitung | ERROR | Eigene Strukturannahme schlug fehl; kein Retry. |
| Nativer PostToolUse-Transport | NICHT_AUSGELÖST | Kein Beobachter registriert, kein Vorprüfungsereignis ausgelöst. |
| FAIL zu PASS | NICHT_AUSGELÖST | Keine Feedbackfreigabe. |
| Budget mit zwei Korrekturen | NICHT_AUSGELÖST | Keine drei nativen Entwürfe. |
| Erwarteter ERROR und neuer Nutzerbeitrag | NICHT_AUSGELÖST | Kein eigentlicher Testfall begonnen. |
| Nicht freigegebene Sitzung | NICHT_AUSGELÖST | Keine native Handlerbeobachtung; Listeninhalt wird nicht als PASS gewertet. |
| Zustandskontrolle/Rückweg | PASS_NO_MUTATION | T0=T1=T2, bestehende Dateien bytegleich, temporärer Handler weiterhin ABSENT. Das ist kein ausgeführter Aktivierungs-/Rückbautest. |

## Offline-Reparatur, getrennt vom nativen Nachweis

Der vorbereitete Helfer bindet nun die lokal gelesenen Bytes an das Zeitfenster
des Versionabrufs: Datei vorher lesen, versionierte Layer abfragen, Datei danach
erneut lesen und Bytegleichheit verlangen. Die API-Versionskennung bleibt für
`expectedVersion` erhalten. Seine API-interne Konfigurationsdarstellung muss
nicht als identisch zur lokalen Parserdarstellung vorausgesetzt werden.

Ein unabhängiger lesender Check fand außerdem zwei Rückweg-Lesefenster und den
Fall eines nie erfolgten Trust-Schreibens. Der Helfer verwendet dafür denselben
Bytebestand für Vergleich und erwarteten Hash sowie einen idempotenten
Zielschlüssel-Rückweg. Vorhandene `hooks.state`-Container sind für diesen engen
Helfer ausdrückliche Voraussetzung. Fremde Zieländerungen werden nicht ersetzt.

Sieben gezielte Offline-Prüfungen auf lokalen Kopien bestanden. Vor Reparatur
wurden fünf Fehlschläge reproduziert. Dabei war der echte Prozessstart gesperrt;
kein zweiter Verwaltungsaufruf und kein nativer Test wurde dadurch ausgeführt.
Diese sieben Helferprüfungen sind kein Zusatz zur früheren Projektsuite von 435
und beweisen weder eine erfolgreiche aktuelle RPC-Reparatur noch Hostwirkung.

## Lokale Belege und weiterer Schritt

Alle Dateien unter `E:\Guardrails-Local\work\native-feedback-20261023\`:

- `run-state.json`: einzige Testchat-ID, Autorisierung und Abbruchzustand.
- `T0.json`, `T1.json`, `T2.json`, `baseline/`: unveränderte Dateien und ABSENT.
- `baseline-hooks.json`, `preparation-error.json`: Metadaten und Fehlergrenze.
- `control.py`, `observer-source.py`: vorbereitete lokale Helfer; nicht aktiviert.
- `helper-red.txt`, `helper-review-red.txt`, `helper-green.txt`: Offline-Regressionen.
- `verification.json`: Abschlusskontrolle und Belegbindung.

Nächster Live-Schritt wäre ein ausdrücklich neu gestarteter Versuch mit dem
korrigierten Helfer und **dem vorhandenen Testchat**. Kein zweiter Testchat,
keine automatische Wiederholung aus dem abgebrochenen Versuch. Zuerst erneut
lesende konsistente Verwaltungsprüfung, danach nur bei Erfolg die bereits
beschriebene temporäre Beobachtung. Produktive Aktivierung bleibt ausgeschlossen.
