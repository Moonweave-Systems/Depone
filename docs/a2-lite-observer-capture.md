# A2-Lite Observer Capture

`depone agent-fabric-observe` runs an observer-owned capture as a separate
process and writes observer artifacts outside the runner sandbox:

```bash
python -m depone agent-fabric-observe \
  --runner-sandbox /path/to/runner-worktree \
  --source-fixture-hash <hash> \
  --out /path/to/observer-owned/observer-capture.json \
  --log /path/to/observer-owned/verify-log.json \
  -- python -m unittest
```

The command refuses to write `--out` or `--log` inside `--runner-sandbox` and
records an `observer_independence` block in the observer capture. This is a real
process and directory separation step, but it is not tamper-proof against a
same-uid runner. It does not add a privilege boundary, does not create a new A2
assurance value, and manifests built from this capture remain
`A1-local-observed`.

This path records better observer architecture; it does not claim superiority
from one run, and n=1 remains n=1.

## Observer-Held HMAC Seal

`depone agent-fabric-observe --seal-key-file <path>` can write
`observer-capture.seal.json` beside the capture. The seal is HMAC-SHA256 over
the canonical capture bytes and uses an observer-held symmetric key that must
live outside the runner sandbox when supplied as a file. It provides keyed
integrity and authenticity to a holder of that key, and detects forgery by a
party without the key.

This is not a public signature, not A3 signing, and not forge-proof against a
same-uid runner that can read the key. Its strength depends on key custody.
Assurance remains `A1-local-observed`.

Full A2 privilege isolation through a distinct uid or container boundary, and
A3 signing, remain deferred.
