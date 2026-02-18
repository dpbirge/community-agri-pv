# Architecture Document Consistency Review

**Reviewer:** Kilo Code  
**Date:** 2026-02-12  
**Documents Reviewed:**
- [`structure.md`](../arch/structure.md) (canonical reference)
- [`policies.md`](../arch/policies.md)
- [`simulation_flow.md`](../arch/simulation_flow.md)

---

## Executive Summary

This review analyzes the logical consistency between the three architecture specification documents. The [`structure.md`](../arch/structure.md) document serves as the canonical starting point, and [`policies.md`](../arch/policies.md) and [`simulation_flow.md`](../arch/simulation_flow.md) should derive their inputs, behaviors, and outputs from it.

**Findings:**
- 3 critical inconsistencies requiring resolution
- 4 specification gaps with missing definitions
- 3 minor inconsistencies for cleanup
- 2 missing cross-references between documents

---

## 1. CRITICAL INCONSISTENCIES

### 1.1 Household Water Policy Availability Mismatch

**Location:**
- [`structure.md:203-204`](../arch/structure.md:203) — "Household/facility policies are limited to: water policy `max_groundwater` or `max_municipal`"
- [`simulation_flow.md:762`](../arch/simulation_flow.md:762) — "Available policies: `max_groundwater`, `max_municipal`, `microgrid`"

**Issue:** `microgrid` is an **energy policy**, not a water policy. This appears to be a copy-paste error in simulation_flow.md. The structure.md specification is correct.

**Resolution:** Remove `microgrid` from the household water policy list in simulation_flow.md line 762.

---

### 1.2 Economic Policy sell_inventory Override Timing Conflict

**Location:**
- [`simulation_flow.md:137-142`](../arch/simulation_flow.md:137) — Economic policy execution stores flag "for use in Step 5 next month"
- [`simulation_flow.md:124-131`](../arch/simulation_flow.md:124) — Market policy checks sell_inventory flag every day

**Issue:** The economic policy runs at the START of a month, but the flag is stored "for use in Step 5 next month" (line 142). This means the sell_inventory decision made in January doesn't affect sales until February. However, Step 5 checks the flag every day.

**Gaps:**
1. No initial value for `sell_inventory` flag before first month boundary
2. Unclear whether flag applies immediately (same month) or with one-month lag

**Resolution Options:**
- **Option A:** Flag applies immediately from day 1 of the month through the last day
- **Option B:** Flag applies with one-month lag (document explicitly)

**Recommendation:** Option A is more intuitive. Update line 142 to: "Store sell_inventory flag for use in Step 5 for the remainder of this month."

---

### 1.3 Energy Policy Scope Conflict (Farm vs Community Level)

**Location:**
- [`structure.md:274-276`](../arch/structure.md:274) — "Each farm selects a energy source allocation strategy."
- [`simulation_flow.md:90-93`](../arch/simulation_flow.md:90) — "FOR each farm (or community if override)"
- [`simulation_flow.md:777-782`](../arch/simulation_flow.md:777) — "When farm and household energy policies differ: The dispatch function uses the MOST PERMISSIVE combination of flags."

**Issue:** If each farm has its own energy policy, but dispatch is community-level with "most permissive" flag combination, then a single farm choosing `all_grid` enables grid import for the entire community even if other farms chose `microgrid`. This contradicts the farm-level policy autonomy described in structure.md.

Note: [`simulation_flow.md:920-923`](../arch/simulation_flow.md:920) (Section 10.3) flags this as needing owner input, but the inconsistency remains unresolved.

**Resolution Options:**
- **Option A:** Dispatch farm and household energy demand separately (respects farm-level autonomy)
- **Option B:** Document explicitly that community-level dispatch uses permissive combination (farm autonomy is advisory, not enforced)

**Recommendation:** Add explicit clarification to structure.md stating that energy dispatch is community-level and uses permissive flag combination when policies differ.

---

## 2. SPECIFICATION GAPS

### 2.1 Missing Storage Cost Data Source

**Location:**
- [`simulation_flow.md:456-463`](../arch/simulation_flow.md:456) — Defines daily storage cost calculation
- [`simulation_flow.md:954-955`](../arch/simulation_flow.md:954) — Section 10.7 flags as needing data

**Issue:** No CSV file exists for `storage_cost_per_kg_per_day`. The formula references:
```python
daily_storage_cost = SUM over all tranches in farm_storage:
    tranche.kg * storage_cost_per_kg_per_day(tranche.product_type)
```

