# Depone Run Receipt Front Door

Slice: `depone-run-receipt-frontdoor`

`depone run` / `evidence-run` now writes `runner-receipt.json` when the
observer launches a uid runner with `--runner-user`. The receipt is included as
a rehashable in-toto statement subject in `evidence-bundle.json` and is
reflected in the OTel GenAI-shaped root span. This does not raise assurance by
itself.

Real machine artifacts are committed under
`docs/depone-run-receipt-frontdoor/`:

- `capture-manifest.json`
- `observer-capture.json`
- `runner-receipt.json`
- `runner-transcript.json`
- `evidence-bundle.json`
- `ingest-verdict.json`
- `evidence-run-summary.json`

The committed capture is A2 because the observer launched the runner as uid
`1002`, the observer uid was `1001`, and the recorded isolation boundary was
true.

Re-validate the committed artifacts:

```bash
python3 - <<'PY'
import json
from depone.agent_fabric.capture_bridge import validate_capture_manifest
from depone.agent_fabric.evidence_substrate import DIGEST_MODE_CANONICAL_JSON, ingest_external_evidence, validate_statement_for_capture
from depone.agent_fabric.paired_run import validate_runner_receipt
root = "docs/depone-run-receipt-frontdoor"
m = json.load(open(f"{root}/capture-manifest.json"))
b = json.load(open(f"{root}/evidence-bundle.json"))
r = json.load(open(f"{root}/runner-receipt.json"))
capture_errors = validate_capture_manifest(m)
runner_errors = validate_runner_receipt(r)
statement_errors = validate_statement_for_capture(b["statement"], m, runner_receipt=r)
ingest = ingest_external_evidence(
    b["dsse_envelope"],
    {
        "depone-capture-manifest": f"{root}/capture-manifest.json",
        "source_fixture": "depone/fixtures/agent_fabric/reference_adapter_shell.json",
        "observer_capture": f"{root}/observer-capture.json",
        "runner_receipt": f"{root}/runner-receipt.json",
    },
    artifact_digest_modes={
        "depone-capture-manifest": DIGEST_MODE_CANONICAL_JSON,
        "source_fixture": DIGEST_MODE_CANONICAL_JSON,
        "observer_capture": DIGEST_MODE_CANONICAL_JSON,
        "runner_receipt": DIGEST_MODE_CANONICAL_JSON,
    },
    otel_spans=b["otel_spans"],
)
subjects = {item["name"]: item["digest"]["sha256"] for item in b["statement"]["subject"]}
print("assurance        :", m.get("assurance"))
print("capture errors   :", capture_errors)
print("runner errors    :", runner_errors)
print("statement errors :", statement_errors)
print("ingest decision  :", ingest.get("decision"))
print("verified subjects:", ingest.get("verified_subject_count"), "/", len(ingest.get("subject_results", [])))
print("runner subject   :", "runner_receipt" in subjects)
print("boundary         :", m.get("isolation", {}).get("boundary"))
print("uids             :", m.get("isolation", {}).get("runner_uid"), "!=", m.get("isolation", {}).get("observer_uid"))
print("REVALIDATE_OK    :", m.get("assurance") == "A2-isolated-observed" and capture_errors == [] and runner_errors == [] and statement_errors == [] and ingest.get("decision") == "pass" and "runner_receipt" in subjects and m.get("isolation", {}).get("boundary") is True and m.get("isolation", {}).get("runner_uid") != m.get("isolation", {}).get("observer_uid"))
PY
```

Observed output:

```text
assurance        : A2-isolated-observed
capture errors   : []
runner errors    : []
statement errors : []
ingest decision  : pass
verified subjects: 4 / 4
runner subject   : True
boundary         : True
uids             : 1002 != 1001
REVALIDATE_OK    : True
```
