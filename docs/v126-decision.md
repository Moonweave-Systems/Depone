# V126 Decision

Status: accepted as first real paired-run capture. Date: 2026-06-28.

V126 now has one real direct-vs-governed Codex run instead of another
source-only contract layer.

Task: `v126-utf8-dogfood-evidence`.

Change requested from both arms: make the fixture reads in
`depone/agent_fabric/dogfood_evidence.py` explicitly use UTF-8 encoding.

Verification command for both arms:

```bash
python -m depone agent-fabric-dogfood-evidence --self-test
```

Observed outcome:

- Direct arm: Codex CLI exited 0, observer verification passed, touched only
  `depone/agent_fabric/dogfood_evidence.py`.
- Governed arm: Codex CLI exited 0, observer verification passed, touched only
  `depone/agent_fabric/dogfood_evidence.py`.
- Paired-run report decision: `paired-run-observed`.
- Governed-arm capture was promoted to
  `depone/fixtures/agent_fabric/capture_manifest_v126_governed_utf8.json`.
- `agent-fabric-paired-evidence --self-test` now derives dogfood evidence from
  that observed capture manifest rather than an inline fabricated dogfood dict.

Boundary:

- This is n=1 local evidence, not a superiority claim.
- The run used a throwaway isolated worktree.
- On this Windows host, `codex exec --sandbox workspace-write` failed before the
  governed run could apply a patch, so the accepted runner receipt records the
  `danger-full-access` fallback. That fallback is diagnostic only and does not
  raise assurance, approve public claims, or weaken the requirement that Depone
  remains the observer rather than the executor.

Decision:

Accept V126 as the first measured rung for connecting Codex as a local agent
runner under Depone observation. Continue with the V127 honesty fix and V128
evidence-substrate work only under the same rule: executed evidence first,
claims second.
