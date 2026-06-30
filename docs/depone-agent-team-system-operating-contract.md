# Depone Agent Team System Operating Contract

Status: planning document for the agent-team runtime.
Date: 2026-06-30.

This document defines what Depone should enforce when it becomes a control
plane for Codex, Claude Code, OpenCode, OMX/LazyCodex-style teams, shell
adapters, and future cloud runners. It is not a new capability claim. No agent
team is proven by this document alone; every claim still needs machine
artifacts that can be revalidated.

## 1. Target Shape

Depone should become the neutral evidence and control layer around agent teams:

- a leader decides the next bounded packet;
- one or more lanes execute under explicit role, adapter, and workspace
  contracts;
- each lane writes receipts, transcripts, changed-file facts, and verification
  output;
- Team Ledger fan-in decides whether lane evidence can continue;
- PR, merge, signing, isolation, and cloud facts become first-class artifacts;
- continuation happens only from validated artifacts, not from chat memory.

This keeps Depone distinct from the runners it controls. Codex, Claude Code,
OpenCode, OMX, LazyCodex, Copilot cloud agent, shell, or a future custom runner
can do the work. Depone records what happened, checks whether it matches the
contract, and refuses unsupported continuation.

## 2. External Benchmark Read

The current benchmark direction is cloud and PR oriented, but not purely cloud:

- OpenAI Codex can act from GitHub PR comments, review PRs, and start cloud
  tasks with PR context when mentioned.
- GitHub Copilot cloud agent works in a GitHub Actions-powered ephemeral
  environment, can research, plan, change a branch, run checks, and optionally
  open a PR. It also exposes custom instructions, custom agents, hooks, skills,
  MCP, logs, commits, and PR metrics.
- OpenAI's Agents SDK frames orchestration as either LLM-directed handoffs or
  code-owned flow. It treats orchestration, tool execution, approvals, and state
  as application responsibilities when the application owns the agent loop.
- Claude Code exposes hooks, skills, project instructions, subagents, worktree
  and PR workflows, and long-running context management surfaces.
- Anthropic's public guidance is still conservative: start simple, measure,
  and add multi-agent complexity only where it beats a simpler workflow.

Depone should benchmark against these surfaces as capabilities, not as brands:
cloud session receipts, PR artifacts, worktree isolation, instructions loaded,
hooks fired, tool permissions, model/adapter identity, logs, changed files,
verification commands, review findings, merge facts, and continuation decisions.

Reference surfaces checked on 2026-06-30:

- OpenAI Codex GitHub integration:
  <https://developers.openai.com/codex/integrations/github>
- OpenAI Agents SDK:
  <https://developers.openai.com/api/docs/guides/agents>
- OpenAI Agents SDK orchestration:
  <https://openai.github.io/openai-agents-python/multi_agent/>
- GitHub Copilot cloud agent:
  <https://docs.github.com/en/copilot/concepts/agents/cloud-agent/about-cloud-agent>
- Claude Code hooks:
  <https://docs.anthropic.com/en/docs/claude-code/hooks>
- Claude Code hooks guide:
  <https://docs.anthropic.com/en/docs/claude-code/hooks-guide>
- Anthropic, Building Effective AI Agents:
  <https://www.anthropic.com/research/building-effective-agents>
- Anthropic, Multi-Agent Research System:
  <https://www.anthropic.com/engineering/multi-agent-research-system>

## 3. Non-Negotiable Design Principles

### 3.1 Evidence beats prose

Markdown explains. JSON artifacts, receipts, hashes, transcripts, and validation
commands prove. A lane is not complete because an agent says it is complete. A
lane is complete only when its artifacts validate against the declared contract.

### 3.2 Roles are contracts, not personalities

Roles should constrain allowed tools, evidence obligations, output schema, and
trust boundary. They should not become prompt flavor, fictional hierarchy, or a
claim that more personas make work better.

### 3.3 Use the smallest capable topology

Single agent first. Multi-step loop only when one step is not enough. Multi-lane
team only when the task splits cleanly or a separate verifier/reviewer lane
materially improves safety. Cloud only when remote execution, PR workflow, or
local resource isolation is worth the operational cost.

### 3.4 Contracts must not reduce model capability

The contract should remove ambiguity and unsafe behavior, not make the model
rigid. Split guidance into three levels:

- hard rules: safety, evidence, destructive operations, secrets, public claims,
  permission gates, and stop conditions;
- defaults: good engineering habits such as search first, read before editing,
  use existing patterns, write focused tests, and keep diffs small;
- skills/runbooks: task-specific procedures loaded only when needed.

Do not push every good idea into a permanent system prompt. Inject only the
clauses needed by the current role, adapter, repo, and task, then record the
contract hash in the receipt.

## 4. Common Engineering Contract

Every lane should inherit this common contract unless an adapter cannot support
part of it. Unsupported clauses must be recorded as residual risk.

### 4.1 Discovery before edits

