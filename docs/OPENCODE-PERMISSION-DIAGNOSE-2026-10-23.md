# OpenCode 2.1.4: gezielte Diagnose der Shell-Ablehnung

Stand 23.10.2026, Europe/Berlin. Gesamtstatus NOT_ACCEPTED.

Die native Metadatendiagnose hat Agent, Modell, Schrittlimit und vollständige
exakte Allowregel bestätigt. Der gewünschte Test wurde im vorherigen Modelllauf
trotzdem mit `Permission denied: shell` abgewiesen. Die tatsächlich geprüfte
Ressource wurde dabei nicht dauerhaft gespeichert. Beide Modellproben bleiben
unverändert; kein neuer Modelllauf für diese Diagnose.

## Nachgewiesen und abgeleitet

Der [Upstream-Kompatibilitätstest](https://raw.githubusercontent.com/anomalyco/opencode/v2.1.4/packages/core/test/shell-parse-compatibility.test.ts)
dokumentiert für PowerShell: `git --flag=value` ergibt im Legacy-Parser die
verkürzte Ressource `git --flag`; der portable Scanner erhält den gesamten
Befehl. Der [Permissiontest](https://raw.githubusercontent.com/anomalyco/opencode/v2.1.4/packages/core/test/permission.test.ts)
prüft dieselbe Abweichung mit `git --work-tree=src status`.

Das [Shelltool](https://raw.githubusercontent.com/anomalyco/opencode/v2.1.4/packages/core/src/tool/plugin/shell.ts)
wählt den portablen Scanner bei explizitem Konfigurationsoverride; sonst bei
fehlenden WASM-Assets oder Kanal local/dev. Der vorhandene Probe-Log nennt
`channel=latest local=false`; die öffentliche Bun-Implementierung bindet die
WASM-Assets statisch ein. Die Probe enthielt keinen Override.

Die zunächst abgeleitete Kürzung wurde anschließend ohne Modell direkt mit
den gepinnten Parserdateien gemessen; Ergebnis und Grenzen stehen unten.
Die konkrete Parserwahl und Ressource des früheren nativen Laufs wurden
nicht instrumentiert und sind dadurch weiterhin nicht nachträglich belegt.

Eine reine Portable-Parserprobe wurde lokal ausgeführt: öffentlicher v2.1.4-
Scanner mit vorhandenem TypeScript 5.9.3 im Speicher übersetzt, anschließend
nur `scanPowerShell()` auf vier Strings angewandt. Originalbefehl, getrennte
Reporterargumente, Zusatzdatei und gequotetes Reporterflag bleiben vollständig
erhalten. Kein String wurde ausgeführt, kein Fixturetest, OpenCode oder Modell
gestartet, keine Abhängigkeit installiert. Das Ergebnis beweist nicht das
Legacy-Verhalten des nativen EXE.

Beleg: `work/opencode-evidence-20261023/parser-check.json`, einschließlich
Quellen-/Compilerhashes und der Grenze `portable only; legacy not executed`.
Die separat benötigte Legacy-PowerShell-WASM-Datei war damals lokal nicht
vorhanden. Auf Nutzerhinweis wurde anschließend ihre gezielte Beschaffung
und eine direkte Parser-/Permissionprobe durchgeführt.

## Direkte Legacy-/Permissionprobe ohne Modell

Der Nutzer wies auf die unnötige Kopplung von Parserdiagnose und Modellverhalten
hin. Deshalb wurde die Parserfrage vor einem weiteren Modelllauf isoliert.
OpenCode v2.1.4 am Commit
`68bc26b7da1990ce10ffecfbc1e09eb13aa5d824` pinnt sowohl
`tree-sitter-powershell` als auch `web-tree-sitter` auf `0.25.10`:
[Manifest](https://github.com/anomalyco/opencode/blob/68bc26b7da1990ce10ffecfbc1e09eb13aa5d824/packages/core/package.json),
[Lockfile](https://github.com/anomalyco/opencode/blob/68bc26b7da1990ce10ffecfbc1e09eb13aa5d824/bun.lock).
Der bisher vorhandene Web-Parser 0.26.12 wurde dafür nicht verwendet.

Zwei gepinnte npm-Tarballs, zusammen 2.038.922 Bytes, wurden in das private
Arbeitsverzeichnis geladen. SHA512 stimmt jeweils mit Lockfile und
Registry-Metadaten überein. Ausschließlich benannte Parserdateien, Manifeste
und Lizenzen extrahiert; kein Paketmanager, keine Installationsskripte,
keine globale Installation. Die vier verwendeten Quellmodule wurden unabhängig
bytegenau mit der unveränderlichen OpenCode-Commitquelle abgeglichen.

Am 23.10.2026 um 23:53:11 Europe/Berlin wurde in vorhandenem Node 24.20.0
die echte PowerShell-Grammatik 0.25.10 mit Web-Parser 0.25.10 geladen.
Der Harness übernimmt per TypeScript-AST den exakten `scanLegacy`-Ausdruck
zur Ressourcenauswahl samt Helpern und die unveränderten reinen Funktionen
`Permission.evaluate` und `Wildcard.match`. Die Effect-Laufzeit und der native
Sessiondienst wurden nicht ausgeführt. Der Befehlsstring blieb reine Eingabe;
kein Shellbefehl, Fixturetest, OpenCode oder Modell wurde gestartet.

| Eingabe/Prüfweg | Tatsächlich ausgewertete Ressource | Ergebnis mit unveränderten Agentregeln |
| --- | --- | --- |
| Legacy: `node --test --test-reporter=tap fail.test.mjs` | `node --test --test-reporter` | Deny durch `* / * / deny`; exakte Allowregel trifft nicht. |
| Portable: derselbe Befehl, Ressource aus vorhandenem Parserbeleg übernommen | `node --test --test-reporter=tap fail.test.mjs` | Allow durch die exakte Shellregel. |

Zusätzlich wurde die Upstream-Referenz `git --flag=value` direkt geparst:
Ressource `git --flag`, wie im Kompatibilitätstest dokumentiert. Der Legacy-AST
meldet einen Parsefehler; Upstream verwirft ihn nicht, sondern sammelt trotzdem
die verkürzten `command`-Nodes. Dieser Ablauf wurde unverändert übernommen.
Die Agentregeln stammen aus der vorher nativ aufgelösten `agent.json`.

**Ergebnis:** Die Ursache ist für die gepinnte Parserimplementierung und die
reine Regelauswertung reproduziert. Ein Konfigurationsverlust ist dafür nicht
erforderlich. Dies ist weiterhin keine Aufzeichnung des historischen nativen
Permission-Events, kein Bytevergleich mit dem im Desktop-EXE eingebetteten WASM
und kein Durchlauf der Session-/Savedrule-Orchestrierung.

Belege unter `work/opencode-evidence-20261023/legacy-parser-probe/`:
`assets.json`, `check-parser.cjs`, `result.json`, `verification.json`.
Pin-/Quellabgleich unter `source-v2/legacy-wasm-pin-metadata.json` und
`source-v2/source-commit-verification.json`. Integritäten und Ergebnisdateihashes
anschließend mit expliziten Fehlerprüfungen unabhängig kontrolliert; weder
Parserprobe noch frühere Tests dafür wiederholt. Automatisierter Methodenreview
in separatem Agentkontext ohne konkreten sachlichen Befund; das ist keine
unabhängige menschliche Zweitabnahme. Keine weitere Modellprobe zur Klärung
dieser Parserfrage nötig.

## Gewählte Vorbereitung

Nur im neuen privaten Probeprofil
`work/opencode-evidence-20261023/native-probe-portable/config/opencode.json`:

```json
{"experimental":{"portable_shell_scanner":true}}
```

Das [V2.1.4-Schema](https://raw.githubusercontent.com/anomalyco/opencode/v2.1.4/packages/schema/src/config/experimental.ts)
führt diesen Schalter ausdrücklich. Testbefehl und Allowregel bleiben exakt
`node --test --test-reporter=tap fail.test.mjs`; Standard-Deny bleibt bestehen.
Guardrails-Adapter und bestehende Produktiv-/Globaldateien werden nicht geändert.

| Vorschlag | Fähigkeiten und Vorteil | Einschränkung |
| --- | --- | --- |
| Privater portabler Scanner | Erhält den vollständigen geprüften Ressourcenstring; vorhandene Implementierung, kein neuer Runtimebedarf oder erweitertes Allow. | Experimenteller Schalter; die spätere native Einzelprobe erlaubt Testausführung, bleibt aber ohne vollständige Guardabnahme und ohne Dauerfreigabe. |

Die abgeänderte Schreibweise `--test-reporter tap` wurde nicht gewählt:
Der derzeitige Belegadapter erkennt nur den fest erlaubten Token
`--test-reporter=tap` (auch gequotet). Das Flag einfach wegzulassen wäre ebenfalls
ungeeignet: Node 24 verwendet standardmäßig den spec-Reporter, siehe
[Node-Testreporter](https://nodejs.org/docs/latest-v24.x/api/test.html#test-reporters).
Keine zusätzliche Adapteränderung für diese Diagnose.

Vorabstand vor dem Lauf vom 24.10.2026: Die private Vorbereitung kopierte die synthetische Fixture und den bewährten
stdin-Controller. `prepared-files.json` pinnte sechs Dateien. Ein Start blieb
gesperrt, solange `NATIVE-START-AUTHORIZED.json` fehlte; das ist eine lokale
Bedienhilfe, keine manipulationssichere Autorisierungsgrenze.
Der echte Controllerpräfix wurde ausschließlich gegen eine harmlose Node-
stdin-Senke geprüft: 507 Zeichen/511 Bytes, identischer SHA256, kein Prompt in
argv, fünf unveränderte Quell-/Testhashes, `run-state.json` damals noch abwesend.
Beleg `native-probe-portable/controller-check.json` mit PASS_OFFLINE.

## Verbleibende native Guardabnahme

Die vorher vorbereitete Modellprobe wurde am 24.10.2026 nach ausdrücklicher
Nutzerfortsetzung genau einmal als Guard-Abnahmetest ausgeführt. Ergebnis:
[Testausführung und Annotation vorhanden, Guardabnahme weiterhin offen](OPENCODE-GUARD-ABNAHME-2026-10-24.md).
Kein weiterer Parser-Modellvergleich. Der experimentelle
Scanner ist ausschließlich eine private Testkonfiguration; die direkte Probe
rechtfertigt keine dauerhafte oder globale Aktivierung. Die Parserdiagnose
und das Modellverhalten werden bei weiteren Schritten getrennt bewertet.

Für den inzwischen ausgeführten Lauf galten: genau ein Start dieses privaten
Profils mit vorhandenem `ollama/gpt-oss-20b-32k`, höchstens zwei Modellschritte,
keine Wiederholung. Ollama-Zustand vorher nur lesen, gepinnte Dateien prüfen,
keine fremden Modelle entladen. Eigener Host mit `--standalone`, numerischem
Loopback, privater Umgebung und 180-Sekunden-Wächter; nur eigener Prozessbaum
bei Timeout, Schutzdateien vorher/nachher abgleichen. Freigabe wurde im lokalen
Autorisierungsbeleg und Controllerzustand festgehalten.

Ziel: tatsächliche Shellausführung des absichtlich fehlschlagenden Tests und
gebundene GL-Quittung beobachten. Ein ehrlicher Fehlerbericht oder leeres Finale
belegt noch keine native Zurückweisung einer falschen Erfolgsmeldung. Dieses
weitere Abnahmekriterium bleibt gegebenenfalls getrennt offen. Keine allgemeine
Verhaltensverbesserung oder OS-Isolation aus einem einzelnen Lauf ableiten.
