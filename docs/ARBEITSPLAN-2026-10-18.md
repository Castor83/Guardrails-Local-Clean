# Arbeitsplan: Zuverlässigkeitskontrolle für KI-Assistenten

Projekt: Guardrails AI + DeepEval + Promptfoo | Stand: 18. Oktober 2026

## 1. Projektziel

Wir bauen eine lokale Prüf- und Korrekturinstanz für KI-Assistenten, die Fehler möglichst erkennt, bevor sie beim Nutzer ankommen oder in einem Projekt umgesetzt werden.

Es geht ausdrücklich nicht darum, die Programmierfähigkeiten eines Sprachmodells künstlich zu erhöhen, sondern seine tatsächliche Arbeitsleistung zuverlässiger zu machen.

Die Lösung soll insbesondere verhindern, dass ein Assistent:

- bereits bekannte Anforderungen oder Entscheidungen ignoriert,
- nicht belegte technische Empfehlungen als Fakten ausgibt,
- unnötige Tests vorschlägt, obwohl die Antwort recherchierbar ist,
- frühere Fehlentscheidungen wiederholt,
- unvollständige oder fehlerhafte Arbeit als erledigt meldet,
- nach einer Korrektur erneut denselben erkannten Fehler produziert.

Zielzustand: Der Assistent arbeitet an einer Aufgabe, seine Ergebnisse werden geprüft, erkannte Fehler führen automatisch zu einer gezielten Korrektur, und erst danach wird das Ergebnis freigegeben.

## 2. Technische Grundlage

KI-Assistent / Entwicklungsagent

Erstellt Vorschläge, Entscheidungen, Rechercheergebnisse oder Code

Prüf- und Korrektursteuerung

DeepEval

Anweisungstreue & Aufgabenerfüllung

Guardrails AI

Validierung & Fehlerreaktion

Projektwissen & Nachweise

Bekannte Entscheidungen, Anforderungen, Belege und Ergebnisse

Freigabe

Prüfkriterien erfüllt

Korrektur

Gezielte Überarbeitung und erneute Prüfung

Promptfoo

Separate Regressionstests, damit bereits behobene Fehler bei Änderungen wieder auffallen

Promptfoo wird bewusst nicht für jede einzelne Live-Antwort gestartet. Es kontrolliert insbesondere Änderungen an der Prüflogik und an den Arbeitsabläufen.

## 3. Verbindliche Rahmenbedingungen

| Bereich         | Vorgabe                                                            |
| --------------- | ------------------------------------------------------------------ |
| Betrieb         | Lokal auf Windows 11                                               |
| GPU             | RTX 4080, 16 GB VRAM                                               |
| Arbeitsspeicher | 48 GB RAM                                                          |
| Cloud           | Keine Cloud-KI als Voraussetzung                                   |
| API-Kosten      | Keine kostenpflichtigen APIs einplanen                             |
| Modelle         | Vorhandene Modelle bevorzugen; keine blinden Downloads             |
| Guardrails AI   | Version 0.11.0 wurde bereits erfolgreich importiert                |
| DeepEval        | Zur Integration vorgesehen                                         |
| Promptfoo       | Zur Integration vorgesehen                                         |
| Modellserver    | Noch nicht endgültig festgelegt                                    |
| Entwicklung     | Vorhandene Funktionen bevorzugen, möglichst wenig Eigenentwicklung |

Der geplante Systemaufbau soll unabhängig davon bleiben, welcher Modellserver später verwendet wird. Der hohe RAM-Verbrauch der LM-Studio-GUI wird berücksichtigt; ihre erneute Einführung ist nicht Teil des Plans.

## 4. Umsetzungsphasen

## 01

Bestand und Kompatibilität

Vorbereitung

Vorhandene Installationen und Schnittstellen ermitteln, Abhängigkeiten und lokale Judge-Unterstützung klären.

Guardrails-Installation und Python-Umgebung erfassen

Node.js und Promptfoo-Voraussetzungen prüfen

DeepEval-Metriken und lokale Modellanbindung verifizieren

Bestehende Projektumgebung unverändert lassen

Ergebnis: Dokumentierte technische Basis ohne unnötige Neuinstallation

## 02

Lokale Prüfgrundlage

Integration

DeepEval und Promptfoo in einer getrennten, nachvollziehbaren Umgebung einrichten.

Versionen und Abhängigkeiten festlegen

DeepEval und Promptfoo installieren

Cloud- und Telemetrie-Einstellungen kontrollieren

Eine gemeinsame lokale Modell-Schnittstelle konfigurieren

Ergebnis: Alle drei Frameworks verfügbar und konfigurierbar

## 03

Anweisungs- und Ergebniskontrolle

Kernfunktion

Vorhandene DeepEval-Metriken in die Kontrollschicht einbinden.

