# Guardrails Local in einem Codex-Chat

## Zweck und Grenze

Der Anschluss verwendet die vorhandene lokale Qualitätskontrolle. Ein
`UserPromptSubmit`-Hook bindet den tatsächlichen Benutzerauftrag und fordert
eine Vorprüfung des vollständigen Antwortentwurfs an. Ein synchroner `Stop`-Hook
prüft die abschließende Antwort automatisch nach. Beides gilt nur für die
ausdrücklich eingetragenen Sitzungs-IDs.

Das ist keine Änderung des internen Codex-Modells und keine garantierte Sperre
vor der Anzeige. Codex kann die Antwort bereits während ihrer Erzeugung
anzeigen. Ein `Stop`-Hook kann eine begrenzte Fortsetzung anstoßen, aber die
bereits sichtbare Antwort nicht zurücknehmen. `suppressOutput` ist laut
[OpenAI-Hook-Dokumentation](https://learn.chatgpt.com/docs/hooks) noch nicht
implementiert. Ein Hookfehler bildet ebenfalls keine externe Anzeigesperre.

## Einrichtung

Vorhandene Umgebung verwenden; keine Installation erforderlich:

```powershell
& 'C:\Users\REDACTED_USER\.venv\Scripts\python.exe' 'E:\Guardrails-Local\configure-codex.py' --session-id '<SITZUNGS-UUID>' --critic
```

`--critic` aktiviert den ausdrücklich freigegebenen lokalen Critic.
`--offline` verwendet ausschließlich die festen Hostprüfungen. Beide Varianten
erhalten die vorhandenen Regeln, Fakten und die Herkunft `chatgpt`.

Die Einrichtung sichert die bisherigen Bytes von `C:\Users\REDACTED_USER\.codex\hooks.json`
unter `work/codex/backups/` und ergänzt zwei Handler. Vorhandene Handler,
insbesondere der `SessionStart`-Hook für die Chatübergabe, bleiben erhalten.
Wiederholte Einrichtung dupliziert keine Handler. Die lokale Aktivierung und
Sitzungsliste stehen im ignorierten `work/codex/config.json`.

Neue Hookdefinitionen benötigen Codex-Vertrauen für ihren aktuellen Hash.
Einrichtung und tatsächliche Freigabe sind getrennte Zustände. Die
interaktive Codex-CLI bietet dafür `/hooks`; der Anschluss verändert selbst
keine Vertrauensdaten und verwendet keine Umgehungsoption. Zur Prüfung liefert
die dokumentierte lesende Schnittstelle `hooks/list` unter anderem `enabled`
und `trustStatus`. Die Erkennung eines Handlers allein beweist keine Ausführung.

## Vorprüfung einer Antwort

Auftrag und vollständigen Antwortentwurf als lokale UTF-8-Dateien bereitstellen:

```powershell
& 'C:\Users\REDACTED_USER\.venv\Scripts\python.exe' 'E:\Guardrails-Local\codex-hook.py' --precheck '<ANTWORTDATEI>' --session-id '<SITZUNGS-UUID>' --task-file '<AUFTRAGSDATEI>'
```

Der später ausgegebene Text muss diesem Entwurf exakt entsprechen. Die
Vorprüfung und die Nachprüfung desselben Textes verwenden denselben gespeicherten
Bericht, soweit Auftrag, Regeln, Katalog und Modelleinstellungen gleich sind.
Damit führt der `Stop`-Hook keine zweite Inferenz nur für denselben Entwurf aus.

Ein `UserPromptSubmit` bindet einen neuen Benutzerauftrag. Der aktuelle Adapter
erzeugt keine automatischen Korrekturprompts über `Stop`: Ihre Herkunft wäre beim
Folgeereignis nicht eindeutig belegt. Ein fehlender, zu großer oder ungültiger
Auftrag wird nicht still gekürzt oder aus einem instabilen Transkriptformat
rekonstruiert.

## Prüfstatus und begrenzte Fortsetzungen

- `PASS`: Nur ein vollständiger Bericht darf Text freigeben.
- `FAIL`: Keine Freigabe und keine native automatische Fortsetzung. Belegte
  Verstöße bleiben sichtbar; direkte lokale Pipelinekorrekturen sind weiterhin
  auf höchstens zwei begrenzt.
- `UNVERIFIED`: Keine vollständige Freigabe und keine automatische
  Umschreibeschleife. Auch eine leere finale Antwort liefert `continue: false`;
  damit verhindert der Adapter Fortsetzungsanforderungen anderer Stop-Hooks.
- `ERROR`: Keine Freigabe und kein automatischer Transportwiederholungsversuch.
- `ESCALATED`: Das Prüf- oder Korrekturbudget ist ausgeschöpft; keine weitere
  automatische Fortsetzung.

`continue: false` bezieht sich auf die Stop-Fortsetzung des betroffenen Turns.
Neue ausdrückliche Benutzernachrichten werden weiterhin angenommen und neu
gebunden. Ein noch ausstehender mehrdeutiger Legacy-Replay bleibt gesondert
gesperrt; diese Einschränkung ist kein allgemeiner Gesprächsstopp.

Die vorhandene Prüfung ist auf belegbare lokale Modell- und API-Empfehlungen
begrenzt. Beliebige Prosa wird dadurch nicht fachlich verifiziert. Außerdem
bleibt bei `source=chatgpt` die Unabhängigkeit der Erzeugerfamilie absichtlich
`UNVERIFIED`. Ein zustimmender Critic hebt diese Grenze nicht auf. Der Anschluss
erfindet keine neue Herkunft wie `codex`, um diese Regel zu umgehen.

Korrekturhinweise des Critics werden nicht als neue Benutzerbefehle übernommen.
Codex soll tatsächliche Belege prüfen; zusätzliche Installationen, Downloads,
Providerwechsel und Eingriffe in fremde Projekte werden dadurch nicht erlaubt.

## Vorbereitetes PostToolUse-Feedback, standardmäßig aus

Der Offline-Anschluss `precheck_feedback.py` ergänzt einen lokalen dauerhaften
Beleg für ausdrücklich freigegebene Feedbacksitzungen. Seine eigene optionale
Liste `precheck_feedback_session_ids` ist ohne Eintrag leer; die vorhandene
Betreiberkonfiguration wurde dafür nicht verändert. Workflowrechte,
Aktionsbelegfreigaben und Critic-Aktivierung werden dadurch nicht übernommen.

Im vorbereiteten Weg benötigt der genaue Vorprüfaufruf zusätzlich die passende
`--turn-id` und die gespeicherte Originalauftragsdatei. Ein lokales Ledger bindet
Auftrag, Antwort, Regeln und Rechte. Höchstens drei feedbackverwaltete
Vorprüfungen und zwei vor Ausgabe reservierte Korrekturen pro Task; Duplikate
erzeugen kein weiteres Feedback. Ein Absturz kann eine reservierte Ausgabe
verlieren, löst aber keine erneute automatische Zustellung aus.

Nur ein gespeicherter FAIL mit belegtem Hostverstoß kann begrenzten Zusatzkontext
im laufenden Turn erzeugen. Critic-only FAIL, ERROR, UNVERIFIED und SKIPPED
erzeugen keine Korrektur. Stop bleibt separate Nachkontrolle ohne Reinjektion;
das Ledger ist keine globale Aufrufgrenze für alle manuellen Prüfwege.
Neue echte Nutzerbeiträge werden weiterhin neu gebunden; ein mehrdeutiger
Legacy-Zustand wird weder gelöscht noch still migriert.

Die erste enge Offline-Ergebnisform erwartet beim kanonischen Werkzeugnamen
`Bash` ein Objekt mit `stdout` und `exit_code`. Andere native Formen schließen
diesen Feedbackablauf als UNVERIFIED. Das ist keine bestätigte Beschreibung des
lokalen Hosttransports. Feedback verwendet den dokumentierten
[PostToolUse-Zusatzkontext](https://learn.chatgpt.com/docs/hooks#posttooluse),
ohne neue Nutzerautorität oder Werkzeugrechte zu erzeugen.

Native Ereignisform, Kontextzustellung, Modellbefolgung und Rückweg benötigen
einen getrennt freizugebenden synthetischen Hosttest. Produktive Aktivierung ist
nicht freigegeben. Lokale Hashes sind keine Isolation gegen denselben Benutzer.
Aktuelle Konfiguration wird an Prüfpunkten erneut gelesen; zwischen Ereignissen
spurlos widerrufene und identisch wiederhergestellte Freigaben lassen sich daraus
nicht historisch rekonstruieren. Für solche Betreiberwechsel fehlt ein separat
nachgewiesenes dauerhaftes Widerrufsregister.

Entwurf und Offline-Abnahmeumfang:
`docs/superpowers/specs/2026-10-23-precheck-feedback-design.md`.

## Modell, Zeit und Datenschutz

Der Critic verwendet unverändert `config/settings.json`: ausschließlich das
vorhandene `huihui_ai/gpt-oss-abliterated:20b-mxfp4` mit festem Digest,
`num_ctx=4096`, `num_predict=1200`, `think=low`, `keep_alive=0`. Ein fremdes
geladenes Ollama-Modell blockiert den Aufruf und wird nicht entladen. Der
Anschluss lädt keine neuen Modelldateien und richtet keine Cloud-Inferenz ein.

Ein eigener Worker begrenzt die Wartezeit der lokalen Prüfoperation auf 180
Sekunden; der Codex-Handler hat etwas zusätzlichen Spielraum zum Protokollieren.
Ein abgebrochener Client ist keine Garantie, dass Ollama eine bereits laufende
GPU-Berechnung augenblicklich beendet. Es gibt keine allgemeine Betriebssystem-
Sandbox und keine atomare Sperre des Ollama-Servers.

Die Eingabegrenze des bestehenden Critics bleibt 8500 UTF-8-Bytes einschließlich
Systemtext, Regeln, Katalog, Auftrag und Antwort. Das ist keine Tokenzählung.
Größere Antworten erhalten einen Fehler, keine verkürzte Scheinprüfung.

Aufträge, Antworttexte und Befunde werden lokal im Klartext unter `logs/` und
`work/codex/` gespeichert. Diese Verzeichnisse sind vom Git-Upload ausgeschlossen.
Andere Chats werden ohne Eintrag ihrer Sitzungs-ID nicht geprüft und lösen
keinen Critic-Aufruf aus.

## Chatübergabe und Abschalten

Bei einem Nachfolgechat muss dessen neue Sitzungs-ID ausdrücklich in die lokale
Sitzungsliste aufgenommen werden, etwa durch denselben Einrichtungsbefehl mit
der neuen ID. Die vollständige Chatübergabe soll dieses Verfahren und den
aktuellen Prüfstatus enthalten. Der vorhandene Komprimierungs-Hook wird nicht
durch die Guardrails-Anbindung ersetzt.

Zum Abschalten dieses Anschlusses `enabled` in `work/codex/config.json` auf
`false` setzen. Der allgemeine Chatübergabe-Hook bleibt davon unabhängig.

## Nachweise

## Ergänzung: Arbeitsaktionen und strukturierter Abschluss

Der neue Modus ist ausdrücklich je Sitzung wählbar:

Die lokalen Guardrails-Validatoren heißen `InstructionCompliance`,
`DecisionConsistency` und `CompletionEvidence`. Sie werden mit der vorhandenen
Guardrails-Installation tatsächlich ausgeführt, ohne ein neues Modell zu laden.
InstructionCompliance prüft die exakte Auftrags-/Quellenbindung und den
verpflichtenden strukturierten Arbeitsstatus. DecisionConsistency prüft die
feste Aktionspolicy sowie die vorhandenen Modell-/API-Entscheidungsregeln.
CompletionEvidence prüft den echten CPU-Abschlussbeleg. Allgemeines semantisches
Auftragsverständnis und beliebige Entscheidungen aus früheren Gesprächen sind
damit ausdrücklich nicht vollständig validiert.

Provenance NLI ist als UNVERIFIED/nicht eingerichtet ausgewiesen. Im benutzten
Python fehlen das Plugin, Torch und Transformers. Die offizielle
[Hub-Dokumentation](https://guardrailsai.com/hub/validator/guardrails/provenance_nli)
fordert zusätzliche Pakete und einen Modell-Download. Es wurde nichts davon
installiert oder geladen. Die bestehende strikte JSON-/Pydantic-Prüfung braucht
hierfür keinen zusätzlichen Valid-JSON-Hub-Download.

```powershell
& 'C:\Users\REDACTED_USER\.venv\Scripts\python.exe' 'E:\Guardrails-Local\configure-codex.py' --session-id '<SITZUNGS-UUID>' --critic --workflow
```

Er ergänzt `workflow_session_ids`; andere registrierte Chats erhalten dadurch
keinen neuen Modus. Die vorhandenen UserPromptSubmit-, Stop- und Compact-
Definitionen bleiben erhalten. Der zusätzliche synchrone PreToolUse-Handler
mit Matcher `^(Bash|apply_patch)$` benötigt separat Vertrauen in Codex.

`config/workflow-policy.json` bindet feste operatorseitige Entscheidungen an
den SHA256 des unveränderten Originalauftrags. Jeder tatsächliche Auftrag
erhält `workflow-contract.json` mit Aufgaben-, Policy- und Quellenbindung.
Dies ist eine kuratierte Regelmenge, keine automatische Erfassung sämtlicher
früheren Gespräche oder ein Beweis allgemeiner Widerspruchsfreiheit.

Der PreToolUse-Handler erlaubt einfache lokale Leseaufrufe ausschließlich in
der Form `Get-Content|Get-Item|Test-Path|Get-ChildItem -LiteralPath '<absoluter Pfad>'`.
Weitere erlaubte Shell-Aufrufe sind der feste Workflow-Runner und die exakte
bestehende Vorprüfung mit gebundenem Auftrag. Unbekannte oder zusammengesetzte
Shellbefehle bleiben gesperrt. Dateiänderungen durch apply_patch sind auf das
Arbeitsrepository begrenzt; Originalauftrag, config/ und work/codex/ sind
geschützt. Löschen und Verschieben sind nicht freigegeben. Unterstützte
Aufrufe werden vor einer Freigabe dauerhaft protokolliert; bei Prüf- oder
Auditfehlern lautet die Werkzeugentscheidung ausdrücklich `deny`.

Der feste Runner startet nur die vorhandene CPU-Testsuite:

```powershell
& 'C:\Users\REDACTED_USER\.venv\Scripts\python.exe' 'E:\Guardrails-Local\workflow-check.py' --session-id '<SITZUNGS-UUID>' --inspect
& 'C:\Users\REDACTED_USER\.venv\Scripts\python.exe' 'E:\Guardrails-Local\workflow-check.py' --session-id '<SITZUNGS-UUID>' --run-tests
```

Er akzeptiert keine freien Kommandos und ruft kein Modell auf. Das Ergebnis
enthält Exitcode, Mindesttestzahl, tatsächliche Ausgabe und Hash sowie den
Dateistand vor/nach dem Lauf. Wiederholung desselben Dateistands verwendet
das gespeicherte Ergebnis; ein unterbrochener reservierter Lauf bleibt ERROR.

Finale Antworten beginnen im Workflow-Modus mit `Arbeitsstatus: OFFEN` oder
`Arbeitsstatus: ABGESCHLOSSEN`. Nur die zweite Deklaration verlangt einen
erfolgreichen, weiterhin aktuellen Runner-Beleg für dieselbe Aufgabe und
dieselben Regeln. Fehlende/alte Belege ergeben FAIL; die native automatische
Korrektur bleibt ausgesetzt. Ohne strukturierte Deklaration bleibt dieser
Prüfbereich UNVERIFIED; beliebige Prosa wird dadurch nicht semantisch erfasst.

Wichtig: Dieser Ausbau deckt die genannten Werkzeugpfade und die feste Suite
ab. Andere Werkzeuge, nicht erfasste Abschlussbehauptungen und zusätzliche
fachliche Abnahmekriterien bleiben außerhalb dieses Belegs. Es gibt keine
OS-Sandbox, keine garantierte Anzeigesperre und keinen Schutz gegen gezielte
Selbständerung des Prüfcodes durch einen Prozess mit denselben Dateirechten.
Die allgemeine Qualität des bestehenden Critics bleibt gesondert offen.

## Critic-Befunde an die tatsächliche Antwort binden

Der Modellkatalog ist Referenzwissen und keine Liste tatsächlich ausgewählter
Modelle. Der Critic-Prompt benennt diesen Unterschied ausdrücklich. Das Feld
`evidence` eines Befundes verlangt ein wortgetreues Zitat aus dem vollständigen
Antworttext. Für LOCAL_ONLY, NO_PAID_API, ABLITERATED und HARDWARE muss es außerdem
genau dem Beleg einer durch die bestehende konservative Texterkennung erkannten
Modellauswahl entsprechen. Vom Aufrufer gelieferte `recommendations` werden dafür
nicht als unabhängiger Nachweis vertraut, sondern aus `draft.text` neu ermittelt.

Ein ausschließlich so nicht gebundener Modell-FAIL wird als UNVERIFIED behandelt,
niemals als PASS. Die unveränderte Modellantwort bleibt in `critic.response`
erhalten. Die wirksamen ungebundenen Hinweise werden als Warnungen gekennzeichnet;
`evidence_binding.checks` protokolliert den Grund je Befund. Eine gebundene
Verletzung bleibt neben weiteren ungebundenen Hinweisen FAIL. Ein ursprüngliches
UNVERIFIED wird durch diese Prüfung nicht hochgestuft. Bereits vorhandene
deterministische Ablehnungen bleiben unverändert wirksam.

Diese mechanische Bindung beweist nicht, dass eine semantische Behauptung aus dem
zitierten Text folgt. Nicht von der Texterkennung erfasste Formulierungen bleiben
UNVERIFIED; allgemeine Critic-Zuverlässigkeit und Gesamtfreigabe sind weiterhin
gesondert offen. Es werden weder Katalogfakten noch Anforderungen umdeklariert.
Der Adapter bindet gespeicherte Prüfungen zusätzlich an den SHA256 des tatsächlich
verwendeten Critic-Quellcodes und verweigert einen fehlenden Quellnachweis. Nach
Codeänderungen wird daher kein alter Antwortbericht als aktuelle Prüfung verwendet.

Die reproduzierbaren Adaptertests verwenden kontrollierte Worker, keine
Modell-Inferenz. Ein separater echter Aufruf und eine tatsächlich durch die
App ausgelöste Hookausführung sind unterschiedliche Nachweise. Der aktuelle
Einrichtungs- und Abnahmestand wird im lokalen Arbeitsbericht festgehalten;
ein erfolgreicher Einzelaufruf ist keine allgemeine Qualitätsabnahme.
# Aktueller Reparaturstand 20.10.2026

Die Gesprächsvorprüfung führt das gebundene Profil einschließlich expliziter
Zeichengrenzen und danach die sitzungsweise freigegebene Aktionsbelegprüfung
aus. Ein erfolgreicher Aktionsbeleg gibt ein ungeprüftes Rechercheprofil nicht
allgemein frei. Statuspriorität: ERROR, FAIL, UNVERIFIED, PASS; SKIPPED liefert
keinen positiven Prüfnachweis. Kein NLI-/Modellaufruf erfolgt dadurch.

Ältere Beschreibungen nativer automatischer Stop-Korrekturen sind historisch:
Der Reparaturstand erzeugt keine automatischen neuen Prompts
aus `Stop`. Die [offizielle Hook-Dokumentation](https://learn.chatgpt.com/docs/hooks)
beschreibt `UserPromptSubmit` mit `prompt` und `turn_id`; ein eindeutiges
Herkunftsfeld für automatisch eingespeiste Fortsetzungen ist dort nicht
garantiert. Gleichheit eines Texthashes beweist diese Herkunft nicht.

Ein neuer Benutzerturn erhält einen neuen Auftrag und übernimmt keine alten
Rechte aus seinem Text. Passt ein Ereignis zu einer noch ausstehenden alten
automatischen Korrektur, bleibt seine Herkunft mehrdeutig: kein Übernehmen von
Autorität, kein Zurücksetzen des Budgets und keine automatische Fortsetzung.
Ein echter Benutzer-Copy und ein alter automatischer Replay mit identischem
Payload lassen sich in diesem Fall nicht unterscheiden; dieser Integrations-
punkt bleibt offen. Beendete alte Aufgaben dürfen neue Eingaben nicht aufgrund
eines historischen Texthashes vereinnahmen.

Die direkte lokale Pipeline behält ihr Limit von höchstens zwei Korrekturen.
Native automatische Korrektur und eine Sperre vor der Anzeige sind weiterhin
nicht abgenommen. Diese Quellcodeänderung aktiviert keinen globalen Hook,
keine Sitzung, keinen Critic und kein Host-Vertrauen.
