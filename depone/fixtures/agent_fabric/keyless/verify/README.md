# Synthetic keyless verification fixture

These pinned bytes are generated once by
`tests/_gen/gen_keyless_verify_fixtures.py`. They use a synthetic P-256 Fulcio
CA and leaf, an Ed25519 transparency-log key, a real Sigstore Bundle v0.3 JSON
shape, a Rekor DSSE v0.0.1 canonicalized body, an RFC 6962 inclusion proof, a
signed checkpoint, and a signed entry timestamp.

`legacy-issuer-bundle.json` exercises Fulcio's deprecated raw-string issuer OID
`1.3.6.1.4.1.57264.1.1`; the valid bundle uses the current DER UTF8String OID
`1.3.6.1.4.1.57264.1.8`.

The identity policy is pinned to:

- issuer: `https://oauth2.sigstore.dev/auth`
- subject/SAN: `octocat@example.com`

These are realistic federated values for a GitHub-associated human identity.
The issuer is deliberately not the literal string `github`: public-good Fulcio
uses Sigstore's OAuth/Dex issuer for this flow, while the SAN carries the
GitHub-associated email identity.

The CA and log are synthetic stand-ins only. Verification is entirely offline;
no fixture names or URLs are contacted.
