// Keelplane reusable template: research / design orchestration.
//
// Proven pattern (figure-agent "Illustrator Hand" dogfood, n=1 win):
//   Scope -> fan-out research -> BARRIER synthesis -> adversarial-verify-AGAINST-SOURCE -> compose doc
//
// Why this exists: turning a Keelplane blueprint into a runnable Workflow script
// was hand-coded each time and broke twice on JS parse errors. This template is
// syntax-validated and parameterized ENTIRELY through `args` -- you should not
// need to edit the JS. Run it with:
//
//   Workflow({ scriptPath: ".../templates/research-orchestration.workflow.mjs",
//              args: {
//                question: "the research/design question",          // REQUIRED
//                sources:  [ "path/to/source.py", "docs/spec.md" ], // REQUIRED ground truth to verify against
//                angles:   [ { key: "perf", prompt: "..." } ],      // OPTIONAL; derived from `question` if omitted
//                outPath:  "where/to/write/design-doc.md",          // OPTIONAL; doc is also returned
//                docKind:  "design document",                       // OPTIONAL label for the final artifact
//                verifyBatchSize: 8 } })                            // OPTIONAL; claims per verifier (default 8)
//
// The script RETURNS { doc, confirmed, partial, refuted, unverified, uncovered, claimCount, angles }.
// The caller (you, the orchestrator) writes `doc` to `args.outPath` if set --
// keeping the workflow pure keeps it resumable and cacheable.
//
// Runtime requirement: the verify phase reads `args.sources` directly, so the
// workflow subagent must have read access to them (Read/Grep for local files,
// WebFetch for urls). Pass sources the agents can actually open.
//
// Enforcement note: the verification discipline is enforced in CODE where it
// matters -- a "confirmed"/"partially-supported" verdict with no evidence locator
// is downgraded to "unverified"; verdicts for claim ids that were never in the
// draft are dropped; duplicate verdicts are deduped (most-conservative wins). What
// stays prompt-enforced (a known limit): whether the final prose silently reuses a
// refuted claim's substance -- the composer is instructed not to, but that is not
// machine-checked.

export const meta = {
  name: 'research-orchestration',
  description: 'Fan-out research, synthesize, adversarially verify claims against source, compose a doc',
  whenToUse: 'Multi-angle research or design questions where claims must be checked against real source/data before they enter a doc',
  phases: [
    { title: 'Scope', detail: 'derive research angles from the question (skipped if angles supplied)' },
    { title: 'Research', detail: 'one worker per angle, each returns checkable claims' },
    { title: 'Synthesize', detail: 'barrier: merge all findings into a draft + flat claim list' },
    { title: 'Verify', detail: 'adversarial verify-against-source; verifiers batch claims (one source read per batch)' },
    { title: 'Compose', detail: 'assemble the final doc from confirmed claims; flag refuted/unverified/uncovered' },
  ],
}

// ---- input contract -------------------------------------------------------

// `args` may arrive as a parsed object OR as a JSON string. Normalize to an
// object; a non-JSON string (e.g. a bare question) gets a clear error, not a
// cryptic SyntaxError.
let input
if (typeof args === 'string') {
  try {
    input = JSON.parse(args || '{}')
  } catch {
    throw new Error('research-orchestration: args was passed as a string that is not valid JSON -- pass an object {question, sources, ...}')
  }
} else {
  input = args || {}
}

const question = input.question
// Keep only usable string sources; a non-string item would render as "[object
// Object]" into the verifier prompt and silently break the against-source check.
const rawSources = Array.isArray(input.sources) ? input.sources : []
const sources = rawSources.filter((s) => typeof s === 'string' && s.trim())
const docKind = input.docKind || 'design document'
// Claims per verifier (one source read per batch). Coerce robustly: a finite
// integer >=1, else 8 (a 0/negative size would make chunk() loop forever; a
// non-finite size would collapse all claims into one verifier).
const batchN = Math.floor(Number(input.verifyBatchSize))
const verifyBatchSize = Number.isFinite(batchN) && batchN >= 1 ? batchN : 8

