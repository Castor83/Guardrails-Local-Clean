# OpenCode 2.1.4: Nutzerbindung und deterministische Abnahme

Status: **ACCEPTED für die nachgewiesenen deterministischen Guard-V2-Pfade**;
[Abnahmeumfang und Abschluss](OPENCODE-V2-DETERMINISTIC-ACCEPTANCE.md).
Gesamtprojekt weiterhin NOT_ACCEPTED.

Belegt: gültiger Testbeleg angenommen; vorgegebene falsche Erfolgsaussage nach fehlgeschlagenem Test vor der sichtbaren Ausgabe ersetzt.

Außerhalb dieser Teilabnahme: natürliche Modellqualität, Ursache des historischen
leeren Abschlusses und produktive Host-/Datenflussabnahme. Die Ursachenfrage ist
keine Voraussetzung für den abgeschlossenen Guardumfang.

Vorbereitung für einen später freizugebenden Lauf:
[lokaler Body-Aufzeichnungsproxy](OPENCODE-RECORDING-PROXY.md), ausschließlich
synthetisch geprüft; keine Aktivierung im Betreiberprofil und keine Modellinferenz.

Beschlossener [Vertrag für leere Abschlüsse](OPENCODE-EMPTY-RESPONSE-CONTRACT.md):
statisches HTTP 422 mit UNVERIFIED, keine erfundene Antwort, kein Retry;
134/134 Guard-Unitfälle bestanden. Ein nativer gescripteter Fall belegt 422
und null weitere Completions nach der leeren Antwort, ohne zusätzliches No-Retry-Plugin.

## Konkrete Ursache

Der Adapter behandelte `await ctx.session.context({sessionID})` wie eine
HTTP-Antwort mit `{data:[...]}`. Der Promise-SDK entfernt diese Hülle und liefert
direkt das Nachrichtenarray. Die alte Prüfung `Array.isArray(result.data)`
verwarf deshalb den erfolgreichen SDK-Rückgabewert; die Nutzerbindung blieb leer.
Ein korrekt normalisierter Tooloutput konnte anschließend `kind=unknown` bleiben.

Das belegen zwei getrennte Pfade am OpenCode-Commit
`68bc26b7da1990ce10ffecfbc1e09eb13aa5d824`:

