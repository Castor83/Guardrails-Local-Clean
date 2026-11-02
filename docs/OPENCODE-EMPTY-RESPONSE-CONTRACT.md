# OpenCode 2.1.4: Vertrag für leere Abschlüsse

Verbindliche Nutzerentscheidung vom 24.10.2026: **HTTP 422 + UNVERIFIED, kein Retry**.
Implementiert und durch 134/134 Guard-Unitfälle abgesichert. Ein nativer
synthetischer Fall belegt den statischen 422 und keine weitere Completion;
keine natürliche Inferenz freigegeben.
Historischer Modelllauf und Gesamtprojekt bleiben NOT_ACCEPTED.
Die [deterministischen Guard-V2-Pfade sind als Teilumfang ACCEPTED](OPENCODE-V2-DETERMINISTIC-ACCEPTANCE.md).

## Verbindliches Verhalten

Ein vollständig empfangener, formal gültiger Abschluss ohne nutzbaren `content`,
ohne nutzbaren `refusal` und ohne gültige Toolcalls wird als begrenzter Guardfehler
zurückgewiesen. Fehlend, null, leerer String und ausschließlich mit JavaScript
`trim()` entfernbarer Leerraum gelten als leer. Reasoningfelder allein sind kein
sichtbarer Abschluss. Eine frühere gültige Toolquittung füllt eine leere Antwort
nicht auf und legitimiert keinen Abschluss.

Der vorhandene Fehlerpfad liefert HTTP 422, `x-guardrails-status: unverified` und
den unveränderten statischen `guardrails_unverified`-Fehlerbody. Er enthält keine
Modellinhalte, Usage, Abschlussgründe oder Reasoning und behauptet keine Ursache.
Keine künstliche erfolgreiche Assistantnachricht und kein sichtbarer Ersatztext
mit HTTP 200. Die Diagnosefelder verbleiben im separaten lokalen Proxybeleg.

Gültige reine Toolcalls ohne Begleittext bleiben erlaubt. Nichtleerer Refusaltext
bleibt erlaubt und unterliegt weiterhin der Prüfung von Erfolgsaussagen. Normale
Antworten, Bindung, Belegtypen und Protokoll-/Abbruchprüfungen bleiben erhalten.

SSE wird bereits vor dem Hostparser vollständig gepuffert und erst nach geprüftem
terminalem Abschluss und [DONE] weitergegeben. Dadurch erhöht sich die Zeit bis
zum ersten weitergegebenen Byte; eine Streaming-Timinggleichheit besteht nicht.
Bestehende Grenzen von maximal 1 MiB und 60 Sekunden bleiben unverändert.
Ein abgebrochener oder fehlerhafter Stream bleibt auf dem vorhandenen statischen
422-Fehlerpfad, ohne dass daraus eine Diagnose „Modell antwortet leer“ folgt.

Der Guard setzt für den fehlgeschlagenen Session-/Agent-/Modellbereich die native
Retryentscheidung auf false. Unitnachweis und beobachtete native Hostwirkung sind
getrennte Kriterien; keine universelle Aussage über sämtliche Host-/Providerpfade.
Der unten dokumentierte native Stubfall sendete nach einem echten synthetischen
Toolergebnis den leeren SSE-Abschluss und zählte sämtliche weiteren POSTs.
Kein zusätzliches No-Retry-Plugin wurde geladen.

## Deterministische Unitbelege

25 neue Fälle in `tests/opencode-v2.test.mjs`: JSON/SSE mit fehlendem, null,
leerem oder whitespace-only Inhalt, Reasoning allein, leerem Refusal/Toolcallarray,
leerer Antwort nach gültiger Toolquittung; Positivkontrollen für sichtbaren Text,
Refusal und gültige reine Toolcalls. Zusätzliche Streamtests sichern Pufferung
bis zum Abschluss und den unveränderten Fehlerpfad beim Streamabbruch ab.

Vor dem Fix: finaler RED mit 79 V2-Fällen, 62 PASS und 17 FAIL, jeweils HTTP 200
statt erwartetem 422. Nach einer Prüfung auf nichtleeren Text oder gültige Calls
im Parser: betroffene V1-/V2-Suiten 134/134 PASS, 0 Fehler, 0 übersprungen, Exit 0.
Der statische Fehlerbody und die lokale Retryentscheidung werden mitgeprüft.
Belege: `work/opencode-empty-response-20261024/red.tap`,
`red-buffered-empty.tap`, `green-combined.tap`, `verification.json`.
Automatisierte Prüfung, keine menschliche Zweitabnahme und keine native Abnahme
aus diesen Unitfällen ableiten. Bestehende Proxytests wurden dafür nicht wiederholt.

## Einzelner nativer Stubnachweis

Am 24.10.2026 von 01:26:35,767 bis 01:26:37,445 Europe/Berlin lief genau ein neuer
OpenCode-2.1.4-Fall mit Adaptercommit `7e43a76` in einem frischen privaten Profil.
Ein echter synthetischer Node-Test bestand 1/1 mit Exit 0 und erhielt
`[GL:4e3f3c67-ff60-4720-b133-673c865cdbed] EVIDENCE kind=tests`.
Die zweite gescriptete Antwort enthielt `content:null`, synthetisches Reasoning,
Usage, `finish_reason:stop` und vollständiges SSE samt [DONE].

Die native CLI protokollierte HTTP 422 mit exakt dem statischen Guardfehlerbody;
kein Reasoning oder finaler Ersatztext wurde freigegeben. CLI-Exit 1 ist hier der
beabsichtigte Fehlerabschluss, kein bestandener Nutzerauftrag und kein Betriebsfehler
des Probeharness. Der Provider zählte drei HTTP-Anfragen: einen Metadaten-GET und
genau zwei POST-/Completionanfragen. Nach der zweiten Antwort kamen im verbleibenden
nativen Lauf und in der 500-ms-Nachbeobachtung **null weitere POSTs** an.

