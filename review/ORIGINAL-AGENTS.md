# Guardrails-Local: Arbeitskontext

## Globale Codex-Vorgaben

C:\Users\REDACTED_USER\.codex\AGENTS.md vor Arbeitsbeginn vollständig lesen. Die dort aktuellen Regeln zu gezieltem Kontextabruf, Sicherung VOR Komprimierung und gebundenem Chatwechsel gelten auch hier und ersetzen ältere widersprechende Übergabe-/Heartbeatvorgaben. Dieser zentrale Regelpfad ist ausdrücklich lesbar; sonstige Projektgrenzen, Freigaben und Pausen bleiben erhalten. Die Dokumentpflege startet keine Modelle, Dienste oder Automationen.

Dieses Repository ist der vorhandene Arbeitsstand des Projekts GuardrailsAI.
Der Wechsel zu einem lokalen Codex-Projekt ist kein Auftrag zur Neuinstallation
oder zur Aktivierung deaktivierter Prüfungen.

- Verbindlicher Originalauftrag: `docs/ORIGINALAUFTRAG.txt`. Das Ziel bleibt eine
  technisch belegte Qualitätskontrolle auch für ChatGPT, über Forge hinaus.
  Insbesondere dürfen Vermutungen und rekonstruierte Chattitel nicht als
  tatsächlich recherchierte oder verifizierte Ergebnisse ausgegeben werden.
- Aktuelle Nutzerentscheidungen und Installationsregel:
  `config/workflow-policy.json`. `NO_NEW_RUNTIME` ist **kein pauschales
  Installationsverbot**: notwendige lokale Ergänzungen für beauftragte
  Einrichtungen sind unter den dort genannten Bedingungen zulässig.
- Verbindliche Datenflussentscheidung vom 20.10.2026:
  `docs/DATENFLUSS-REGELN.md`. Private Verarbeitung lokal absichern, öffentliche
  Recherche getrennt erlauben, jeden Validator einzeln prüfen. Dokumentierte
  Vorgabe nicht als bereits durchgesetzte oder abgenommene Isolation ausgeben.
- Fortführung und überprüfter Übernahmestand:
  `work/codex-project-transfer/CONTEXT.md`. Fachlicher Restauftrag:
  `work/codex/assistant-goal.json`; Gesamtstatus derzeit `NOT_ACCEPTED`.
- Vorhandene Pläne: `docs/WORKFLOW-PLAN.md`, `docs/WORKFLOW-ENTWURF.md` und
  `docs/IMPLEMENTIERUNGSPLAN.md`. Alte Statusnotizen und frühere pauschale
  Installationsverbote darin sind historisch; aktuelle Nutzerentscheidungen
  gehen vor. Keine erneute allgemeine Freigaberunde für bereits beauftragte Arbeit.
- Ergänzender Nutzerplan vom 18.10.2026, unverändert zum Abgleich gesichert:
  `docs/ARBEITSPLAN-2026-10-18.md`. `docs/QUALITY-STACK.md` beschreibt den
  expliziten lokalen Anschluss. Prompt Alignment/G-Eval sind keine bereits
  abgenommene native Task Completion; echter Traceadapter, allgemeine
  Entscheidungsablage und verbindlicher Hostdurchlauf bleiben getrennte Kriterien.
- Reparatur und Grenzen: `docs/CONVERSATION-EVIDENCE.md`,
  `docs/LOCAL-EVALS.md`, `work/repair-20261018/verification.json` und
  `work/repair-20261018/full-tests.txt`. Vorbereitete Logik, CPU-Vertragstests,
  echte Modellaufrufe und native Host-Abnahme getrennt benennen.
- Betreiberzustand erhalten: Die Sitzung
  `01a146ea-9298-7c13-b7ad-0d52596649f0` bleibt außerhalb der Freigabelisten;
  `critic_enabled=false`. Projektzuordnung erweitert keine Aktivierungsbefugnis.
- Bestehende Nutzeränderung an `config/workflow-policy.json`, uncommittete
  Arbeit und die fremden leeren Dateien `UserPromptSubmit` und `hooks` erhalten.
  Synchronisierte Quellen unter dem bisherigen ChatGPT-Projektpfad `sources/`
  bleiben nur lesbare Referenzen; nicht ändern, verschieben oder löschen.
- Historische lokale Nachfolge-IDs in work/handoff/<Ursprungs-ID>.json erhalten; vor jeder Erstellung den aktuell global geforderten eindeutigen Ursprung prüfen.

Keine erledigten Prüfungen, Downloads oder Modellläufe allein für die
Kontextübernahme wiederholen. Neue Abschlussbehauptungen benötigen tatsächliche
Belege für den betroffenen Stand; ein bestandener Formtest ist keine
Wahrheitsgarantie.

## Bestehende Übergabedaten

Vorhandene lokale Übergabeberichte und UUID-working-Dateien erhalten. Die aktuelle globale Sicherungs-/Stoppreihenfolge und Commitregel gelten; alte Komprimierungsnacharbeit oder automatische Chaterstellung daraus nicht erneut aktivieren.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Local scope: code-only AST extraction; `.graphifyignore` excludes protected references, runtime data, documents and images. See `docs/GRAPHIFY.md` for setup and verification. The global instruction to read `graphify-out/GRAPH_REPORT.md` first remains binding.

When the user types `/graphify`, use the installed graphify skill or instructions before doing anything else.

Rules:
- When graphify-out/graph.json exists, run `graphify query "<question>"` before your first grep, search or source-file read for a codebase question, and put this rule in every subagent prompt that explores code. Read raw files only for lines the graph or an earlier read already located. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- Dirty graphify-out/ files are expected after hooks or incremental updates; dirty graph files are not a reason to skip graphify. Only skip graphify if the task is about stale or incorrect graph output, or the user explicitly says not to use it.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md first as required by the global instructions; reuse it within the same chat and use query/path/explain for focused follow-up questions.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
- A committed graphify-out/graph.json is rewritten whole on every build, so a large diff to it in a pull request is expected. Do not flag it as churn or suggest skipping the graph rebuild or its hooks.
