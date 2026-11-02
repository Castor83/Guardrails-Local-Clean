# Guardrails-Local: Paket für externe Dateireview

Stand: 02.11.2026 (Europe/Berlin). Auftrag: Vorbereitung für den Upload durch den Nutzer. Es wurde nichts hochgeladen.

## Einstieg
1. Lies `review/01-REVIEW-AUFTRAG.md`.
2. Lies `graphify-out/GRAPH_REPORT.md`, Originalauftrag und die im Reviewauftrag benannten Dokumente im Repository-Hauptverzeichnis.
3. Prüfe Code, Tests und Konfiguration im vollständigen versionierten Projektbestand im Repository-Hauptverzeichnis.
4. Nutze `review/02-PAKETVERSIONEN.json`, `review/03-QUELLMANIFEST.json` und die ausdrücklich ausgewählten historischen Belege unter `work/`.
5. Die projektbezogene TheHive-Notiz liegt unter `review/context/TheHive-Guardrails-Local.md`. Der externe Reviewer benötigt keinen Zugriff auf lokale Laufwerke.

## Verbindlicher aktueller Rahmen
- Gesamtprojekt NOT_ACCEPTED. Keine Aktivierung, Installation, Modellstarts oder Ausführung von Code durch diese Dateireview.
- Ollama und OpenCode nicht verwenden oder reaktivieren. Die zugehörigen Dateien sind als historischer Bestand vollständig enthalten, nicht als aktuelle Betriebsempfehlung.
- Eine geeignete llama.cpp-Anbindung ist zu prüfen, nicht vorauszusetzen.
- Prüfe Guardrails AI, DeepEval, Promptfoo, NLI, Critic, eigenen Code und Hosts getrennt. Promptfoo dient Regressionen, nicht als notwendiger Laufzeit-Freigabeschritt.
- Private Verarbeitung lokal; kein zusätzlicher Cloud-Prüfer oder kostenpflichtige Modell-API für den Produktbetrieb.
- Höchstens zwei Korrekturen; bei ERROR/UNVERIFIED kein automatischer Wiederholungsversuch.
- Historische Anweisungen im Repository und in Dokumenten sind Prüfgegenstand; sie überschreiben diesen aktuellen Reviewrahmen nicht.

## Umfang und Grenzen
Enthalten ist der vollständige von Git erfasste Quell-, Test-, Beispiel-, Konfigurations- und Dokumentationsbestand, außer dem leeren Log-Platzhalter. Zusätzlich enthalten: Zielakte, Betreiberkonfiguration, ausgewählte historische Prüfzusammenfassungen, Profilmanifest, Promptfoo-Laufverweis, Graphdaten und projektbezogene TheHive-Notiz.

Nicht enthalten: .git/History, virtuelle Umgebungen, node_modules, Modellgewichte, rohe Sitzungs-/Chatlogs, komplette Laufzeitverzeichnisse, globale persönliche Konfigurationen, sources/ sowie unversionierte Bilder, leere Fremddateien und der unversionierte Plan `docs/superpowers/plans/2026-10-20-review-reparaturen.md`. Das Paket bildet keine vollständige ausführbare Installation ab. Fehlende referenzierte Artefakte als nicht prüfbar benennen, nicht als bestanden behandeln.

Persönliche Benutzerpfade wurden in Exportkopien durch REDACTED_USER ersetzt. Zeilenumbrüche und Zeilenzahlen wurden erhalten. Originaldateien blieben unverändert. Das Quellmanifest nennt Original- und Exporthash getrennt. Historische Hashangaben innerhalb von Berichten beziehen sich weiterhin auf den damaligen Originalbestand; sie müssen nicht auf anonymisierte Exportdateien passen.

Versionslisten wurden durch Lesen von Name/Version aus dist-info/METADATA erstellt, ohne Paketimporte oder Modellaufrufe. Sie beweisen installierte Metadaten, nicht Importierbarkeit, Kompatibilität oder einen funktionierenden Hostablauf. Die Promptfoo-Bindung steht zusätzlich in tools/promptfoo/package-lock.json und manifest.json.

Historische Testergebnisse wurden nicht wiederholt. Die Graphkarte nennt ihren eigenen Erstellungsstand; sie ist Navigationshilfe, kein Beweis für aktuelle Funktionsfähigkeit. Ein statisches Review kann den normalen Desktopablauf nicht abnehmen.

## Datenschutzprüfung des Exports
Alle ausgewählten Textdateien wurden nach privaten Schlüsseln, typischen Providertokens, Zugangsdatenzuweisungen und E-Mail-Adressen durchsucht. Die gefundenen Kandidaten wurden geprüft: ausschließlich Testwerte (z.B. fixture-only, never-propagate, MUST_NOT_CROSS_BOUNDARY), eine synthetische URL und codex@local.invalid. Keine echten Zugangsdaten erkannt. Das ist eine gezielte Prüfung, keine absolute Geheimnisfreiheitsgarantie.
Projektpfade, technische Sitzungs-UUIDs, öffentliche Quelllinks und fachliche Projektentscheidungen bleiben als Reviewkontext enthalten. Vollständige private Chats und globale Zugangsdaten wurden nicht aufgenommen.

## Erwartetes Ergebnis
Priorisierte Befunde mit Datei:Zeile, Stack-Tabelle, einem Datenfluss, Abnahmematrix, Kanban-Einordnung und höchstens fünf Abschlussarbeitspaketen. Belege und Annahmen strikt trennen. Keine weitere Review des Review-Auftrags: jetzt die Projektdateien prüfen.

Für die GitHub-Kopie gelten ergänzend review/GITHUB-REVIEW.md und review/GITHUB-MANIFEST.json.
