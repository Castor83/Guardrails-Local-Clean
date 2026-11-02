# OpenCode: begrenzter lokaler Aufzeichnungsproxy

Nutzerauftrag vom 24.10.2026: erst Kreuztyp-Unitfälle ergänzen, dann Proxy bauen
und ohne Modell prüfen. Ein späterer natürlicher Lauf benötigt eine eigene
Freigabe. Die Kreuztypfälle sind mit 109/109 und Commit `35ae615` abgeschlossen.

## Entscheidung und Umfang

Kleine eigenständige Node.js-Lösung mit den vorhandenen Standardmodulen. Sie
zeichnet HTTP-Bodybytes vor dem Guard auf und leitet denselben API-Pfad weiter.
Vorteil: keine Installation, einfache synthetische Bytevergleiche. Nachteil:
begrenzte Bodies werden gepuffert; SSE-Zeitverhalten und HTTP-Chunkgrenzen ändern
sich. Ein externer Proxy bräuchte zusätzliche Einrichtung; eine Aufzeichnung
im Guard würde gerade dessen Interpretation statt des vorgelagerten Bodys prüfen.

Meine Implementierungsentscheidungen: ausschließlich `127.0.0.1`, expliziter
HTTP-Upstream-Origin ohne DNS, Start ohne Upstreamkontakt. Nur POST
`/v1/chat/completions` und GET `/api/tags`; keine Queryvarianten, Redirects oder
andere Ziele. GET dient nur Metadaten, zählt nicht als Completion. Maximal zwei
Completionversuche und zehn angenommene HTTP-Anfragen pro Proxyinstanz; Plätze
vor asynchroner Verarbeitung reservieren und bei Fehlern nicht freigeben.

## Aufzeichnung und Grenzen

Neues absolutes Ausgabeverzeichnis zwingend; vorhandene Verzeichnisse niemals
überschreiben. Pro Anfrage: request.body, response.body, Metadaten mit Bytezahlen,
SHA256 und getrenntem HTTP-Abschluss sowie beobachtetem SSE-[DONE]-Marker.
Headergeheimnisse werden nicht protokolliert. Bodies können private Daten
enthalten und bleiben im lokalen ignorierten `work/`-Bereich.

Standardlimit 1 MiB je Body und absolute 60-Sekunden-Frist je angenommener Anfrage.
Damit wird die bestehende Guardgrenze nicht erhöht. Bei Abbruch, Übergröße,
Zeitlimit oder Schreibfehler keine vollständige Aufzeichnung behaupten und keine
unaufgezeichnete Antwort als Erfolg ausliefern. Teilbytes soweit möglich erhalten.
Erfasst werden HTTP-Entitybytes nach Transferframing, keine TCP-/TLS-Rohpakete.
HTTP-Vollständigkeit und ein beobachteter SSE-Marker sind keine Modellabnahme.

Keine automatische Profiländerung. Später müssten Provider-baseURL und
Guard-options.endpoint gemeinsam auf denselben Proxyport eines neuen privaten
Profils zeigen. Dieses Einrichten und eine echte Inferenz werden hier nicht ausgeführt.
Keine OS-Netzwerkisolation oder Behebung der historischen leeren Antwort behaupten.

## Abnahme ohne Modell

Neue Node-Tests betreiben ausschließlich synthetische Server an zufälligen
Loopbackports. Prüfen: JSON und fragmentierte SSE-/UTF-8-Bytes unverändert,
Hashes und Abschlussmarker, Metadatenroute, Routen-/Zielgrenzen, Höchstzahl auch
parallel, absolute Frist, übergroße und unterbrochene Bodies, vorhandenes
Ausgabeverzeichnis sowie Aufzeichnungsfehler. Alle eigenen Listener schließen.
Kein Kontakt zu Port 11434 oder fremden Diensten, keine OpenCode-/Modellprozesse.
