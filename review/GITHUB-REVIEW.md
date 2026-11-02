# Full-source review snapshot

This private-repository PR compares the complete sanitized source snapshot against a fresh baseline. It does not change prototype, rewrite remote history, activate integrations, or authorize merging. Historical OpenCode/Ollama files remain present for static review only.

The project files are at the repository root (not under project/ as in the earlier ZIP). Supplemental context, package metadata and the review request are under review/. Original AGENTS.md is preserved at review/ORIGINAL-AGENTS.md. The ZIP source manifest uses project/ prefixes; remove that prefix when locating exported project files here. The manifest describes the ZIP input; GITHUB-MANIFEST.json binds this GitHub export.

Read review/01-REVIEW-AUFTRAG.md. Review Guardrails AI, DeepEval, Promptfoo, NLI, local transport, evidence binding, correction budgets, and host release enforcement. Promptfoo is a regression tool, not a required runtime gate. Distinguish documented requirements, implemented code, historical tests, and actual host acceptance. The overall product remains NOT_ACCEPTED.

Privacy: personal Windows usernames were replaced in export copies. Only selected project evidence is included; no raw chats, credentials, .git history, dependency directories or model weights. Technical session IDs and project context remain. No actual credentials were detected by targeted scans; dummy credentials in tests remain. No claim of absolute anonymization.

Validation: JSON parsing, Python syntax parsing, manifest hashes and source completeness are checked. No product tests or model executions were repeated for this snapshot. Installed package metadata is not a live functionality test.

GitHub export line endings are normalized to LF, and two whitespace-only lines in work/codex/config.json are cleaned. Source line counts remain unchanged. GITHUB-MANIFEST.json describes the normalized uploaded bytes.
