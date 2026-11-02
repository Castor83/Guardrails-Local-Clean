# Technische Abnahme – 16.10.2026

## Aktueller Review-Reparaturstand vom 20.10.2026

Der Gesamtstatus bleibt **NOT_ACCEPTED**. Die folgenden älteren Bestands- und
Laufaussagen sind historische Nachweise, keine Abnahme des Reparaturstands.
Aktuelle paketbezogene RED-/GREEN-Belege und Dateibindungen liegen unter
`work/review-repair-20261020/`; der abschließende Gesamtbericht wird dort mit
dem tatsächlichen Commit, Auftrag, Policy und Prüflauf gebunden.

Die Reparaturen begrenzen Belegerfassung und Setup auf aktuell freigegebene
Sitzungen, beschränken Lesepfade auf das Repository und priorisieren
`ERROR > FAIL > UNVERIFIED > PASS`. Ungeklärte Pflichtbefunde stoppen weitere
Modell-/Korrekturschritte. Deutsche Recherchebehauptungen und klare eingebettete
Modellentscheidungen werden enger geprüft; unbekannter Resttext bleibt offen.

Der neue kooperative unittest-Runner trennt strukturierte Resultate von
stdout/atexit und zählt Skips nicht für die Mindestzahl. Siehe
`docs/TEST-RUNNER.md`. Vier DeepEval- und zwei NLI-Smoke-Fälle sind synthetisch,
versioniert und vollständig gepinnt. Promptfoo verlangt genau die acht festen
Einzelfälle mit Fallhashes, Assertions und tatsächlichen Resultaten.

| Review-ID | Reparaturumfang | Verbleibende Grenze |
|---|---|---|
| 4305391551 | Explizite Belegfreigabe je Sitzung; Widerruf vor Erfassung/Verwertung | Kein Nachweis einer aktivierten nativen Erfassung |
| 4305391553 | Setup-Gate vor Vertrag und Nebenwirkungen | Keine Einrichtung oder Modellaktion ausgeführt |
| 4305391564 | Aufgelöste Leseziele bleiben innerhalb der Repository-Wurzel | Nachträglicher Linkaustausch keine bewiesene Sicherheitsgrenze |
| 4305391589 | Terminales ERROR auch am letzten Budgetindex; NLI-Befund im Korrekturauftrag | CPU-/Double-Prüfung |
| 4305391588 | FAIL bleibt neben UNVERIFIED sichtbar; ungeklärter Pflichtbefund stoppt | Keine Freigabe aus gemischten offenen Befunden |
| 4305391548 | Prüfverben sind Ergebnisansprüche | Keine semantische Web-Verifikation |
| 4305391555 | Zusätzliche enge deutsche Behauptungsformen erkannt | Keine vollständige Sprachabdeckung |
| 4305391562 | stdout-/atexit-Spoofing geschlossen; Runnervertrag gebunden | **Teilweise:** keine adversariale Trennung gegenüber demselben Benutzer |
| 4305391592 | OFFEN übergeht erkannte Abschlussbehauptungen nicht | Begrenzte deutsche Muster |
| 4305391570 | Feste DeepEval-Inhalte und Sollwerte vor Aufruf geprüft | Kein erneuter echter Modell-Smoke |
| 4305391576 | Synthetische Standardfälle im Checkout enthalten | Vorbereitung ist keine Live-Inferenzabnahme |
| 4305391591 | Exakte acht Promptfoo-Fälle statt bloßem Zähler | **Teilweise:** CPU-Vertrag geprüft; korrigierter CLI-Abnahmelauf offen |
| 4305391559 | Gesprächsprofil läuft bereits in precheck | Keine allgemeine Inhaltsprüfung |
| 4305391584 | Keine Rechte aus Texthash; neue Bindung nach beendeter Aufgabe; Legacy-Mehrdeutigkeit stoppt | **Teilweise:** Herkunft identischer ausstehender Replays nicht sicher unterscheidbar |
| 4305391579 | Erfasste Auswahl überlebt neutralen Zusatztext; Zitatbindung bleibt erhalten | Unverstandener Resttext und mehrdeutige Rollen bleiben offen |

Die native automatische Stop-Wiedereinspeisung ist im reparierten Quellcode
ausgesetzt, solange die Herkunft des Folgeereignisses nicht eindeutig belegt
werden kann. Der direkte Pipelinepfad behält höchstens zwei Korrekturen.
Betreiberkonfiguration, deaktivierter Critic, geschützte Sitzung und globale
Hooks werden durch diese Reparatur nicht aktiviert oder geändert.