- Read the task packet, current branch state, nearby docs, and relevant code
  before editing.
- Use fast repo search first: `rg`, `rg --files`, `git grep`, or an available
  symbol/LSP query.
- Prefer existing helpers, command patterns, validators, and fixtures over new
  abstractions.
- Separate evidence from inference. If a fact comes from memory, chat, or a
  prior run, recheck it when cheap and risk-relevant.

### 4.2 Bounded implementation

- Keep one lane to one packet and one ownership boundary.
- Make minimal reversible diffs.
- Do not broaden into unrelated cleanup.
- Add an abstraction only when it removes real duplication, clarifies a contract,
  or matches an existing pattern.
- Do not add dependencies unless the packet explicitly authorizes it.

### 4.3 Verification discipline

- Define the claim before running verification.
- Run the smallest tests that can prove the changed behavior.
- Escalate to broader lint, typecheck, contract, smoke, browser, or integration
  checks when the blast radius requires it.
- Report exact commands and exact pass/fail output.
- If verification cannot run, record why and the next-best evidence.

### 4.4 Safety boundaries

- No destructive git commands unless explicitly authorized.
- No secrets, production systems, paid cloud resources, external messaging, or
  credentialed actions unless the task grants that authority.
- No arbitrary shell execution from model-generated strings.
- No worker launch without adapter capability detection and a launch receipt.
- No assurance upgrade without independently revalidatable facts.

### 4.5 Review and repair separation

- Reviewer lanes find bugs, regressions, missing tests, and overclaims.
- Reviewer lanes do not repair their own findings unless a separate repair
  packet is created.
- Verifier lanes report evidence, not product success.
- The leader integrates and owns final validation.

## 5. Role System

The existing V22 base roles remain the base vocabulary:

- `planner`: converts objective into packets, gates, budgets, and ownership;
- `explorer`: maps repo facts, runtime state, impact surface, and unknowns;
- `worker`: edits or runs one bounded packet;
- `reviewer`: finds correctness, regression, and missing-test risks;
- `verifier`: runs falsification, tests, smoke checks, and artifact validation;
- `operator`: summarizes state, blockers, and next safe action.

Future names should be specializations, not new ontology:

| Specialization | Base role | Added contract |
| --- | --- | --- |
| generalist coder | `worker` | default bounded edit/test packet |
| Python CLI developer | `worker` | stdlib, argparse, exit-code, fixture, and contract-test obligations |
| frontend developer | `worker` | responsive UI, visual verification, accessibility, screenshot evidence |
| infrastructure developer | `worker` | environment, shell, service, container, and rollback evidence |
| security reviewer | `reviewer` | secret, injection, permission, provenance, and supply-chain checks |
| test engineer | `verifier` | coverage gaps, regression tests, flaky-test notes, falsification output |
| integration maintainer | `operator` or `planner` | PR/check/merge evidence and branch hygiene |
| cloud runner observer | `explorer` or `verifier` | remote session facts, provider residuals, log/artifact validation |

A new specialization is allowed only when it changes at least one of:

- allowed tools;
- required evidence;
- output schema;
- trust boundary;
- validation command;
- measured benchmark outcome.

## 6. Adapter Contracts

Each adapter must declare capability before launch and write a receipt after
launch or block. Missing binary, missing auth, missing config, unsupported
workspace, or denied permission is a blocked artifact, not an implicit human
gate.

### 6.1 Shell adapter

Current Wave 3 shape:

- explicit JSON argv allowlist;
- no arbitrary shell string;
- command receipt with cwd, argv, exit code, transcript, and hashes;
- no live model;
- no team worker;
- no assurance upgrade by itself.

### 6.2 Codex local adapter

First real coding adapter candidate after Wave 3:

- detect `codex` binary, version, auth/config readiness, repo root, branch, and
  allowed sandbox/approval mode;
- block safely if any prerequisite is missing;
- launch only a bounded prompt packet;
- capture stdout, stderr, transcript, changed files, exit code, and verification
  commands;
- record loaded instruction files such as `AGENTS.md` when observable;
- keep provider superiority out of claims.

### 6.3 Claude Code local adapter

Add only after the Codex local adapter pattern is stable:

- detect `claude` binary, auth/config readiness, project instructions, hooks,
  and permitted tools;
- record hook configuration and hook execution artifacts when available;
- treat subagents as lane events with receipts, not as trusted summaries.

### 6.4 OpenCode adapter

Add only if local operator use justifies it:

- detect config, provider/model resolution, and cache state;
- record resolved model/provider facts in the receipt;
- block when config cannot be resolved without guessing.

### 6.5 OMX/LazyCodex-style team adapter

Depone should first observe this runtime before owning an equivalent runtime:

- bind worker claims to mailbox/task state;
- capture worker pane/task results as artifacts;
- validate task transitions, worktree boundaries, commits, tests, and shutdown;
- treat cross-lane conflicts as evidence events.

### 6.6 Cloud adapters

