# OpenCode evidence implementation

Spec: docs/superpowers/specs/2026-10-23-opencode-evidence-design.md
Ausführung: direkt im beauftragten Repository, Branch prototype, kein neuer
Worktree und keine neue Freigaberunde. Ausgangscommit 86989b0.

## Global Constraints

Keine Pakete, Modelle, globalen Änderungen, Prozesssteuerung oder Cloudprüfer.
Nur eigene Dateien gezielt committen. Fremde Dateien und sources erhalten.
Keine alten Tests allein für Kontextübernahme wiederholen.

## Task 1: ausführbarer Pluginvertrag

Create tests/opencode-evidence.test.mjs and tools/opencode/guardrails-evidence.mjs.
Interface: default async plugin({client,directory}, options) returns V1 hooks.
1. Erst Regressionen schreiben und fehlenden Schutz beobachten (RED).
2. SDK-geprüfte session/call/tool/parent-Bindung und begrenzte Quittungen bauen.
3. Kennzeichnung fehlender, falscher, fehlgeschlagener und veralteter Belege;
   echte Test-/Schreib-/Recherchebelege mit passender Referenz zulassen.
4. Tests: MCP isError, Exit null/nonzero/zero ohne Summary, falscher Pfad/Befehl,
   Taskwechsel/Parallelität/mehrere Teile, SDK-Ausfall, ehrlicher/Plan-/Zitattext,
   Review ist keine Autorisierung, bestehendes Systemarray erhalten.
5. Run node --test tests/opencode-evidence.test.mjs; expected 0 failures.
6. Unabhängiges Review, notwendige Regressionen RED/GREEN reparieren.
7. Passende Prüfung abschließen, eigene Änderungen committen und work/handoff/
   01a169b1-1899-7af3-8164-edfbd5ae2818-working.md aktualisieren.

## Task 2: konkrete Betriebsanleitung und nativer Versuch

Create docs/OPENCODE-INTEGRATION.md mit Quellen, tatsächlich geprüfter Schicht,
lokaler isolierter Einbindung und genau einem begrenzten Funktionsversuch.
Bestehenden Prozess nicht neu starten; globales Ablegen wäre Aktivierung.
Nur konkret fehlende Betriebsbefugnis benennen, falls für den echten Versuch
ein neuer OpenCode-/Modellaufruf erforderlich ist. Keine allgemeine Freigabe.
Belege lokal unter work/opencode-evidence-20261023 sichern; gezielt committen.

## Review Focus

- Gefälschte Zusammenfassungen und zusammengesetzte Shellbefehle.
- API-Ausfälle und nicht eindeutig an echten Parent gebundene ToolParts.
- Weitere Nutzerbeiträge während laufender Werkzeuge, alte Referenzen.
- Geheimnisse in Argumenten/Ausgaben, unbegrenzter Speicherverbrauch.
- MCP-Rohresultate, mehrere Textteile und unveränderte fremde Plugins.

Pre-flight: Task 2 dokumentiert die echten V1-Hooks aus Task 1; keine zweite API.