Die zusätzliche Codeprüfung deckte vier konkrete Restlücken auf: direkte
Belegverwertung nach Widerruf, verdeckte UNVERIFIED-Einzelbefunde, eine fremde
Komma-Negation vor einer Erfolgsbehauptung und vor-/nachgestellte explizite
Negativrollen bei Modellauswahl. Die Reparatur bindet nun auch die öffentlichen
Record-/Check-Einstiege an aktuelle Belegfreigaben und erhält terminale
Einzelstatus. Diese Fälle besitzen eigene Regressionen; der tatsächliche
abschließende Laufstatus steht ausschließlich im gebundenen Prüfbericht.

Offen bleiben außerdem allgemeine Entscheidungsablage, native Task Completion
mit vollständigem echtem Trace, akzeptierter Live-DeepEval-Lauf und technische
Freigabe vor der Anzeige. Eine zusätzliche Codeprüfung in einem frischen
Agentenkontext ist keine unabhängige Modellbewertung und keine Host-Abnahme.

Der Prototyp ist ausführbar. Der zuvor offene manuelle ChatGPT-Originalimport
ist inzwischen erfolgt und mit echtem lokalem Critic geprüft. Die Herkunft
beruht auf dem ausdrücklich vom Benutzer bereitgestellten Wortlaut. Die
fachliche Zuverlässigkeit des Critic ist weiterhin nicht abgenommen.

## Verifizierter Bestand

Python 3.12.10 aus `C:\Users\REDACTED_USER\.venv`, Guardrails AI 0.11.0,
Pydantic 2.14.1. Kein pytest, keine Neuinstallation. Die real verfügbaren APIs
`Validator`, `register_validator`, `PassResult`, `FailResult`, `Guard.use` und
`Guard.validate` werden ausgeführt.

Ollama 0.40.5 antwortet auf numerischem Loopback. Die beiden vorhandenen Tags
`latest` und `20b-mxfp4` besitzen denselben vollständigen Digest
`81c701845c4945940852ba02e3fda8b919cd513da988eec9e3b4cd7bde243b4c`.
Es wurde kein Tag entfernt oder heruntergeladen. Paketgröße 13.792.656.623 Byte;
F16-Anzeige und lokale Metadaten `mxfp4-abliterated`, Basismodell Huihui BF16
Abliterated v2, sind getrennt dokumentiert. Keine vollständige Tensoranalyse.