Cloud should be preferred when it gives better isolation, reproducibility, PR
traceability, or local resource relief. First support observed cloud lanes, then
owned cloud launch:

- observed cloud lane: validate provider-exported run facts, PR URL, base/head
  SHA, logs, checks, and residuals;
- owned cloud lane: only after setup recipe, permission, cost, secret, and
  artifact capture are contract-bound.

## 7. Team Runtime Model

The eventual native team loop should be:

1. `team-plan`: leader creates packets, roles, budgets, ownership, stop rules,
   and verification requirements.
2. `team-preflight`: validate paths, adapters, instructions, and capability.
3. `team-worktree-prep`: create or select isolated local workspaces when local.
4. `team-launch`: run one lane through one adapter and write a launch receipt.
5. `team-evidence-run`: capture lane evidence under observer control.
6. `team-next`: validate lane evidence and decide continue, blocked, or repair.
7. `team-review`: reviewer lane inspects artifacts and diff.
8. `team-repair`: bounded worker packet fixes accepted findings.
9. `team-fan-in`: Team Ledger validates all lane states and merge receipts.
10. `team-pr`: capture PR/check artifacts.
11. `team-attest`: sign evidence bundle when signing is configured.
12. `team-advance`: run at most one next packet, then stop.

Every step must be restartable from committed or local artifacts. A crashed
agent should not force the operator to reconstruct truth from chat.

## 8. Prompt And Contract Injection Model

Depone should avoid one giant global prompt. Use layered, hash-bound injection:

1. common engineering contract;
2. role contract;
3. adapter contract;
4. repo contract from files such as `AGENTS.md`, `CLAUDE.md`, or Depone docs;
5. packet-specific instructions;
6. verification contract.

Receipts should record:

- contract ids and hashes;
- prompt/instruction files loaded when observable;
- role id and specialization id;
- adapter id and version/capability facts;
- allowed tools and denied tools;
- evidence obligations;
- residual risks.

The model may still reason freely inside those boundaries. The contract should
not prescribe every search query, every variable name, or every design choice.

## 9. Machine-Readable Surfaces To Add

Add these only when needed by the next implementation slice:

- `packaging/depone-agent-operating-contract.json`: minimal machine contract
  identity, boundary flags, V22 worker-role binding, and role-registry hash.
- `packaging/depone-role-specializations.json`: thin role specializations over
  V22 base roles.
- `depone agent-contract inspect`: print resolved common + role + adapter
  contract for a lane.
- `depone agent-contract validate`: validate a receipt's declared contract ids
  and hashes.
- `agent_contract_hash` fields on launch receipts and Team Ledger lane entries.

Do not add these as source-only scaffolding. Add them when the next adapter PR
can emit and revalidate them.

## 10. Implementation Order

### Now: finish Wave 3

Merge and review PR #51, the single-lane shell launch receipt. This gives the
first non-model command launch receipt and transcript fixture.

### Next: contract hash slice

Before real Codex/Claude launch, add the minimal contract surface needed for
adapter receipts:

- define the common engineering contract as machine-readable JSON;
- bind existing V22 role ids to a lane receipt field;
- hash the resolved contract and store the hash in the shell lane fixture;
- validate that committed fixture hash matches the contract JSON.

For the current shell-lane fixture, the minimal machine-readable contract lives
under `packaging/depone-agent-operating-contract.json`. It binds the receipt to
V22 base role `worker` and records the contract facts in `receipt.json` as
`agent_contract_hash` plus the `agent_contract` object.

This makes later Codex/Claude adapter launches auditable without making the
system prompt huge.

### Then: Codex local capability detection

Add one PR that detects Codex local readiness and emits blocked/pass capability
artifacts. It should not launch a coding task until capability detection is
boring.

### Then: Codex local launch receipt

Launch one bounded Codex packet only after detection passes. Capture transcript,
instruction facts, changed files, verification, and `evidence-next`.

### Then: PR/check evidence fan-in

Bind lane results to PR artifacts and check status before any merge automation.

### Later: cloud-owned lanes

Start with observed cloud lanes, then add owned cloud launch when setup,
permission, cost, and artifact capture are deterministic enough to validate.

## 11. Stop Conditions

Stop and report blocked when:

- a required artifact is missing or cannot be regenerated from committed inputs;
- an adapter cannot prove its capability facts;
- a lane would need secrets, paid resources, or external production authority;
- two lanes need the same owned files without a merge plan;
- a claim depends on prose instead of receipts and hashes;
- verification fails;
- the next step would upgrade assurance without a revalidator.

## 12. Success Criteria

This operating contract is doing its job when:

- agents stop less often for ordinary safe steps;
- hard stops happen only at real destructive, credentialed, or unverified
  boundaries;
- every lane can be resumed or audited from artifacts;
- reviewers can revalidate the committed evidence without trusting the author;
- role specialization improves evidence or outcomes rather than prompt theater;
- local and cloud runners are interchangeable adapter surfaces under the same
  ledger.
