# Lokale Sicherung vor Komprimierung

**Auftrag:** Die bereits global beschlossene Vorsicherung technisch umsetzen. Der Nutzer verlangt die tatsächliche Einrichtung; zusätzliche allgemeine Freigaberunden für diese lokale Ergänzung entfallen.

**Umfang:** Ein eigenständiges Python-Standardskript wird projektseitig versioniert, geprüft und als globales PreCompact-Kommando installiert. Es sichert den vom Host benannten lokalen Verlauf unter CODEX_HOME/sessions oder archived_sessions und den vorhandenen Arbeitsstand `<cwd>/work/handoff/<session_id>-working.md` nach CODEX_HOME/handoff-snapshots. Keine Modellaufrufe, keine Abhängigkeiten, kein Netzwerk, keine Chat-Erstellung und keine Änderung bestehender Hook-Vertrauenseinträge.

**Grenzen:** Pro Ereignis ein neuer Ordner, kein Überschreiben. Kopie des Dateistandes beim Öffnen, SHA256 und Bytezahl im Manifest. Maximal 128 MiB Verlauf und 4 MiB Arbeitsstand; bei Übergröße keine stille Kürzung. Fehlende oder abgewiesene Quellen separat protokollieren. Symlink-/Junction-Auflösung darf den Quellen-/Zielbereich nicht verlassen. Keine Sicherungsinhalte im stdout oder Git. Ein fehlender Arbeitsstand ergibt PARTIAL, ein fehlender/abgewiesener Verlauf ERROR. Der Hook warnt dann, blockiert aber nicht die Komprimierung.

**Schritte:**

- [x] Dateisicherungs-Vertragstests schreiben und erwartetes RED beobachten.
- [x] Eigenständiges Skript implementieren; gezielte Tests und bestehende CPU-Suite ausführen.
- [x] Unabhängigen Diff-Review durchführen; gefundene wesentliche Fehler vor Abschluss beheben.
- [x] Bestehende globale Hookdatei sichern, Skript global kopieren, genau eine neue PreCompact-Definition ergänzen. Bestehende Definitionen und Vertrauen erhalten. Installation und direkten Protokollaufruf mit Testdaten prüfen.
- [x] Aktuellen Stand, Belege und Aktivierungsgrenze dokumentieren, eigenen Schritt committen. Fehlendes Hook-Vertrauen nicht selbst umgehen; dem Nutzer die konkrete Freigabe nennen. Ein synthetischer Lauf ist kein echter Lifecycle-Nachweis.

**Prüfung:** Vollständige lokale Kopien und Hashes; falsches Ereignis; ungültige Sitzungs-ID; fehlender Arbeitsstand; Quelle außerhalb des erlaubten Bereichs; Übergröße; wiederholtes Ereignis ohne Überschreiben; CLI mit Testdaten. Kein Test darf echte Modelle, Chats oder private Historien starten/weiterleiten.

Ergebnis: 9 gezielte Tests und 401 CPU-Tests bestanden, 102.893 Sekunden für die Suite. Statischer unabhängiger Review durch review_precompact_backup ohne blockierende Befunde. Optional zusätzliche Tests für unlesbaren/fehlenden Verlauf und umgeleitetes Sicherungsverzeichnis empfohlen; nicht als vorhandene Tests ausgegeben. Installierter Protokollaufruf mit echten lokalen Testdateikopien PASS. Globale Konfiguration REGISTERED_NEEDS_TRUST; Aktivierung und echter PreCompact-Durchlauf bleiben offen. Belege: `work/precompact-20261023/`.
