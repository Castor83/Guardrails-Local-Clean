---
tags: [projekt/guardrails-local]
typ: projekt
erstellt: 2026-10-27
aktualisiert: 2026-10-27
status: in_bearbeitung
verifikation: bestaetigt
agent: "@codex-desktop-agent"
quelle: "Lokale Guardrails-Originalquellen, Konfigurationsdatei und lesender Git-Abgleich vom 27.10.2026; historische Prüfbelege getrennt bezeichnet"
origin_channel: mcp-tool
---

# Guardrails-Local – belegter Wissensstand

Quellenabgleich: 27.10.2026, Europe/Berlin. Herkunft: @codex-desktop-agent.
Auftrag: bisherige Erkenntnisse dauerhaft in TheHive speichern. Bestätigt sind die unten bezeichneten Dokument- und Dateibefunde; Tests und Modellläufe wurden hierfür nicht wiederholt. Diese Wissensnotiz setzt keine pausierte Projektarbeit fort.

## Ziel und belegter Repositorybezug

Das Projekt soll technisch belegte Qualitätskontrolle auch für ChatGPT über Forge hinaus ermöglichen. Workspace: E:\Guardrails-Local; am 27.10.2026 gelesener Branch prototype, HEAD 8962de023d7c0f1402963b72931ff762d8fd7ff1 (Commit vom 24.10.2026). Quellen: E:\Guardrails-Local\docs\ORIGINALAUFTRAG.txt, work\codex\assistant-goal.json und lesende Git-Abfrage. Der Commit ist ein Quellenstand, keine Gesamtfreigabe.

## Erkenntnisse und Grenzen

1. **Gesamtprojekt NOT_ACCEPTED.** Die allgemeine Zielakte und die begrenzte Guard-Abnahme halten Anforderungen, allgemeine Entscheidungsablage, breitere Hostdurchsetzung, native Fehlerkorrektur und auftragsspezifische Abschlussbelege offen. Quellen: E:\Guardrails-Local\work\codex\assistant-goal.json und E:\Guardrails-Local\docs\OPENCODE-V2-DETERMINISTIC-ACCEPTANCE.md.

2. **Guard V2 hat eine abgeschlossene deterministische Teilabnahme vom 24.10.2026.** Sie gilt für synthetische Unitfälle und native gescriptete Stubpfade unter OpenCode 2.1.4. Historische Belege: 134 Guard-Unitfälle, zwei native Beleg-/Aussagefälle und ein nativer Leerabschlussfall. Verhaltensstand: 7e43a7620f77f973d5b28cce95c018028d149e5a. Natürliche Modellqualität, produktiver Betrieb und allgemeine Host-/Datenflussabnahme sind damit nicht abgenommen. Quelle: E:\Guardrails-Local\docs\OPENCODE-V2-DETERMINISTIC-ACCEPTANCE.md mit den dort verlinkten Prüfartefakten. Kein neuer Testlauf.

3. **Die geschützte Codex-Sitzung bleibt in der gelesenen Konfiguration ausgeschlossen.** E:\Guardrails-Local\work\codex\config.json enthält critic_enabled=false; 01a146ea-9298-7c13-b7ad-0d52596649f0 steht weder in session_ids noch workflow_session_ids. Das ist der Dateizustand vom 27.10.2026; ein laufender Host und seine tatsächlich geladene Konfiguration wurden nicht geprüft. Keine Aktivierung aus dieser Speicherung ableiten.

4. **Automatischer NLI-Anschluss weiterhin begrenzt/offen.** Ohne ausdrücklich gebundene Quelle ist der automatische Codex-Anschluss SKIPPED; explizite Quellenbindung und reservierte Ausführung fehlen dort noch. Ein ausdrücklicher Profilaufruf existiert. Der begrenzte Modus umfasst höchstens 512 Tokens einschließlich Sondertokens; Überlänge führt zu UNVERIFIED. Ein NLI-PASS ist keine allgemeine Wahrheitsgarantie. Quelle: E:\Guardrails-Local\docs\LOCAL-EVALS.md, zuletzt geändert mit 9a613c4 vom 20.10.2026.