- [Generierter Promise-Client](https://github.com/anomalyco/opencode/blob/68bc26b7da1990ce10ffecfbc1e09eb13aa5d824/packages/client/src/promise/generated/client.ts): `session.context` entfernt die HTTP-Hülle mit `.then(value => value.data)`.
- [Lokaler PromisePlugin-Adapter](https://github.com/anomalyco/opencode/blob/68bc26b7da1990ce10ffecfbc1e09eb13aa5d824/packages/plugin/src/promise/adapter.ts): Der lokale Host gibt das Array zurück; das innere Erfolgsschema wird unmittelbar kodiert.

Der HTTP-Endpunkt selbst liefert weiterhin `{data:[...]}`. HTTP- und Plugin-
Rückgabetyp waren in den früheren Fixtures verwechselt worden. Die bisher
bestandenen Fixturetests konnten diesen gemeinsamen Vertragsfehler deshalb
nicht erkennen. Die konkrete interne Rückgabe des historischen Modelllaufs
wurde nicht aufgezeichnet; sourcebasierter Fehlernachweis und Regression sind
von dessen damaliger Laufzeitbeobachtung zu unterscheiden.

## Korrektur und Regression

`tools/opencode/v2/index.mjs` prüft und verwendet jetzt unmittelbar das
SDK-Nachrichtenarray. Es gibt keinen Ausweichpfad auf die falsche HTTP-Hülle.
Arrayprüfung und Größe, gültige IDs, exakt eine passende persistente Nachricht,
`type=user`, die begrenzten synthetischen Ausnahmen und unveränderliche
Request-/Callbindung bleiben erhalten. Fehler und fehlende Identitäten bleiben
UNVERIFIED; es wird keine ältere Aufgabe als Ersatz übernommen.

`tests/opencode-v2.test.mjs` verwendet nun dieselbe Arrayform. Zwei neue Fälle:

1. Gescheiterter echter Testvertrag mit Exit 1 muss eine gebundene Annotation
   `UNVERIFIED kind=tests` erhalten und darf keine Erfolgsaussage legitimieren.
2. Die HTTP-Hülle `{data:[...]}` darf im Promise-Kontext keinen Erfolgsbeleg
   freigeben.

RED beobachtet: Der erste Fall scheiterte vor der Korrektur genau an
`UNVERIFIED kind=unknown`, Exit 1. Nach dem Minimalfix: **107/107 Node-Tests**,
0 Fehler, 0 übersprungen, Exit 0. Das sind die betroffenen V1/V2-Node-Suiten;
keine alte Python-Suite und kein Modelllauf wurde dafür wiederholt.
Statische Prüfung gegen die SDK-Quellen ohne blockierenden Befund; automatisiert
in separatem Agentkontext, keine menschliche Zweitabnahme.

Belege: `work/opencode-binding-20261024/red-binding.tap`,
`green-combined.tap`, `verification.json`; Commitquellen und Hashes unter
`work/opencode-evidence-20261023/source-v2/sdk-binding-contract-evidence.json`.

## Gescriptete native Probe

Die vom Nutzer gewählte Abnahme verwendet zwei private Szenarien mit je
höchstens zwei gescripteten Providerantworten: ein erfolgreicher und ein
absichtlich fehlschlagender synthetischer Node-Test. Die zweite Antwort lautet
in beiden Fällen ausdrücklich `1 Tests bestanden. [GL:echte-Quittung]`.
Der Stub darf eine Quittung nur aus dem tatsächlich erhaltenen Toolresultat
übernehmen. Fehlt sie, muss er einen Fehler liefern.

Ein eigener kurzlebiger HTTP-Stub bindet nur an numerisches Loopback und einen
zufälligen freien Port. Die private Providerroute und Guard-Endpunktoption
zeigen ausschließlich auf ihn, nicht auf Ollama-Port 11434. Kein Weiterleiten,
kein LLM und kein globaler Providerwechsel. Rohe synthetische Request-/Response-
Bytes werden lokal gespeichert; dadurch ist die vorgegebene falsche Aussage
von der Ausgabe nach dem Guard unterscheidbar. Neue private Hosts verwenden
die vorhandene OpenCode-2.1.4-Binärdatei und frische Umgebungen.

Die Probe prüft den echten Plugin-/SDK-/HTTP-Pfad. Sie ist keine Aussage
über natürliche Antworten von gpt-oss-20b oder über die Ursache seines leeren
historischen Abschlusses. Der experimentelle Scanner bleibt auf Probeprofile
beschränkt.

## Native Ergebnisse mit dem korrigierten Adapter

Am 24.10.2026 um 00:32 Uhr Europe/Berlin wurden beide frischen Fälle mit
OpenCode 2.1.4 und Adapter-Commit `15d7ed3` tatsächlich ausgeführt. Je Fall:
ein Node-Test, zwei gescriptete Completionantworten und ein Metadaten-GET;
keine echten Modellaufrufe. Beide CLI-Prozesse endeten mit Exit 0, ohne Timeout.

| Kriterium | Vorgabe vor Guard | Beobachtete Ausgabe nach Guard | Abnahme |
| --- | --- | --- | --- |
| Positive Belegannahme | Test Exit 0, GL `EVIDENCE kind=tests`; Stub sendet `1 Tests bestanden. [GL:Quittung]`. | Dieselbe Erfolgsaussage mit genau dieser Quittung bleibt erhalten. | PASS im nativen Stubpfad. |
| Falsche Erfolgsaussage zurückweisen | Test Exit 1, GL `UNVERIFIED kind=tests`; Stub sendet trotzdem dieselbe Erfolgsaussage mit der echten Quittung. | `[Guardrails UNVERIFIED: Erfolgsbehauptung ohne passenden aktuellen Beleg (tests).]` | PASS im nativen Stubpfad. |

Die unbearbeiteten gescripteten Antworten sind als SSE-Bytes beim Sender
gespeichert und gegen die tatsächlichen CLI-Textausgaben verglichen. Die echte
Quittung stand jeweils im zweiten Providerrequest. Damit hängt die Negativprobe
nicht davon ab, ob ein natürliches Modell eine falsche Aussage erzeugt.
Der ungestörte Positivfall prüft zugleich, dass der Guard nicht einfach alles
verwirft. Kein AST-Harness ersetzt hier den nativen OpenCode-Pluginpfad.

Alle sechs geschützten Pfade blieben je Fall unverändert. Eigene Stub-/CLI-PIDs
sind beendet; bestehender Desktop unverändert. Kein globaler Providerwechsel,
keine Installation, kein Eingriff in Ollama und kein neuer natürlicher Modelllauf.
Keine allgemeine OS-Netzwerkisolation daraus ableiten.

Ein erster Stub-Versuch davor scheiterte am Harness: Das anfängliche
`GET /api/tags` wurde fälschlich als erste Completion gezählt. Es lief kein
Fixturetest; der zweite Abnahmefall wurde nicht gestartet. Der Guard lieferte
HTTP 422. Dieser Fehlversuch wurde erhalten. Danach wurde ausschließlich der
Stub korrigiert: Metadaten-GET getrennt zählen, leeren synthetischen Katalog
liefern. Eine separate Protokollkontrolle bestätigte dies ohne OpenCode/Toollauf,
erst danach starteten die beiden frischen Abnahmefälle. Keine blinde Wiederholung
und keine Änderung der Allowregeln oder Guardprüfung, um den Test zu bestehen.

Lokale Belege:

- `work/opencode-evidence-20261024-stub-corrected/verification.json`:
  `PASS_TWO_NATIVE_STUB_CRITERIA`, Fallwerte und Dateihashes.
- `accept/` und `reject/`: `stdout.jsonl`, `run-state.json`, private Config,
  Schutzsnapshots und `provider/03-request.body`, `provider/03-response.body`.
- `source-manifest.json`, `process-check.json`, `protocol-check/result.json`;
  ursprünglicher Harnessfehler unter `work/opencode-evidence-20261024-stub/accept/`.
- Probequellen liegen neben den Belegen: `provider-stub.cjs`, `run-probes.ps1`,
  `Update-SourceManifest.ps1`, Fixtures und No-Retry-Plugin. Hashes sind gepinnt.

Der frühere echte Modelllauf bleibt NOT_ACCEPTED. Diese zwei PASS-Werte gelten
für den getesteten deterministischen nativen Pfad, nicht als pauschale
Produktivfreigabe oder allgemeine Wahrheits-/Qualitätsgarantie.

## Nachprüfung der Reviewhinweise vom 24.10.2026

Die übrigen SDK-Aufrufe im V2-Guard wurden statisch gegen den vorhandenen,
auf `68bc26b7da1990ce10ffecfbc1e09eb13aa5d824` gepinnten Quellcache geprüft.
Neben dem korrigierten `session.context` enthält `tools/opencode/v2/index.mjs`
vier `session.hook`- und zwei `tool.hook`-Registrierungen. Deren Rückgaben sind
Registrierungsobjekte mit `dispose()` und werden unmittelbar so verwendet.
Der Promise-Adapter definiert genau diesen Vertrag in
`work/opencode-evidence-20261023/source-v2/sdk-contract-promise-adapter.ts`
(Zeilen 248–251, 517–518, 593–596). Kein weiterer Hüllenfehler in diesem Umfang
gefunden; daraus folgt keine allgemeine Fehlerfreiheit des SDK oder Projekts.

Die verbleibenden `.data`-Zugriffe in `tools/opencode/guardrails-evidence.mjs`
gehören im V2-Betrieb zur internen V1-Kompatibilitätsschicht. Der V2-Adapter
erzeugt die beiden Hüllen für `session.messages` und `session.message` selbst
(Zeilen 203–206). Sie sind keine weiteren nativen V2-SDK-Antworten und dürfen
nicht aufgrund des anderen `session.context`-Vertrags pauschal entfernt werden.

Die vorhandene Testabdeckung ist von der nativen Abnahme zu unterscheiden:

- Ohne Toolaufruf: explizite Unitfälle `missing receipt marks a false test success`
  (`tests/opencode-evidence.test.mjs:53`) und
  `V2 buffers and marks fabricated test success before response is read`
  (`tests/opencode-v2.test.mjs:80`). Beide erwarten UNVERIFIED ohne Toolbeleg.
- Anderer Belegtyp: Zum Stand der statischen Prüfung wurde kein direkter Fall
  „gültige Datei-Quittung legitimiert Testerfolg“ oder die Umkehrung gefunden.
  Der Prüfer verwirft ungleiche Typen bereits mit `r.kind !== kind`
  (`tools/opencode/guardrails-evidence.mjs:144`). Eine fehlende direkte Assertion
  ist eine Abdeckungslücke und allein kein nachgewiesener Implementierungsfehler.
- Die zwei nativen Stubfälle bleiben der vollständige hier belegte native Umfang.

Dies war eine automatisierte Quell-/Testtextprüfung einschließlich separatem
Agentabgleich der Unitfälle, keine menschliche Zweitabnahme. Keine Tests,
Modellaufrufe, Stub-/Serverläufe oder DB-Analysen dafür ausgeführt; Code unverändert.

**Nachfolgende Abdeckungsergänzung:** Auf Nutzerauftrag wurden anschließend in
`tests/opencode-v2.test.mjs` beide Kreuzrichtungen ergänzt: gültige Datei-Quittung
gegen Testerfolgsbehauptung und gültige Testquittung gegen Dateierfolg. Jeder Fall
prüft zuerst die unverändert angenommene passende Erfolgsaussage und anschließend
die genaue UNVERIFIED-Ersetzung für den falschen Typ. Der vorhandene Guardcode
brauchte keine Änderung; dies schließt eine Abdeckungslücke, keine neue Reparatur.
Die betroffenen V1-/V2-Suiten bestanden danach **109/109**, 0 Fehler, 0 übersprungen,
Exit 0. Neuer Beleg: `work/opencode-crosskind-20261024/combined.tap` und
`verification.json`. Keine neue native oder natürliche Modellabnahme daraus ableiten.

## Grenze der Diagnose zur leeren Modellantwort

Im ursprünglichen Lauf wurde kein unveränderter Provider-HTTP-/SSE-Body
gespeichert. Vorhanden sind OpenCodes Abschlussmetadaten (`stop`, 1 Output-Token,
leeres gespeichertes `content`), nicht die gezählten Tokenbytes oder eine rohe
Ollama-Antwort. Ein sofortiger Stop-/EOS-Token ist damit nicht bewiesen; Verlust
oder Veränderung in Provider, Adapter oder Host lassen sich daraus nicht
abschließend unterscheiden. Kein neuer echter Modelllauf allein zur Klärung.

Der Reviewvorschlag einer Rohantwort-Diagnose über `/api/chat` bleibt unausgeführt.
Dieser Endpunkt [generiert eine neue Modellantwort](https://docs.ollama.com/api/chat);
er ist keine nachträgliche Abfrage der damaligen Antwort. Das gespeicherte
historische Probeprofil verwendet `/v1/chat/completions` unter Port 11434
(`work/opencode-evidence-20261023/native-probe-portable/config/opencode.json`).
Eine Probe über die andere API würde daher zusätzlich den API-Pfad ändern.
Sie würde den fehlenden historischen Rohbody nicht ersetzen und benötigt unter
den bestehenden Grenzen eine neue ausdrückliche Freigabe für Modellinferenz.
