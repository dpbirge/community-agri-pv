# Simulation Flow Order-of-Operations Audit

**Date:** 2026-02-19
**Scope:** `specs/simulation_flow.md` — ordering correctness and completeness only.
**Not in scope:** calculation correctness, parameter values, missing input data.

---

## 1. Ordering Correctness

Each entry below names the two steps involved, states which depends on the other, and
gives a verdict.

---

### O-1 — Monthly Reset (Step 8) Runs AFTER Step 2 Uses the Value It Resets

**Steps involved:** Step 2 (Water Policy) and Step 8 (Boundary Operations).
**Dependency:** Step 2 reads `cumulative_gw_month_m3` and `cumulative_monthly_community_water_m3`
to enforce quota limits and compute tiered community water prices. Step 8 resets both
counters to 0 on the first day of each new month.
**Spec order:** Step 2 → ... → Step 7 → Step 8 (reset).
**Problem:** On day 1 of month M, Step 2 executes with the month M-1 cumulative values still
present. The quota-enforced water policy will see full last-month usage, potentially
triggering quota limits or tiered-price breakpoints that should not apply at the start of
a fresh month. The reset in Step 8 is too late.
**Required fix:** Monthly accumulator resets must happen before Step 1 on the first day of
a new month — logically at the very start of the daily loop, before any policy reads them.
The monthly metrics snapshot (Section 9.1 item 3) must be captured *before* the reset.

> Note: `state.py`'s `update_monthly_consumption()` auto-resets on first access when the
> month changes, so the code handles this correctly via a different mechanism. The spec,
> however, says to reset in Step 8 — these are inconsistent and the spec needs to be
> updated to match the correct approach.

---

### O-2 — Step 6 (Economic Policy) Uses a Monthly Snapshot That Step 8 Hasn't Taken Yet

**Steps involved:** Step 6 (Economic Policy, monthly) and Step 8 (Boundary Operations,
monthly snapshot).
**Dependency:** Step 6 assembles `EconomicPolicyContext` with "previous month's aggregated
revenue and costs" (Section 9.1 item 1). The monthly metrics snapshot that produces that
aggregated data is described in Section 9.1 item 3 as part of Step 8.
**Spec order:** Step 6 runs before Step 8.
**Problem:** On day 1 of month M, Step 6 fires before Step 8's monthly snapshot. The
month M-1 snapshot does not yet exist when Step 6 needs it. Step 6 would therefore be
reading either (a) the month M-2 snapshot (two months old), or (b) raw un-aggregated daily
records. The spec calls for "previous month's" data but does not specify which of these
two interpretations is correct.
**Required fix:** Either (a) move Step 6 to run after Step 8's monthly snapshot is taken,
or (b) explicitly state that Step 6 aggregates directly from the trailing daily records
rather than from the monthly snapshot.

---

### O-3 — Yearly Degradation Update (Step 8) Runs After Day-1 Dispatch (Step 3)

**Steps involved:** Step 3 (Energy Dispatch) and Step 8 (Yearly Boundary: equipment
degradation update).
**Dependency:** `battery_capacity_kwh` and `pumping_kwh_per_m3` (effective pump head) are
updated in Step 8 on the first day of each new year. Step 3 uses these values during
dispatch.
**Spec order:** Step 3 → ... → Step 8 (degradation update).
**Problem:** Day 1 of year Y+1 dispatches energy using year Y's (stale) battery capacity and
pumping energy, and only receives the updated degraded values from day 2 onward. The spec
neither acknowledges this one-day lag nor states it is acceptable.
**Recommended fix:** Add a note to Section 9.2 explicitly accepting the one-day lag (the
magnitude is negligible: ~1.8%/yr battery fade, ~0.5%/yr PV fade), or move the degradation
update to run before Step 0 on the first day of the new year.

---

### O-4 — Economic Policy Appears in Two Locations (Step 6 and Section 9.1)