**Impact:** Daily accounting (Step 7) cannot compute storage costs without this data.

**Resolution:** Create `data/parameters/crops/storage_costs-toy.csv` with schema:
```csv
product_type,cost_per_kg_per_day_usd
fresh,0.001
packaged,0.0005
canned,0.0003
dried,0.0002
```

---

### 2.2 E_other Demand Component Undefined

**Location:**
- [`simulation_flow.md:86-87`](../arch/simulation_flow.md:86) — Lists `E_other = community buildings, industrial`
- [`structure.md:138-139`](../arch/structure.md:138) — Defines `industrial_buildings_m2`, `community_buildings_m2`
- [`simulation_flow.md:958-959`](../arch/simulation_flow.md:958) — Section 10.8 flags as unclear

**Issue:** structure.md defines the configuration parameters but no formula exists for computing E_other. The household demand calculation (lines 750-754) includes `community_buildings_m2` and `industrial_buildings_m2`, suggesting E_other may be bundled into E_household—but this is not explicitly stated.

**Resolution:** Either:
1. Merge E_other into E_household calculation explicitly, OR
2. Add separate formula: `E_other = community_buildings_m2 * energy_per_m2_day + industrial_buildings_m2 * energy_per_m2_day`

---

### 2.3 Multiple Planting Dates Behavior Undefined

**Location:**
- [`structure.md:154`](../arch/structure.md:154) — `planting_dates: list of MM-DD strings (e.g., ["02-15", "11-01"])`
- [`simulation_flow.md:966-967`](../arch/simulation_flow.md:966) — Section 10.10 flags as undefined

**Issue:** No specification for:
- How `area_fraction` is split across multiple plantings
- Whether concurrent growth cycles share the `percent_planted` value
- How water tracking works for overlapping growth cycles of the same crop

**Resolution:** Add section to structure.md defining multi-planting behavior, or restrict planting_dates to single value for MVP.

---

### 2.4 Community-Override YAML Schema Not Defined

**Location:**
- [`structure.md:199-202`](../arch/structure.md:199) — References community-level override "set in the scenario YAML"
- [`simulation_flow.md:939-951`](../arch/simulation_flow.md:939) — Section 10.6 proposes schema but marked as needing input

**Issue:** The actual YAML schema for expressing community overrides is not defined in structure.md.

**Proposed Schema (from simulation_flow.md):**
```yaml
community_policies:
    water_policy: cheapest_source    # overrides all farm water policies
    energy_policy: null              # no override, farms use individual
    food_policy: null
    market_policy: null
    crop_policy: null
    economic_policy: null
```

**Resolution:** Add this schema to structure.md Section 3 (Policies).

---

## 3. MINOR INCONSISTENCIES

### 3.1 Decision Output Field Naming

**Location:**
- [`policies.md:30`](../arch/policies.md:30) — "Every policy output includes a `policy_name: str` field"
- [`structure.md:241,256,268,282,294,311`](../arch/structure.md:241) — Context→Decision mappings don't include `policy_name`

**Issue:** policies.md specifies `policy_name` as a required output field, but structure.md's Decision dataclass definitions don't include it.

**Resolution:** Add `policy_name: str` to all Decision dataclasses in structure.md Section 3.

---

### 3.2 Treatment Type Options Mismatch

**Location:**
- [`structure.md:52`](../arch/structure.md:52) — `treatment_type: [bwro, swro, ro, none]`
- [`simulation_flow.md:440`](../arch/simulation_flow.md:440) — References only BWRO

**Issue:** structure.md lists three treatment types (`bwro`, `swro`, `ro`) plus `none`, but simulation_flow.md only references BWRO in the blended cost calculation. The distinction between:
- BWRO (Brackish Water Reverse Osmosis)
- SWRO (Seawater Reverse Osmosis)  
- RO (generic Reverse Osmosis)

...is not explained in the context of energy consumption calculations.

**Resolution:** Either:
1. Document which treatment types are MVP vs. future, OR
2. Add energy consumption parameters for each treatment type

---

### 3.3 Processing Energy Timing Lag Not Explicit in Daily Loop

**Location:**
- [`simulation_flow.md:168-171`](../arch/simulation_flow.md:168) — Processing Energy Timing Note (one-day lag)
- [`simulation_flow.md:37-166`](../arch/simulation_flow.md:37) — Daily loop pseudocode

