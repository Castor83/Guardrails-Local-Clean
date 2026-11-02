# OpenCode: Belegschutz und geprüfte Grenzen

Aktuelle [Teilabnahme der deterministischen Guard-V2-Pfade: ACCEPTED](OPENCODE-V2-DETERMINISTIC-ACCEPTANCE.md).
Keine produktive Aktivierung; Gesamtprojekt weiterhin NOT_ACCEPTED.

## Tatsächlicher Bestand

Am 23.10.2026 getrennt festgestellt:

- npm-CLI: opencode-ai 1.19.4 unter
  `C:/Users/REDACTED_USER/AppData/Roaming/npm/node_modules/opencode-ai`.
- Laufender Desktop-Prozess PID 70496:
  `C:/Users/REDACTED_USER/AppData/Roaming/ai.opencode.desktop/cli/2.1.4-x64/opencode-cli.exe`.
  Dateigröße 246919560, SHA256
  `404110F618D557DE383044DE86AAFB1126BD69FDC312C5A3E6E7ABA137568E3C`.
  Eingebettetes Versionsliteral 2.1.4; kein authentifizierter Releasehash-Abgleich.
- npm-Binärdatei: 211699592 Bytes, SHA256
  `41C848C0986720C02D39B015BD2672E454A221052F6947854BC508D8765D9711`.
- Beide PE-Produktversionen beziehen sich auf Bun und sind kein OpenCode-
  Versionsnachweis. Die unterschiedlichen Installationen erklären den
  notwendigen getrennten Anschluss.

V1-Pluginfunktionen laufen laut offizieller Migration in V2 nicht. Der
bestehende SecondBrain-Anschluss und seine Dateien bleiben erhalten.
Keine der folgenden Implementierungen ist bislang global aktiviert.

## Gemeinsame Belegregeln

`tools/opencode/guardrails-evidence.mjs` erzeugt begrenzte Quittungen mit
zufälliger GL-ID, Sitzungs-/Task-/Werkzeugbindung und SHA256 von Argumenten und
Resultat. Originalprompts und komplette Werkzeugresultate werden weder in
Dateien noch an zusätzliche Prüfdienste geschrieben. Die Werkzeugresultate
bleiben ohnehin Teil der OpenCode-Sitzung; der Schutz ändert daran nichts.
Keine Modellprüfung und keine automatische Korrektur-/Retry-Schleife.

Erfasste Erfolgsaussagen brauchen passende aktuelle `[GL:ID]` auf derselben
Zeile. Dateibehauptungen brauchen einen exakten absoluten Pfad in Backticks.
Ein enger Testbeleg braucht direkten Node-TAP- oder unittest-Befehl, Exit 0
und eine passende positive Zusammenfassung. Exit 0 allein, Echo-Ausgaben,
fehlgeschlagene MCP-Ergebnisse oder falsche Zahlen/Befehle reichen nicht.
Spätere und überlappende Mutationen entwerten Testbelege. Recherchebelege
belegen die Ausführung, nicht die inhaltliche Wahrheit einer Quelle.
Allgemeiner Gesamtabschluss wird nicht aus einem Werkzeugresultat abgeleitet.

Dies ist eine begrenzte deterministische Erkennung deutscher/englischer
Formulierungen. Umschreibungen können unerkannt bleiben; Plan-, Code- und
Zitatzeilen sind ausgenommen. Nachgestellte Negation kann derzeit vorsichtig
als UNVERIFIED markiert werden. Keine allgemeine Wahrheitserkennung und keine
manipulationssichere Grenze gegen andere Plugins oder veränderte Testprogramme.

## V1-CLI 1.19.4

Der SDK-Abgleich sucht den echten gespeicherten ToolPart mit callID, tool,
Argumenthash und Assistant-parentID. Die Modellrequestbindung wird vor dem
Werkzeugaufruf eingefroren. Ein verspäteter Toolbeleg wird nicht anhand der
neuesten Nutzernachricht umgebunden. SDK-Ausfälle ergeben keinen Erfolgsbeleg.

