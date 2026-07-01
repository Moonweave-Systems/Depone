# Team Merge Attempt Receipt

`python3 -m depone team-merge-attempt` derives fan-in evidence from a real
`git merge --no-commit --no-ff` attempt in a disposable worktree by default. It
writes `merge-attempt.json` with the base commit, head commits, merged files,
conflict files, git exit code, and cleanup state.

Use it before Team Ledger fan-in when passed lanes overlap:

```bash
python3 -m depone team-merge-attempt \
  --repo . \
  --base <base_sha> \
  --head <head_sha> \
  --out docs/team-merge-attempt/merge-attempt.json \
  --json
```

Boundary:

- The command runs a git merge attempt to observe machine facts.
- It refuses dirty in-place target worktrees unless explicitly allowed.
- It uses a disposable worktree unless `--in-place` is selected.
- It does not launch agents.
- It does not call live models.
- It does not approve merges.
- It does not raise assurance.

Team Ledger accepts this `depone-team-merge-attempt` receipt as a merge receipt
source for overlapping passed lanes while preserving compatibility with the
older `team-ledger-merge-receipt` command artifact.
