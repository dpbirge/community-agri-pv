# Code Review: mvp-calculations.md vs src/ Implementation

**Reviewer:** claude (AI assistant)
**Date:** 2026-02-05
**Scope:** `docs/architecture/mvp-calculations.md` (doc) vs `src/` codebase (code)
**Methodology:** Section-by-section comparison of documented formulas against implementation

## Status

The initial review identified items across three categories: doc updates needed, code updates needed, and deferred future work. The doc updates and safe code fixes have been applied. This file now tracks only the **remaining items** that require more careful implementation.

### Completed

- Doc updates: pumping energy constants, treatment energy lookup, irrigation efficiency note, K_y values, tiered pricing, QuotaEnforced policy, revenue concentration metric, sensitivity analysis, crop diversity basis — all applied to `mvp-calculations.md`
- Code fixes: PV degradation multiplier (`simulation.py`), processing availability factor (`calculations.py`) — applied and lint-clean

---

## Remaining Code Items (require careful implementation)

### 1. Aquifer Drawdown Feedback — Medium priority, Medium effort

**Section:** mvp-calculations.md Section 2.9
**Status:** Documented but not implemented

The doc specifies a linearized drawdown model where cumulative extraction increases effective pumping head over time, creating a feedback loop to pumping energy cost:

```
Drawdown_m(year) = max_drawdown_m × (Cumulative_extraction / exploitable_volume)
Effective_head_m(year) = well_depth_m + Drawdown_m(year)
E_pump(year) = Effective_head(year) / (367.0 × η_pump)
```

**Why not done yet:** Requires:
- New YAML config parameter `max_drawdown_m` in `water_system.groundwater_wells`
- Changes to `loader.py` dataclass to accept the new field
- Changes to `simulation.py` to recompute pumping energy per-year using effective head from `AquiferState`
- Potential changes to `calculate_pumping_energy()` signature or a new function

**Risk:** Modifying pumping energy mid-simulation changes water policy cost calculations, which changes allocation decisions. All policy comparison results will shift. Need to validate that the feedback is numerically stable and doesn't cause oscillation in cost-sensitive policies like `CheapestSource`.

**Recommended approach:**
1. Add `max_drawdown_m` to YAML and loader (default 0 for backward compatibility)
2. At each year boundary in the simulation loop, recompute `pumping_kwh_per_m3` using `well_depth_m + drawdown`
3. Pass updated value into `build_water_policy_context`
4. Test with a multi-year scenario to verify gradual cost increase

### 2. Crop Diversity Index Weighting — Low priority, Low effort

**Section:** mvp-calculations.md Section 4.5
**Status:** Code uses area-based proportions; doc suggests yield or revenue weighting is more meaningful

Currently the Shannon diversity index is computed on planted area. The doc notes "revenue-weighted is more meaningful for economic resilience."

**Why not done yet:** Changing the basis changes metric values for all existing outputs. Need to decide whether to:
- Replace area-based with revenue-based (breaking change to metric values)
- Add a second metric alongside the existing one
- Keep area-based and document it as the chosen approach

**Risk:** Low — this is a reporting metric, not an input to any policy decision. But changing it silently would make before/after comparisons inconsistent.

**Recommended approach:** Add `crop_diversity_index_revenue` as a second field alongside the existing area-based one, computed from `crop_revenue_usd` proportions in `_compute_spec_metrics()`.

---

## Deferred Items (future development phases)

These are acknowledged gaps where both doc and code agree implementation is future work.

| Item | Doc Status | Target Phase | Notes |
|------|------------|-------------|-------|
| Energy dispatch (battery, generator, grid) | Partially TBD | Phase 4+ | Largest gap; all energy policies are stubs |
| PV temperature derating (NOCT model) | Documented | Phase 4 | Check if precomputed data already includes it |
| Soil salinity yield reduction (FAO-29) | Documented, MVP-exempt | Phase 4+ | Only matters for simulations >3 years |
| Stewart multiplicative yield model | Documented | Phase 4 | Growth-stage-sensitive K_y |
| Processed product output & allocation | Documented | Phase 6 | Processing capacity is Layer 2 only currently |
| Labor model (FTE, peak demand) | TBD | Phase 7 | Data loading exists; model does not |
| Infrastructure financing costs | Documented | Phase 8 | 6 financing categories specified |
| NPV, IRR, payback period, ROI | Documented | Phase 8 | Depends on financing model |
| Equipment replacement costs | Documented | Phase 8 | Sinking fund approach specified |
| Blended electricity cost | Documented | Phase 8 | Depends on energy dispatch |
| Debt-to-revenue, cash reserves | Documented | Phase 8 | Depends on financing model |
| Monte Carlo simulation | TBD | Phase 10-11 | Sensitivity analysis is a partial step |
| Diesel fuel cost tracking | Data loaded | Phase 4+ | Generator dispatch needed first |

---

## Previous Review Items: All Resolved

Cross-referencing the 2026-02-05 dpbirge review — all 6 findings have been fixed:

| Finding | Status |
|---------|--------|
| Pumping energy ignored | FIXED — calculated and passed to policy context |
| Water storage dynamics missing | FIXED — WaterStorageState implemented |
| Aquifer depletion not tracked | FIXED — AquiferState with years-remaining |
| Simplified energy availability (×5.0 hardcode) | FIXED — uses precomputed PV/wind data |
| Capacity allocation (equal split) | FIXED — area-proportional sharing |
| Missing metric fields | FIXED — populated in `_compute_spec_metrics()` |
