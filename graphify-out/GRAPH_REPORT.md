# Graph Report - Guardrails-Local  (2026-10-31)

## Corpus Check
- 82 files · ~63,137 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 5 file(s) not represented in the graph (top: (none) 5)

## Summary
- 1613 nodes · 3737 edges · 54 communities (34 shown, 20 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 128 edges (avg confidence: 0.87)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `45473310`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- manifest.json
- codex_hook.py
- import_text
- dependencies
- HookTests
- fake_ollama
- create_server
- FeedbackTests
- unittest
- provenance_nli.py
- ActionEvidenceTests
- WorkflowTests
- DeepEvalError
- NliContractTests
- QualityPipelineTests
- orchestrator.py
- optionalDependencies
- action_evidence.py
- quality_pipeline.py
- CodexSetupTests
- QualityEvaluationTests
- opencode-recording-proxy.test.mjs
- ProfileTests
- guardrails-evidence.mjs
- index.mjs
- recording-proxy.mjs
- conversation_profiles.py
- after
- peerDependenciesMeta
- json
- QualityControllerTests
- ScopedHookTests
- ClaimHookTests
- verified_cli_run
- DeepEvalWorkerTests
- PromptfooRunnerTests
- PythonApiTests
- promptfoo/package.json
- opencode-v2.test.mjs
- argparse
- PreCompactionSnapshotTests
- npm_artifact
- peerDependencies
- os
- LocalImportTests
- python_api.py
- setup
- QualityCLITests
- v2/package.json
- setup

## God Nodes (most connected - your core abstractions)
1. `import_text()` - 74 edges
2. `HookTests` - 58 edges
3. `FeedbackTests` - 46 edges
4. `fake_ollama()` - 42 edges
5. `DeepEvalError` - 38 edges
6. `ActionEvidenceTests` - 37 edges
7. `OllamaCritic` - 32 edges
8. `NliContractTests` - 30 edges
9. `WorkflowTests` - 30 edges
10. `OrchestratorTests` - 28 edges

## Surprising Connections (you probably didn't know these)
- `call_api()` --calls--> `record_tool_result()`  [INFERRED]
  regressions/promptfoo/provider.py → src/guardrails_local/action_evidence.py
- `call_api()` --calls--> `_canonical_hash()`  [INFERRED]
  regressions/promptfoo/provider.py → src/guardrails_local/promptfoo_runner.py
- `call_api()` --calls--> `_fixed_cases()`  [INFERRED]
  regressions/promptfoo/provider.py → src/guardrails_local/promptfoo_runner.py
- `evaluator()` --calls--> `contract_hash()`  [INFERRED]
  regressions/promptfoo/provider.py → src/guardrails_local/quality_pipeline.py
- `corrector()` --calls--> `contract_hash()`  [INFERRED]
  regressions/promptfoo/provider.py → src/guardrails_local/quality_pipeline.py

## Import Cycles
- None detected.

## Communities (54 total, 20 thin omitted)

### Community 0 - "manifest.json"
Cohesion: 0.02
Nodes (130): acorn, ai, ajv, ajv-formats, @anthropic-ai/claude-agent-sdk, @anthropic-ai/sdk, @apidevtools/json-schema-ref-parser, async (+122 more)

### Community 1 - "codex_hook.py"
Cohesion: 0.06
Nodes (90): _archive_state(), _atomic_bytes(), _atomic_json(), _checked_report(), _claim_check(), _config(), _context(), _conversation_check() (+82 more)

### Community 2 - "import_text"
Cohesion: 0.05
Nodes (16): import_text(), Orchestrator, MustNotReview, OrchestratorApplicabilityTests, CriticEvidenceBindingTests, finding(), BrokenCritic, OrchestratorTests (+8 more)

### Community 3 - "dependencies"
Cohesion: 0.03
Nodes (77): acorn, ai, ajv, ajv-formats, @anthropic-ai/sdk, @apidevtools/json-schema-ref-parser, async, binary-extensions (+69 more)

### Community 4 - "HookTests"
Cohesion: 0.08
Nodes (9): HookTests, changing(), masked_error(), running(), fail(), error(), fail_audit(), fail() (+1 more)

### Community 5 - "fake_ollama"
Cohesion: 0.07
Nodes (14): OllamaCritic, review_applicability(), CriticApplicabilityTests, CriticTests, envelope(), fake_ollama(), do_GET(), do_POST() (+6 more)

### Community 6 - "create_server"
Cohesion: 0.11
Nodes (9): create_server(), do_GET(), do_POST(), _error(), _response(), _valid_host(), _hash_source(), _LocalServer (+1 more)

### Community 9 - "provenance_nli.py"
Cohesion: 0.11
Nodes (25): admit_request(), _bound_pass(), check_nli(), create_native_validator(), _get_model_prediction_from_inference_endpoint(), _get_model_prediction_from_local_model(), get_query_function(), __init__() (+17 more)

### Community 14 - "DeepEvalError"
Cohesion: 0.06
Nodes (42): CriticError, _json_loads(), _NoRedirect, BoundedOllamaBridge, build_worker_environment(), DeepEvalError, _error_report(), _finite_json() (+34 more)

### Community 16 - "QualityPipelineTests"
Cohesion: 0.13
Nodes (7): QualityPipelineTests, self_verified(), failed(), bad(), corrector(), evaluator(), stale()

### Community 17 - "orchestrator.py"
Cohesion: 0.08
Nodes (12): _bind_evidence(), not_applicable_review(), analyze_text(), Draft, load_catalog(), load_requirements(), Recommendation, _hash() (+4 more)

### Community 18 - "optionalDependencies"
Cohesion: 0.07
Nodes (28): optionalDependencies, @anthropic-ai/claude-agent-sdk, @aws/bedrock-token-generator, @aws-sdk/client-bedrock-agent-runtime, @aws-sdk/client-bedrock-runtime, @aws-sdk/client-s3, @aws-sdk/client-sagemaker-runtime, @aws-sdk/credential-provider-sso (+20 more)

### Community 19 - "action_evidence.py"
Cohesion: 0.14
Nodes (24): _chat_entries(), entry(), walk(), check_action_claims(), _claims(), _directory(), _error_payload(), _json_bytes() (+16 more)

### Community 20 - "quality_pipeline.py"
Cohesion: 0.06
Nodes (27): call_api(), corrector(), evaluator(), _build_orchestrator(), _emit_report(), FixtureCorrector, _load_draft(), main() (+19 more)

### Community 22 - "QualityEvaluationTests"
Cohesion: 0.17
Nodes (3): native_doubles(), QualityEvaluationTests, ScriptedBridge

### Community 23 - "opencode-recording-proxy.test.mjs"
Cohesion: 0.12
Nodes (9): checkCapture(), checkFailure(), deadline(), delay(), exec, fixture(), stop(), request() (+1 more)

### Community 26 - "guardrails-evidence.mjs"
Cohesion: 0.16
Nodes (19): absolute(), claims(), data(), digest(), canonical(), GuardrailsEvidence(), parentForTool(), session() (+11 more)

### Community 27 - "index.mjs"
Cohesion: 0.21
Nodes (19): absolute(), annotate(), bounded(), endpoint(), fingerprint(), canonical(), guardError(), isID() (+11 more)

### Community 28 - "recording-proxy.mjs"
Cohesion: 0.20
Nodes (17): bodyState(), boundedBody(), abort(), close(), data(), end(), errorEvent(), finish() (+9 more)

### Community 29 - "conversation_profiles.py"
Cohesion: 0.23
Nodes (8): main(), _area(), _native(), _safe_file(), setup_components(), _sha(), verify_components(), _write_file()

### Community 30 - "after"
Cohesion: 0.10
Nodes (21): regressions/promptfoo/cases.json, regressions/promptfoo/config.json, regressions/promptfoo/offline.cjs, regressions/promptfoo/provider.py, src/guardrails_local/action_evidence.py, src/guardrails_local/conversation_profiles.py, src/guardrails_local/promptfoo_runner.py, src/guardrails_local/quality_pipeline.py (+13 more)

### Community 31 - "peerDependenciesMeta"
Cohesion: 0.10
Nodes (21): optional, optional, optional, optional, peerDependenciesMeta, optional, optional, @huggingface/transformers (+13 more)

### Community 32 - "json"
Cohesion: 0.29
Nodes (15): main(), _artifact_contract(), build_environment(), _canonical_hash(), checked_summary(), evaluation_command(), _fixed_cases(), install_runtime() (+7 more)

### Community 33 - "QualityControllerTests"
Cohesion: 0.13
Nodes (6): QualityControllerTests, worker(), worker(), QualityWorkerOutputTests, noisy_dependency(), worker_report()

### Community 38 - "verified_cli_run"
Cohesion: 0.12
Nodes (17): verified_cli_run, checked_at, errors, exit_code, failed, framework, global_installation, live_model_quality_verified (+9 more)

### Community 42 - "promptfoo/package.json"
Cohesion: 0.17
Nodes (11): @libsql/win32-x64-msvc, promptfoo, dependencies, @libsql/win32-x64-msvc, promptfoo, description, name, overrides (+3 more)

### Community 43 - "opencode-v2.test.mjs"
Cohesion: 0.23
Nodes (7): completedResponseFixture(), completionUsage, frame(), MODEL, sse(), start(), STATIC_UNVERIFIED_ERROR

### Community 44 - "argparse"
Cohesion: 0.23
Nodes (7): main(), _atomic_bytes(), configure(), _json_bytes(), main(), _read_object(), _policy()

### Community 46 - "npm_artifact"
Cohesion: 0.18
Nodes (11): pf, promptfoo, node, npm_artifact, bin, engines, integrity, license (+3 more)

### Community 47 - "peerDependencies"
Cohesion: 0.18
Nodes (11): peerDependencies, @huggingface/transformers, ibm-cloud-sdk-core, @ibm-cloud/watsonx-ai, @langfuse/client, @openai/agents, @openai/codex-security, playwright (+3 more)

### Community 48 - "os"
Cohesion: 0.16
Nodes (4): capture_snapshot(), _copy_prefix(), _local(), main()

### Community 50 - "python_api.py"
Cohesion: 0.43
Nodes (4): _binding_root(), check_python_apis(), _missing_call(), _python_fragment()

### Community 53 - "setup"
Cohesion: 0.60
Nodes (6): setup(), call(), context(), json(), request(), response()

### Community 55 - "v2/package.json"
Cohesion: 0.33
Nodes (5): main, name, private, type, version

## Knowledge Gaps
- **115 isolated node(s):** `@anthropic-ai/sdk`, `@apidevtools/json-schema-ref-parser`, `@hono/node-server`, `@inquirer/checkbox`, `@inquirer/confirm` (+110 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 631 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **20 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `import_text()` connect `import_text` to `codex_hook.py`, `fake_ollama`, `create_server`, `orchestrator.py`, `quality_pipeline.py`?**
  _High betweenness centrality (0.059) - this node is a cross-community bridge._
- **What connects `@anthropic-ai/sdk`, `@apidevtools/json-schema-ref-parser`, `@hono/node-server` to the rest of the system?**
  _115 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `manifest.json` be split into smaller, more focused modules?**
  _Cohesion score 0.015267175572519083 - nodes in this community are weakly interconnected._
- **Why does `HookTests` connect `HookTests` to `unittest`?**
  _High betweenness centrality (0.059) - this node is a cross-community bridge._
- **Should `codex_hook.py` be split into smaller, more focused modules?**
  _Cohesion score 0.05980952380952381 - nodes in this community are weakly interconnected._
- **Why does `npm_artifact` connect `npm_artifact` to `manifest.json`, `dependencies`, `peerDependencies`, `optionalDependencies`, `peerDependenciesMeta`?**
  _High betweenness centrality (0.033) - this node is a cross-community bridge._
- **Should `import_text` be split into smaller, more focused modules?**
  _Cohesion score 0.0526195378631892 - nodes in this community are weakly interconnected._