// Accept angles as objects {key, prompt, why} or bare strings; normalize, then
// drop anything that is not a usable {key, prompt} so a malformed element cannot
// leak `undefined` into prompts or crash `angles.map(a => a.key)`.
const suppliedAngles = (Array.isArray(input.angles) ? input.angles : [])
  .map((a, i) => (typeof a === 'string' ? { key: `angle-${i + 1}`, prompt: a } : a))
  .filter((a) => a && typeof a.key === 'string' && typeof a.prompt === 'string')

if (typeof question !== 'string' || !question.trim()) {
  throw new Error('research-orchestration: args.question (non-empty string) is required')
}
if (rawSources.length !== sources.length) {
  log(`WARNING: dropped ${rawSources.length - sources.length} non-string source(s); ${sources.length} usable source(s) remain`)
}
if (sources.length === 0) {
  // Against-source verification is the whole point. Without ground truth the
  // verify phase can only check plausibility, which is the weak form we reject.
  log('WARNING: no usable sources -- verifiers have no ground truth, so every claim will come back "unverified". Supply real files/data/urls for the high-value against-source check.')
}

// ---- schemas (validated at the tool layer; agents retry on mismatch) ------

const ANGLES_SCHEMA = {
  type: 'object',
  required: ['angles'],
  properties: {
    angles: {
      type: 'array',
      minItems: 1,
      items: {
        type: 'object',
        required: ['key', 'prompt'],
        properties: {
          key: { type: 'string', description: 'short kebab-case label' },
          prompt: { type: 'string', description: 'what this worker should investigate' },
          why: { type: 'string', description: 'why this angle matters to the question' },
        },
      },
    },
  },
}

const FINDINGS_SCHEMA = {
  type: 'object',
  required: ['angle', 'claims'],
  properties: {
    angle: { type: 'string' },
    claims: {
      type: 'array',
      items: {
        type: 'object',
        required: ['id', 'statement'],
        properties: {
          id: { type: 'string', description: 'stable id, unique within this angle, e.g. perf-1' },
          statement: { type: 'string', description: 'a single checkable factual claim' },
          support: { type: 'string', description: 'reasoning or evidence the worker has for it' },
          source_hint: { type: 'string', description: 'where this could be verified (file, dataset, url)' },
        },
      },
    },
    notes: { type: 'string', description: 'context that is not itself a checkable claim' },
  },
}

const DRAFT_SCHEMA = {
  type: 'object',
  required: ['sections', 'claims'],
  properties: {
    sections: {
      type: 'array',
      minItems: 1,
      items: {
        type: 'object',
        required: ['title', 'body'],
        properties: {
          title: { type: 'string' },
          body: { type: 'string', description: 'prose; reference claims by their id' },
        },
      },
    },
    claims: {
      type: 'array',
      description: 'flat, de-duplicated list of every checkable claim the doc relies on; ids MUST be unique',
      items: {
        type: 'object',
        required: ['id', 'statement', 'origin_angle'],
        properties: {
          id: { type: 'string', description: 'stable id unique across the whole draft' },
          statement: { type: 'string' },
          source_hint: { type: 'string' },
          origin_angle: { type: 'string', description: 'the angle key this claim came from (provenance)' },
        },
      },
    },
    open_questions: { type: 'array', items: { type: 'string' } },
  },
}

const VERDICT_SCHEMA = {
  type: 'object',
  required: ['claim_id', 'verdict', 'reason'],
  properties: {
    claim_id: { type: 'string' },
    verdict: { type: 'string', enum: ['confirmed', 'partially-supported', 'refuted', 'unverified'] },
    evidence: {
      type: 'object',
      properties: {
        locator: { type: 'string', description: 'file:line, dataset key, or url actually read' },
        excerpt_or_value: { type: 'string', description: 'the exact text/value found at the locator' },
      },
    },
    reason: { type: 'string', description: 'why the ground truth does or does not support the claim' },
  },
}

