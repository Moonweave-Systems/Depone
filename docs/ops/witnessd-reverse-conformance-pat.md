# witnessd reverse-conformance PAT

Depone CI runs a reverse-conformance job against the witnessd repository. Until
witnessd is public, that job needs an operator-created read-only token.

Expected GitHub Actions secret:

```text
WITNESSD_REVERSE_CONFORMANCE_PAT
```

Token requirements:

- GitHub fine-grained personal access token
- Resource owner: `Moonweave-Systems`
- Repository access: selected repository `witnessd` only
- Repository permission: `Contents: Read-only`
- Metadata: read-only, automatically included by GitHub
- No write permissions
- Expiration: operator policy, recommended 90 days or less

Registration:

1. Open `Moonweave-Systems/Depone`.
2. Go to Settings -> Secrets and variables -> Actions.
3. Add repository secret `WITNESSD_REVERSE_CONFORMANCE_PAT`.
4. Paste the token value.
5. Re-run the `witnessd reverse conformance` CI job.

The workflow consumes the token only through `http.extraheader` during
`git clone`; the token must never be committed, printed, or stored in fixtures.