`experimental.text.complete` kontrolliert fertige Textteile **nach** den
Streaming-Deltas. Abbruchpfade können diesen Hook umgehen. Das ist eine
Nachkontrolle, keine allgemeine Sperre vor Anzeige.

Prüfung: 55/55 Node-Tests, Exit 0, einschließlich echtem lokalen Node-TAP-
Kindprozess. Vier wichtige unabhängige Reviewbefunde mit RED/GREEN korrigiert.
Commit `c68fe98dcd63952c4f5bdd4c56d0f94dba2fdddc`.
Belege lokal unter `work/opencode-evidence-20261023/`; kein V1-Hostversuch.

## V2-Desktop 2.1.4

Implementiert und lokal geprüft: `tools/opencode/v2/` als Pluginverzeichnis mit
`default { id, setup }`, ohne zusätzliches npm-Paket. Der geprüfte öffentliche
Anschluss ist `session.hook("http.response")`: OpenCode wartet ihn ab, bevor
der Providerparser Textdeltas erzeugt. Für den untersuchten Ollama-HTTP-Pfad
kann die vollständige Antwort dadurch begrenzt geprüft und ersetzt werden.
Diese Quellcodeeigenschaft ist noch kein nativer Nachweis unserer Integration.
Der Adapter importiert den vorhandenen Prüfkern aus dem übergeordneten Ordner;
deshalb beide Dateien im Repository belassen und das Verzeichnis konfigurieren.

V2 hat kein natives Assistant-parentID. Die Taskbindung muss aus dem echten
Modellkontext und dauerhaftem Nachrichtentyp `user` abgeleitet werden. Eine
abgeleitete interne Normalisierung darf nicht als natives Tracefeld gelten.
Call-IDs aus der tatsächlich geprüften Modellantwort sowie die echten
V2-Toolereignisse bilden die Bindung; neue Nutzerbeiträge dürfen sie nicht
ändern. HTTP-Requests werden über ihre tatsächliche Objektidentität verbunden.

Der Adapter wird ausschließlich für `primary`, Provider `ollama` und den
ausdrücklich angegebenen numerischen Loopback-Endpunkt gebaut. SSE/JSON des
OpenAI-Chat-Formats, beide sichtbaren Textkanäle content/refusal, feste
Größen-/Zeitgrenzen und Abbruchbehandlung sind separat zu prüfen. Andere
Provider und WebSockets sind nicht durch diesen Anschluss abgedeckt.
Vollständiges Puffern verzögert die Anzeige und Werkzeugaufrufe eines
Modellschritts. Andere spätere Plugins können Antworten erneut verändern.

Geprüfte Grenzen: maximal 1 MiB je Body und 60 Sekunden, weniger per
Pluginoption möglich. Unbekannte/ungebundene native Aktionen entwerten ältere
und überlappende Belege. Eine solche Aktion während der asynchronen Textprüfung
verhindert die Freigabe der betroffenen Antwort. Fehler ergeben HTTP 422 mit
UNVERIFIED; der Adapter unterbindet danach native Wiederholungen für den
betroffenen Ollama-Sitzungs-/Agenten-/Modellbereich. Bei 128 Fehlerbereichen
werden Ollama-Wiederholungen vorsichtig insgesamt bis zum Entladen unterdrückt.

V2 unterstützt derzeit Erfolgsbelege für erkannte direkte `shell`-Testläufe
und native `write`-Ergebnisse mit exakt passendem absoluten Pfad. Nicht sicher
übersetzte `edit`-, Recherche-, MCP- und Custom-Ergebnisse bleiben UNVERIFIED.
Eine korrekt beendete Aktion ist dabei nicht automatisch ein Erfolgssiegel.

Offline-Abschlussprüfung: **105/105 Tests**, Exit 0 (55 gemeinsamer/V1-Vertrag,
50 V2-Regressionen). Echte Web-API-Objekte/Streams, Hostereignisse als Fixtures;
Diese Tests sind kein nativer OpenCode- oder Modellnachweis. Zwei wichtige V2-Reviewbefunde und
eine daraus abgeleitete zeitliche Grenzverletzung wurden reproduziert und
per RED/GREEN korrigiert. Voller Beleg:
`work/opencode-evidence-20261023/final-combined-suite.tap`.

