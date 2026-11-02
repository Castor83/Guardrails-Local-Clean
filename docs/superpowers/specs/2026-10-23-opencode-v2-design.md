# Desktop V2: enger Ollama-Anschluss

Ergänzung zum autorisierten OpenCode-Auftrag und V1-Entwurf. Die tatsächliche
Desktop-Version 2.1.4 wurde erst bei Betriebsvorbereitung erkannt; npm1.19.4
ist eine andere Installation. Deshalb V2-Anschluss ergänzen, keine neue
allgemeine Freigaberunde und kein ungefragter Providerwechsel.

Entscheidung: deterministischen V1-Prüfbaustein über einen kleinen V2-Adapter
weiterverwenden. V2-default{id,setup} ohne zusätzliche Laufzeitpakete. Kontext
ergänzen, echte User-ID im Modellkontext gegen das unmittelbar von
ctx.session.context() gelieferte Array mit type:user prüfen. Korrektur vom
24.10.2026: Die frühere Annahme `.data` verwechselte den HTTP-Endpunkt mit dem
Promise-SDK; siehe docs/OPENCODE-BINDING-REPARATUR-2026-10-24.md.
Taskbindung pro tatsächlichem Request unveränderlich halten.
Kein Bindungswechsel durch bloßen Prompt-Eingang oder synthetischen role:user.

Nur primäre Ollama-HTTP-Aufrufe an expliziten numerischen Loopback-Endpunkt.
http.request und http.response besitzen dieselbe finale Request-Objektidentität.
Antwort vollständig begrenzt puffern, OpenAI-Chat-SSE oder JSON prüfen,
sichtbares content/refusal gemeinsam kontrollieren und vor dem Parser
zurückgeben. Bei Fehler/Abbruch/Übergröße keine ungeprüfte Originalantwort.
Toolaufrufe, Reasoning, Nutzungswerte und Abschlussdaten strukturell erhalten.
Keine allgemeine Protokollunterstützung, kein WebSocketanschluss.

Echte ausgegebene Call-ID, Werkzeugname und Argumente aus der geprüften
Antwort an den Task binden. Native before/after-Ereignisse mit sessionID,
messageID,id,input müssen dazu passen. Status error erzeugt keinen
Erfolgsbeleg. V2 besitzt kein natives parentID: ein internes V1-Kompatibilitäts-
Envelope ist abgeleitete Normalisierung aus diesen Fakten, kein vorgetäuschtes
persistiertes Feld. Nur begrenzter flüchtiger Speicher, keine Rohprotokolle.

Abnahme: neue Node-Regressionssuite mit echten Request/Response/ReadableStream-
Objekten und SDK-/Hook-Fixtures. Fragmentierte UTF-8/SSE-Deltas, refusal,
Taskwechsel, Fehler, Zeit-/Bytegrenze, Abbruch und erlaubte Erfolgsbelege.
Unabhängiges Review, wichtige Fehler per Regression korrigieren, Commit und
laufenden Übergabestand aktualisieren. Native Desktop-/Modellprobe bleibt
separat UNVERIFIED bis zum tatsächlich genehmigten und ausgeführten Versuch.

Quelle der HTTP-Grenze:
https://raw.githubusercontent.com/anomalyco/opencode/v2.1.4/packages/core/src/session/model-request.ts
