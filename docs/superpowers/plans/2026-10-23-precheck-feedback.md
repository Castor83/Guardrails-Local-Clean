# Gebundenes Vorprüfungsfeedback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Standardmäßig inaktives, dauerhaft begrenztes Feedback nach einer gebundenen Vorprüfung offline implementieren und prüfen.

**Architecture:** Eine fokussierte lokale Ledgerkomponente reserviert Prüfungen und
verbraucht Korrekturbelege unter der bestehenden Sitzungssperre. Der vorhandene
Adapter ruft sie ausschließlich für explizit freigegebene Feedbacksitzungen auf.

**Tech Stack:** Vorhandenes Python, Standardbibliothek, unittest, atomare JSON-Dateien.

**Spec:** `docs/superpowers/specs/2026-10-23-precheck-feedback-design.md`

## Global Constraints

- Maximal drei verschiedene feedbackverwaltete Vorprüfungen und zwei reservierte Korrekturen pro Task.
- Neue optionale Freigabeliste `precheck_feedback_session_ids`; fehlend ist inaktiv.
- Keine Änderung bestehender Konfiguration, Sitzungsliste, Modelle oder Hookregistrierung.
- ERROR/UNVERIFIED/ESCALATED: keine automatische Folgeprüfung oder Korrektur.
- Normale neue Nutzernachrichten übernehmen keine alten Rechte oder Budgets.
- Gesamtstatus NOT_ACCEPTED; native Hostabnahme und Betriebssystem-Isolation offen.

## Review Focus

- Gleichlautender neuer Auftrag mit alter Task-Datei muss abgewiesen werden.
- Identischer Beleg mit neuer Tool-ID darf kein zweites Feedback auslösen.
- Absturz zwischen Reservierung und Ausgabe darf nicht erneut ausgeben/prüfen.
- Widerruf oder Regelwechsel zwischen Prüfung und Verbrauch darf nicht korrigieren.
- Unbekannte native Ausgabeform darf weder als PASS noch als Korrekturgrund gelten.

### Task 1: Ledger und standardmäßig inaktiver Adapteranschluss

**Files:** Create `src/guardrails_local/precheck_feedback.py`,
`tests/test_precheck_feedback.py`; modify `src/guardrails_local/codex_hook.py`,
`src/guardrails_local/workflow.py`, `docs/CODEX-INTEGRATION.md`.

**Interfaces:**
- `precheck_feedback.run(root, directory, state, config, answer_path, task_path, turn_id, text, check)`:
  Aufruf unter Sitzungssperre; `check()` liefert vorhandenen Prüfbericht.
  Ergebnis ist Prüfbericht mit lokal gebundener `feedback_receipt_id`.
- `precheck_feedback.consume(root, directory, state, config, payload) -> dict`:
  Aufruf unter Sitzungssperre; liefert höchstens einmal unterstützten Zusatzkontext.
- Bestehendes `codex_hook.precheck` bleibt ohne neue Freigabe unverändert.

- [x] Tests zuerst: reale Profil-Längenverletzung, Maximalbudget, richtige Bindungen,
  alle fünf Review-Focus-Fälle sowie terminale Ergebnisse, gefälschte Ausgabe,
  nicht korrigierbarer Critic-only-Befund, Parallelverbrauch und normale neue Nachricht.
- [x] Gezielte Suite mit Controller-Python ausführen; fehlender Anschluss muss rot sein.
- [x] Ledger und engen Callbackanschluss implementieren; keine Runtime-Konfiguration ändern.
- [x] Gezielte Suite und bestehende Hook-/Workflow-Verträge ausführen, Ausgabe lokal sichern.
- [x] Unabhängigen lesenden Review einholen; echte Befunde gezielt mit RED/GREEN beheben.
- [x] Eigene zusammengehörige Änderungen gezielt committen, laufenden Übergabestand aktualisieren.

Task 1: 34 neue gezielte Tests nach Reviewreparatur bestanden. Ursprünglicher
RED-Lauf 21 Tests/13 Fehlschläge; Review-RED 34 Tests/10 Subtest-Fehlschläge.
Vor Reviewreparatur 46 bestehende Hook- und 24 Workflowtests bestanden. Erste
Gesamtsuite: 430/430 bestanden, aber globale Konfigurationsdrift seit früherer
Sitzungsaufnahme separat gemeldet. Reparierten Gesamtstand unter Task 2 prüfen.

### Task 2: Integrationsnachweis und Abschlussstand

**Files:** Planstatus und laufender lokaler Übergabestand; lokale Nachweise unter
`work/precheck-feedback-20261023/`. Keine neue Produktfunktion.

**Interfaces:** Task 1 produziert den vollständigen geprüften Quellstand und
ausgeschalteten Anschluss. Abschluss berichtet dessen genaue Grenzen.

- [x] Passende gesamte CPU-Vertragssuite für den neuen Quellstand ausführen;
  kein Modell und keine bereits abgeschlossene alte CLI-Abnahme wiederholen.
- [x] Quellstand, Prüfresultate und unveränderte geschützte Dateien per Hash binden.
- [x] Native Hostwirkung UNVERIFIED und Gesamtstatus NOT_ACCEPTED festhalten.
- [x] Planstatus sichern; eigene Dokumentationsänderung prüfen und committen.
- [x] Laufenden Übergabestand mit Commit, Belegpfaden und genau nächstem Schritt aktualisieren.

Task 2: reparierter Stand 435/435 CPU-Vertragstests bestanden, Exit 0, null
Failures/Errors/Skips; 110.718 Sekunden. 74 Quell-/Konfigurationsdateien stabil,
elf Schutzdateien während des letzten Laufs unverändert. Ursprüngliche globale
Konfigurationsdrift wird im Negativbeleg erhalten; nachgereichter Nutzerbericht
ordnet sie separat freigegebenem PreCompact zu. Gespeicherte Trustinspektion und
aktuelle Skripthashes abgeglichen, kein Lifecycle-Nachweis behauptet.

Native Fortsetzung: `docs/NATIVE-FEEDBACK-TESTPLAN.md`, noch nicht freigegeben.
Keine Produktivaktivierung. Belege und laufender Stand unter
`work/precheck-feedback-20261023/` bzw. `work/handoff/`.
