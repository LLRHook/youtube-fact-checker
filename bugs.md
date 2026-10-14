# Research Evidence Workbench — Bug Tracker

## Conventions

Append evidence-backed defects at the end of `## Open`; never reuse an ID or truncate history. IDs are actual UNIX epoch seconds at filing, prefixed `BUG-`. Area tags: api, ui, services, storage, security, tests, docs.

Each entry has an unchecked Severity line, Area, File(s), Observation, Expected, Repro / Notes, Bump, and Status. Extra Test plan, Dependencies and Docs fields may clarify delivery.

Severity: crit blocks build/run or a hard constraint; high covers data loss/crash or a defining feature failure; med is a material defect; low covers polish or limited drift. Bump is patch for compatible fixes; mark breaking behavior major for explicit release planning. Never infer permission to cut a major release.

Lifecycle: `open -> in-progress -> fixed-pending-migration`. Only tick verified fixes; add Fix and Docs notes. Only a successful full V&V run moves completed entries to `## Migrated to changelog` and adds the corresponding changelog line. Preserve every ID.

---

## Open

### [BUG-1792003575] Correct Sonnet 5.5 cache-read pricing and reject unrated usage

- [ ] **Severity:** med
- **Area:** services, tests
- **File(s):** backend/services/llm.py, tests/unit/test_llm.py
- **Observation:** The inspected PRICING table rates claude-sonnet-5-5 cache-read tokens at $0.20 per million; the official pricing checked in this session is $0.10. Existing tests encode the current table, so they do not establish provider-rate correctness.
- **Expected:** Match the verified applicable provider price schedule and retain an explicit unknown-price failure for workbench admission rather than silently pricing a different model. Source: SRS FR-017–FR-018; ARCHITECTURE.md §7.4; official Claude pricing linked in PRODUCT_FEASIBILITY.md.
- **Repro / Notes:** Inspect PRICING in backend/services/llm.py and compute a cache-read-only usage fixture. Compare against the dated official Claude pricing page for this model; do not change model IDs. Add an independent price fixture so a mirrored implementation test cannot hide the discrepancy.
- **Test plan:** Unit exact-price/counter/unknown model cases; verify existing legacy accounting callers before replacing fallback semantics.
- **Bump:** patch
- **Status:** open
- **Depends on:** None
- **Execution gate:** Recheck official applicable prices at implementation; no new model, provider or paid API request is required.
- **Docs:** Update the dated provider-rate reference and relevant accounting notes; do not change model identifiers.

---

## Migrated to changelog

_No fixes migrated._
