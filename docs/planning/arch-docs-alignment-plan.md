# Architecture Docs Cross-Alignment Fixes

## Context

Cross-reference review of `structure.md`, `policies.md`, `simulation_flow.md`, and `calculations.md` revealed 16 misalignments, undefined variables, missing schema parameters, and inconsistent naming. These must be fixed before using the docs as implementation guides for Claude Opus/Sonnet code generation.

This plan covers documentation fixes plus one new data file and one code change.

## Files to Modify

- `docs/arch/structure.md`
- `docs/arch/policies.md`
- `docs/arch/simulation_flow.md`
- `docs/arch/calculations.md`
- `settings/settings.yaml`
- `settings/data_registry.yaml`
- `src/policies/economic_policies.py` (remove `investment_allowed`)
- `data/parameters/crops/food_storage_costs-toy.csv` (NEW)

## Fixes

### Fix 1: TDS blending formula — use policies.md version everywhere
**File:** `calculations.md` lines 331-340
- Replace the `gw_fraction = (target_tds - municipal_tds) / (groundwater_tds - municipal_tds)` formulation with the `required_municipal_fraction` version from `policies.md` Section 2.3
- Add note that `gw_fraction = 1 - required_municipal_fraction` for use in aquifer drawdown tracking and metrics
- Remove the `[OWNER: verify TDS blending formula]` tag

### Fix 2: Household water policy — remove `microgrid`
**File:** `simulation_flow.md` Section 8.2, line 762
- Change available household water policies from `max_groundwater`, `max_municipal`, `microgrid` to `max_groundwater`, `max_municipal`

### Fix 3-5: Standardize method names across all docs
**Actual code method names** (from source files):

| Domain | Code method | File |
|---|---|---|
| Water | `allocate_water()` | water_policies.py |
| Energy | `allocate_energy()` | energy_policies.py |
| Crop | `decide()` | crop_policies.py |
| Food | `allocate()` | food_policies.py |
| Market | `decide()` | market_policies.py |
| Economic | `decide()` | economic_policies.py |

**Changes needed:**
- **`structure.md`** line 230: `execute_water_policy()` → `water_policy.allocate_water(ctx)`
- **`structure.md`** line 274: `execute_energy_policy()` → `energy_policy.allocate_energy(ctx)`
- **`structure.md`** line 286: `execute_crop_policy()` → `crop_policy.decide(ctx)`
- **`structure.md`** line 245: `process_harvests()` → `food_policy.allocate(ctx)`
- Add a note in `policies.md` Section 1 (Common patterns) listing the canonical method names per domain, matching the code

### Fix 6: Remove `investment_allowed` flag
**Files:** `simulation_flow.md` line 143, `policies.md` Section 7, `src/policies/economic_policies.py`
- Remove `Store investment_allowed flag (reserved for future use)` from `simulation_flow.md` Step 6
- Remove `investment_allowed` from `policies.md` Section 7 MVP note
- **Code:** Remove `investment_allowed` field from `EconomicDecision` dataclass and all four policy implementations

### Fix 7: Define `min_cash_months` as configurable parameter
**Current code state:** Already a constructor parameter in `AggressiveGrowth` (default 1), `Conservative` (default 6), and `RiskAverse` (default 3).

**Changes:**
- **`settings/settings.yaml`** — add under `community_policy_parameters`:
  ```yaml
  aggressive_growth:
    min_cash_months: 1
  conservative:
    min_cash_months: 6
  risk_averse:
    min_cash_months: 3
  ```
- **`structure.md`** Economic policies — add `min_cash_months` to configurable parameters note
- **`policies.md`** Section 7 — add as explicit configurable parameter with defaults per-policy

### Fix 8: Add `policy_name` note to policies.md
- Add a note in Common Patterns: "`policy_name` is a standard field present in all decision dataclasses. Not listed in each output table to avoid repetition. Value matches the policy registry key."

### Fix 9: Remove `sell_inventory` override from simulation_flow.md
- **`simulation_flow.md`** Step 5: Remove the `IF economic_policy.sell_inventory == true` block
- **`simulation_flow.md`** Section 10.4: Remove the `[NEEDS OWNER INPUT]` item (resolved)
- Step 5 always calls `market_policy.decide(ctx)` and uses its `sell_fraction`

### Fix 10: Create food storage costs CSV
**New file:** `data/parameters/crops/food_storage_costs-toy.csv`

Columns: `product_type, storage_condition, cost_per_kg_per_day_usd`

Values derived from industry benchmarks for food warehousing in developing regions:
- Fresh: ~$0.005-0.010/kg/day (higher, needs cold chain or rapid turnover)
- Packaged: ~$0.003-0.005/kg/day
- Canned: ~$0.001-0.002/kg/day (shelf-stable, ambient)
- Dried: ~$0.001-0.002/kg/day (shelf-stable, ambient)

**Also:**
- Register in `data_registry.yaml` under `crops`: `storage_costs: data/parameters/crops/food_storage_costs-toy.csv`
- Mark `simulation_flow.md` Section 10.7 as resolved

