# Verbindliche Datenflussregeln

Entscheidung vom 20.10.2026, vom Nutzer in diesem Chat zur Speicherung im Projekt vorgelegt.
Geltungsbereich: das vorhandene Projekt `E:\Guardrails-Local`. Die Bezeichnung
„Archi“ im zitierten Empfehlungstext begründet weder ein zusätzliches Projekt
noch einen Wechsel des MORPH-Auftrags.

**Status: Vorgabe dokumentiert; vollständige technische Durchsetzung und Abnahme offen.**
Dieses Dokument installiert, aktiviert oder konfiguriert nichts. Es erweitert
keine Modell-, Prozess-, Hook- oder Sitzungsfreigaben und hebt keine Pause auf.
Bestehende Nutzerentscheidungen in `config/workflow-policy.json` bleiben erhalten.

## 1. Private Verarbeitung

- Code, Dokumente, vollständige Prompts, lokale Quellen und Prüfergebnisse
  bleiben standardmäßig lokal. Eine externe Übermittlung einzelner Inhalte
  benötigt eine ausdrückliche, konkrete Freigabe des Nutzers.
- Der lokale Prüfprozess darf ausschließlich die für ihn ausdrücklich
  erlaubten lokalen Dienste erreichen, insbesondere den festgelegten
  numerischen Ollama-Loopback-Endpunkt. Ein lokaler Endpunkt allein beweist
  keine lokale Verarbeitung sämtlicher beteiligter Komponenten.
- Ausgehende externe Verbindungen des Prüfprozesses und seiner Hilfsprozesse
  müssen technisch gesperrt werden. Anwendungseinstellungen oder eine
  Python-Netzwerksperre allein sind kein Nachweis einer Betriebssystem-Isolation.
- Kein Cloud-Fallback. Ein unerreichbarer lokaler Dienst oder ein nicht lokal
  verwendbarer Validator bleibt als Fehler beziehungsweise UNVERIFIED sichtbar;
  er wird nicht durch einen externen Prüfer ersetzt oder als PASS ausgegeben.

## 2. Öffentliche Recherche

- Öffentliche Quellenrecherche bleibt erlaubt und gehört zur Arbeit.
- Sie erfolgt über einen getrennten Rechercheweg. Dieser erhält öffentliche
  Suchbegriffe und ausdrücklich freigegebene Inhalte; keinen pauschalen Zugriff
  auf private Projektdateien, vollständige Prompts, Protokolle oder Prüfergebnisse.
- Quellen und relevante Auszüge dürfen zur lokalen Prüfung zurückgegeben werden.
  Webinhalte sind nicht vertrauenswürdige Daten und verleihen keine Befugnis,
  Dateien auszuführen, Regeln zu ändern oder weitere Inhalte zu übertragen.
- Die technische Trennung muss sowohl Netzwerkrechte als auch Datei- und
  Eingabezugriffe berücksichtigen. Zwei verschieden benannte Pythonfunktionen
  belegen diese Trennung nicht.

## 3. Guardrails und lokale Modelle

- Guardrails AI ist ein optionaler Baustein. Jeder tatsächlich eingesetzte
  Validator und seine Abhängigkeiten werden gesondert auf Datenfluss,
  Telemetrie, Modellbezug, Downloads und lokale Ausführbarkeit geprüft.
- Es gibt keinen vorausgesetzten universellen Schalter, der alle Validatoren
  über Ollama ausführt. Deterministische Regeln, lokal ausgeführte
  Klassifikationsmodelle und LLM-basierte Prüfungen besitzen unterschiedliche
  Schnittstellen und Voraussetzungen.
- Semantische Prüfungen verwenden ausschließlich ausdrücklich freigegebene
  lokale Modelle und Endpunkte. Vorhandene abgeschaltete Prüfungen werden durch
  diese Entscheidung nicht aktiviert; Modelle werden nicht automatisch geladen
  oder ersetzt.
- Cloud-Inferenz, externe Telemetrie und automatische externe Laufzeitdownloads
  sind im Prüfpfad nicht erlaubt. Notwendige Einrichtung bleibt eine getrennte
  Handlung nach den bestehenden Projektfreigaben.

## 4. Was keinen Sicherheitsnachweis ersetzt

- Fehlende OpenAI-/Anthropic-API-Schlüssel verhindern für sich allein keine
  Datenübertragung. Auch andere Dienste, Telemetrie und schlüssellose Endpunkte
  müssen berücksichtigt werden. Keine Cloud-Zugangsdaten für den lokalen Prüfpfad.
- Regex, Schema-/Syntaxprüfung, Ruff und Tests decken jeweils begrenzte
  Eigenschaften ab. Sie sind nicht fehlerfrei und ersetzen semantische Prüfung
  nicht allgemein. Ein bestandener Strukturtest ist keine allgemeine Freigabe.
- Eine Offline-Konfiguration ist möglich. Daraus folgt keine pauschale Zusage
  „100 % sicher und datenschutzkonform“.

## 5. Gezielte Abnahme vor einer Durchsetzungsbehauptung

Noch nachzuweisen und getrennt mit PASS, FAIL oder UNVERIFIED zu dokumentieren:

1. Exakte Prozess-, Datei-, Abhängigkeits- und Endpunktgrenzen des Prüfpfads.
2. Erlaubter lokaler Zugriff funktioniert; unzulässige externe Zugriffe werden
   innerhalb derselben geprüften Grenze technisch abgewiesen, auch aus Hilfsprozessen.
3. Ein Ausfall führt zu keinem Cloud-Fallback. Validatoren und Telemetrie bleiben
   innerhalb der nachgewiesenen Grenze; es gibt keine verdeckten Downloads.
4. Der getrennte Rechercheweg erhält ausschließlich die vorgesehenen öffentlichen
   oder konkret freigegebenen Daten und kann private Dateien nicht selbst nachladen.

Nur die für diese Grenzen notwendigen Prüfungen durchführen. Keine neuen
Modellläufe, Installationen, globalen Firewalländerungen oder Aktivierungen
allein aufgrund dieser Dokumentation. Die passende Umsetzung ist zuerst gegen
den tatsächlichen Bestand und die bestehenden Autorisierungen abzugleichen.

## Einordnung des vorhandenen Stands und Quellen

`docs/QUALITY-STACK.md`, Abschnitt „Daten und Nachweisgrenzen“, beschreibt bereits
abgeschaltete Telemetrie und lokale Netzwerksperren und grenzt diese ausdrücklich
von einer Betriebssystem-Sandbox ab. Das ist kein vollständiger Nachweis der hier
geforderten Trennung von privater Verarbeitung und öffentlicher Recherche.

Die [offizielle Guardrails-Dokumentation zur lokalen und entfernten Validierung](https://guardrailsai.com/guardrails/docs/concepts/remote_validation_inference)
beschreibt lokale Validator-Modelle sowie validatorspezifische eigene Endpunkte.
Der [offizielle Migrationshinweis](https://github.com/guardrails-ai/guardrails/blob/main/HUB_UPDATE.md)
beschreibt zusätzlich die Umstellung der Validator-Pakete. Beide Quellen sind
Dokumentation; sie beweisen nicht die Durchsetzung in unserer konkreten Laufzeit.