const VERDICT_BATCH_SCHEMA = {
  type: 'object',
  required: ['verdicts'],
  properties: {
    verdicts: { type: 'array', items: VERDICT_SCHEMA },
  },
}

// ---- prompts --------------------------------------------------------------

const sourceList = sources.length ? sources.map((s) => `- ${s}`).join('\n') : '(none supplied)'

const scopePrompt = `You are scoping a research/design question into independent investigation angles.

QUESTION:
${question}

${sources.length ? `Ground-truth sources that exist to check claims against:\n${sourceList}` : 'No ground-truth sources were supplied.'}

Decompose the question into 3-6 distinct, non-overlapping angles. Each angle is a
separate surface or perspective a worker can investigate without coordinating with
the others. Avoid angles that just restate the question. Return the angles only.`

const researchPrompt = (angle) => `You are one research worker in a fan-out. Investigate ONLY your angle.

OVERALL QUESTION:
${question}

YOUR ANGLE (${angle.key}):
${angle.prompt}
${angle.why ? `Why it matters: ${angle.why}` : ''}

${sources.length ? `Ground-truth sources available (read them when relevant):\n${sourceList}` : ''}

Return discrete, CHECKABLE claims -- each a single factual statement another agent
could later confirm or refute against a source. Do not pad with generalities.
For every claim give a source_hint pointing at where it could be verified.
Do NOT label anything "verified" or "confirmed" -- that is a later phase's job.`

const synthPrompt = (findings) => `You are the synthesis barrier. You have ALL fan-out findings below.

OVERALL QUESTION:
${question}

FINDINGS (JSON):
${JSON.stringify(findings, null, 2)}

Produce a coherent draft ${docKind}: ordered sections that answer the question,
referencing claims by id. Then produce a flat \`claims\` list of every checkable claim
the draft relies on. Rules for the claims list:
- Each claim id MUST be unique across the whole draft.
- Set origin_angle to the angle the claim came from.
- Merge duplicate claims from different angles into ONE id (keep the clearest
  statement + a source_hint).
- Do NOT invent claims that no worker reported.
Carry forward unresolved tensions as open_questions.`

const verifyBatchPrompt = (claimsChunk) => `You are an INDEPENDENT adversarial verifier. Your job is to REFUTE these claims, not
rubber-stamp them. You did not produce them and owe them no benefit of the doubt.

Read the ground-truth sources ONCE, then judge EVERY claim below against them.

GROUND-TRUTH SOURCES you may read:
${sourceList}

CLAIMS (JSON):
${JSON.stringify(claimsChunk.map((c) => ({ id: c.id, statement: c.statement, source_hint: c.source_hint })), null, 2)}

Rules:
- Verify against GROUND TRUTH, not against the producer's reasoning. Open the actual
  source/data/artifact yourself, read the relevant part, and cite it in evidence
  (locator = file:line / key / url you ACTUALLY read; excerpt_or_value = the exact
  text or number found there). The source_hint is the producer's guess -- do not
  trust it; confirm by reading.
- Any "verified"/"confirmed" wording attached to a claim is itself a claim to refute,
  not a fact.
- Verdicts:
  - "confirmed": you read a source whose content fully supports the claim. REQUIRES
    a real evidence locator + excerpt.
  - "partially-supported": the source supports only a NARROWER version (the claim is
    overstated, over-generalized, or right-in-part). REQUIRES evidence; in reason,
    state exactly which part is unsupported and the narrower version that holds.
  - "refuted": the ground truth contradicts the claim.
  - "unverified": no supplied source lets you check it (default when unsure or when
    no sources were supplied).
- A "confirmed" or "partially-supported" verdict WITHOUT a real evidence locator is
  invalid and will be downgraded to "unverified" -- so always cite.
- Return EXACTLY ONE verdict per claim, each carrying the matching claim_id. Do not
  merge, skip, invent, or relabel claim ids.`