### Fix 11: Add `cost_allocation_method` to structure.md
- **`structure.md`** Community Structure section: add `cost_allocation_method: [equal, area_proportional, usage_proportional]`
- **`settings/settings.yaml`** under `community_structure`: add `cost_allocation_method: equal`

### Fix 12: Add `net_metering_ratio` to structure.md
- **`structure.md`** Energy Pricing section: add `net_metering_ratio` (default 0.70)
- **`settings/settings.yaml`** under `energy_pricing`: add `net_metering_ratio: 0.70`

### Fix 13: Add `exchange_rate_egp_per_usd` to structure.md
- **`structure.md`** Economic Configuration section: add `exchange_rate_egp_per_usd`
- **`settings/settings.yaml`** under `economics`: add `exchange_rate_egp_per_usd: 49.5`

### Fix 14: Clarify capacity clipping ownership
- **`policies.md`** Section 3 shared logic: add cross-reference note: "Applied by the simulation loop after the policy returns, not inside the policy class. See `simulation_flow.md` Section 4.4."

### Fix 15: Add tiered water pricing schema to structure.md

**Research basis:** Egyptian domestic water uses a 5-tier increasing block tariff (IBT) set by Council of Ministers decree. Last official decree: June 2018. De facto rates in 2024-2025 are ~40-50% above the 2018 levels per investigative reporting, though no new decree published. We use the 2018 official tiers as the baseline since they're the last formally published rates. All EGP values converted at 49.5 EGP/USD.

**Egyptian domestic water tariff tiers (2018 decree, official):**

| Tier | Consumption (m3/month) | EGP/m3 | USD/m3 |
|------|------------------------|--------|--------|
| 1    | 0-10                   | 0.65   | 0.013  |
| 2    | 11-20                  | 1.60   | 0.032  |
| 3    | 21-30                  | 2.25   | 0.045  |
| 4    | 31-40                  | 2.75   | 0.056  |
| 5    | 41+                    | 3.15   | 0.064  |

**Wastewater surcharge:** 75% of water bill (set June 2018). Total effective cost = water charge x 1.75.

**Note:** These USD prices look very low because Egyptian domestic water is heavily subsidized. The actual cost of production is ~1.4 EGP/m3 (2014 estimate). This contrasts sharply with the agricultural unsubsidized rate of 0.75 USD/m3 in the current settings, which represents desalinated water cost, not piped municipal supply. The simulation's domestic vs agricultural price difference is realistic: households pay subsidized piped supply; farms pay for self-produced desalinated groundwater or unsubsidized municipal.

**Changes:**
- **`structure.md`** domestic water subsidized section: expand to include 5-tier definitions:
  ```yaml
  domestic:
    pricing_regime: [subsidized, unsubsidized]
    subsidized:
      tier_pricing:
        - tier: 1
          max_m3_per_month: 10
          price_egp_per_m3: 0.65
        - tier: 2
          max_m3_per_month: 20
          price_egp_per_m3: 1.60
        - tier: 3
          max_m3_per_month: 30
          price_egp_per_m3: 2.25
        - tier: 4
          max_m3_per_month: 40
          price_egp_per_m3: 2.75
        - tier: 5
          max_m3_per_month: null
          price_egp_per_m3: 3.15
      wastewater_surcharge_pct: 75
    unsubsidized:
      base_price_usd_m3: 0.75
      annual_escalation_pct: 3.0
  ```
- **`settings/settings.yaml`**: update domestic water pricing to include the 5 tier brackets with EGP values (converted to USD at load time using `exchange_rate_egp_per_usd` from Fix 13)
- **Note:** Tier prices stored in EGP (native currency) per the pricing discussion. Converted to USD at data load time using the exchange rate parameter.

### Fix 16: E_processing Day 1 initialization
- **`simulation_flow.md`** Pre-Loop Initialization: add item 11: `Set E_processing = 0 for Day 1`

### Verification: Fresh food forced sales before market policy
The execution order (Step 4b → Step 5) already ensures expired/overflow inventory is force-sold before market policy runs. During implementation, I will:
- Verify the language in all three docs (structure.md, policies.md, simulation_flow.md) is unambiguous
- Add explicit cross-references where the umbrella rule is mentioned but the execution order isn't stated
- Confirm `simulation_flow.md` Section 10.5 resolution: forced sales are tagged with `decision_reason = "forced_expiry"` or `"forced_overflow"` and counted separately from voluntary market policy sales in metrics

## Execution Order

Batch 1 (independent schema additions): Fixes 11, 12, 13
Batch 2 (method naming): Fixes 3-5
Batch 3 (individual fixes): 1, 2, 6, 7, 8, 9, 10, 14, 15, 16

## Verification

1. Grep all four docs for stale method names (`execute_water_policy`, `execute_energy_policy`, `execute_crop_policy`, `process_harvests`)
2. Grep for `investment_allowed` across all files — confirm zero matches
3. Run `python src/settings/validation.py --registry` — verify new data file registered
4. Run `python src/settings/validation.py settings/settings.yaml` — verify YAML loads
5. Review cross-references between docs for consistency
