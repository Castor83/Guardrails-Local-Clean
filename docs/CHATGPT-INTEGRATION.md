# ChatGPT-Integration: belegte Möglichkeiten und Grenzen

Stand: 16.10.2026. Öffentliche Primärquellen wurden an diesem Tag geöffnet und
inhaltlich geprüft. Diese Recherche installiert oder aktiviert keine Integration.

Die vorhandene lokale CLI und die manuelle Loopback-Oberfläche sind der erste
umgesetzte Zugang für ChatGPT-Ausgaben. Der Import und die HTTP-Anbindung wurden
im Projekt getestet. Der inzwischen vom Benutzer unverändert eingefügte
ChatGPT-Antworttext wurde manuell übernommen und mit echtem lokalem Critic
geprüft. Die Herkunft beruht auf seiner ausdrücklichen Angabe. Eine interne
Kontrolle der ChatGPT-Anzeige ist nicht nachgewiesen.

## 1. Aktueller Projektstand

| Bestandteil | Stand und Aussagegrenze |
| --- | --- |
| CLI-Import | Implementiert; nimmt lokal bereitgestellte Texte oder strukturierte Entwürfe entgegen. |
| Lokale Prüfoberfläche | Implementiert und per HTTP-Integration getestet; ausdrückliches manuelles Einfügen, Verarbeitung über Loopback. |
| Automatische ChatGPT-DOM-Erfassung | Nicht implementiert. Die geprüften Nutzungsbedingungen erlauben ihre Zulässigkeit nicht als bestätigt zu melden. |
| Echter ChatGPT-Antwortimport | Ausgeführt: Der Benutzer lieferte den unveränderten Antworttext anschließend selbst. Er wurde über den lokalen CLI-Prüfeingang an den echten Critic übergeben. |
| Herkunftsnachweis | Manuelle Übernahme laut ausdrücklicher Benutzerangabe, unverändertes Textfeld und SHA256 dokumentiert. Keine unabhängige Authentifizierung des internen Erzeugermodells. Der frühere Chat-Lesezugriff lieferte nur Inhaltsverweise. |
| Unabhängigkeit des Critic | Bei `source: chatgpt` ist die Erzeugerfamilie derzeit unbekannt. Ohne weiteren Nachweis bleibt das Gesamtergebnis `UNVERIFIED`; eindeutig nachgewiesene harte Verstöße ergeben `FAIL`. |
| Neue offizielle Integrationen | Sign in with ChatGPT, MCP/Plugins und Hooks sind recherchiert. Sie wurden hierfür nicht installiert, verbunden oder praktisch getestet. |

Der Herkunftseintrag `chatgpt` ist eine Quellenangabe des Importierenden. Er ist
allein kein technischer Nachweis des erzeugenden Modells oder seiner Familie.
Insbesondere darf ein grünes Critic-Urteil diese Lücke nicht in `PASS` verwandeln.

## 2. Nachkontrolle und Vorabfreigabe

Bei der aktuellen ChatGPT-Nutzung ist die Antwort bereits im fremden Produkt
erschienen, bevor sie manuell importiert wird. Das ist eine lokale Nachkontrolle.
Sie kann die Weiterverarbeitung im eigenen System verhindern, aber die frühere
Anzeige in ChatGPT nicht rückgängig machen.

In einer selbst kontrollierten Anwendung kann ein Entwurf vor der Freigabe an
nachgelagerte Komponenten geprüft werden. Entwurf, Prüfbericht und freigegebenes
Ergebnis müssen dort getrennt behandelt werden. Eine solche Freigabegrenze gilt
nur für diese Anwendung. Sie beweist keine Kontrolle über ChatGPT selbst.