Prompt Alignment für einzelne Anweisungen

Task Completion für Aufgabenerfüllung

Projektentscheidungen als relevante Prüfgrundlage bereitstellen

Prüfergebnisse mit Gründen und Einzelbefunden speichern

Ergebnis: Ein prüfbarer Fehlerbericht pro bearbeiteter Aufgabe

## 04

Automatische Antwortkorrektur

Kernfunktion

Guardrails erhält Prüfergebnisse und koordiniert eine gezielte Überarbeitung.

Fehlschläge eindeutig klassifizieren

Nur die beanstandeten Punkte zur Korrektur zurückgeben

Maximal zwei Korrekturversuche konfigurieren

Bei ausbleibendem Erfolg den Fehler offen melden, nicht freigeben

Ergebnis: Funktionierende, begrenzte Korrekturschleife

## 05

Recherche- und Entscheidungskontrolle

Erweiterung

Technische Empfehlungen auf relevante Fakten und widersprüchliche Projektvorgaben prüfen.

Quellen und bekannte Entscheidungen einbeziehen

Fehlende Belege erkennbar machen

Bereits ausgeschlossene Ansätze kennzeichnen

Recherchebedarf von notwendigem Gerätetest unterscheiden

Ergebnis: Nachvollziehbare technische Empfehlungen mit erkennbaren Konflikten

## 06

Coding- und Abschlusskontrolle

Erweiterung

Für Entwicklungsaufträge prüfen, ob die verlangten Änderungen tatsächlich vorliegen.

Vorhandene Dateien und Änderungen berücksichtigen

Linter, Compiler oder bestehende Projekttests bei Bedarf anbinden

Abschlussmeldungen gegen reale Ergebnisse prüfen

Nur belegte Arbeitsschritte als erledigt markieren

Ergebnis: Weniger unbelegte Fertigmeldungen

## 07

Promptfoo-Regressionen

Qualitätssicherung

Reale wiederkehrende Fehlertypen in reproduzierbare Prüffälle übersetzen.

Bereits dokumentierte Fehlertypen verwenden

Deterministische Prüfungen vor Modell-Judge-Prüfungen bevorzugen

Fehlerfälle als kleine Testsammlung hinterlegen

Nach Änderungen nur betroffene Prüfgruppen ausführen

Ergebnis: Regressionserkennung ohne laufende Testorgien

## 08

Einbindung und Betrieb

Abschluss

Die Prüf- und Korrekturschicht mit einem tatsächlich verwendeten Assistenten verbinden.

Antworten verbindlich durch die Prüfschicht leiten

Lade- und RAM-Verhalten kontrollieren

Fehlerprotokoll und nachvollziehbare Berichte bereitstellen

Betriebs- und Wiederherstellungsanleitung abschließen

Ergebnis: Nutzbarer lokaler Kontrollablauf statt einzelner Demo-Skripte

## 5. Wichtige technische Entscheidungen vor der Umsetzung

Aus der Dokumentation ergeben sich vier Punkte, die wir bereits jetzt festlegen können.

### A. Kein zusätzliches großes Prüfermodell als Voraussetzung

DeepEval unterstützt eigene Bewertungsmodelle, und Promptfoo kann lokale beziehungsweise OpenAI-kompatible Modellserver verwenden.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://deepeval.com\&sz=32)

DeepEval - The LLM Evaluation Framework

+1



Wir verwenden möglichst zunächst ein vorhandenes Modell und laden die Modelle nacheinander, wenn RAM oder VRAM knapp wird.

Offener Punkt: Ob eines deiner vorhandenen Modelle als zuverlässiger Judge geeignet ist, ist noch nicht belegt. Deshalb wird kein weiteres Modell fest eingeplant.

### B. DeepEval nicht für jeden einfachen Fehler aufrufen

Für eindeutige Anforderungen – etwa fehlende Dateien, ungültige Formate oder nicht vorhandene Abschlussnachweise – ist normaler Programmcode ausreichend.

DeepEval übernimmt vor allem die schwerer zu beurteilenden Fälle: Anweisungstreue, semantische Widersprüche und Aufgabenerfüllung. Die offizielle Dokumentation bestätigt dafür Prompt Alignment und Task Completion. Letzteres kann auch vollständige Agentenabläufe berücksichtigen, benötigt dafür aber passende Ausführungsdaten.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://deepeval.com\&sz=32)

DeepEval - The LLM Evaluation Framework

+1



### C. Promptfoo nicht als vierten laufenden KI-Agenten betreiben

Promptfoo unterstützt deterministische Prüfungen und lokale Bewertungsmodelle.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://www.promptfoo.dev\&sz=32)

Promptfoo

+1



Wir nutzen es hauptsächlich nach Änderungen, um festzustellen, ob zuvor erkannte Fehler wieder auftreten.