**Issue:** The daily loop pseudocode does NOT show the E_processing lag explicitly. Step 3 (line 94) calls `dispatch_energy()` with `E_processing` but there's no indication this value comes from the PREVIOUS day.

**Resolution:** Add comment in Step 3:
```python
# E_processing from previous day's harvest (see Processing Energy Timing Note)
```

---

## 4. MISSING CROSS-REFERENCES

### 4.1 Aquifer Drawdown Feedback Not in Daily Loop

**Location:**
- [`structure.md:48`](../arch/structure.md:48) — `max_drawdown_m` parameter "used in aquifer drawdown feedback"
- [`simulation_flow.md:716-727`](../arch/simulation_flow.md:716) — Aquifer state update only at YEARLY boundaries

**Issue:** No daily check for whether groundwater extraction is limited by drawdown. The `max_drawdown_m` parameter exists but no daily logic uses it.

**Resolution:** Either:
1. Add daily drawdown constraint check in water policy context, OR
2. Update structure.md to clarify that drawdown only affects yearly pumping head recalculation (not daily extraction limits)

---

### 4.2 Financing Status Not Used in Daily Loop

**Location:**
- [`structure.md:23-34`](../arch/structure.md:23) — Defines 6 financing status options
- [`simulation_flow.md:36`](../arch/simulation_flow.md:36) — "Compute infrastructure annual costs from financing profiles"
- [`simulation_flow.md:146-151`](../arch/simulation_flow.md:146) — Step 7 Daily Accounting

**Issue:** Financing profiles are loaded during initialization but never referenced in the daily accounting (Step 7) or cost allocation (Section 6). The mapping from `financing_status` to daily/monthly/yearly cost calculations is not specified.

**Resolution:** Add explicit formulas in simulation_flow.md showing how financing_status affects:
- Debt service payments (monthly)
- O&M costs (daily/monthly)
- CAPEX depreciation (if applicable)

---

## 5. SUMMARY TABLE

| Issue # | Severity | Document | Line | Issue | Status |
|---------|----------|----------|------|-------|--------|
| 1.1 | Critical | simulation_flow.md | 762 | Wrong policy in household water list | Needs fix |
| 1.2 | Critical | simulation_flow.md | 137-142 | sell_inventory timing unclear | Needs clarification |
| 1.3 | Critical | structure.md, simulation_flow.md | 274, 777 | Energy policy scope conflict | Needs decision |
| 2.1 | Gap | N/A | N/A | Missing storage_costs CSV | Needs data file |
| 2.2 | Gap | simulation_flow.md | 86-87 | E_other undefined | Needs formula |
| 2.3 | Gap | structure.md | 154 | Multi-planting undefined | Needs spec |
| 2.4 | Gap | structure.md | 199 | Community-override YAML missing | Needs schema |
| 3.1 | Minor | structure.md | 241+ | Missing policy_name field | Needs addition |
| 3.2 | Minor | structure.md | 52 | Treatment types unclear | Needs doc |
| 3.3 | Minor | simulation_flow.md | 94 | E_processing lag implicit | Needs comment |
| 4.1 | Cross-ref | simulation_flow.md | 716 | Daily drawdown check missing | Needs clarification |
| 4.2 | Cross-ref | simulation_flow.md | 146-151 | Financing status not used | Needs formulas |

---

## 6. RECOMMENDED ACTIONS

### Immediate (Before Implementation)

1. **Fix household water policy list** — Remove `microgrid` from simulation_flow.md line 762
2. **Clarify economic policy timing** — Specify sell_inventory applies same-month
3. **Add storage_costs-toy.csv** — Create with reasonable default values
4. **Add community_policies YAML schema** — Add to structure.md Section 3

### Short-term (During Implementation)

5. **Resolve energy policy scope** — Document permissive combination behavior OR implement separate dispatch
6. **Define E_other formula** — Merge into E_household or add explicit calculation
7. **Add policy_name to Decision dataclasses** — Update structure.md Section 3
8. **Add E_processing lag comment** — Update simulation_flow.md Step 3

### Long-term (Post-MVP)

9. **Define multi-planting behavior** — Full specification for concurrent growth cycles
10. **Document treatment type distinctions** — Energy consumption by treatment type
11. **Add daily drawdown constraint** — If needed for aquifer sustainability modeling
12. **Document financing cost flow** — Explicit formulas for debt service, O&M, CAPEX

---

*End of review.*