const composePrompt = (draft, ledger) => `You are composing the final ${docKind}.

OVERALL QUESTION:
${question}

DRAFT (sections + claims, JSON):
${JSON.stringify(draft, null, 2)}

VERIFICATION LEDGER (JSON: confirmed / partial / refuted / unverified / uncovered):
${JSON.stringify(ledger, null, 2)}

Write the final document in Markdown:
- Build the argument on CONFIRMED claims; cite each one's evidence locator inline.
- For PARTIALLY-SUPPORTED claims, assert ONLY the narrower supported version stated
  in the verdict's reason, and cite the locator. Never assert the overstated form.
- Treat REFUTED, UNVERIFIED, and UNCOVERED claims as NOT established: do not assert
  their content anywhere in the prose, even if it appears in the draft sections.
- Add a short "Unverified / open" section listing (i) refuted claims (with why),
  (ii) unverified claims, (iii) uncovered claims (ledger.uncovered -- no verdict
  because a verifier batch failed or skipped them; they were NOT checked), and
  (iv) open questions.
- End with a "Verification summary" line: counts of confirmed / partial / refuted /
  unverified / uncovered.
Return the Markdown document only -- no preamble.`

// ---- orchestration --------------------------------------------------------

phase('Scope')
let angles = suppliedAngles
if (!angles.length) {
  const scoped = await agent(scopePrompt, { schema: ANGLES_SCHEMA, label: 'scope', phase: 'Scope' })
  angles = (scoped && scoped.angles) || []
}
if (!angles.length) {
  throw new Error('research-orchestration: no angles to research (scoping failed or returned none)')
}
log(`${angles.length} angle(s): ${angles.map((a) => a.key).join(', ')}`)

phase('Research')
const findings = (await parallel(
  angles.map((a) => () =>
    agent(researchPrompt(a), { schema: FINDINGS_SCHEMA, label: `research:${a.key}`, phase: 'Research' })),
)).filter(Boolean)
if (findings.length < angles.length) {
  log(`WARNING: ${angles.length - findings.length}/${angles.length} research angle(s) failed -- synthesizing from the rest`)
}
if (!findings.length) {
  throw new Error('research-orchestration: every research worker failed -- nothing to synthesize')
}

phase('Synthesize')
// Barrier is justified: synthesis needs the COMPLETE finding set to de-duplicate
// claims across angles and resolve cross-angle tensions.
const draft = await agent(synthPrompt(findings), { schema: DRAFT_SCHEMA, label: 'synthesize', phase: 'Synthesize' })
if (!draft) {
  throw new Error('research-orchestration: synthesis failed (agent returned null) -- nothing to verify or compose')
}
const claims = draft.claims || []
if (!claims.length) {
  log('WARNING: synthesis produced 0 checkable claims -- the composed doc would rest on unverified prose')
}
log(`draft has ${(draft.sections || []).length} section(s) and ${claims.length} checkable claim(s)`)

phase('Verify')
// Batch claims so each verifier reads the sources once and judges several claims.
const chunk = (arr, size) => {
  const out = []
  for (let i = 0; i < arr.length; i += size) out.push(arr.slice(i, i + size))
  return out
}
const claimBatches = chunk(claims, verifyBatchSize)
const runBatch = (batch, i, suffix) =>
  agent(verifyBatchPrompt(batch), { schema: VERDICT_BATCH_SCHEMA, label: `verify:batch-${i + 1}${suffix}`, phase: 'Verify' })