Dies belegt das beobachtete Verhalten dieses Hostpfads ohne zusätzliches
No-Retry-Plugin. Der Aufruf des Retryhooks wurde nicht separat instrumentiert;
der Befund schreibt die Ursache der unterbliebenen Wiederholung nicht allein dem
Hook zu und beweist keine universelle Retryfreiheit.

Alle sechs Schutzsnapshots blieben gleich; eigene Stub-/CLI-PIDs 249808 und 261840
sind beendet. Kein Ollama-Kontakt oder echter Modellaufruf, keine Datenbankanalyse,
Installation oder Betreiberaktivierung. Grenzen aus Konfiguration/Snapshots sind
kein Nachweis einer OS-weiten Isolation.

Ein erster Runneraufruf davor scheiterte vor jedem Prozessstart an der Konvertierung
des manifestierten ISO-Datums: PowerShell hatte den Wert bereits als DateTime
eingelesen. Dieser Vorstart mit null Stub-/Native-Starts ist unter
`work/opencode-empty-native-20261024/` unverändert erhalten. Der typgerechte Cast
wurde isoliert für DateTime, ISO-String und DateTimeOffset geprüft; ausschließlich
eine neue Geschwisterkopie erhielt die Korrektur. Erst diese startete den einen
tatsächlichen nativen Fall. Kein blinder Wiederholungsstart.

Aktuelle Belege: `work/opencode-empty-native-20261024-corrected/verification.json`
(`PASS_NATIVE_EMPTY_FINAL_GUARD422_SCOPE`), `process-check.json`,
`source-manifest.json`, `case/stdout.jsonl`, `case/provider/03-request.body`,
`03-response.body` und `stub-state.json`. Automatisierte Artefaktprüfung durch
Agent und Hauptagent; keine menschliche Zweitabnahme. Historischer Modelllauf
und Gesamtprojekt bleiben NOT_ACCEPTED.

## Auswertung einer später separat freizugebenden natürlichen Stichprobe

Genau ein Versuch, höchstens zwei Completions, keine automatische Wiederholung.
Kein Warmup, Entladen, Providerwechsel, Neustart oder Erhöhen der Zeitgrenze als
stillschweigende Vorbedingung. Der historische Prompt und die übrigen Profilwerte
werden abgeglichen; notwendige Änderungen an Proxy-URLs, Adapterstand und diesem
neuen Vertrag werden als Unterschiede ausgewiesen. Kein bitgleiches Profil behaupten.

| Beobachtung | Zulässiger Befund und Ende |
| --- | --- |
| Normale sichtbare Antwort | Fehler nicht reproduziert. Stichprobe beenden, Belege sichern, keine Wiederholung und keine rückwirkende Abnahme des historischen Falls. Die aktuelle Pipeline wurde beobachtet, die historische Ursache bleibt offen. |
| Vollständiger gültiger Rohabschluss ohne sichtbaren Inhalt/Refusal/Toolcall | Leerer sichtbarer Abschluss wurde bereits vom lokalen HTTP-Upstream geliefert. Guard soll 422 liefern. Requesterzeugung, Systemzusätze, Provider und Modellinternes sind dadurch nicht pauschal ausgeschlossen oder erklärt. |
| Nur Reasoning, gültige Toolcalls oder Refusal | Felder getrennt ausweisen und nach obigem Vertrag bewerten; `content:null` allein ist kein leerer Abschluss. Keine echten Reasoningtexte in Ergebnisdokumente übernehmen. |
| Timeout, Teilbody, fehlendes SSE-Ende oder Aufzeichnungsfehler | UNVERIFIED / nicht entscheidbar. Keine Modellursache ableiten, keine Grenze erhöhen und nicht neu starten. |

## Lokale Logs derselben späteren Stichprobe

Vor einer Inferenz muss die tatsächlich aktive Ollama-Instanz samt Logziel
feststehen. Der [dokumentierte Windows-Standardpfad](https://docs.ollama.com/troubleshooting)
ist `%LOCALAPPDATA%/Ollama/server.log` samt `server-*.log`-Rotationen. Solche Dateien
wurden hier rein über Dateinamen, Größen und Änderungszeiten gefunden; ihre
Zuordnung zur aktuellen Serverinstanz ist damit nicht belegt. Kein Loginhalt
wurde für diesen Vertrag exportiert und kein Debugmodus/Neustart aktiviert.

Für den später freigegebenen Versuch lokale Vorher-/Nachherkopien der passenden
Serverlogs, Originalpfade, Größen, SHA256, Kopierzeit und UTC-Lauffenster unter
dem neuen ignorierten `work/`-Belegordner sichern. Rotation und fehlende Dateien
offen dokumentieren. Bei ungeklärtem Logziel die Inferenzvorbereitung anhalten;
kein Logging-Reparaturlauf oder Neustart aus diesem Dokument ableiten.

Mit Proxysequenz, Request-/Responsehashes und Laufzeit korrelieren. Fehlt eine
gemeinsame Request-ID, bleibt die Zuordnung eine begrenzte zeitliche Korrelation.
Logs können Lade- oder Laufzeitbeobachtungen ergänzen, müssen aber keine Ursache
für EOS oder eine leere Antwort enthalten. Rohbodys und Logs können private
Daten enthalten und bleiben lokal; keine externe Übermittlung.

Eine natürliche Inferenz und die private Profilaktivierung sind weiterhin nicht
freigegeben. Dieses Dokument autorisiert ausschließlich die beauftragte
Implementierung, Unitprüfung und den gezählten synthetischen nativen Stubfall.