Die Anbieterquellen nennen die Abliterationsvariante; öffentlicher Digestpräfix
und lokaler Digest passen. Quellen: [Ollama-Paket](https://ollama.com/huihui_ai/gpt-oss-abliterated:20b-mxfp4),
[Huihui-Modellkarte](https://huggingface.co/huihui-ai/Huihui-gpt-oss-20b-mxfp4-abliterated-v2).

Vor den echten Tests war kein Ollama-Modell geladen. RTX4080: 16376 MiB gesamt,
13713 MiB frei unmittelbar vor dem ersten Test. Beim lokalen Beispielsatz
meldete `/api/ps` `size=size_vram=12739621682` Byte (etwa 11,86 GiB),
`context_length=4096`, Runner `llamacpp`. Sechs Laufzeitsamples wurden gespeichert.
Dies bestätigt vollständige VRAM-Zuordnung laut Ollama, keine absolute Messung
des gesamten GPU-Overheads. Danach `/api/ps`: leere Modellliste.

## Automatisierte Tests

```powershell
Set-Location 'E:\Guardrails-Local'
& 'C:\Users\REDACTED_USER\.venv\Scripts\python.exe' -m unittest discover -s tests -v
```

87 Tests, 0 Fehler, 0 Fehlschläge nach Review-Korrekturen, Advisory-Abgrenzung
und ergänzter statischer API-Prüfung am echten ChatGPT-Originaltext.
Suite enthält 19 lokale Ollama-Protokolltests, 13 Integrationstests und
Tests für Validator, Freigabe, Identität und Korrekturen. Keine echte Inferenz
im automatisierten Testsatz. Guardrails-Deprecation-Warnungen stammen aus der
vorhandenen Bibliothek. Sie wurden nicht als bestandene Fachtests gezählt.

| Vorgabe | Ausgeführter Nachweis | Ergebnis |
|---|---|---|
| 1 Cloud-API mit falschem Lokalversprechen | eigener Guardrails-Validator, echter Critic zusätzlich | FAIL; keine erfundene VRAM-Verletzung |
| 2 dokumentiertes lokales Modell | Guardrails, echter Critic, Ollama-Laufzeitsamples | PASS innerhalb ausgewiesenen Prüfumfangs |
| 3 bloßes Umbenennen | Validator-Test | FAIL |
| 4 Projektausschluss | aktive deny_model-Testregel | FAIL |
| 5 negative Erwähnung | negativer Satz und zusätzliche mehrzeilige Warnungsfälle | kein erfundener Cloudverstoß; unklare Fälle UNVERIFIED |
| 6 kaputter Critic | echtes Fake-HTTP: JSON, Schema, fehlende Felder, Widerspruch, Timeout, Verbindung | technischer Fehler; kein PASS |
| 7 erfolgreiche Korrektur | Fixture-Korrektor, erneute Prüfung, Audit; zusätzlich echter Critic in beiden Schritten | FAIL → PASS |
| 8 zwei erfolglose Korrekturen | kontrollierter lokaler Testgenerator | drei Gesamtversuche, ESCALATED |
| 9 falsches Critic-PASS | Testdouble und tatsächlich beobachtetes reales falsches PASS | deterministisches FAIL bleibt bestehen |

Zusatztests verhindern unter anderem Ausblenden höherer Textkontexte durch
JSON, Ausblenden zweiter Empfehlungen desselben Modells, fehlende/zu große
VRAM-Belege, gefälschte Abliterationsflags, Auftragswechsel durch Korrekturen,
Entfernung der Erzeugeridentität und Freigabe ohne beschreibbares Audit.

## Sechs echte Modellaufrufe, getrennt von Simulationen

Alle Aufrufe: ausschließlich das vorhandene gepinnte Modell, nativ `/api/chat`,
4096 Kontext, höchstens 1200 Ausgabetoken, `think=low`, `keep_alive=0`,
kein automatischer Transport-Retry. Kein anderes Modell geladen/entladen.

1. Ursprünglicher GPT-4o-Fehlervorschlag: Critic `pass`, keine Befunde;
   Gesamtstatus trotzdem `FAIL`. Laufzeit etwa 7,67 Sekunden, 1262 Prompttoken,
   354 Ausgabetoken. Audit `457a3f58-a93e-44a2-8292-c81cf8495b01.jsonl`.
2. Belegter lokaler Beispielsatz: Critic `pass`, Gesamtstatus `PASS`;
   etwa 5,70 Sekunden, 1302 Prompttoken, 122 Ausgabetoken.
   Audit `0cd676c6-6d09-4eea-94b4-e8406de7334c.jsonl`.
3.–4. Ein zusammenhängender Gesamtlauf über die CLI mit kontrollierter
   Fixture-Korrektur: erster Entwurf `FAIL` mit Critic `fail`, korrigierter
   lokaler Entwurf `PASS` mit Critic `pass`.
   Audit `ac495324-45c3-4823-9b25-eed1f2f25f08.jsonl`.
5. Vom Benutzer manuell übernommener ChatGPT-Originaltext: Critic `pass`, Host
   `UNVERIFIED`, keine Freigabe. Audit `8bec85e4-948f-410f-a599-11dcd6766e1f.jsonl`.
6. Derselbe unveränderte Text nach Ergänzung eines statischen API-Prüfers und
   gebundenem Betreiberbeleg für die positive Codeempfehlung: deterministisches
   `FAIL`, Critic `fail`, keine Freigabe. Audit
   `b545b301-1e4f-4f0a-b6be-fe855c67ac67.jsonl`.

Im `fail`-Ergebnis des Gesamtlaufs waren mehrere Korrekturen fachlich falsch:
lokaler Wrapper für die Cloud-API, Kostenflag entfernen, Abliterationsflag
eintragen. Auch der Hardwarebefund und einzelne Schlussfolgerungen waren
unbegründet. Nach diesem Befund wurden Modellhinweise im Gesamtbericht mit
`origin=critic` als unverifiziert markiert und ihre rohen Korrekturvorschläge
aus automatischen Korrekturaufträgen entfernt. Zwei zunächst fehlschlagende
Regressionstests belegen diese Grenze. Das ursprüngliche rohe Modellresultat
bleibt im Audit erhalten. Kein zusätzlicher Modellaufruf zum Schönrechnen.

Der Gesamtlauf verwendet einen vorgegebenen lokalen Korrekturtext. Er beweist
die technische Schleife mit realem Critic, **keine KI-generierte Korrektur**.

Vergleich zum früheren manuellen Test: Früher `fail` mit übersehener Cloud-/Kosten-
Problematik und erfundenem VRAM-Befund. Hier ein falsches `pass` im ersten Test,
im separaten Gesamtlauf `fail`. Die Inputs unterscheiden sich unter anderem
in Herkunftsmetadaten und Text-Whitespace. Deshalb kein identischer
Reproduzierbarkeitsversuch und keine isolierte Ursachenaussage. Belegt ist die
unzureichende Zuverlässigkeit über diese Beispiele. Das Modell wurde deshalb
weder als allgemeiner Qualitätsgarant freigegeben noch ungefragt ersetzt.

## ChatGPT-Eingabe und Oberfläche

CLI-Text-/JSON-Import, manueller Loopback-HTTP-Import und Token-/Origin-/Host-
Prüfung sind getestet. Ein echter Browserlauf im In-App-Browser übernahm den
vorgegebenen Cloud-Testtext, zeigte FAIL und ließ den Freigabebereich leer.
Das ist ein realer Oberflächentest mit Fixture, kein nachgewiesenes originales
ChatGPT-Antwortsample. Kein DOM-Leser und keine Browsererweiterung installiert.

Ein lesender Zugriff auf den vorhandenen Chat „Guardrails AI Installation“
lieferte ausschließlich `chatgpt-content-reference`-Verweise. Der Antwortinhalt
war darüber nicht verfügbar. Der Benutzer wurde um einen unveränderten kurzen
Antwortausschnitt gebeten. Diesen hat er anschließend geliefert. Der unveränderte
Text wurde als `examples/chatgpt-original.txt` mit 756 UTF-8-Bytes gespeichert,
SHA256 `655505061310237da782c5387de66d3cddc7f254282c243dfb54d313e62923bd`.
Der echte lokale Importlauf endete zunächst `UNVERIFIED` ohne Freigabe; der
Critic übersah einen separat lokal belegten API-Fehler. Details und nachfolgende
statische Prüfung: `CHATGPT-ORIGINALPRUEFUNG.md`. Keine Installationsbefehle aus
dem Text wurden ausgeführt. Der ChatGPT-Import-Abnahmepunkt ist damit erfüllt;
die interne Modellfamilie bleibt unbekannt.
Die abschließende statische Prüfung erkannte den lokal nicht vorhandenen
Aufruf `Guard.from_string`. Der erneute echte Gesamtlauf endete `FAIL`, ohne
Freigabe. Die Codeempfehlungsrolle wurde separat verifiziert und ist an den
exakten Originaltexthash gebunden; unbestätigte/negative Rollen bleiben
`UNVERIFIED` statt eines erfundenen Anforderungsverstoßes.

Grenzen und aktuelle Primärquellen stehen in CHATGPT-INTEGRATION.md. Automatische
DOM-Extraktion ist nach den geprüften EU-Bedingungen nicht als zulässig belegt.
Offizielle Hooks, MCP und Sign in with ChatGPT sind untersucht, nicht eingerichtet.
Eine interne Freigabeschnittstelle für jede bestehende ChatGPT-Antwort wurde
nicht nachgewiesen. Das ist von Freigabe in einer eigenen Oberfläche getrennt.

## Akzeptanzmatrix

- [x] Vorhandene Guardrails-Installation und Validator-API ausgeführt
- [x] Lokale Ollama-API und exaktes vorhandenes Modell identifiziert
- [x] Eigener Guardrails-Validator mit strukturierten Daten
- [x] Cloudfehler abgelehnt; belegte lokale Konfiguration berücksichtigt
- [x] Negative Erwähnung von positiver Empfehlung unterschieden
- [x] Echter lokaler Critic, Schema und technische Fehlerbehandlung
- [x] Falsches Critic-PASS kann harte Ablehnung nicht überschreiben
- [x] Orchestrator und maximal zwei Korrekturen
- [x] Erfolgreiche Fixture-Korrektur und Eskalation geprüft
- [x] Lokales Audit, reproduzierbare Tests, README und Startanleitung
- [x] Ausführbare lokale Schnittstelle für fremde Antworten
- [x] Unveränderten, vom Benutzer als ChatGPT-Antwort gelieferten Text manuell übernommen und lokal geprüft
- [x] Grenzen der automatischen ChatGPT-Integration mit Quellen dokumentiert
- [x] Keine zusätzliche Cloud-KI oder kostenpflichtige Modell-API eingebunden

Die inhaltliche Critic-Qualität und eine unabhängige lokale KI-Korrektur sind
weiterhin offen. Der Prototyp schützt die implementierten Regeln, nicht
beliebige Fakten oder das Verhalten eines Prozesses mit Dateisystemzugriff.

## Unabhängige Codeprüfung

Vier Important-Befunde wurden unabhängig berichtet, offline reproduziert,
mit zunächst fehlschlagenden Regressionstests belegt und korrigiert:
Originaltext nicht von JSON verdrängen; Originalauftrag einfrieren;
gemessenen VRAM prüfen; Warnungskontext erhalten. Zusätzlich wurden
Erzeugeridentität und unbekannte ChatGPT-Familie konservativ behandelt.
Die abschließende Gesamtsuite ist der Nachweis der Korrekturen.

Originalauftrag SHA256:
`EFAAF16DB0DEE2C011185C500DDF564C7B760C4EF17682F133302677F85333C7`.
Kopie und bereitgestellte Quelldatei stimmen bytegenau überein.
