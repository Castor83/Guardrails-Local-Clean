# Local Promptfoo regressions

From this repository, using the existing controller interpreter:

```powershell
& 'C:\Users\REDACTED_USER\.venv\Scripts\python.exe' .\run-regressions.py --install
& 'C:\Users\REDACTED_USER\.venv\Scripts\python.exe' .\run-regressions.py
```

The first command installs the exact npm lock into `work/promptfoo-runtime`.
It never installs globally or changes Python packages. Lifecycle scripts and
optional dependencies are disabled. The matching Windows libsql binary is an
explicit pinned dependency because the CLI imports its local database driver.
Node uses the Windows system certificate store; TLS verification stays enabled.

The second command runs the actual installed Promptfoo CLI and its Python
provider, with one case at a time, no cache, no sharing, no database history,
no telemetry, no updates, and no configured remote provider. Home, configuration,
logs, npm cache, and exports remain under the project runtime. Process-local
network guards protect the fixed Node/Python fixture path; they are not an OS
sandbox. Python permits only its own ephemeral loopback socketpair for Windows
asyncio and forbids provider subprocess/model launches.

The Python provider calls the real `QualityPipeline`. Only the evaluator and
corrector judgments are explicit synthetic fixtures. Passing this harness proves
the eight named control-flow regressions, not model quality, a trusted native
hook installation, or general answer correctness. `released_text` remains null
and `verified` remains false. Synthetic chat receipts exist only in a temporary
fixture repository and are never written to the live project's receipt store.

Read `work/promptfoo-runtime/latest-run.json` for the bounded summary and paths
to the genuine CLI output and export. Node >=22.22.0 is required; Node 24 is
recommended upstream. The tested published CLI version is pinned in
`tools/promptfoo/package.json` and its integrity lock.

Primary references:

- https://www.promptfoo.dev/docs/installation/
- https://www.promptfoo.dev/docs/providers/python/
- https://www.promptfoo.dev/docs/usage/command-line/
- https://registry.npmjs.org/promptfoo/0.124.1
# Feste Fall- und Ergebnisbindung (20.10.2026)

Der Controller pinnt die vollständigen acht Fälle, Konfiguration, Provider und
Offline-Guard. JSON wird kanonisch gehasht, Quelltext mit normalisierten
Zeilenenden. Die Artefakte müssen vor und nach dem Lauf dem festen Vertrag
entsprechen. Jeder Export benötigt acht eindeutige tatsächliche Fall-IDs,
passende Variablen, Eingaben, Assertions, Provider-Fallhashes, Sollurteile und
Ausführungszähler. Ein reiner Zählerbericht ist kein Erfolgsnachweis.

Diese modellfreien Fälle prüfen die echte Produktpipeline mit synthetischen
Urteilen. Sie belegen keine Live-Modellqualität oder native Host-Abnahme.
