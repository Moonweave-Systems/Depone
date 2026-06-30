# Cloud Lane Artifact Fixture

This directory is a re-validatable fixture for Team Ledger cloud lane artifact
validation. It is not a live cloud-provider run and it does not attest provider
runtime isolation.

The fixture proves only that `team-ledger` can bind a passed `env_kind=cloud`
lane to local machine JSON with adapter kind, external run id, repo, base/head
SHA, an `evidence_next_verdict` SHA256, and an honest boundary statement:
`observed_external_facts_only=true` and `attests_runtime_isolation=false`.

Revalidate from the repo root:

```bash
python3 -m depone team-ledger --ledger docs/cloud-lane-artifact/team-ledger.json --json
```
