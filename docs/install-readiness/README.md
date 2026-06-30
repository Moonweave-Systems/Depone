# Install Readiness Smoke

This directory records a real source-install smoke artifact for Depone.

Re-run from a fresh clone or worktree:

```bash
python scripts/install_smoke.py --json
```

The expected result is `"decision": "pass"`. The smoke creates a temporary
virtualenv, installs Depone from the local source tree with `pip install
--no-deps`, runs the installed `depone doctor --json`, runs the installed
`python -m depone team-ledger --self-test`, and re-validates the committed cloud
lane team-ledger artifact.

Honest limit: this proves source installation in the observed environment. It
does not publish a package, install runtime dependencies, or claim PyPI
readiness.
