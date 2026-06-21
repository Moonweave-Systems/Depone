// JS reference for the verdict-integrity pass, run against the SHARED test vectors
// (fixtures/verdict-integrity/cases.json) so it cannot drift from the Python core
// (scripts/keelplane_verdict_integrity.py). The orchestration template
// (templates/research-orchestration.workflow.mjs) embeds this same logic and must
// match this contract. Run: node scripts/verdict_integrity_check.cjs
const fs = require('fs')
const path = require('path')
const CASES = path.join(__dirname, '..', 'fixtures', 'verdict-integrity', 'cases.json')

const CONSERVATIVE_RANK = { refuted: 3, unverified: 2, 'partially-supported': 1, confirmed: 0 }

const hasEvidence = (v) => !!(v.evidence && v.evidence.locator && v.evidence.excerpt_or_value)

function applyIntegrity(claims, rawVerdicts) {
  const claimIds = new Set(claims.map((c) => c.id).filter(Boolean))
  const byClaim = new Map()
  let dropped = 0
  let downgraded = 0
  for (const raw of rawVerdicts) {
    if (!raw || !claimIds.has(raw.claim_id)) {
      dropped++
      continue
    }
    const v = { ...raw }
    if ((v.verdict === 'confirmed' || v.verdict === 'partially-supported') && !hasEvidence(v)) {
      v.reason = `downgraded (no evidence locator/excerpt): ${v.reason || ''}`
      v.verdict = 'unverified'
      downgraded++
    }
    if (!(v.verdict in CONSERVATIVE_RANK)) {
      v.reason = `normalized (unknown verdict "${v.verdict}"): ${v.reason || ''}`
      v.verdict = 'unverified'
    }
    const prev = byClaim.get(v.claim_id)
    if (!prev || CONSERVATIVE_RANK[v.verdict] > CONSERVATIVE_RANK[prev.verdict]) byClaim.set(v.claim_id, v)
  }
  const verdicts = [...byClaim.values()]
  const cnt = (k) => verdicts.filter((v) => v.verdict === k).length
  const uncovered = claims.filter((c) => !byClaim.has(c.id)).map((c) => c.id).sort()
  return { confirmed: cnt('confirmed'), partial: cnt('partially-supported'), refuted: cnt('refuted'), unverified: cnt('unverified'), uncovered, dropped, downgraded }
}

const data = JSON.parse(fs.readFileSync(CASES, 'utf8'))
let failures = 0
for (const c of data.cases) {
  const got = applyIntegrity(c.claims, c.raw_verdicts)
  const want = c.expect
  for (const k of ['confirmed', 'partial', 'refuted', 'unverified', 'dropped', 'downgraded']) {
    if (got[k] !== want[k]) {
      console.error(`FAIL ${c.name}: ${k} expected ${want[k]} got ${got[k]}`)
      failures++
    }
  }
  if (JSON.stringify(got.uncovered) !== JSON.stringify([...want.uncovered].sort())) {
    console.error(`FAIL ${c.name}: uncovered expected ${JSON.stringify([...want.uncovered].sort())} got ${JSON.stringify(got.uncovered)}`)
    failures++
  }
  const bucketed = got.confirmed + got.partial + got.refuted + got.unverified
  if (bucketed + got.uncovered.length !== c.claims.length) {
    console.error(`FAIL ${c.name}: invariant broken`)
    failures++
  }
}
if (failures) {
  console.error(`verdict-integrity JS check: ${failures} failure(s)`)
  process.exit(1)
}
console.log(`verdict-integrity JS check: pass (${data.cases.length} cases)`)
