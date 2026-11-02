# Lokale Graphify-Einbindung

Eingerichtet am 31.10.2026 in `E:\Guardrails-Local` mit dem vorhandenen
Graphify 0.9.94 (`uv tool`, Paket `graphifyy`). Keine Neuinstallation.

## Nutzung

- Wissenskarte: `E:\Guardrails-Local\graphify-out\GRAPH_REPORT.md`
- Interaktive Ansicht: `E:\Guardrails-Local\graphify-out\graph.html`
- Rohgraph: `E:\Guardrails-Local\graphify-out\graph.json`
- Gezielt abfragen: `graphify query "<Frage>"`
- Manuell aktualisieren: `graphify update .`
- Hookstatus: `graphify hook status`

Alle Befehle im Projektordner ausführen. Die Auswertung verwendet lokale
AST-Parser, also strukturelle Codeanalyse ohne Modell-/Cloudaufrufe.
Dokumente und Bilder werden nicht semantisch ausgewertet. Die Ausschlüsse
in `.graphifyignore` schützen insbesondere `sources/`, `work/` und `logs/`.
Der erste Lauf umfasste 82 Codedateien. `Start-Guardrails.ps1` lieferte keine
Symbole; diese Parsergrenze bleibt sichtbar.

## Aktualisierung nach Git-Ereignissen

`graphify hook install` installiert die vorhandenen Standardhooks lokal unter
`.git/hooks/`: `post-commit`, `post-checkout`, `post-merge`, `post-rewrite`.
Dadurch aktualisieren auch Branchwechsel, Merges und abgeschlossene Rebases
die Karte. Bestehende Hooks werden ergänzt. Ein lokaler Merge-Treiber wird
registriert; die vorhandenen Regeln in `.gitattributes` bleiben erhalten.

Nach einem Commit startet die Aktualisierung im Hintergrund. Sie kann einige
Sekunden benötigen. Graphify bündelt überlappende Aktualisierungen über eine
Sperre und Warteschlange. Während Merge/Rebase wird bis zum Abschluss
gewartet. Reine Graph-Ausgabecommits werden zur Schleifenvermeidung übersprungen.
`GRAPHIFY_SKIP_HOOK=1` setzt die Hooks für einen Aufruf aus.

Standardprotokoll auf diesem Rechner:
`C:\Users\REDACTED_USER\.cache\graphify-rebuild.log`.
Ein erfolgreicher Git-Commit allein beweist keinen erfolgreichen Graphaufbau;
bei Zweifeln Protokoll und den Abschnitt `Graph Freshness` im Bericht prüfen.
Reine Dokumentations-/Konfigurationscommits ohne erkannte Codeänderung werden
übersprungen. Auch `graphify update .` lässt die Ausgaben bei unverändertem
Codegraphen unangetastet. `Built from commit` bezeichnet deshalb den letzten
tatsächlichen Graphaufbau und kann hinter dem aktuellen HEAD liegen.

Die erzeugten Dateien bleiben lokal und sind über `.gitignore` ausgeschlossen.
Sie werden weder automatisch gestagt noch committed. Die Hooks sind lokale
Git-Metadaten und werden nicht mitgeklont. Nach einem neuen Checkout mit
vorhandenem Graphify erneut ausführen:

```powershell
graphify extract . --code-only --max-workers 1
graphify update .
graphify hook install
```

Die Projektanleitung in `AGENTS.md` verweist auf die Karte. Ein durch
`graphify codex install` zusätzlich erzeugter wirkungsloser `PreToolUse`-Hook
wurde nicht übernommen; die Aktualisierung erfolgt durch Git.

## Prüfung am 31.10.2026

- Projektgraph gültig: 1.613 Knoten, 3.737 Verbindungen, 54 Communities.
- Erkennung: 82 Codedateien; keine Dokumente, Bilder, PDFs oder Medien.
- Graph enthält keine Quellen aus `sources/`, `work/` oder `logs/`.
- `graphify hook status`: alle vier Standardhooks und Merge-Treiber installiert.
- Echter Einrichtungscommit `d3e8938`: Hookstart beobachtet; Codegraph blieb
  erwartungsgemäß unverändert, da nur Konfiguration/Anleitung geändert wurden.
- Isolierter Git-Funktionstest unter
  `E:\Guardrails-Local\work\graphify-verification-20261031-01a19074`:
  Commit `8a9e00e2` fügte `graphify_commit_probe()` hinzu. Ohne manuellen
  Updateaufruf erschien das Symbol im Graphen; der erzeugte Bericht nennt
  genau diesen Testcommit. Damit ist ein tatsächliches Git-Ereignis geprüft.
- Keine Guardrails-Modellläufe oder fachlichen Abnahmetests gestartet.

## Quellen

- Lokal geprüfte CLI: `graphify --help`, `graphify hook status`.
- Installierte Implementierung: `C:\Users\REDACTED_USER\AppData\Roaming\uv\tools\graphifyy\Lib\site-packages\graphify\hooks.py`.
- Hersteller: https://docs.graphify.com/cookbooks/shared-team-graph

Die Einrichtung verändert keine Guardrails-Validatoren, Modellfreigaben oder
fachlichen Pausen. Die Graphkarte ist eine Navigationshilfe und keine Abnahme
der Guardrails-Qualitätskontrolle.
