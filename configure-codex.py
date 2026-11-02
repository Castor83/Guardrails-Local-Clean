"""Startpunkt zur ausdrücklichen Einrichtung des Codex-Anschlusses."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / 'src'))
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, 'reconfigure'):
        stream.reconfigure(encoding='utf-8', errors='backslashreplace')

from guardrails_local.codex_setup import main

if __name__ == '__main__':
    raise SystemExit(main())