5. **DeepEval-Ersatzmodell dokumentiert, neue Abnahme offen.** Seit der dokumentierten Nutzerfreigabe vom 23.10.2026 verwenden Critic, DeepEval und lokaler Korrektor gpt-oss:20b mit Digest f38aa0c53da5f8c49d08c43a99df24ff53167fe68e24664a7777288e7656fdfe. Dies ist ein gelesener Konfigurations-/Dokumentationsstand, keine neue Prüfung des laufenden Modellservers. Der neue Bewertungs-/Korrekturlauf und die native TaskCompletionMetric mit vollständigem Trace bleiben offen. Historischer Versuch: E:\Guardrails-Local\work\live-deepeval-20261023\50eaee5615ba\live-prompt-alignment.json, ERROR vor Inferenz, calls=0. Quelle: E:\Guardrails-Local\docs\QUALITY-STACK.md, Commit 395331e vom 23.10.2026. Historische Funktionsbelege existieren; die pauschale Aussage „NLI und DeepEval wurden nie funktional geprüft“ wäre falsch.

## Verbindliche Grenzen für spätere Nutzung

Bestehende Pausen und Sitzungsgrenzen erhalten. Die Speicherung autorisiert keine Implementierung, globale Aktivierung, Installation, Downloads, Modellaufrufe oder Veröffentlichung. Vorbestehende unzugehörige und unversionierte Dateien bleiben erhalten. Historische Belege dürfen nicht als neue Messung oder als Abnahme des gesamten Projekts ausgegeben werden.

Bei einer später ausdrücklich beauftragten Fortsetzung zuerst diese Quellen und den dann aktuellen projektgenauen Arbeitsstand heranziehen; keine erledigten Tests allein wegen eines neuen Chats wiederholen.

<!-- thehive-navigation:v1 -->
## Explizit erwähnte Notizen

Diese Notizen werden im Text ausdrücklich erwähnt:

- [[10_Projekte/Forge]] — ausdrücklich im Text erwähnt.
- [[10_Projekte/OpenCode]] — ausdrücklich im Text erwähnt.
- [[10_Projekte/TheHive]] — ausdrücklich im Text erwähnt.

## Lokale Graphify-Karte und Commit-Hooks, geprüft 31.10.2026

Herkunft: @codex-desktop-agent, Nutzerauftrag im Chat 01a19074-a79c-7e70-87a7-b0b8a5a22eba. In E:\Guardrails-Local wurde die bereits installierte Graphify-Version 0.9.94 verwendet, ohne Neuinstallation oder Modell-/Cloudaufrufe. Lokale Karte: graphify-out/GRAPH_REPORT.md, graph.html und graph.json; 82 Codedateien, 1.613 Knoten, 3.737 Verbindungen, 54 Communities. .graphifyignore schließt sources/, work/, logs/ sowie Dokumente/Bilder aus; Ausgaben bleiben lokal Git-ignoriert.

Native Git-Einrichtung mit graphify hook install: post-commit, post-checkout, post-merge, post-rewrite und lokaler Merge-Treiber. Der Hook startet nach Commits im Hintergrund; ohne Codeänderung überspringt er den Neuaufbau. Auch ein manueller Updateaufruf lässt unveränderte Topologie unangetastet, daher bezeichnet Built from commit den letzten tatsächlichen Graphaufbau. Standardlog: C:\Users\REDACTED_USER\.cache\graphify-rebuild.log. Prüfbefehle: graphify hook status; graphify update . im Projektordner.

Echte Auslösung beim Einrichtungscommit d3e8938 beobachtet. Separater isolierter Git-Test unter E:\Guardrails-Local\work\graphify-verification-20261031-01a19074: Commit 8a9e00e2 fügte graphify_commit_probe() hinzu; ohne manuellen Updateaufruf erschienen neues Symbol und passende Commitkennung im Graph/Report. Details: E:\Guardrails-Local\docs\GRAPHIFY.md. Ein zusätzlich vom Codex-Installer erzeugter wirkungsloser PreToolUse-Eintrag wurde nicht übernommen. Fachliche Guardrails-Pausen und NOT_ACCEPTED bleiben erhalten. Start-Guardrails.ps1 lieferte keine Symbole; Dokumente/Bilder sind nicht semantisch erfasst. Keine Liveabnahme von Guardrails oder Modellen abgeleitet.

## Zukünftiger Plan aus den Hermes-Erfahrungen – 02.11.2026

@codex-desktop-agent. Quelle: Nutzerkorrektur im Chat 01a19dd3-ea5c-73e2-b2d1-48427eb1b198: Guardrails jetzt **nicht** wieder aufnehmen, sondern die gemeinsamen Überlegungen als zukünftigen Plan festhalten. Die zuvor besprochene Priorität Hermes ist eine mögliche spätere Richtung, keine aktuelle Ausführungsfreigabe. Bestehende Pausen, abgeschaltete Prüfungen und NOT_ACCEPTED bleiben bestehen.

### Anlass und gewünschter Nutzerablauf