Die geprüften offiziellen Plugin-Schnittstellen dokumentieren Werkzeugaufrufe
und optionale Oberflächen. Ein allgemeiner verpflichtender Hook, der sämtliche
normalen ChatGPT-Antwortentwürfe vor deren erster Anzeige lokal abfangen und
zurückhalten kann, wurde darin nicht gefunden. Dies ist die Grenze der geprüften
Dokumentation, keine Behauptung über unveröffentlichte Produktfunktionen.
[MCP-Konzepte](https://developers.openai.com/plugins/concepts/mcp-server),
[Plugin-UI-Referenz](https://developers.openai.com/plugins/reference).

## 3. Browserintegration und Nutzungsbedingungen

Die geöffneten europäischen OpenAI-Nutzungsbedingungen tragen den Stand
16.01.2026. Sie untersagen unter anderem die automatische oder programmgesteuerte
Extraktion von Daten und Ausgaben sowie die Umgehung von Schutzmaßnahmen und
Nutzungslimits. Die Zuordnung von Rechten am Output enthält dort keine
ausdrückliche Ausnahme für einen eigenen automatischen DOM-Leser. Auch eine
einmalige per Klick gestartete Extraktion ist in dieser Quelle nicht ausdrücklich
ausgenommen. Deshalb wird sie hier nicht als bedingungskonform freigegeben.
[OpenAI: Nutzungsbedingungen für Europa](https://openai.com/de-DE/policies/eu-terms-of-use/).

Technisch können Browsererweiterungen den sichtbaren DOM-Inhalt mit passenden
Berechtigungen lesen. Das verschafft ihnen keinen dokumentierten Zugriff auf
interne, noch nicht angezeigte ChatGPT-Entwürfe. DOM-Änderungen, Streaming und
nachgeladene Inhalte müssten außerdem mit dem jeweils aktuellen Produkt geprüft
werden. In diesem Projekt wurde kein solcher Leser gebaut oder am echten
ChatGPT-DOM getestet.

Eine spätere begrenzte Erweiterung kann zunächst ein eigenes Eingabefeld für
ausdrückliches Einfügen anbieten. Dafür ist keine automatische Erfassung des
Chatverlaufs erforderlich. Für einen künftig ausdrücklich zulässigen DOM-Modus
wären `activeTab` und `scripting` enger als dauerhafte Rechte für alle Websites.
Chrome gewährt damit zeitweiligen Zugriff nach einer Nutzeraktion.
[Chrome: activeTab](https://developer.chrome.com/docs/extensions/develop/concepts/activeTab).

Für eine lokale Weiterleitung sollten eine feste Loopback-Zieladresse,
authentifizierte Anfragen und begrenzte Eingabegrößen gelten. Ein Content-Script
darf dem Hintergrundprozess keine beliebigen Ziel-URLs vorgeben. Direkte
Cross-Origin-Anfragen aus Content-Scripts unterliegen weiterhin CORS; für
Hintergrundanfragen gelten die benötigten Hostrechte.
[Chrome: Cross-origin network requests](https://developer.chrome.com/docs/extensions/develop/concepts/network-requests).

Edge unterstützt weitgehend kompatible Chromium-Erweiterungen, verlangt aber
eigene Funktionsprüfung. Firefox hat ebenfalls Content-Scripts und eigene
Berechtigungs- und Laufzeitgrenzen. Aus der Dokumentation folgt keine getestete
Browserunterstützung dieses Projekts.
[Microsoft: Chrome-Erweiterung nach Edge portieren](https://learn.microsoft.com/en-us/microsoft-edge/extensions/developer-guide/port-chrome-extension),
[Mozilla: Content scripts](https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/Content_scripts).

## 4. Manueller Import und offizieller Export

Der sofort nutzbare Ablauf lautet: Antwort selbst in ChatGPT kopieren, lokal
einfügen, prüfen und anschließend Prüfbericht beziehungsweise Korrekturauftrag
verwenden. Es wird dafür weder ein ChatGPT-Token ausgelesen noch ein zusätzlicher
OpenAI-Modellaufruf benötigt. Der Import muss als nachträgliche Prüfung sichtbar
bleiben.

OpenAI bietet außerdem einen offiziellen Datenexport über die Kontoeinstellungen
oder das Privacy Portal. Das ZIP enthält den Chatverlauf und weitere Kontodaten.
Die Bereitstellung kann bis zu sieben Tage dauern; ein Downloadlink gilt 24
Stunden. Dieser Weg eignet sich für spätere Archivimporte, nicht als unmittelbare
Antwortschnittstelle. Ein ZIP-Importer wurde für diesen Prototyp nicht als
implementiert oder getestet nachgewiesen.
[OpenAI: ChatGPT-Verlauf und Daten exportieren](https://help.openai.com/en/articles/7260999-exporting-your-chatgpt-history-and-data).

## 5. Offizielle MCP- und Plugin-Wege

MCP stellt Werkzeuge mit strukturierten Eingaben und Ergebnissen bereit. Das
Modell wählt ein Werkzeug und nutzt dessen Rückgabe für die weitere Antwort. Ein
lokales `validate_draft`-Werkzeug wäre damit grundsätzlich anschließbar. Seine
Existenz erzwingt jedoch nicht, dass jede Antwort vollständig über dieses
Werkzeug läuft. Eine Freigabelogik muss weiterhin außerhalb des Modells liegen.
[OpenAI: MCP server](https://developers.openai.com/plugins/concepts/mcp-server).

Die offiziellen UI- und Extension-Schnittstellen umfassen unter anderem
Werkzeugdaten, Dateiauswahl, Sidebar-Oberflächen, Gesprächspanels und
Folgemitteilungen. Daraus ergibt sich kein belegter globaler Antwortfilter.
[OpenAI: Plugin Extensions](https://developers.openai.com/plugins/build/extensions),
[OpenAI: UI-Referenz](https://developers.openai.com/plugins/reference).

Ein öffentlicher Drittanbieter-Tunnel ist inzwischen nicht der einzige offizielle
Weg: Secure MCP Tunnel verbindet private Server über eine ausgehende Verbindung
mit OpenAI. Anfragen und Ergebnisse werden dabei über OpenAI weitergeleitet.
Das ist keine ausschließlich lokale Prüfkette.
[OpenAI: Private MCP-Server verbinden](https://developers.openai.com/blog/connect-private-mcp-servers-to-openai-products).

Desktop-only-Plugins können lokale stdio-MCP-Server enthalten. Die öffentliche
Einreichung solcher Plugins ist laut Dokumentation auf zugelassene Partner
begrenzt. Die Nutzbarkeit im konkreten Konto und die private lokale Einrichtung
wurden hier nicht getestet; aus der Veröffentlichungsvoraussetzung wird keine
pauschale Aussage über private Installationen abgeleitet.
[OpenAI: Desktop-only-Plugins](https://developers.openai.com/plugins/deploy/desktop-only).

## 6. Sign in with ChatGPT: neuer kontrollierter Client

Die aktuelle offizielle Dokumentation beschreibt die Nutzung eines vorhandenen
ChatGPT-Plans für geeignete Responses-Anfragen aus quelloffenen und lokal
gehosteten Apps. Dazu sind eigene OAuth-Berechtigungen erforderlich. Der Weg
gewährt ausdrücklich keinen Zugriff auf bestehende ChatGPT-Unterhaltungen oder
anderen Kontokontext.
[OpenAI: ChatGPT plan usage](https://developers.openai.com/siwc/token-sharing-open-source).

Der Quickstart nennt geeignete Plus-/Pro-Konten, Open-Source-Partner und
ausgewählte private Clients. Deshalb wäre die Aussage, jede offizielle externe
Oberfläche brauche zwingend einen zusätzlichen bezahlten API-Key, nach diesen
Quellen zu pauschal. Zugang und Eignung des konkreten Kontos bleiben ungetestet.
Planverbrauch und gegebenenfalls Credits sind nicht mit unbegrenzter kostenloser
Nutzung gleichzusetzen.
[OpenAI: Sign-in-Quickstart](https://developers.openai.com/siwc/quickstart).

Der dokumentierte Inferenzweg verwendet den offiziellen Responses-Endpunkt mit
`store: false` und `stream: true`, nicht die internen ChatGPT-`backend-api`-Pfade.
Die Preview besitzt weitere Einschränkungen, etwa bei persistenter Conversation-
Anbindung und gehosteten Werkzeugen.
[OpenAI: Models and inference](https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference),
[OpenAI: Preview limitations](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations).

Technische Folgerung: Ein eigener berechtigter Client könnte einen neuen
Antwortstream lokal sammeln und vor der Freigabe in seiner Oberfläche prüfen.
Das wäre weiterhin Cloud-Erzeugung und eine neue kontrollierte Oberfläche. Es
wäre keine Abfangfunktion für bestehende ChatGPT-Chats. Für dieses Projekt wurde
dieser Weg ausschließlich recherchiert; keine Anmeldung, Autorisierung,
Implementierung oder Inferenz wurde darüber vorgenommen.

## 7. Codex-/Work-Hooks

Die offizielle Hook-Dokumentation beschreibt lokale Befehle und MCP-Werkzeuge im
Codex-Lebenszyklus. Ein `Stop`-Hook erhält unter anderem
`last_assistant_message` und kann eine Fortsetzung mit Korrekturprompt anstoßen.
Eine solche Blockentscheidung verwirft den Turn ausdrücklich nicht.
`suppressOutput` ist dokumentiert, aber noch nicht implementiert. Fehler oder
nicht verfügbare MCP-Hooks blockieren Vorgänge nicht automatisch.
[OpenAI: Hooks](https://learn.chatgpt.com/docs/hooks).

Das ermöglicht eine automatische Nachprüfung für unterstützte Codex-Abläufe.
Daraus folgt keine garantierte Sperre vor der Erstanzeige und keine Freigabe
bei Hook-Ausfall. Der ergänzte lokale Codex-Anschluss und seine getrennten
Einrichtungs-, Freigabe- und Ausführungsnachweise sind in
[`CODEX-INTEGRATION.md`](CODEX-INTEGRATION.md) beschrieben.

## 8. Nachgewiesener manueller Originalimport

Der Benutzer lieferte den angefragten unveränderten ChatGPT-Antwortausschnitt.
Dieser wurde mit dokumentierter Übernahmeart über die lokale CLI geprüft.
Der Originaltext bleibt in `examples/chatgpt-original.txt`, Herkunft und SHA256
sind separat protokolliert. Der erste echte Critic-Aufruf meldete trotz eines
lokal belegten API-Fehlers `pass`; der Orchestrator hielt `UNVERIFIED` und gab
keinen Text frei. Bericht: `CHATGPT-ORIGINALPRUEFUNG.md`. Die interne
Erzeugerfamilie bleibt ungeprüft. Die manuelle Integration ist nachgewiesen;
automatische Erfassung und interne Vorabkontrolle sind durch diesen manuellen
Originalimport nicht belegt.

Die aktuellen Quellen rechtfertigen den manuellen lokalen Prüfeingang als
ersten umgesetzten Integrationsweg. Sie rechtfertigen keine Behauptung einer
internen ChatGPT-Vorabkontrolle, einer erlaubten automatischen DOM-Erfassung
oder einer getesteten SIWC-/MCP-Anbindung. Der separate Codex-Hook-Anschluss
wird mit eigenen Nachweisen bewertet.