Konkrete V2-Einbindung für eine getrennte Testkonfiguration:

```json
{
  "plugins": [{
    "package": "file:///E:/Guardrails-Local/tools/opencode/v2",
    "options": { "endpoint": "http://127.0.0.1:11434/v1/chat/completions" }
  }]
}
```

Das Beispiel ist keine ausgeführte globale Konfigurationsänderung.

## Native Proben: nicht abgenommen

Am 23.10.2026 wurde zunächst die ausdrücklich freigegebene einzelne Probe ausgeführt,
mit getrenntem Host und synthetischen Dateien. Beide lokalen Plugins wurden
geladen. Das Modell versuchte jedoch `dir /B` statt des vorgeschriebenen Tests;
die native Berechtigung verweigerte den Aufruf. Zwei Modellschritte, keine
Abschlussantwort, keine GL-Quittung, keine Guard-Ersetzung.
**NOT_ACCEPTED; falsche Erfolgsmeldung NICHT_AUSGELÖST.**
Globale Konfiguration und bestehender Desktop-Prozess blieben unverändert.
Keine automatische Wiederholung. Vollständiger Beleg und Transportbefund:
[Nativergebnis](OPENCODE-NATIVE-ERGEBNIS-2026-10-23.md).
Eine Konfigurationsdatei allein beweist keine OS-Isolation oder Datenflussabnahme.
Keine Downloads oder Paketinstallation als verdeckte Voraussetzung auslösen.

Konkrete Probe liegt lokal unter
`work/opencode-evidence-20261023/native-probe/`: vollständige V2-Konfiguration,
synthetische Testdatei, genauer Prompt und PLAN.md mit Aufruf/Kindumgebung.
Die Testdatei wurde separat geprüft: absichtlicher Exit 1, genau eine
fehlgeschlagene Assertion. Vorab nur JSON-Syntax geprüft; der native Start
belegt inzwischen Konfigurationsannahme und Plugin-Ladeereignisse.
Einzelne Guard-Callbacks sind damit noch nicht nachgewiesen.
Ein V2-Aufruf muss `run --standalone` verwenden und cwd/PWD auf das
Fixtureverzeichnis setzen. Ein Lauf ohne diesen Schalter könnte den
bestehenden Dienst verwenden. Kein `--dir` aus V1 übernehmen.

Zusätzlich zeigte die DB einen doppelt und mit literalen Anführungszeichen
verarbeiteten Prompt. Der verwendete `--`-Aufruf passt exakt zur doppelten
Argumentübernahme im CLI-Handler. Für einen späteren freigegebenen Versuch
UTF-8-stdin ohne Promptargument und ohne `--` nutzen. Dieser reine Transport
wurde zunächst mit Node und nach dem ausdrücklichen „Weiter.“ in genau einem
korrigierten nativen Lauf geprüft: Prompt unverändert übernommen; nun exakt
der vorgesehene Node-Test angefordert. OpenCode verweigerte aber auch diesen
Aufruf mit `Permission denied: shell`, `executed=false`. Zwei Modellabschlüsse,
keine finale Antwort, GL-Quittung oder Guard-Ersetzung.
**Prompttransport PASS; native Guardabnahme UNVERIFIED.**

