# Code Review - gpt-5.2-codex - 2026-02-05

Scope:
- Reviewed `src/` implementation against `docs/architecture/mvp-calculations.md`
  and `docs/architecture/mvp-structure.md`
- Skimmed active planning docs in `docs/planning/` for inconsistencies

## Summary
The water simulation MVP runs, but several core calculations diverge from the
architecture specs. Most of the gaps relate to water demand/efficiency,
groundwater cost composition, tiered pricing, and area-based sharing. Planning
docs also state “unlimited grid energy” and “no capacity constraints” for MVP,
while the implementation applies PV/wind-limited energy and per-farm capacity
constraints.

## Findings (Logic / Calculation)

### High severity
1) Groundwater cost omits pumping energy and conveyance
   - Spec calls for GW cost/m3 = (pumping_kwh + treatment_kwh) × electricity_price + maintenance
   - Implementation only includes treatment energy + maintenance
   - Impact: underestimates GW cost and biases policy selection
   - Files: `src/policies/water_policies.py`, `src/simulation/simulation.py`

2) Irrigation demand ignores irrigation system efficiency
   - Spec: `Water_demand = (ET_crop × Area) / η_irrigation`
   - Implementation uses precomputed irrigation m3/ha directly, with no adjustment
     for `water_system.irrigation_system.type`
   - Impact: demand is overstated/understated depending on irrigation type
   - Files: `src/simulation/simulation.py`

3) Crop water tracking uses *demand* not *allocated* water
   - `update_farm_state()` adds full crop demand even when policy allocation is
     constrained
   - Per-crop water totals and WUE metrics are incorrect under shortages
   - Impact: water-per-yield and per-crop efficiency are wrong in constrained runs
   - Files: `src/simulation/simulation.py`, `src/simulation/metrics.py`

4) Tiered pricing uses marginal price for total cost
   - When tier pricing is enabled, policy uses marginal tier price for decisions
   - `WaterAllocation.cost_usd` still multiplies *all* municipal volume by the
     marginal price (not the tiered total)
   - Impact: municipal cost is wrong under tiered pricing; pricing curves are distorted
   - Files: `src/simulation/simulation.py`, `src/policies/water_policies.py`,
     `src/simulation/data_loader.py`

### Medium severity
5) Infrastructure sharing uses equal split, not area-proportional
   - Planning decisions say infrastructure sharing is proportional to farm area
   - `calculate_system_constraints()` divides well/treatment capacity by farm count
   - Impact: farms with smaller/larger area get incorrect capacity constraints
   - Files: `src/simulation/simulation.py`

6) Yield does not incorporate `yield_factor` or water-stress
   - Spec: yield depends on water stress and `farms[].yield_factor`
   - Implementation uses precomputed yields directly and applies no factor or stress
   - Impact: yields are insensitive to water shortfalls or farm quality
   - Files: `src/simulation/state.py`, `src/simulation/simulation.py`

7) Water shortfall does not affect yield
   - Spec includes demand gap and delivery ratio for yield impact
   - Implementation harvests expected yield even when demand is unmet
   - Impact: policy results do not penalize shortages
   - Files: `src/simulation/simulation.py`

### Low severity
8) Post-harvest losses are fixed at 10% and not crop/processing-specific
   - Spec suggests pathway-specific loss rates and crop-specific overrides
   - Impact: small; but mismatches the calculations doc
   - Files: `src/simulation/simulation.py`

## Planning / Architecture Inconsistencies
1) Energy availability
   - Planning doc: “Unlimited grid energy for MVP”
   - Implementation: if PV/wind exists, treatment energy is limited to PV/wind output;
     grid is treated as unlimited only when PV and wind are zero
   - Files: `docs/planning/water_simulation_followup_questions.md`,
     `src/simulation/simulation.py`

2) Capacity constraints
   - MVP plan: storage/throughput constraints deferred (Phase 7)
   - Implementation: well capacity, treatment throughput, and energy constraints
     are enforced in the MVP loop
   - Files: `docs/planning/water_simulation_mvp_plan.md`, `src/policies/water_policies.py`

3) State mutability
   - Plan: “Immutable updates (new state each day)”
   - Implementation mutates the same state objects in-place
   - Impact: not wrong, but inconsistent with planning assumptions and docs
   - Files: `docs/planning/water_simulation_mvp_plan.md`, `src/simulation/state.py`

## Notes / Assumptions
- Data credibility is assumed correct per request; findings focus on logic and
  calculation consistency only.
- I did not run the simulation; this is a static review of code and docs.