const batchResults = await parallel(claimBatches.map((batch, i) => () => runBatch(batch, i, '')))
// Retry batches that failed (e.g. a transient API error) ONCE, so one blip does not
// drop a whole batch of claims unverified.
const failedIdx = batchResults.map((r, i) => (r ? -1 : i)).filter((i) => i >= 0)
if (failedIdx.length) {
  log(`retrying ${failedIdx.length} failed verify batch(es) once`)
  const retried = await parallel(failedIdx.map((i) => () => runBatch(claimBatches[i], i, '-retry')))
  failedIdx.forEach((origIdx, k) => {
    if (retried[k]) batchResults[origIdx] = retried[k]
  })
}
const droppedBatches = batchResults.filter((r) => !r).length
if (droppedBatches) {
  log(`WARNING: ${droppedBatches}/${claimBatches.length} verify batch(es) still failed after retry -- their claims stay UNVERIFIED, not silently confirmed`)
}

// Integrity pass over raw verdicts: (1) drop verdicts whose claim_id was never in
// the draft (hallucinated); (2) downgrade evidence-less confirmations so "confirmed"
// always means "checked against a cited source"; (3) dedupe to one verdict per
// claim, keeping the most CONSERVATIVE on conflict (never over-claim).
// CONTRACT: this logic mirrors scripts/keelplane_verdict_integrity.py (the
// model-agnostic core) + scripts/verdict_integrity_check.cjs; all three are pinned to
// the shared vectors in fixtures/verdict-integrity/cases.json. Keep them in sync.
const rawVerdicts = batchResults.filter(Boolean).flatMap((r) => Array.isArray(r.verdicts) ? r.verdicts : [])
const claimIds = new Set(claims.map((c) => c.id))
const conservativeRank = { refuted: 3, unverified: 2, 'partially-supported': 1, confirmed: 0 }
const byClaim = new Map()
let droppedVerdicts = 0
let downgraded = 0
for (const v of rawVerdicts) {
  if (!v || !claimIds.has(v.claim_id)) {
    droppedVerdicts++
    continue
  }
  if ((v.verdict === 'confirmed' || v.verdict === 'partially-supported') &&
      !(v.evidence && v.evidence.locator && v.evidence.excerpt_or_value)) {
    v.verdict = 'unverified'
    v.reason = `downgraded (no evidence locator/excerpt): ${v.reason || ''}`
    downgraded++
  }
  // Normalize any unexpected/missing verdict string to unverified, so it can never
  // vanish from both the buckets AND the uncovered list (we do not trust the schema
  // enum to be enforced on nested items).
  if (!(v.verdict in conservativeRank)) {
    v.reason = `normalized (unknown verdict "${v.verdict}"): ${v.reason || ''}`
    v.verdict = 'unverified'
  }
  const prev = byClaim.get(v.claim_id)
  if (!prev || conservativeRank[v.verdict] > conservativeRank[prev.verdict]) byClaim.set(v.claim_id, v)
}
if (droppedVerdicts) log(`dropped ${droppedVerdicts} verdict(s) addressing claim ids not in the draft (hallucinated)`)
if (downgraded) log(`downgraded ${downgraded} evidence-less confirmation(s) to unverified`)
const verdicts = [...byClaim.values()]

const confirmed = verdicts.filter((v) => v.verdict === 'confirmed')
const partial = verdicts.filter((v) => v.verdict === 'partially-supported')
const refuted = verdicts.filter((v) => v.verdict === 'refuted')
const unverified = verdicts.filter((v) => v.verdict === 'unverified')
// Claims with NO verdict at all (dropped batch, or a verifier that skipped them):
// a real coverage gap that must be disclosed downstream, not hidden.
const uncovered = claims.filter((c) => !byClaim.has(c.id))
log(`verify: ${confirmed.length} confirmed, ${partial.length} partial, ${refuted.length} refuted, ${unverified.length} unverified, ${uncovered.length} uncovered (no verdict)`)

phase('Compose')
const doc = await agent(composePrompt(draft, { confirmed, partial, refuted, unverified, uncovered }), {
  label: 'compose',
  phase: 'Compose',
})
if (!doc) {
  log('WARNING: compose returned null -- no document produced; returning the verification ledger only')
}

return { doc, confirmed, partial, refuted, unverified, uncovered, claimCount: claims.length, angles }
