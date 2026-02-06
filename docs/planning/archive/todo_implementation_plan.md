# TODO.md Implementation Plan

**STATUS: Implementation Roadmap (Not Started)**

This plan outlines 8 phases for enhancing the water simulation with constraints, decision tracking, and advanced policies.

**Progress:**
- Phase 1: ✅ Complete (water metadata moved)
- Phase 2-8: 📋 Planned (not started)

---

## Overview
Implement all TODO items sequentially with web research for pricing phases. Focus on QuotaEnforced as the primary new policy.

---

## Phase 1: Data Reorganization
**Goal:** Move water metadata from YAML to proper locations

**Tasks:**
1. Extract documentation from `water_policy_only.yaml` lines 18-83:
   - BWRO vs SWRO source definitions
   - Egyptian HCWW tariff explanations
   - Salinity/energy requirements
   - Treatment capacity calculations

2. Create new files:
   - `data/parameters/water/water_source_metadata.yaml`
   - `docs/research/egyptian_water_pricing.md`

3. Simplify scenario YAML to reference new files

**Files to modify:**
- [water_policy_only.yaml](../../settings/scenarios/water_policy_only.yaml)
- New: `data/parameters/water/water_source_metadata.yaml`
- New: `docs/research/egyptian_water_pricing.md`

---

## Phase 2: Physical Constraints
**Goal:** Add max water draw, treatment throughput, quotas

**Tasks:**
1. Extend `WaterPolicyContext` dataclass with:
   ```python
   max_groundwater_m3: float  # well_capacity / num_farms
   max_treatment_m3: float    # treatment_capacity / num_farms
   cumulative_gw_today_m3: float
   ```

2. Remove `available_energy = float("inf")` from [simulation.py:92](../../src/simulation.py#L92)

3. Add `_apply_constraints()` to `BaseWaterPolicy`

4. Update all 4 policies to check constraints before allocating

**Files to modify:**
- [water_policies.py](../../settings/policies/water_policies.py)
- [simulation.py](../../src/simulation.py)
- [state.py](../../src/state.py)

---

## Phase 3: Decision Metadata & Logging
**Goal:** Track WHY policies made decisions

**Tasks:**
1. Create `WaterDecisionMetadata` dataclass:
   ```python
   decision_reason: str  # "gw_cheaper", "energy_constrained", etc.
   gw_cost_per_m3: float
   muni_cost_per_m3: float
   constraint_hit: str | None  # "well_limit", "treatment_limit"
   ```

2. Add metadata field to `WaterAllocation`

3. Update each policy to populate decision metadata

4. Extend `DailyWaterRecord` with decision fields

**Files to modify:**
- [water_policies.py](../../settings/policies/water_policies.py)
- [state.py](../../src/state.py)
- [simulation.py](../../src/simulation.py)

---

## Phase 4: Enhanced Visualizations
**Goal:** Visual tracking of policy triggers

**New plots:**
1. Box plot: daily water cost distribution per farm
2. Stacked bar: decision_reason counts per year
3. Timeline scatter: constraint hit events
4. Per-farm stacked area: GW vs municipal over time

**CSV updates:**
- Add decision_reason, constraint_hit, gw_cost_per_m3, muni_cost_per_m3 columns

**Files to modify:**
- [results.py](../../src/results.py)

---

## Phase 5: Seasonal Pricing (Research First)
**Goal:** Add seasonal water and power price changes

**Research tasks:**
- Search for Egyptian agricultural electricity tariffs
- Find summer/winter water rate differentials
- Document HCWW seasonal patterns if any

**Implementation (if research supports):**
1. Extend electricity CSV with seasonal columns
2. Add seasonal lookup to `data_loader.py`
3. Add seasonal multipliers to scenario config
4. Create `docs/research/egyptian_utility_pricing.md`

**Files to modify:**
- `data/prices/electricity/*.csv`
- [data_loader.py](../../src/data_loader.py)
- [loader.py](../../settings/scripts/loader.py)

---

## Phase 6: Tier Pricing (Research First)
**Goal:** Demand-based tiered pricing

**Research tasks:**
- Find Egyptian water tariff tier thresholds (m3/month)
- Document agricultural electricity tier structure

**Implementation (if research supports):**
1. Create `TierPricingConfig` dataclass
2. Add `calculate_tiered_cost()` function
3. Track cumulative consumption for tier calculation
4. Update policies to use tiered costs

**Files to modify:**
- [loader.py](../../settings/scripts/loader.py)
- [data_loader.py](../../src/data_loader.py)
- [state.py](../../src/state.py)

---

## Phase 7: QuotaEnforced Policy
**Goal:** Hard annual groundwater limits with monthly tracking

**New policy:**
```python
class QuotaEnforced(BaseWaterPolicy):
    """Enforces annual groundwater quota with monthly tracking."""
    name = "quota_enforced"

    def __init__(self, annual_quota_m3, monthly_variance_pct=0.15):
        self.annual_quota = annual_quota_m3
        self.monthly_variance = monthly_variance_pct
```

**Logic:**
- Cannot exceed annual quota across entire year
- Monthly draw stays within variance of equal distribution (annual/12 +/- variance)
- Forces municipal when quota exhausted

**Files to modify:**
- [water_policies.py](../../settings/policies/water_policies.py)
- [__init__.py](../../settings/policies/__init__.py)
- [water_policy_only.yaml](../../settings/scenarios/water_policy_only.yaml)

---

## Phase 8: Sensitivity Analysis
**Goal:** Systematic parameter variation framework

**Tasks:**
1. Create `src/sensitivity.py`:
   - `run_sensitivity_analysis()` for multi-parameter sweeps
   - `run_parameter_sweep()` for single parameter variation

2. Add tornado plot to results.py

3. Create sensitivity results CSV format

**Files to create/modify:**
- New: `src/sensitivity.py`
- [results.py](../../src/results.py)

---

## Verification Plan

After each phase:
1. Run: `python src/results.py settings/scenarios/water_policy_only.yaml`
2. Check `results/` folder for new outputs
3. Verify CSV has expected columns
4. Inspect plots for correctness

**Final validation:**
- All 4 original policies still work
- New QuotaEnforced policy triggers quota limits
- Box plots show per-farm cost distributions
- Decision metadata appears in daily CSV

---

## Implementation Order

1. Phase 1 - Data reorganization
2. Phase 2 - Physical constraints
3. Phase 3 - Decision metadata
4. Phase 4 - Visualizations
5. **Research break** - Egyptian pricing investigation
6. Phase 5 - Seasonal pricing (if supported)
7. Phase 6 - Tier pricing (if supported)
8. Phase 7 - QuotaEnforced policy
9. Phase 8 - Sensitivity analysis
