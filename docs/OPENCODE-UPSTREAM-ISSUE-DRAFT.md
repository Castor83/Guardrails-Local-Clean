# OpenCode upstream issue draft

Local draft only. No issue has been submitted. The proposed maintainer reproducer below has not been run as a full OpenCode test by this diagnostic harness.

## Proposed title

PowerShell legacy parser truncates an exact shell permission resource at `--test-reporter=tap` in v2.1.4

## Summary

For the command string `node --test --test-reporter=tap fail.test.mjs`, the PowerShell legacy WASM parsing path yields the permission resource `node --test --test-reporter`. With a deny-all rule followed by an exact allow for the original command, the upstream pure permission evaluator therefore returns `deny`. The complete resource produced by the portable scanner matches the exact allow.

This is a narrowly measured parser/permission compatibility report. The existing upstream compatibility test already documents a related difference for `git --flag=value`, so this behavior may be known. I am not presenting it as a new security vulnerability or claiming that every option containing `=` is affected.

## Version and diagnostic environment

- OpenCode tag: `v2.1.4`, resolved to commit [`68bc26b7da1990ce10ffecfbc1e09eb13aa5d824`](https://github.com/anomalyco/opencode/commit/68bc26b7da1990ce10ffecfbc1e09eb13aa5d824).
- PowerShell grammar: `tree-sitter-powershell@0.25.10`.
- Parser runtime: `web-tree-sitter@0.25.10`.
- Diagnostic runtime: Node.js `v24.20.0`; TypeScript `5.9.3` was used to extract/transpile the upstream source expressions.
- Shell selection for the measured legacy extraction: PowerShell (`powershell.exe`).

The grammar/runtime package tarball integrity values matched the pinned OpenCode lockfile. The relevant parser, portable scanner, permission evaluator, and wildcard matcher source bytes were compared with the immutable commit and matched. This does not establish byte identity with assets embedded in a desktop executable.

## Minimal input and rules

Treat this as input to the parser; no test file or execution of the command is needed to inspect its permission resource:

```text
node --test --test-reporter=tap fail.test.mjs
```

The relevant rule order is:

```json
[
  { "action": "*", "resource": "*", "effect": "deny" },
  {
    "action": "shell",
    "resource": "node --test --test-reporter=tap fail.test.mjs",
    "effect": "allow"
  }
]
```

The measured evaluator used an existing ruleset containing these rules in this order. Its additional read/browser rules do not match this shell request; the two rules above isolate the relevant matching behavior.

## Minimal maintainer reproduction

These are proposed checks against the upstream test environment, not a claim that this harness ran the complete public `ShellParse.scan` API or OpenCode host:

1. Use the pinned commit with its WASM assets available and select `powershell.exe` or `pwsh`. Ensure `ShellParse.scan` takes its legacy WASM branch; an empty Bash WASM mapping selects the portable fallback instead.
2. Parse the input above with `ShellParse.scan(command, "powershell.exe", "C:/fixture")`, using the same `Effect.runPromise` pattern as the existing compatibility test.
3. Inspect `commands[0].resource`, then pass that resource to `Permission.evaluate("shell", resource, rules)` with the ordered rules above.
4. Compare with `ShellParse.scan(command, "powershell.exe", "C:/fixture", { portable: true })` and evaluate its complete resource against the same rules.

## Expected and measured actual behavior

Expected: preserve the complete shell command as the permission resource for this input, allowing the exact allow rule to match. If the legacy parser cannot analyze it completely, explicitly report that condition rather than silently evaluating a shortened resource.

Measured actual behavior:

| Parsing path | Resource | Pure permission result |
| --- | --- | --- |
| Legacy PowerShell grammar + upstream extraction | `node --test --test-reporter` | `deny` |
| Portable scanner comparison | `node --test --test-reporter=tap fail.test.mjs` | `allow` |

The legacy grammar returned a tree with `rootNode.hasError === true`. The legacy extraction walks descendant `command` nodes and uses their text; in this case the command node ends before `=tap` and the trailing filename. The resulting saved prefix was `node *`; this report does not test granting or persisting that prefix.

As a control, the same legacy diagnostic returned `git --flag` for `git --flag=value`, matching the existing upstream fixture.

## What was actually verified

The diagnostic loaded the real pinned PowerShell grammar WASM with the real pinned `web-tree-sitter` runtime. It extracted the exact legacy `reduce` expression and its required helpers from the upstream TypeScript AST, then evaluated the resulting resource using the actual upstream pure `Permission.evaluate` and `Wildcard.match` functions. It did not approximate the parsing behavior with a hand-written tokenizer.

The portable resource was reused from an earlier standalone measurement of the pinned upstream `ShellScan.scanPowerShell` source. Only its permission evaluation was performed again in the later comparison; a fresh full portable `ShellParse.scan` run was not performed there.

No OpenCode host, model client, shell command from the input string, or fixture test was executed by this diagnostic. Native session permissions, saved-rule orchestration, hooks, and desktop execution were not exercised. An earlier desktop observation did not record its evaluated resource, so this diagnostic must not be treated as proof of that historical resource or its complete failure cause. No binary comparison of the downloaded package WASM with a desktop-embedded asset was performed.

## Existing upstream coverage and public sources

The fixture named `native preserves complete PowerShell flag=value resources` in the existing [compatibility test](https://github.com/anomalyco/opencode/blob/68bc26b7da1990ce10ffecfbc1e09eb13aa5d824/packages/core/test/shell-parse-compatibility.test.ts#L218-L224) explicitly expects legacy `git --flag` versus portable `git --flag=value`. This report adds the concrete consequence for an exact allow rule on the Node test command. Please treat it as a possible known limitation or follow-up to that coverage.

- [Legacy resource extraction and parser selection](https://github.com/anomalyco/opencode/blob/68bc26b7da1990ce10ffecfbc1e09eb13aa5d824/packages/core/src/shell/parse.ts#L163-L206).
- [Portable scanner](https://github.com/anomalyco/opencode/blob/68bc26b7da1990ce10ffecfbc1e09eb13aa5d824/packages/core/src/shell/scan.ts).
- [Pure permission evaluator](https://github.com/anomalyco/opencode/blob/68bc26b7da1990ce10ffecfbc1e09eb13aa5d824/packages/core/src/permission.ts#L74-L84) and [wildcard matcher](https://github.com/anomalyco/opencode/blob/68bc26b7da1990ce10ffecfbc1e09eb13aa5d824/packages/core/src/util/wildcard.ts).
- [Pinned core dependencies](https://github.com/anomalyco/opencode/blob/68bc26b7da1990ce10ffecfbc1e09eb13aa5d824/packages/core/package.json#L135-L136) and [lockfile](https://github.com/anomalyco/opencode/blob/68bc26b7da1990ce10ffecfbc1e09eb13aa5d824/bun.lock).
- Registry metadata: [tree-sitter-powershell 0.25.10](https://registry.npmjs.org/tree-sitter-powershell/0.25.10), [web-tree-sitter 0.25.10](https://registry.npmjs.org/web-tree-sitter/0.25.10).

Could the Node input above be added to the compatibility/permission regression coverage, and could maintainers clarify the intended treatment of an error-containing legacy tree when its command resource is incomplete?