Die Hermes-Arbeit zeigte: Anweisungen in SOUL.md erzwingen weder tatsächliche Quellenlektüre noch einen belegten Abschluss. Ein technisch abgeschlossener Modellturn ist kein Nachweis eines erledigten Nutzerauftrags. Der Nutzer möchte Hermes normal bedienen und weder Python-Skripte selbst ausführen noch jede behauptete Leseaktion manuell kontrollieren müssen.

Ein eng angeleiteter synchroner Review konnte die richtige Berichtsdatei und fünf Quellen tatsächlich lesen. Das belegt diesen einzelnen Ablauf, aber keine verlässliche autonome Ausführung im normalen Desktop. Quellen: C:\Users\REDACTED_USER\Documents\Codex\2026-11-01\schau-mal-in-unseren-chats-ich\work\hermes_setup\evidence\report-fresh-review.json und report-fresh-review-verification.json. Neue Einsicht gegenüber der alten Reviewplanung: Elternfolge tatsächlich delegate_task→read_file; der Kindprüfer las den Bericht zuerst. Kein erneuter Modelllauf für diese Notiz.

### Vorschlag für eine spätere Fortsetzung

1. **Vorhandenen Guardrails-Kern nutzen.** Bei künftig ausdrücklich beauftragter Umsetzung zuerst E:\Guardrails-Local und dessen bestehende Beleg-/Auftragsprüfung weiterverwenden. Keine parallele neue Kontrollplattform. Die bisherige Codex-spezifische Belegerfassung ist noch keine fertige Hermes-Anbindung.
2. **Nachweise aus tatsächlichen Werkzeugereignissen.** Leseanforderungen an konkrete Quellen, erfolgreichen Zugriff und relevante Inhalte binden. Bericht und unabhängigen Review an denselben Dateistand binden; ein fremder/alter Bericht oder eine bloße Prüferbehauptung genügt nicht. Ein Werkzeugaufruf beweist dabei keine vollständige inhaltliche Richtigkeit.
3. **Reihenfolge und Abschluss kontrollieren.** Bericht erstellen, genau diesen Stand prüfen, Befunde verarbeiten, erst danach einen belegten Abschluss freigeben. Fehlende oder widersprüchliche Belege müssen einen offenen/fehlgeschlagenen Zustand ergeben. Bestehende Grenze von höchstens zwei Korrekturen erhalten; ERROR/UNVERIFIED nicht automatisch wiederholen oder als PASS ausgeben.
4. **Normale Desktopbedienung als Abnahmekriterium.** Ein Sonderaufruf über ein Skript oder ein bestandener Komponententest ersetzt diesen Ablauf nicht. Auch sichtbare Ausgabe, Streaming, Abbruch, Prüferausfall und Wiederaufnahme müssen im später vereinbarten Prüfumfang berücksichtigt werden.
5. **Vor der Umsetzung die Hostgrenze klären.** Am 02.11.2026 gelesene Hermes-Quellen: agent/verification_stop.py behandelt Codeänderungen, schließt reine Prosa/.md aus und verwendet begrenzte Nachfragen. agent/turn_finalizer.py sowie website/docs/user-guide/features/hooks.md zeigen einen transform_llm_output-Hook, dessen Fehler die Ausführung nicht stoppen; Streaming kann Text schon vor einer Transformation anzeigen. Ein bloßer Ausgabe-Hook ist deshalb noch keine belastbare Sperre vor Anzeige. Ob eine vorhandene Integration genügt oder eine minimale Hermes-Anpassung nötig ist, muss vor einer späteren Umsetzung konkret entschieden und geprüft werden.

### Grenzen und Status

Dies ist ein zukünftiger Plan, kein fertiger Entwurf, keine Implementierung, keine neue Modell-/Hook-/Installationsfreigabe und keine Gesamtwahrheitsgarantie. Keine Guardrails-Produktdatei, Konfiguration oder Aktivierung wurde für diese Überlegungen geändert. Aktuelle Verbote von Ollama und OpenCode gehen historischen Projektplänen vor. Semantische Qualitätsprüfung und technische Belegbindung bleiben unterschiedliche Aufgaben.

Vertiefender aktueller Befund: C:\Users\REDACTED_USER\Documents\Codex\2026-11-01\schau-mal-in-unseren-chats-ich\outputs\Hermes-Normalbetrieb-Abschlusspruefung-2026-11-02.md. Öffentliche Grundlagen: https://www.anthropic.com/research/building-effective-agents und https://hermes-agent.nousresearch.com/docs/user-guide/features/hooks/ .