Eine reine Metadatendiagnose bestätigte danach den Fixturepfad und die
vollständig aufgelöste exakte Shell-Allowregel. Zunächst nur eingebaute Agenten,
bei der nächsten Anfrage nach 200-ms-Pause auch `guard-probe`: Direktes
`agent.get` wartet in V2.1.4 nicht
auf die Pluginaktivierung. Locationauswahl: `location[directory]` oder
`x-opencode-directory`, kein flaches `directory`. Dieser Befund erklärt
die Shell-Ablehnung noch nicht. Die anschließende
[Parserdiagnose](OPENCODE-PERMISSION-DIAGNOSE-2026-10-23.md) fand eine
dokumentierte Legacy-Abweichung bei `=` und reproduzierte sie anschließend
direkt mit den gepinnten Parserdateien 0.25.10, ohne Modell oder Befehlsausführung.
Die verkürzte Ressource trifft auf Deny; die vollständige portable Ressource
trifft bei identischen Regeln auf Allow. Reine Permission-Funktion geprüft,
kein nachträglicher nativer Eventbeleg. Das private Profil mit experimentellem
Scanner-Override war zu diesem Zeitpunkt vorbereitet und startgesperrt.
Am 24.10.2026 folgte nach ausdrücklicher Nutzerfortsetzung genau ein
[nativer Guard-Test](OPENCODE-GUARD-ABNAHME-2026-10-24.md): Test tatsächlich
ausgeführt (Exit 1, absichtlicher Fehler), GL-Annotation vorhanden, aber
`UNVERIFIED kind=unknown` und keine finale Antwort. Textzurückweisung weiterhin
NICHT_AUSGELÖST; Gesamtstatus NOT_ACCEPTED. Keine automatische Wiederholung.

Nachfolgende Korrektur vom 24.10.2026: Der Promise-SDK liefert den Sessionkontext
direkt als Array; die frühere `.data`-Annahme verlor die Nutzerbindung.
Minimal korrigiert und per RED/GREEN abgesichert, **107/107 Node-Tests**.
Zwei anschließend tatsächlich ausgeführte native Stubfälle belegen positive
Belegannahme und Zurückweisung einer bewusst vorgegebenen falschen Erfolgsaussage.
Details, Rohbelege und Grenzen: [Bindungsreparatur und Stub-Abnahme](OPENCODE-BINDING-REPARATUR-2026-10-24.md).
Keine neue echte Modellinferenz oder globale Aktivierung; Gesamtziel weiter
NOT_ACCEPTED. Der historische leere Modellabschluss bleibt ungeklärt.

Der vorhandene numerische Loopback-Endpunkt wurde vorab über `/api/ps` und
`/api/tags` ausschließlich lesend geprüft: konfiguriertes Modell registriert,
zum Aufnahmezeitpunkt nicht geladen, keine anderen geladenen Ollama-Modelle.
Das beweist keine allgemeine GPU-Verfügbarkeit. Nach dem genehmigten Lauf war
das Modell geladen; kein Entladen ausgelöst. Die Einzelfreigabe ist verbraucht
und wurde nicht automatisch wiederverwendet. Der spätere korrigierte Lauf
hat eigene Belege unter `native-probe-stdin/`; die anschließenden reinen
GET-Abfragen unter `native-permission-inspect-location/` verwendeten kein Modell.

## Primärquellen

- [V1-Hookvertrag](https://raw.githubusercontent.com/anomalyco/opencode/v1.19.4/packages/plugin/src/index.ts)
- [V1-Streaming-Lifecycle](https://raw.githubusercontent.com/anomalyco/opencode/v1.19.4/packages/opencode/src/session/processor.ts)
- [V2-Migration](https://dev.opencode.ai/v2/docs/build/plugins/migrate-v1/)
- [V2-Release 2.1.4](https://github.com/anomalyco/opencode/releases/tag/v2.1.4)
- [V2-Session-Hooks](https://raw.githubusercontent.com/anomalyco/opencode/v2.1.4/packages/plugin/src/promise/session.ts)
- [V2-Tool-Hooks](https://raw.githubusercontent.com/anomalyco/opencode/v2.1.4/packages/plugin/src/promise/tool.ts)
- [V2-HTTP-Grenze](https://raw.githubusercontent.com/anomalyco/opencode/v2.1.4/packages/core/src/session/model-request.ts)
- [V2-Ollama-Anschluss](https://raw.githubusercontent.com/anomalyco/opencode/v2.1.4/packages/core/src/plugin/provider/local.ts)
- [V2-CLI und Standalone](https://raw.githubusercontent.com/anomalyco/opencode/v2.1.4/packages/cli/src/commands/commands.ts)
- [V2-Konfigurationsschema](https://raw.githubusercontent.com/anomalyco/opencode/v2.1.4/packages/schema/src/config.ts)
