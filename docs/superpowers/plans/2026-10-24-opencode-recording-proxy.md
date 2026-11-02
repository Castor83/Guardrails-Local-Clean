# OpenCode Recording Proxy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Lokalen Aufzeichnungsproxy bauen und ausschließlich synthetisch prüfen.
**Architecture:** Node-http-Proxy mit festen Loopbackrouten, begrenzten gepufferten
Bodybytes und lokalem Artefaktordner; eigenständiges manuelles CLI, keine Aktivierung.
**Tech Stack:** Vorhandenes Node.js, node:http, node:fs/promises, node:crypto, node:test.
**Spec:** `docs/superpowers/specs/2026-10-24-opencode-recording-proxy-design.md`.

## Global Constraints

Nur numerisches 127.0.0.1; expliziter Upstream; kein Kontakt beim Start;
maximal zwei Completions, zehn angenommene HTTP-Anfragen, 1 MiB je Body,
absolute Frist 60 Sekunden. Keine natürlichen Modellläufe, Installationen,
Profiländerungen, Pushes oder Ausweitungen der Guardgrenzen.

## Review Focus

Bytegleichheit bei UTF-8/SSE-Fragmentierung; dauerhaft verbrauchte Plätze bei
Parallelität/Fehlern; partielle Artefakte bei Timeout/Abbruch/Übergröße;
Schreibfehler verhindern Erfolgsausgabe; keine Redirect-/DNS-/Routenausweichpfade.
Diese Klassen erhalten Tests in Task 1; keine erneuten historischen Laufserien.

## Task 1: Proxy und gezielter synthetischer Vertrag

**Files:** `tools/opencode/recording-proxy.mjs`,
`tests/opencode-recording-proxy.test.mjs`, `docs/OPENCODE-RECORDING-PROXY.md`.
**Interface:** `createRecordingProxy({ upstream, outputDir, port=0, maxBytes=1048576,
timeoutMs=60000 })` -> Promise mit `url`, `close()`; Import hat keine Startwirkung.
CLI verlangt `--upstream`, `--out`, optional `--port`; keine voreingestellte Modellroute.

- [x] Tests für alle Review-Focus-Klassen schreiben; fehlendes Modul als RED belegen.
- [x] Minimalen Bodyrecorder und festes CLI implementieren; keine JSON-Neuserialisierung.
- [x] Proxytests und betroffene V1-/V2-Suiten laufen lassen; Ausgaben lokal sichern.
- [x] Automatisierte separate Quellprüfung; echte Defekte gezielt korrigieren.
- [x] Bedienung, Aufzeichnungsumfang und Freigabegrenzen dokumentieren.
- [x] Diff und Indexumfang prüfen, nur eigene Taskdateien committen; Übergabestand aktualisieren.

Ergebnis: 21 Proxyfälle im gemeinsamen Lauf mit den betroffenen Guard-Suiten,
130/130 bestanden. Reviewbefund zur Clientdeadline bei wartender Dateischreibung
gezielt RED reproduziert und korrigiert; automatisiert nachgeprüft.
Belege: `work/opencode-recording-proxy-20261024/verification.json`.
OS-Dateisystem-Cleanup ist keine hart abbrechbare Zeitgarantie; siehe Betriebsdoku.
Keine Modellinferenz, Betreiberaktivierung, neue native OpenCode-Abnahme oder Push.