**Steps involved:** Step 6 (daily loop) and Section 9.1 item 1 (Monthly Boundaries).
**Problem:** Step 6 in the daily loop ("IF today is first day of month: call
economic_policy.decide()") is logically the same operation as Section 9.1 item 1
("Economic policy execution" under Monthly Boundaries). The spec does not say these are
the same invocation — a reader could interpret it as two separate triggers both firing on
the first day of the month, causing the economic policy to run twice.
**Required fix:** Explicitly state in Section 9.1 that item 1 is implemented as Step 6 of
the daily loop (cross-reference only, no second execution). Remove ambiguity about whether
Section 9.1 is a conceptual description or a separate execution trigger.

---

## 2. Missing Specification Gaps

---

### G-1 — Pre-Loop Step 6 Is Marked TBD (Processing Capacities) — Blocks Step 4

**Location:** Pre-Loop Step 6, Step 4.2 (capacity clipping).
**Problem:** Step 4.2 (food processing capacity clipping) calls `clip_to_capacity()`, which
divides by `harvest_yield_kg` and references `capacities[pathway]`. The `capacities` dict
is described as computed at scenario load time in Pre-Loop Step 6, which is marked **TBD**.
Without this step being resolved, capacity clipping has no source for `capacities` and
cannot execute.
**Verdict:** Blocking gap. Pre-Loop Step 6 must be defined before Step 4 can run.

---

### G-2 — `E_processing` State Field Is Not Specified

**Location:** Section 3 Step 3 (uses E_processing), Section 3 Step 4 (computes
E_processing), Pre-Loop Step 14 (initializes to 0).
**Problem:** The spec defines the one-day lag behavior (E_processing computed in Step 4
today is used in Step 3 tomorrow) and initializes it to 0 at Pre-Loop Step 14. However,
no state dataclass field is ever specified to carry this value between days. `EnergyState`
in `state.py` has no `e_processing` field. The spec (Section 12 State Dataclass
Cross-Reference) does not map `E_processing` to any field.
**Required fix:** Add `e_processing_kwh: float = 0.0` to `EnergyState` (or a dedicated
state dataclass) and reference it in Section 12.

---

### G-3 — `contribution_kg` Reset Policy Is Unspecified

**Location:** Section 5.9 (Revenue Attribution), Step 4.1 (accumulation), Step 5 (usage).
**Problem:** Section 5.9 states that `contribution_kg` "accumulates across the simulation"
and is the denominator for revenue attribution. No reset event is ever specified. Over
a multi-year simulation, a farm that contributed large harvests early and then reduced
planting area will continue receiving a disproportionately large revenue share indefinitely.
The spec is silent on whether this is intentional.
**Required fix:** Explicitly state the reset policy: (a) never reset — proportional share
reflects cumulative lifetime contribution; (b) reset yearly at the year boundary alongside
other annual resets; or (c) reset per crop cycle. All three are defensible designs, but
one must be chosen and stated.

---

### G-4 — Harvest Hand-Off Between Step 0 and Step 4 Is Ambiguous

**Location:** Section 6.4 (daily state transition, part of Step 0), Section 6.5 (harvest
trigger), Section 3 Step 4.1.
**Problem:** Section 6.4 transitions `crop.state` to HARVEST_READY during Step 0. Section
6.5 says harvest "triggers the food processing pipeline (Steps 4.1–4.2 in the daily loop)."
This implies Step 0 sets the state and Step 4 executes the processing. However, the spec
never explicitly states:

1. The crop remains in HARVEST_READY state between Step 0 and Step 4.
2. Step 4 queries for crops in HARVEST_READY state (not re-running the transition logic).
3. Step 4 is responsible for transitioning the crop from HARVEST_READY → DORMANT.

Without this hand-off spelled out, an implementer could read Section 6.5 as executing
entirely within Step 0 (making Step 4 redundant for harvest crops), which would break
the energy dispatch order for processing energy.
**Required fix:** Add explicit language such as: "Step 0 only advances state; it does NOT
execute the harvest. Step 4 queries all farms for crops in HARVEST_READY state, executes
the yield calculation and food processing pipeline, then transitions those crops to DORMANT."

---

### G-5 — Step 8 Monthly Snapshot Order Relative to Resets Is Not Specified

**Location:** Section 3 Step 8, Section 9.1 items 2 and 3.
**Problem:** Step 8 lists three operations: (1) reset monthly GW tracking, (2) reset monthly
community water tracking, (3) snapshot monthly metrics. The spec does not state the order
of these three sub-operations. If the resets happen before the snapshot, the snapshot
captures zeroed-out month M-1 data instead of the completed month's totals.
**Required fix:** Add explicit ordering within Step 8: snapshot must run before resets.

---

### G-6 — Step 0 Does Not List Retrieval of `E_household` and `E_community_bldg`

**Location:** Section 3 Step 0 (retrieve daily conditions), Step 3 (energy dispatch,
uses `E_household` and `E_community_bldg`).
**Problem:** Step 3 requires `E_household` (daily household electricity demand) and
`E_community_bldg` (daily community building electricity demand). These are daily
precomputed time-series lookups. Step 0 lists weather, crop growth stages, and prices,
but does not list these demand lookups. Similarly, Step 2b lists community water lookups
but does not list community energy lookups. Step 3 is the first step that uses them and
has no retrieval step above it that would populate these values.
**Required fix:** Add household and community building energy demand retrieval to Step 0
(or explicitly to Step 2b as a companion to the water demand lookups).

---

### G-7 — `sell_inventory` Flag from Step 6 Has No Integration Point in Step 5

**Location:** Section 3 Step 6 ("Store sell_inventory flag for use in Step 5 next month"),
Section 3 Step 5 (calls `market_policy.decide(ctx)`, `MarketPolicyContext` does not include
this flag).
**Problem:** Step 6 produces `EconomicDecision.sell_inventory` and says it is used "in
Step 5 next month." However, Step 5's pseudocode assembles a `MarketPolicyContext` and
calls `market_policy.decide()`. Neither the context nor the market policy interface
includes a `sell_inventory` flag. The economic decision is stored but never consumed.
**Required fix:** Either (a) specify that when `sell_inventory = True`, Step 4.3 or Step 5
performs a forced-sell-all operation before the normal market policy runs, or (b) define
a new pre-Step-5 sub-step that checks the economic flag and overrides the market policy
decision.

---

## 3. First-Day Edge Cases

The following initialization states are needed for Day 1 but are not covered (or only
partially covered) by Pre-Loop Steps 1–14.

| # | Value | Pre-Loop Step | Status |
|---|-------|--------------|--------|
| 1 | `E_processing = 0` | Step 14 | ✓ Covered |
| 2 | `battery_soc = 50%` | Step 10 | ✓ Covered |
| 3 | `water_storage = 50%` | Step 9 | ✓ Covered |
| 4 | `cumulative_gw_month_m3 = 0` | Step 8 (implicit via state init) | Minor gap — not stated explicitly in pre-loop |
| 5 | `cumulative_monthly_community_water_m3 = 0` | Not mentioned | Gap — no pre-loop step initializes this |
| 6 | `contribution_kg = 0` for all crops | Not mentioned | Gap — tied to G-3 (reset policy unspecified) |
| 7 | Economic policy decision flag (Day 1 if start is first of month) | Not mentioned | Gap — if simulation starts on the first of a month, Step 6 fires with no prior month's data; the spec handles months_elapsed < 12 but not months_elapsed == 0 |

---

## 4. Ambiguous Triggers

### A-1 — "First Day of Month" Fires Step 6 AND Step 8

Step 6 and Step 8 each check `IF today is first day of month`. The spec does not state
whether these are one trigger dispatching to both steps, or two independent triggers. A
naive reading could result in both blocks executing independently without coordination
— particularly problematic for O-2 (Step 6 needs the snapshot that Step 8 produces).

---

### A-2 — When Does the Crop State Machine Run Relative to Dispatch on Harvest Day?

Section 6.4 says it is consulted in "Step 0 (retrieve crop growth stages)." Section 6.5
says harvest triggers "Execute food processing pipeline (Steps 4.1–4.2 in the daily loop)."
It is not stated whether the phrase "in the daily loop" means the processing is deferred
to Step 4, or executed immediately as part of the state machine transition within Step 0.
If the harvest fires in Step 0, the resulting `E_processing` is available for the same
day's Step 3 (bypassing the intended one-day lag). If it fires in Step 4, the lag is
preserved. The spec needs to make this explicit.

---

### A-3 — January 1: Two Boundary Triggers Fire Simultaneously

January 1 is both "first day of new month" and "first day of new year." Both Step 8
sub-blocks fire. The spec addresses the `cumulative_gw_month_m3` interaction in Section
9.2 item 6 ("On January 1, the monthly accumulator was already reset when the
December-to-January month boundary triggered"). However, the ordering within Step 8 of
monthly operations vs. yearly operations on January 1 is not stated. If the yearly
snapshot runs before the monthly snapshot, or the monthly reset fires before the yearly
snapshot, data could be inconsistent.
**Required fix:** Define explicit ordering within Step 8 for January 1: (1) monthly
snapshot, (2) monthly reset, (3) yearly snapshot, (4) yearly resets and updates.

---

## 5. Summary

**Verdict: The spec does not define a complete, gap-free execution sequence.**

The spec is structurally sound and covers the major subsystems. The daily loop ordering
from Step 1 through Step 7 is correct for the core data-flow dependencies (crop policy
before water policy, water policy before energy dispatch, food processing lag to next-day
dispatch). No steps are fundamentally out of place for the central water-energy-food chain.

However, seven issues prevent it from serving as an unambiguous implementation reference:

**Ordering errors (must fix before implementing):**

1. **O-1** — Monthly accumulators are read by Step 2 before Step 8 resets them. Fix:
   reset before Step 1 on the first day of each month; snapshot before the reset.
2. **O-2** — Step 6 (economic policy) runs before the monthly snapshot it depends on exists.
   Fix: move Step 6 after Step 8's snapshot, or specify it reads daily records directly.

**Blocking gaps (missing spec prevents implementation):**

3. **G-1** — Pre-Loop Step 6 (processing capacities) is TBD; blocks Step 4 capacity
   clipping.
4. **G-2** — No state field specified to carry `E_processing` between days.
5. **G-7** — `sell_inventory` flag from Step 6 has no specified consumption point in
   Step 5.

**Ambiguities that will produce divergent implementations:**

6. **G-4** — Harvest hand-off between Step 0 (state transition) and Step 4 (processing
   execution) is implicit. Must be made explicit.
7. **G-3** — `contribution_kg` reset policy is undefined; multi-year attribution will
   drift unless a reset schedule is specified.

The remaining issues (O-3, O-4, G-5, G-6, A-1, A-2, A-3, and the first-day edge cases)
are lower severity: they represent minor ambiguities or one-day lags that do not prevent
a simulation from running but will cause confusing behavior or spec-vs-code divergence if
not clarified.
