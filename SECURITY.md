# Security Policy

Depone is the non-executing verifier and evidence-contract source of truth. The
default `proofcheck` path re-derives structural and content-hash consistency
from persisted evidence bytes; the evidence-contract track verifies DSSE
signatures under a configured trust anchor when required. Depone never launches
workers, mutates worktrees, executes recipes, or calls live APIs.

```text
Depone verifies; witnessd executes; ORRO exposes the workflow.
```

## Supported Versions

Depone is pre-1.0. Only the latest published release is supported.

| Version        | Supported          |
| -------------- | ------------------- |
| 0.1.x (current) | Yes                 |
| DWM (legacy, retired dual-engine era) | No |
| Older / pre-release builds | No |

There is no LTS line yet. Once Depone reaches 1.0, this table will be
revisited with a real support window.

## Reporting a Vulnerability

Report privately through GitHub's private vulnerability reporting for this
repository: **Security → Report a vulnerability** on
[Moonweave-Systems/Depone](https://github.com/Moonweave-Systems/Depone). If
private vulnerability reporting is not enabled when you go to file a report,
open a minimal, non-sensitive placeholder issue asking a maintainer to enable
it, and hold the details until it is.

Do not open a public issue or pull request for a vulnerability report. Do not
post exploit details, sensitive evidence bundles, or signing material in any
public channel.

## Response Expectations

Depone is pre-1.0 and maintained without a formal SLA. Best effort: an
acknowledgement within a few business days of a private report. Timelines for
triage, fix, and release depend on severity and maintainer availability, and
will be communicated in the report thread as they firm up.

## Coordinated Disclosure

We ask for a reasonable embargo period while a fix or mitigation is prepared
and released. We will credit reporters in the fix notes unless the reporter
asks not to be named. Please do not publicly disclose details before a fix or
mitigation is available, or before we've agreed on a disclosure date.

## Severity Guidance

**High severity** — anything that lets Depone assert a verdict the evidence
does not support:

- **Verdict-soundness bugs**: the verifier returns `pass` or A2 assurance for
  evidence that should be `blocked` or `refuted`.
- **Canonical-hash or DSSE/signature verification bypass**: evidence that
  should fail hash or signature checks is accepted anyway.
- **Trust-root confusion**: a forged, copied, or stale verdict is accepted as
  if it were freshly and correctly derived.
- **Isolation / observer re-derivation gaps**: re-derivation accepts
  runner-writable observer paths instead of the isolated, tamper-evident
  paths it is supposed to require.
- **Fail-open paths**: any path that should fail-closed on missing,
  malformed, or ambiguous input instead proceeds as if the input were valid.

**Lower severity** — documentation errors, non-security bugs, CLI ergonomics,
error-message clarity, and similar issues. File these as normal (public)
issues rather than security reports, unless they hint at one of the high
severity categories above.

## Secret & Evidence Handling

Do not include secrets, private keys, signing material, tokens, or live
credentials in a report. If a report needs to demonstrate a problem with real
evidence, prefer evidence paths and redacted excerpts over raw bundles or
full command output. Secret-looking material in a report is not, by itself,
proof of anything — describe what the bytes show and how to reproduce the
derivation.

## Depone Boundary

Depone is non-executing. It does not:

- run workers or execute verification recipes,
- mutate worktrees,
- call live MCP servers, SaaS APIs, databases, or other external services,
  or
- approve merges.

Depone only decides what persisted evidence bytes support, offline, using its
own re-derivation. `proofcheck` checks structure and content-hash consistency;
the evidence-contract track also checks DSSE signatures under a configured
trust anchor when required. Its assurance vocabulary (A0 / A1 / A2) reflects
what was actually re-derived from those bytes — nothing else counts as evidence.

Security reports must not ask Depone to reinterpret missing, failed, stale,
or forged evidence as `pass`, and must not ask it to upgrade assurance based
on prose, model confidence, skill text, MCP tool output, or operator intent.
None of those are evidence Depone can verify; treating them as such would be
the vulnerability, not the fix.

## Out of Scope

- Requests to treat wrapper artifacts, run reports, handoff prose, or agent
  session transcripts as proof of anything Depone hasn't independently
  re-derived from the applicable persisted evidence bytes and checks.
- Theoretical gaps already tracked on the roadmap, such as AAL-4 assurance
  or transparency-log support, unless you can show a concrete exploitable
  path today.
- Bugs in the witnessd runtime (the execution engine) or in third-party
  adapters/integrations, rather than in Depone's own verification logic.
  Report those against the relevant repository instead.
- General reliability, performance, or usability issues with no security
  impact — file these as normal issues.
