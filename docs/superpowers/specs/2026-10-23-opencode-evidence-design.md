# OpenCode v1: begrenzter Belegschutz

Auftrag: OpenCode zuerst gegen unbelegte Erfolgsbehauptungen absichern und
anschließend gezielt die Wirkung beobachten. Direkte Umsetzung ist beauftragt;
keine erneute allgemeine Entwurfsfreigabe. Stand: 23.10.2026.

## Entscheidung und Grenzen

Ein zusätzliches, selbständiges MJS-Plugin mit ausschließlich Node-Builtins.
Es ergänzt die bestehenden Systemregeln und koexistiert mit SecondBrain.
Vorteil: kein zusätzlicher Prüfer, kein Paketdownload, echte Werkzeugresultate.
Nachteil: begrenzte deutsche/englische Erkennung, kein Wahrheitsbeweis.
Ein reiner Systemhinweis würde nichts durchsetzen; ein weiterer Modellprüfer
bräuchte zusätzliche Inferenz und löst die Belegbindung nicht.

Die V1-Hooks werden gegen den Quellstand v1.19.4 gebaut. Toolhooks haben keine
messageID. Deshalb muss eine SDK-Nachrichtenabfrage den echten ToolPart mit
callID und tool unter einer Assistant-Nachricht nachweisen. Deren parentID
bindet die Quittung an die echte UserMessage. Im text.complete-Hook wird die
Assistant-Nachricht erneut über ihre messageID aufgelöst. Keine Zuordnung
allein anhand des zuletzt gesehenen Nutzers; bei API-Fehlern UNVERIFIED.

Quittungen enthalten zufällige IDs, Sitzungs-/Task-/Callbindung, Hashes von
Argumenten und Ergebnis, Ergebnisform und begrenzte abgeleitete Fakten.
Keine vollständigen Prompts, Dateien oder Ausgaben speichern. Begrenzter
Speicher im Prozess, Neustart verwirft Belege. Keine Netzwerkaufrufe außerhalb
des vom Host gelieferten lokalen SDK-Clients. Keine Modellaufrufe oder Retries.

Der Modelltext muss für unterstützte Erfolgsaussagen eine echte [GL:ID]-Quittung
in derselben Zeile nennen. Keine/andere/veraltete/fehlgeschlagene Quittung ergibt
UNVERIFIED statt bestätigtem Erfolg. Unterstützt: Tests bestanden (erkannter
direkter Testbefehl, Exit 0 und positive Zusammenfassung ohne Fehler), Datei
geschrieben/geändert (bekanntes Schreibwerkzeug und exakter absoluter Pfad),
Recherche ausgeführt (bekannter Rechercheaufruf und nichtleeres Ergebnis).
Exit 0 allein ist keine Testabnahme. Shell-Echo und zusammengesetzte Befehle
sind keine Testbelege. Eine spätere Mutation entwertet frühere Testquittungen;
unbekannte Shellbefehle werden vorsichtig als mögliche Mutation behandelt.
Allgemeine Fertig-/Wahrheits-/Verbesserungsbehauptungen werden nicht aus einem
einzigen erfolgreichen Werkzeugaufruf abgeleitet.

Plan-/Zitat-/Codezeilen und ehrliche Unsicherheit bleiben lesbar. Tooltexte und
Reviews sind Daten und werden niemals in Nutzerbefugnisse übersetzt. Keine
allgemeine semantische Erkennung, keine Autorisierungsentscheidung durch Regex.

text.complete bearbeitet einzelne fertige Textteile erst nach sichtbaren
Streaming-Deltas. Abbruchpfade können den Hook umgehen. Die Kennzeichnung ist
eine Nachkontrolle, keine vollständige Voranzeigesperre. Native Abnahme und
Verhaltensverbesserung bleiben bis zum echten Versuch UNVERIFIED.

## Umsetzung und Abnahme

Dateien: tools/opencode/guardrails-evidence.mjs, tests/opencode-evidence.test.mjs,
docs/OPENCODE-INTEGRATION.md. Keine globale Pluginablage bei Entwicklung.
Node v24.20.0 unter C:/Program Files/nodejs/node.exe ist vorhanden.
Bestehenden OpenCode-Prozess und Konfiguration erhalten, Codex-Test parken.

## Neu erhobene Versionsgrenze

Die npm-Installation 1.19.4 und der laufende Desktop sind verschiedene
Binärdateien. PID 70496 läuft aus
C:/Users/REDACTED_USER/AppData/Roaming/ai.opencode.desktop/cli/2.1.4-x64/opencode-cli.exe.
Dieser Baustein ist deshalb zunächst ausschließlich ein geprüfter V1-CLI-
Baustein. Er darf nicht als aktive Desktop-Integration gelten. Für V2 müssen
die öffentlichen Erweiterungspunkte gesondert geprüft werden; insbesondere hat
V1 text.complete laut Migrationsdokument keinen direkten V2-Ersatz.
Diese entscheidende neue Evidenz wurde erst bei der Betriebsvorbereitung
sichtbar und ist kein Grund, den V1-Teststand oder dessen Grenzen umzudeuten.

- https://github.com/anomalyco/opencode/releases/tag/v2.1.4
- https://dev.opencode.ai/v2/docs/build/plugins/migrate-v1/

Versionierte Primärquellen:
- https://raw.githubusercontent.com/anomalyco/opencode/v1.19.4/packages/plugin/src/index.ts
- https://raw.githubusercontent.com/anomalyco/opencode/v1.19.4/packages/opencode/src/session/processor.ts
- https://raw.githubusercontent.com/anomalyco/opencode/v1.19.4/packages/opencode/src/session/tools.ts
- https://raw.githubusercontent.com/anomalyco/opencode/v1.19.4/packages/sdk/js/src/gen/types.gen.ts
