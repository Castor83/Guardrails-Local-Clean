# Gesprächsprofile und tatsächliche Werkzeugbelege

Der Originalauftrag bleibt maßgeblich: Eine eigene Vermutung darf nicht als
erfolgreiche Suche oder verifizierter Chattitel ausgegeben werden. Eine bloße
Selbstauskunft des Assistenten ist dafür kein Ausführungsbeleg.

## Belegprüfung

`action_evidence.py` speichert begrenzte Ergebnisse nativer `PostToolUse`-
Ereignisse mit Sitzung, Turn, Werkzeugaufruf-ID und Inhalts-Hashes. Nur passende
erfolgreiche Chatwerkzeuge können erkannte Suchbehauptungen und tatsächlich
enthaltene Chattitel belegen. Eine Zusammenfassung, ein Projekttitel, ein
Shell-Ausdruck mit selbst gedrucktem JSON oder ein Ergebnis eines anderen
Turns ersetzt diesen Beleg nicht.

Die Belegprüfung läuft unabhängig vom Modellcache. Ein neuer echter Beleg kann
eine zuvor unbelegte Aussage stützen, ohne den Critic erneut aufzurufen. Der
kombinierte Bericht verlinkt Basisprüfung und Belegprüfung getrennt. Erkannte
Verstöße können höchstens zwei Korrekturen auslösen; identische Wiederholungen
starten keine unbegrenzte Schleife.

Grenzen: Die Erkennung erfasst ausgewiesene deutsche Formulierungen, keine
beliebige Sprache oder allgemeine Wahrheit. Unvollständig erfasste Ergebnisse
bleiben UNVERIFIED. Die Hashes authentisieren keinen Ereignisabsender gegenüber
anderen Prozessen desselben Benutzers. Der Host muss die tatsächlichen
Ereignisse liefern. Hosted-Websuche wird laut offizieller Hook-Dokumentation
nicht über diesen Ereignispfad erfasst. Stop kann nach Anzeige einer Antwort
laufen; es ist keine garantierte Sperre vor der Anzeige.

## Passende Zusatzregeln

| Profil | Zweck und Grenze |
| --- | --- |
| Gespräch | Kein pauschaler Modellaufruf und kein vorgeschriebener Arbeitsstatus; Belegpflicht für erkannte Suchbehauptungen bleibt. |
| Erklärung | Ausdrücklich vorgegebene Form- und Längengrenzen prüfen; keine allgemeine Wahrheitsfreigabe. |
| Recherche | Quellenfelder und HTTP-/HTTPS-URL-Syntax prüfen; Erreichbarkeit und Wahrheit bleiben ungeprüft. |
| Empfehlung | Kriterien, höchstens drei Optionen, Entscheidung und Begründung als strukturierte Angaben prüfen; keine Eignungsfreigabe. |
| Code/Projekt | Bestehenden auftragsgebundenen Workflow und Abschlussbelege nutzen; kein Modellkatalog für beliebigen Code. |
| Quellenprüfung | Explizite vollständige Quelle an den NLI-Prüfpfad binden; keine stille Kürzung und keine allgemeine Qualitätsfreigabe. |

Die sechs Profile lassen sich über die erste Auftragszeile explizit auswählen:
`Profil: Gespräch`, `Profil: Erklärung`, `Profil: Recherche`,
`Profil: Empfehlung`, `Profil: Code`, `Profil: Quellenprüfung`.
Daneben erkennt der Router begrenzte konkrete Auftragsverben.
`Guardrails: Projekt` und `Guardrails: Modelle` bleiben explizite Fachbereiche.

Die kleinen nativen Guardrails-Bausteine ValidLength und ValidURL liegen mit
festen Wheel- und Modul-Hashes unter `work/profile-components/`. Sie verändern
keine Pakete der Steuerumgebung. Ihre erfolgreiche Formprüfung ist kein
Nachweis einer tatsächlichen Suche und keine semantische Freigabe.

## Einrichtung und tatsächlicher Betriebsstatus

`configure-codex.py --action-evidence` ergänzt optional einen `PostToolUse`-Handler.
Der Einrichtungspfad registriert und aktiviert zugleich die angegebene Sitzung;
er darf deshalb nicht bloß zur Handlerergänzung gegen eine vom Betreiber
deaktivierte Sitzung ausgeführt werden. Neue Hookdefinitionen benötigen
ausdrückliches Vertrauen im Host; die Einrichtung setzt dieses Vertrauen nicht.

Stand der Reparatur: Die aktuelle Hauptsitzung
`01a146ea-9298-7c13-b7ad-0d52596649f0` bleibt aus den beiden Freigabelisten
entfernt, `critic_enabled` bleibt false. Der echte globale Hook wurde in dieser
Reparatur nicht um `PostToolUse` erweitert. Temporäre Vertragstests beweisen
die implementierte Logik, keinen vertrauenswürdigen nativen Gesamtdurchlauf.
Das Projektziel bleibt NOT_ACCEPTED. NLI-/DeepEval-Installation und echte
Modellfunktionstests sind getrennte Nachweise; siehe `LOCAL-EVALS.md`.
Der zusätzliche explizite DeepEval-/Guardrails-Prüfpfad und die tatsächlichen
Promptfoo-Regressionen sind in `QUALITY-STACK.md` beschrieben.

## Lokales Codex-Projekt

Für die Entwicklung kann der vorhandene Ordner `E:\Guardrails-Local` als
lokales Projekt und Hauptordner verwendet werden. Ein physischer Dateiumzug
ist dafür nicht nötig. Der bisherige Chatverlauf wird nicht automatisch zum
vollständigen Kontext eines neuen Chats; Originalauftrag, Entscheidungen und
Arbeitsstand müssen gezielt mitgegeben werden. Ein Projektwechsel behebt
keine fehlende Belegprüfung. Der vorhandene Chat wurde am 18.10.2026 tatsächlich
dem lokalen Codex-Projekt Guardrails-Local mit Arbeitsordner E:\Guardrails-Local
zugeordnet. Beleg: `work/codex-project-transfer/verification.json`. Die
Sitzungsfreigaben und der abgeschaltete Critic wurden dabei erhalten.

Primärquellen:

- https://learn.chatgpt.com/docs/hooks
- https://learn.chatgpt.com/docs/projects?surface=app
