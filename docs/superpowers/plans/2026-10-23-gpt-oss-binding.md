# Lokale Modellbindung auf gpt-oss:20b umstellen

> **For agentic workers:** Use inline execution for this single scoped migration. User approved the concrete replacement in this chat with "ok"; no additional approval round for this same change.

**Goal:** Critic, DeepEval and corrector accept only the approved installed `gpt-oss:20b` package.

**Architecture:** Retain the current exact model-name/digest admission checks and shared Critic transport. Replace only their approved identity and HTTP contract fixtures. Historical recommendation fixtures and provenance remain unchanged.

**Tech Stack:** Python unittest, existing local Ollama HTTP adapter; no installation.

**Spec:** User-approved proposal immediately preceding "ok": replace the unavailable Huihui judge with installed gpt-oss:20b, updating configuration, adapter and tests together; suitability remains untested.

## Global Constraints

- Model `gpt-oss:20b`; digest `f38aa0c53da5f8c49d08c43a99df24ff53167fe68e24664a7777288e7656fdfe`, verified in local `/api/tags`.
- Preserve 4096 context tokens, 1200 output tokens, loopback-only transport, model/digest checks, foreign-model refusal and call limits.
- No inference, download, installation, activation, process restart, commit or push.
- Retain historical fixtures, original instructions and old evidence. Do not label the new model abliterated or independently accepted.

## Review Focus

Stale configuration, missing/changed digest, duplicate catalog entries, foreign loaded models and returned model-name mismatch are exercised by the existing Critic HTTP contract tests. DeepEval consumes the same transport; its current tests must pass after the migration. Configuration/code drift is caught by making the success test consume actual project settings with only the fake loopback URL and short timeout substituted.

### Task 1: Migrate the exact binding

- [x] Save read-only model metadata, protected-file hashes and backups under `work/model-binding-20261023/`.
- [x] Update `tests/test_critic.py` HTTP fixtures to the new identity, consume actual settings in its successful request test, and add legacy identity to rejection cases. Run that test first; expected FAIL before migration.
- [x] Update `config/settings.json` and `src/guardrails_local/critic.py` to the approved identity; update current README/quality-stack documentation.
- [x] Run affected offline HTTP/evaluation contract tests, then the existing CPU unit suite with persistent result/log. No model smoke.
- [x] Review the diff, verify operator and policy hashes unchanged, save report with exact results and remaining live-evaluation gap.

Pre-flight: one task; no cross-task interfaces. User approval covers implementation in this existing checkout. Preserve foreign/uncommitted files; no isolation reset or copying old evidence.

Task 1 complete: RED one intended failure; GREEN 19 Critic tests; full suite 392 tests, zero failures/errors/skips, 100.212 seconds. Working-tree review by review_model_binding: no findings. Evidence and backups: `work/model-binding-20261023/`. No commit, push, live inference or activation performed.
