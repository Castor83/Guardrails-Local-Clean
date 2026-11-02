# OpenCode: lokaler Body-Aufzeichnungsproxy

Zweck: Bei einem künftig separat freigegebenen Lauf die tatsächlich vom lokalen
Upstream gesendeten HTTP-Bodybytes vor der Guardinterpretation sichern. Der Proxy
behebt und rekonstruiert den historischen leeren Modellabschluss nicht.

## Betrieb und Freigabegrenze

Eigenständiges Node-Modul `tools/opencode/recording-proxy.mjs`, keine Zusatzpakete.
Import startet nichts. Auch der manuelle Start kontaktiert den Upstream nicht;
erst eine erlaubte eingehende Anfrage wird weitergeleitet. Aktuell ist nur die
synthetische Prüfung beauftragt, keine Anfrage an Ollama und keine Profilaktivierung.

Für einen späteren ausdrücklich freigegebenen Einsatz verlangt das CLI drei
Angaben: expliziten Upstream, neues absolutes Ausgabeverzeichnis und optionalen
Listenerport. Beispiel erst für diesen späteren Einsatz:

```powershell
node E:/Guardrails-Local/tools/opencode/recording-proxy.mjs --upstream http://127.0.0.1:11434 --out E:/Guardrails-Local/work/opencode-next-capture --port 0
```

Die ausgegebene Loopback-URL enthält den tatsächlich belegten Listenerport.
In einem neuen privaten Profil müssten dann **beide** Werte darauf zeigen:
Provider-`baseURL` auf `<Proxy-URL>/v1`, Guard-`options.endpoint` auf
`<Proxy-URL>/v1/chat/completions`. Keine Betreiberdatei wird automatisch verändert.
Ctrl+C beendet den Proxy; das Import-API bietet `await close()` für Tests.

## Vertrag

- Listener und expliziter HTTP-Upstream verwenden ausschließlich `127.0.0.1`.
- Nur POST `/v1/chat/completions` und GET `/api/tags`, ohne Query oder andere Route.
  Metadaten werden auf derselben Route weitergeleitet und zählen nicht als Completion.
- Höchstens zwei Completionversuche und zehn angenommene HTTP-Anfragen je Instanz.
  Fehler verbrauchen ihren Platz; keine Wiederholung, kein Redirect-Following.
- Je Body maximal 1 MiB, je Anfrage absolute Frist von 60 Sekunden. Keine Erhöhung
  der bestehenden Guardgrenzen. Tests können kleinere Grenzen verwenden.
- HTTP-Bodybytes werden ohne JSON-Neuserialisierung oder Dekompression gespeichert
  und weitergereicht. Gepuffertes SSE verändert Zeitverhalten und Chunkgrenzen.
  Aufzeichnung von TCP-/TLS-Paketen oder ursprünglichem HTTP-Transferframing fehlt.
- Keine Antwortweitergabe vor erfolgreicher Body-/Metadatensicherung. Abbruch,
  Übergröße, Zeitlimit, Redirect und Schreibfehler ergeben keinen COMPLETE-Status.

## Artefakte und Aussagegrenzen

Ausgabeverzeichnis muss neu sein; vorhandene Pfade werden zurückgewiesen.
`session.json` beschreibt die feste Instanz, `summary.json` ihren beendeten Stand.
Pro angenommener Anfrage entsteht ein eigener nummerierter Ordner:

- `request.body` und `response.body`: gespeicherte Bytes, bei Fehlern begrenzte Teilbytes.
- `capture.json`: SHA256, Bytezahlen, Status COMPLETE/PARTIAL/ERROR und Fehlergrund;
  HTTP-Vollständigkeit und `sse_done_seen` sind getrennte Werte.

Ein vollständiger HTTP-Body ohne SSE-[DONE] bleibt als solcher erkennbar. Ein
beobachteter Marker beweist weder gültiges SSE insgesamt noch Modellqualität.
Headergeheimnisse werden nicht aufgezeichnet; Prompt-/Antwortbodies können private
Daten enthalten. Für diesen Arbeitsablauf ist ein lokaler Ausgabepfad unter dem
ignorierten `work/` zu verwenden; die API erzwingt diesen Projektordner nicht.
Bei einem Schreibfehler können auch Metadaten fehlen; ein fehlender Beleg ist
keine vollständige Aufzeichnung. Keine OS-Isolation oder menschliche Abnahme ableiten.

Node unterscheidet einen vollständig empfangenen HTTP-Body über `message.complete`;
ein Timeoutereignis allein bricht eine Anfrage nicht ab. Der Proxy verwendet eine
eigene absolute Frist und zerstört betroffene Verbindungen.
[Node-24-HTTP-Vertrag](https://nodejs.org/docs/latest-v24.x/api/http.html).
Die Timeout-Antwort wartet auch bei ausstehender Dateischreibung nicht auf deren
Rückkehr. Aufzeichnung und `close()` warten anschließend auf die Schreibjobs;
ein hartes Abbrechen blockierender OS-Dateisystemarbeit ist damit nicht belegt.
Verspätete Schreibabschlüsse dürfen keinen COMPLETE-Status legitimieren.

Entwurf und Prüfplan: `docs/superpowers/specs/2026-10-24-opencode-recording-proxy-design.md`
und `docs/superpowers/plans/2026-10-24-opencode-recording-proxy.md`.

## Synthetischer Prüfstand vom 24.10.2026

Der Testvertrag entstand in separatem Agentkontext vor dem Produktmodul.
RED: Import scheiterte am noch fehlenden Modul, Exit 1. Zunächst bestanden
20/20 Proxytests. Ein separater automatisierter Quellreview fand danach eine
verzögerte Timeout-Antwort bei wartendem Dateisystem-I/O. Ein zusätzlicher Test
reproduzierte dies vor der Korrektur; der Timer antwortet jetzt unmittelbar 504.
Anschließend bestanden **21/21 Proxyfälle und insgesamt 130/130** in den
betroffenen Guard-/Proxy-Suiten, 0 Fehler, 0 übersprungen, Exit 0.
Keine bereits durchgeführten historischen
Modell-/Parserproben oder die gesamte Python-Projektsuite dafür wiederholt.

Belege: `work/opencode-recording-proxy-20261024/red.tap`,
`green-attempt-1.tap`, `combined-attempt-1.tap`, `red-disk-deadline.tap`,
`combined-final.tap`, `verification.json`.
Geprüft: echte synthetische HTTP-Verbindungen, Körperbytes/Hashes, JSON und
fragmentiertes SSE/UTF-8, feste Routen, Metadaten, Parallelität, Höchstzahlen,
1-MiB-Standardgrenze, absolute Frist trotz Datenfluss, Teilantwort, Schreibfehler
und Shutdown. Testlistener wurden durch den getesteten Cleanup geschlossen.
Der CLI-Import wurde geprüft; ein produktiver CLI-Lauf wurde nicht gestartet.

Dies ist Vorbereitung für eine spätere begrenzte Stichprobe, keine Inferenzfreigabe,
keine neue native OpenCode-Abnahme und keine Abnahme der historischen leeren Antwort.
Gesamtprojekt weiterhin NOT_ACCEPTED.