### D. Die echte Integration ist ein eigener Arbeitsschritt

Die drei Programme allein bilden noch keine fertige Kontrollinstanz. Wir benötigen eine schlanke Steuerung, die Prüfergebnisse übergibt, Korrekturen auslöst und entscheidet, wann ein Ergebnis freigegeben werden darf.

Dafür ist ein kleiner Python-Dienst naheliegend. Keine zusätzliche große Agentenarchitektur.

## 6. Abnahmekriterien

Damit wir nicht wieder bei einer schönen Architekturzeichnung stehen bleiben, bekommt jede Kernfunktion ein überprüfbares Ergebnis.

Abnahme-Checkliste

0 / 8

Installation

DeepEval und Promptfoo sind erreichbar; Guardrails funktioniert weiter.

Anweisungstreue

Eine absichtlich verletzte, ausdrücklich hinterlegte Vorgabe wird erkannt.

Entscheidungskonsistenz

Ein klarer Widerspruch zu einer bereitgestellten Entscheidung wird zurückgewiesen.

Korrektur

Ein erkannter Fehler führt automatisch zu einer gezielten Überarbeitung.

Schleifenbegrenzung

Nach maximal zwei Korrekturversuchen wird ein Fehlschlag gemeldet.

Aufgabenerfüllung

Ein unbelegter Fertigstatus wird nicht als erfolgreicher Abschluss akzeptiert.

Regression

Promptfoo kann frühere dokumentierte Fehlertypen erneut prüfen.

Lokaler Betrieb

Alle erforderlichen Modellaufrufe bleiben lokal; keine kostenpflichtige API wird benötigt.

&#x20;Checkliste kopierenDie Punkte sind zunächst nicht abgenommen. Sie werden erst nach tatsächlicher Umsetzung und erfolgreicher Prüfung markiert.

## 7. Geplante Projektstruktur

Die Kontrollinstanz sollte eigenständig bleiben und nicht fest in Forge eingebaut werden, damit sie später auch für andere Assistenten verwendet werden kann.

```
AI-Reliability/
│
├── config/
│   ├── settings.yaml
│   └── validation_rules.yaml
│
├── core/
│   ├── orchestrator.py
│   ├── model_client.py
│   └── correction_loop.py
│
├── validators/
│   ├── guardrails_adapter.py
│   └── deepeval_adapter.py
│
├── knowledge/
│   └── project_constraints.json
│
├── promptfoo/
│   ├── promptfooconfig.yaml
│   └── cases/
│
├── reports/
├── logs/
├── tests/
├── requirements.txt
└── README.md
```

Vorgeschlagene Struktur, noch keine erstellten Dateien. Der endgültige Laufwerksordner wird mit der vorhandenen Projektumgebung abgestimmt.

## 8. Reihenfolge und Prioritäten

P1

Guardrails + DeepEval + automatische Korrektur

Das ist die erste funktionsfähige Ausbaustufe. Sie muss stehen, bevor wir weitere Prüfmechanismen ergänzen.

P2

Promptfoo + Entscheidungskonsistenz

Bekannte Fehler werden als Regressionen erfasst. Entscheidungen werden gegen relevante Anforderungen abgeglichen.

P3

Coding-Kontrolle + Integration weiterer Assistenten

Erst hier erweitern wir den Dienst um tiefere Projektprüfungen und zusätzliche Schnittstellen.

## 9. Fertiges Zielbild

Die erste nutzbare Version soll einen einfachen, aber vollständigen Ablauf beherrschen:

Ein Assistent bekommt einen Auftrag, erzeugt eine Antwort oder Änderung, die Kontrollinstanz prüft das Ergebnis anhand relevanter Anforderungen, veranlasst bei Bedarf eine Korrektur und gibt ein akzeptiertes Ergebnis oder einen konkreten Fehlerbericht zurück.

Nicht Teil der ersten Version sind eine neue Modellverwaltung, zusätzliche Supervisor-Agenten, eine eigene Benutzeroberfläche oder weitere Modell-Downloads.

Damit bleibt der Arbeitsplan auf das eigentliche Ziel konzentriert: mehr Zuverlässigkeit durch tatsächlich ausgeführte Kontrolle und Korrektur, nicht durch weitere Erklärungen.

Die Recherchegrundlagen sind die offiziellen Dokumentationen von [Guardrails AI](https://guardrailsai.com/?utm_source=chatgpt.com), [DeepEval](https://deepeval.com/docs/metrics-prompt-alignment?utm_source=chatgpt.com) und [Promptfoo](https://www.promptfoo.dev/docs/getting-started/?utm_source=chatgpt.com). Die Umsetzung ist bereits als Work-Auftrag übergeben; dieser Plan beschreibt die vollständigen Arbeitsphasen und die Kriterien, anhand derer das fertige System beurteilt werden soll.