# Antwort- und Arbeitsablauf: verbindliche Erweiterung

## Auftrag und Ausführung
Der unveränderte ORIGINALAUFTRAG verlangt eigenständige Implementierung ohne
zusätzliche Freigaberunden. Die Nutzererinnerung vom 16.10.2026 konkretisiert
fünf Ziele: Anforderungsbindung, Entscheidungskonsistenz, Zurückweisung,
Korrektur und belegte Abschlüsse. Dieser Ausbau bleibt im vorhandenen eigenen
Repository; die festen globalen Hookpfade erfordern dieses Checkout. Kein
Worktree, Modellwechsel, Download, Upload oder Eingriff in andere Projekte.

## Mechanismus
Eine operatorseitige Workflow-Policy bindet bestätigte Grenzen an den Hash
des Originalauftrags. Für jede echte Aufgabe wird ein Vertrag mit exaktem
Auftragshash und Policysnapshot gespeichert. Der Vertrag behauptet keine
vollständige automatische Interpretation beliebiger früherer Gespräche.

Der optionale, ausdrücklich je Sitzung aktivierte PreToolUse-Handler betrifft
Bash und apply_patch. Dateiänderungen sind auf das Arbeitsrepository begrenzt;
Originalauftrag, Regelkonfiguration und Laufzeitaudits sind geschützt. Löschen
und Verschieben bleiben gesperrt. Shell-Aufrufe benötigen eine positive,
vollständige Erkennung: einfache lokale Lesezugriffe, feste Diagnoseaufrufe,
die vorhandene Vorprüfung und der feste Testrunner. Zusammengesetzte oder
unbekannte Befehle werden zurückgewiesen, nicht per Schlagwort freigegeben.
Andere Werkzeugpfade sind damit nicht als abgesichert nachgewiesen.

Der feste Runner startet ausschließlich die vorhandene unittest-Suite mit dem
vorhandenen Python, ohne Shell, Installation oder Modellinferenz. Er speichert
Auftrag, Policy, Befehl, Exitcode, Ausgabehash und Dateistand vor/nach dem Lauf.
Eine Mindesttestzahl verhindert einen erfolgreichen Leerlauf. Ein Timeout
beendet nur seinen eigenen Prozess; dies ist keine Betriebssystem-Sandbox.

Finale Texte deklarieren `Arbeitsstatus: OFFEN` oder `Arbeitsstatus: ABGESCHLOSSEN`.
ABGESCHLOSSEN benötigt einen erfolgreichen Testrunner-Beleg für dieselbe
Aufgabe, Policy und unveränderte Projektdateien. Fehlende/alte/fehlgeschlagene
Belege ergeben FAIL; fehlende strukturierte Deklaration UNVERIFIED. Dieser
Prüfbereich ersetzt keine allgemeine semantische Wahrheitsprüfung.

Vorprüfung und Stop erhalten den zusätzlichen Workflow-Befund. Bestätigte
Workflow-Verstöße nutzen das bestehende Budget von maximal zwei Korrekturen;
ERROR/UNVERIFIED werden nicht automatisch wiederholt. Die bisherige Herkunft
chatgpt, der feste Critic und sämtliche Grenzen bleiben bestehen.

## Abnahme und reale Grenzen
Tests müssen Fremdsitzungen, Shell-Verkettung, fremde Pfade, Auditmanipulation,
fehlende Belege, geänderte Dateien, Policydrift und einen echten CPU-Testlauf
abdecken. Native Hook-Erkennung, Vertrauen und tatsächliche Blockierung bleiben
getrennte Nachweise. Neue PreToolUse-Definitionen benötigen Codex-Vertrauen.
Keine garantierte Anzeigesperre und keine Garantie gegen einen Prozess mit
gleichen Dateirechten oder gezielte Selbständerung des Prüfcodes.

Quelle für PreToolUse: https://learn.chatgpt.com/docs/hooks
