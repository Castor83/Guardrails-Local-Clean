# Guardrails Workflow Implementation Plan

> For agentic workers: Use superpowers:executing-plans inline; perform TDD and a final fresh code review.

**Goal:** Bind task rules, intercept supported work actions and require actual evidence for structured completion claims.
**Architecture:** Scoped deterministic workflow module alongside the existing bounded response adapter. One fixed CPU test runner produces task- and tree-bound evidence; no added model or dependency.
**Tech Stack:** Existing Python 3.12, unittest, Guardrails integration, local JSON/fsync.
**Spec:** E:/Guardrails-Local/docs/WORKFLOW-ENTWURF.md

## Global Constraints
- Work only in E:/Guardrails-Local; preserve foreign zero-byte files and read-only mirrors.
- Existing critic, exact original task, 4096 context, 8500-byte limit and two-correction budget remain.
- No installs, new models, cloud inference, upload or trust database edits.
- Native trust and actual PreToolUse blocking must not be inferred from unit tests.

## Review Focus
- An unknown/composed shell command must be denied rather than partly parsed.
- Other registered chats must not silently gain workflow restrictions.
- Rule/task/tree drift must invalidate old completion evidence and caches.
- Failed/missing audits must never allow a supported action.
- Zero tests, timeout and a forged/mismatched task must never prove completion.

## Task 1: Deterministic workflow and evidence
Files: src/guardrails_local/workflow.py, src/guardrails_local/workflow_validators.py, workflow-check.py, config/workflow-policy.json, tests/test_workflow.py.
Interfaces: ensure_contract(root,state), tool_decision(root,state,payload), completion_report(root,state,text), run_checks(root,state).
- [ ] Write behavioral tests for denied foreign patch/shell, bounded allowed reads and fixed runner, missing/stale completion evidence, exact task/policy binding.
- [ ] Run tests RED for missing implementation, retaining the assertion evidence.
- [ ] Implement positive tool grammar, durable contracts/audits, fixed runner and snapshot validation.
- [ ] Run targeted tests GREEN, including a real tiny local unittest subprocess without inference.

## Task 2: Existing hook integration and scoped setup
Files: src/guardrails_local/codex_hook.py, src/guardrails_local/codex_setup.py, tests/test_codex_hook.py, tests/test_codex_setup.py.
Consumes Task 1 interfaces. Adds optional workflow_session_ids and --workflow; existing callers retain their prior mode.
- [ ] Write RED tests for scoped prompt context, error-to-deny PreToolUse handling, protected edits and workflow completion FAIL triggering bounded correction.
- [ ] Implement workflow context, snapshot/cache binding and response status merge; setup adds one optional PreToolUse handler without changing existing definitions or trust.
- [ ] Run targeted hook/setup/workflow tests GREEN.

## Task 3: Verification and activation evidence
Files: docs/CODEX-INTEGRATION.md and ignored work/codex/ evidence.
- [ ] Document exact commands, supported scope, unknown-command denial, completion marker and remaining limits.
- [ ] Run full suite once for the changed product, git diff --check and independent code review; repair material findings with regression tests.
- [ ] Produce a real task-bound completion proof with the fixed runner after the final file change.
- [ ] Configure only current session --workflow, preserve other modes/IDs and record trust/recognition honestly. Native activation requiring user trust is the final external step.
- [ ] Save checked final text and execute the currently required exact precheck. Commit only intended product files locally; no push.
