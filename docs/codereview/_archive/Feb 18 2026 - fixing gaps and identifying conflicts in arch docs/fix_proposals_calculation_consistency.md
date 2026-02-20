# Fix Proposals: Calculation Consistency (Section 5)

**Generated:** 2026-02-18
**Scope:** Section 5 (Calculation Consistency) and Section 7 action items #2-4, 8-10, 17-18, 22, 37
**Source:** `docs/codereview/systematic_doc_review_report.md`

---

## Summary of Issues Addressed

| Issue # | Section ID | Short Title | Severity |
| --- | --- | --- | --- |
| 2 | (missing formula) | E_irrigation_pump derivation | CRITICAL |
| 3 | (missing formula) | Daily storage cost formula | CRITICAL |
| 4 | (missing formula) | Daily labor cost formula | CRITICAL |
| 8 | C-2 | Battery discharge efficiency direction | IMPORTANT |
| 9 | C-3 | Generator minimum load behavior | IMPORTANT |
| 10 | C-4 | SOC_min vs battery_reserve_pct | IMPORTANT |
| 17 | C-5 | Blended vs cash cost distinction | IMPORTANT |
| 18 | C-7 | Salinity yield reduction | IMPORTANT |
| 22 | C-9 | E_treatment vs E_desal naming | MINOR |
| 37 | (minor) | Water pricing tier dependencies | MINOR |
| -- | C-1 | Post-harvest loss contradiction | CRITICAL |
| -- | C-6 | Fresh revenue formula loss_rate | IMPORTANT |
| -- | C-8 | Total energy demand 6 vs 7 components | IMPORTANT |

---

### Issue 2 / (missing formula): E_irrigation_pump Derivation

**Action Item:** Add E_irrigation_pump section to calculations.md. Document the derivation: P = (1.5 bar x 100000 Pa) / (0.75 x 3.6e6 J/kWh) = 0.056 kWh/m3.

**Severity:** CRITICAL

**Summary:** The simulation_flow.md (Section 5.5) references a hardcoded constant `irrigation_pressure_kwh_per_m3 = 0.056 kWh/m3` for drip irrigation pressurization energy, described as "drip irrigation at 1.5 bar, eta=0.75." However, calculations.md has no corresponding section deriving this value. A developer cannot verify or adjust this parameter without understanding the physics behind it.

**Proposed Solution:**

Add a new section to `calculations.md` after "Water Conveyance Energy" (Section 2) and before "Irrigation Water Demand." Title it "### Irrigation Pressurization Energy". The section should contain:

```markdown
### Irrigation Pressurization Energy

**Purpose:** Calculate energy required to pressurize treated water for drip irrigation delivery. This is distinct from groundwater pumping energy (which lifts water from the aquifer) and conveyance energy (which moves water horizontally through pipes). Drip irrigation systems require a minimum operating pressure at the emitter to ensure uniform distribution.

**Formula (specific energy per m3):**

    E_irrigation_pump [kWh/m3] = ΔP_drip / (eta_booster x 3,600,000)

Where:
- ΔP_drip: Required operating pressure for drip emitters (Pa)
- eta_booster: Booster pump efficiency (dimensionless)
- 3,600,000: Conversion factor from J to kWh (1 kWh = 3.6 x 10^6 J)

**Daily total:**

    E_irrigation_pump_daily [kWh/day] = E_irrigation_pump [kWh/m3] x total_irrigation_m3 [m3/day]

Where total_irrigation_m3 includes water delivered to ALL crops on ALL farms for the day (both groundwater-sourced and municipal-sourced water requires pressurization at the field).

**Default parameters:**

- ΔP_drip = 1.5 bar = 150,000 Pa (typical operating pressure for drip emitter systems; range 1.0-2.5 bar depending on emitter type, lateral length, and terrain)
- eta_booster = 0.75 (small booster pump efficiency; range 0.65-0.85 for fractional-HP centrifugal pumps)

**Worked example:**

    E_irrigation_pump = 150,000 / (0.75 x 3,600,000) = 0.0556 kWh/m3 (rounded to 0.056)

At 200 m3/day total irrigation: E_irrigation_pump_daily = 0.056 x 200 = 11.1 kWh/day

**Note:** This energy is applied to ALL irrigated water regardless of source (groundwater or municipal). Groundwater has already been pumped to the surface and treated; municipal water arrives at low pressure from the mains. Both require pressurization for drip delivery. This is NOT double-counted with the groundwater pumping energy (E_pump), which covers vertical lift only, or conveyance energy (E_convey), which covers horizontal transport losses. The irrigation pressurization pump is a separate physical device located at the field header.

**Output:** E_irrigation_pump in kWh/m3; E_irrigation_pump_daily in kWh/day

**Dependencies:**

- Configuration: `water_system.irrigation_system.type` (determines required pressure; drip = 1.5 bar, sprinkler = 2.5-4.0 bar)
- Parameter file: `data/parameters/equipment/irrigation_systems-toy.csv` (operating pressure, pump efficiency)

**Sources:**

- Drip irrigation operating pressure: Netafim design guides (1.0-2.5 bar at emitter); FAO Irrigation Manual
- Booster pump efficiency: Small centrifugal pumps 0.65-0.85 (lower for fractional HP units)
```

Also update the `E_demand` formula section in calculations.md to reference this new section. The `E_irrigation_pump(t)` line item in the Total Energy Demand description should add: "(see Irrigation Pressurization Energy above)".

**Files to edit:**
- `docs/arch/calculations.md`: Add new section after "Water Conveyance Energy"; update Total Energy Demand component description for E_irrigation_pump to cross-reference the new section.

**Confidence:** 5 -- The derivation is straightforward fluid mechanics (pressure energy = pressure / efficiency / unit conversion). The hardcoded value in simulation_flow.md is confirmed correct by the worked example.

---

**Owner Response:** Implement proposed solution

---

### Issue 3 / (missing formula): Daily Storage Cost Formula

**Action Item:** Add daily storage cost formula to calculations.md. Include rate table reference and Total OPEX integration.

**Severity:** CRITICAL

**Summary:** The simulation_flow.md Step 7 (Daily Accounting) and Section 4.10 deduct daily storage costs for held inventory, but calculations.md contains no formula, no reference to the data file, and no description of how storage costs integrate with Total OPEX. The data file `data/parameters/crops/food_storage_costs-toy.csv` exists (registered as `crops.storage_costs`) with per-product-type daily rates.

**Proposed Solution:**

Add a new section to `calculations.md` in Section 5 (Economic Calculations), after "Crop Revenue Calculation" and before "Debt Service Calculation." Title it "### Daily Storage Cost":

```markdown
### Daily Storage Cost

**Purpose:** Calculate the daily cost of holding processed food inventory in storage. Inventory holding cost is a material operating expense that accrues every day a product remains unsold.

**Formula:**

    daily_storage_cost [USD/day] = SUM over all tranches in farm_storage:
        tranche.kg x storage_cost_per_kg_per_day(tranche.product_type)

Where each tranche is a StorageTranche as defined in simulation_flow.md Section 4.7. The storage cost rate is looked up by product_type from the parameter file.

**Storage cost rates (from `food_storage_costs-toy.csv`):**

| Product Type | Ambient (USD/kg/day) | Climate Controlled (USD/kg/day) |
|---|---|---|
| fresh | 0.008 | 0.015 |
| packaged | 0.004 | 0.008 |
| canned | 0.001 | 0.002 |
| dried | 0.001 | 0.002 |

For MVP, use ambient storage rates for all product types. Climate-controlled rates apply to fresh produce in future scenarios with cold chain infrastructure.

**Integration with daily accounting:**

Daily storage cost is deducted in Step 7 of the simulation loop (Daily Accounting) as part of the daily cost aggregation:

    daily_costs = water_cost + energy_cost + daily_storage_cost + daily_labor_cost + daily_debt_service

**Integration with Total OPEX:**

    Annual_storage_cost = SUM(daily_storage_cost) over all days in year
    Total_OPEX += Annual_storage_cost

**Output:** daily_storage_cost in USD/day per farm; annual_storage_cost in USD/yr per farm

**Dependencies:**

- Parameter file: `data/parameters/crops/food_storage_costs-toy.csv` (via registry `crops.storage_costs`)
- Simulation state: farm_storage inventory (list of StorageTranches per farm)

**Notes:**

- Fresh produce has the highest daily holding cost because it requires rapid turnover or cold chain
- Shelf-stable products (canned, dried) are cheap to store, which is part of their economic value proposition
- Storage costs incentivize timely sales and penalize excessive hoarding
```

**Files to edit:**
- `docs/arch/calculations.md`: Add new section in Section 5 (Economic Calculations)

**Confidence:** 5 -- The data file already exists with clear column semantics. The formula is a direct lookup-and-multiply. simulation_flow.md Section 4.10 already specifies the identical formula; this proposal simply adds the missing calculations.md section.

---

**Owner Response: **Implement proposed solution

---

### Issue 4 / (missing formula): Daily Labor Cost Formula

**Action Item:** Add daily labor cost formula. Specify how annual labor estimates translate to daily costs (fixed daily rate? harvest-day multiplier?).

**Severity:** CRITICAL

**Summary:** The labor_requirements-toy.csv file contains per-hectare annual hours, per-kg processing hours, per-day management hours, and aggregate model parameters (base_field_labor = 200 hrs/ha/yr, working_days = 280/yr, harvest_multiplier = 3.0). The labor_wages-toy.csv file provides hourly wage rates by skill level. calculations.md Section 7 (Labor Calculations) is marked TBD. simulation_flow.md Step 7 lists "labor" as a daily cost aggregation component but provides no formula.

**Proposed Solution:**

Add a new section to `calculations.md` replacing the TBD marker at Section 7. Title it "## 7. Labor Calculations":

```markdown
## 7. Labor Calculations

**Purpose:** Calculate daily labor costs from annual labor requirement estimates, distinguishing between baseline (non-harvest) days and harvest days, when labor demand spikes.

### Daily Labor Cost

**Formula:**

Labor costs are modeled as a two-tier daily rate: a baseline rate on non-harvest days, and an elevated rate on harvest days.

**Annual labor hours (per farm):**

    annual_field_hours = base_field_labor_per_ha_yr x plantable_area_ha x crop_multiplier
    annual_processing_hours = annual_processed_kg x processing_labor_per_kg
    annual_maintenance_hours = SUM(equipment_maintenance_hours)
    annual_management_hours = (management_planning + management_coordination
                              + management_sales + management_administration) x working_days
    total_annual_hours = annual_field_hours + annual_processing_hours
                        + annual_maintenance_hours + annual_management_hours
    total_annual_hours *= (1 + admin_overhead)

**Where (from labor_requirements-toy.csv):**

- base_field_labor_per_ha_yr = 200 hours/ha/year
- working_days = 280 days/year
- crop_multiplier: per-crop multiplier (tomato=1.2, potato=0.9, onion=0.8, kale=0.7, cucumber=1.1)
- processing_labor_per_kg = 0.02 hours/kg
- management hours: planning=4, coordination=2, sales=3, administration=4 hours/day
- admin_overhead = 0.05 (5% overhead on total hours)
- harvest_multiplier = 3.0

**Daily allocation:**

    baseline_daily_hours = total_annual_hours / working_days
    harvest_daily_hours = baseline_daily_hours x harvest_multiplier

    IF today is a harvest day for any crop on this farm:
        daily_labor_hours = harvest_daily_hours
    ELSE:
        daily_labor_hours = baseline_daily_hours

**Daily cost:**

    daily_labor_cost [USD/day] = daily_labor_hours x blended_wage_rate_usd_per_hour

**Blended wage rate:**

    blended_wage_rate = 3.50 USD/hour (from labor_wages-toy.csv: blended_agricultural)

The blended rate is a weighted average across worker categories (field workers, supervisors, processing workers, managers) reflecting the typical skill mix for community agricultural operations. Using a single blended rate avoids the complexity of tracking individual worker categories at the daily level while remaining representative of actual labor costs.

**Output:** daily_labor_cost in USD/day per farm

**Dependencies:**

- Parameter file: `data/parameters/labor/labor_requirements-toy.csv` (via registry `labor.requirements`)
- Parameter file: `data/parameters/labor/labor_wages-toy.csv` (via registry `labor.wages`)
- Configuration: `farms[].plantable_area_ha` (farm size)
- Configuration: `farms[].crops[].name` (for crop multiplier lookup)
- Simulation state: harvest day flag per farm (from Step 0 daily conditions)

**Notes:**

- The harvest_multiplier of 3.0 reflects the seasonal surge in labor demand during harvest periods (additional seasonal workers, extended hours)
- Processing labor (per-kg) is computed annually from expected total throughput, then distributed across working days. On non-harvest, non-processing days this component is still present as maintenance, logistics, and preparation work
- For MVP, use the simple baseline/harvest two-tier model. Future enhancement: track labor by activity category for more granular cost allocation and FTE reporting
```

**Files to edit:**
- `docs/arch/calculations.md`: Replace TBD Section 7 with the above
- `docs/arch/simulation_flow.md`: No changes needed; Step 7 already references labor as a daily cost component. Optionally add a brief note in Step 7 referencing calculations.md Section 7 for the formula.

**Confidence:** 4 -- The formula is grounded in the actual data file parameters and follows standard agricultural labor costing methodology. The two-tier approach (baseline vs harvest day) is a reasonable simplification. The exact integration of processing labor hours across non-processing days may need owner review.

**Alternative Solutions:** Instead of distributing annual processing hours evenly, processing labor cost could be applied ONLY on days when food processing occurs (harvest days), using the per-kg rate directly: `processing_labor_cost_today = processed_kg_today x processing_labor_per_kg x processing_worker_wage`. This would make processing labor costs zero on non-harvest days and spike on harvest days. The annualized approach is simpler for MVP but the per-event approach is more physically accurate.

---

**Owner Response: **Implement a per-event approach. Labor is calculated for field prep, planting, nutrient application, harvesting, processing, storage, etc. based on csv file. If there are any missing categories, add to the csv file. The timing of events should be based on the crop planting schedule and standard practices. Research as needed to fill in gaps. If any questions remain, add notes at the bottom of the calculations. I would strongly suggest pre-building a labor hours per event table that spreads harvesting over a few days, etc. 

---

### Issue 8 / C-2: Battery Discharge Efficiency Direction

**Action Item:** Standardize battery discharge efficiency. Choose `* eta` or `/ eta` and update inconsistent doc.

**Severity:** IMPORTANT

**Summary:** calculations.md (Section 3, Battery Storage Dynamics) specifies the SOC update formula as `SOC(t+1) = SOC(t) + (P_charge x eta_charge - P_discharge / eta_discharge) x dt / capacity_kwh`. simulation_flow.md (Section 5.4, dispatch pseudocode) specifies `available_discharge = max(0, available_discharge) * eta_discharge`, meaning the usable energy OUT of the battery is `stored_energy x eta_discharge`. These two formulations model the efficiency loss in opposite directions: dividing by eta in the SOC formula means more energy is removed from the battery than is delivered, while multiplying by eta means less energy is delivered than is removed. Both are valid conventions but they must be consistent.

**Proposed Solution:**

The correct convention depends on where the "accounting boundary" is placed:

- **Convention A (calculations.md, SOC-centric):** The discharge command says "deliver X kWh to the load." To deliver X kWh, the battery must release X/eta kWh internally. The SOC formula tracks energy inside the battery, so it subtracts X/eta: `SOC -= P_discharge / eta_discharge / capacity_kwh`. This is the standard convention in battery modeling literature (e.g., HOMER, SAM).

- **Convention B (simulation\_flow.md, load-centric):** The discharge command says "the battery has Y kWh available above the reserve." The usable energy delivered to the load is Y * eta: `available_to_load = available_stored * eta_discharge`. Then the amount removed from the battery SOC is the full Y.

Both are physically correct if applied consistently. The simulation_flow.md dispatch pseudocode uses Convention B in the dispatch logic (line 568: `available_discharge = max(0, available_discharge) * eta_discharge`), but then the SOC update block (lines 920-923) uses:

```
energy_stored [kWh] = Battery_charge(t) x eta_charge
energy_removed [kWh] = Battery_discharge(t) / eta_discharge
SOC(t+1) = SOC(t) + (energy_stored - energy_removed) / capacity_kwh
```

This SOC update uses Convention A (dividing by eta), which contradicts the dispatch logic above it that uses Convention B (multiplying by eta). If the dispatch already reduced the delivered energy by eta, then dividing by eta again in the SOC update would double-count the loss.

**Resolution: Standardize on Convention A (calculations.md is correct). Fix simulation\_flow.md dispatch pseudocode.**

The dispatch should calculate available discharge as follows:

```
# Battery discharge (Convention A -- SOC-centric)
IF allocation.use_battery AND remaining_demand > 0:
    available_energy_in_battery = (battery_soc - allocation.battery_reserve_pct) * battery_capacity_kwh
    available_energy_in_battery = max(0, available_energy_in_battery)
    max_deliverable = available_energy_in_battery * eta_discharge   # energy out after losses
    battery_discharged = min(max_deliverable, remaining_demand)     # energy delivered to load
    remaining_demand -= battery_discharged
```

And the SOC update should be:

```
# SOC update (Convention A -- SOC-centric)
energy_stored_in_battery = Battery_charge(t) * eta_charge          # energy entering battery
energy_removed_from_battery = Battery_discharge(t) / eta_discharge  # energy leaving battery
SOC(t+1) = SOC(t) + (energy_stored_in_battery - energy_removed_from_battery) / capacity_kwh
```

Here `Battery_discharge(t)` is the energy delivered to the load (kWh), and `Battery_discharge(t) / eta_discharge` is the larger amount drained from the battery to achieve that delivery. This is internally consistent: the dispatch calculates how much can be delivered (`available * eta`), and the SOC update backs out how much was drained (`delivered / eta`).

**Rationale:** Convention A (SOC-centric with `/ eta_discharge`) is the standard in battery energy storage modeling. It maps directly to the physical reality: you always drain more energy from the battery than you deliver, due to internal resistance and power electronics losses.

**Files to edit:**
- `docs/arch/simulation_flow.md`: Section 5.4 dispatch pseudocode -- update battery discharge block and add clarifying comment. No change needed in the SOC update block (it already uses Convention A correctly).
- `docs/arch/calculations.md`: No change needed (already correct). Optionally add a note clarifying the convention choice.

**Confidence:** 5 -- This is standard battery modeling convention. The calculations.md formulation matches HOMER, SAM, and IEEE 2030.2 conventions. The dispatch pseudocode just needs a clarifying comment and alignment.

---

**Owner Response: **Implement proposed solution

[blank]

---

### Issue 9 / C-3: Generator Minimum Load Behavior

**Action Item:** Resolve generator minimum load behavior. Update calculations.md to match simulation_flow.md resolved behavior (always start, run at minimum).

**Severity:** IMPORTANT

**Summary:** calculations.md (Section 3, Backup Generator) specifies: "P_gen(t) = 0 if deficit < P_rated x min_load_fraction" (do not start the generator if demand is below minimum load). simulation_flow.md Section 5.4 and the resolved flag in Section 10.9 specify: the generator always starts when there is unmet demand under the microgrid policy, running at minimum load (30%) even if demand is below that threshold, with excess generation curtailed. The simulation_flow.md resolution is the correct behavior for off-grid communities where grid fallback does not exist.

**Proposed Solution:**

Update `calculations.md` Section 3 (Backup Generator Fuel Consumption) to replace the minimum load constraint pseudocode. Change from:

```
P_gen(t) = 0                          if deficit < P_rated x min_load_fraction
P_gen(t) = max(P_rated x 0.30, deficit)   otherwise
```

To:

```
IF deficit > 0:
    P_gen(t) = max(P_rated x min_load_fraction, deficit)
    generator_curtailed = max(0, P_gen(t) - deficit)
ELSE:
    P_gen(t) = 0
    generator_curtailed = 0
```

Add the following clarifying note after the formula:

> **Note:** The generator always starts when there is any unmet demand, even if the demand is below the minimum load threshold. Running below 30% load causes wet stacking and carbon buildup, so the generator runs at the minimum load floor and the excess generation above the actual demand is curtailed (wasted as heat). This wastes some fuel but ensures no unmet demand for off-grid communities using the `microgrid` policy. For grid-connected policies (`renewable_first`, `all_grid`), the generator is not dispatched because grid import serves as the fallback.

**Rationale:** An off-grid community cannot leave demand unmet just because the deficit happens to be small. The generator must start. The previous formulation in calculations.md was appropriate for grid-connected scenarios where small deficits can be met by grid import, but the microgrid policy explicitly has no grid fallback. simulation_flow.md Section 10.9 already resolved this question.

**Files to edit:**
- `docs/arch/calculations.md`: Replace the minimum load pseudocode in the "Backup Generator Fuel Consumption" section

**Confidence:** 5 -- This is explicitly resolved in simulation_flow.md Section 10.9. The calculations.md text simply needs to match.

---

**Owner Response: **Implement proposed solution

[blank]

---

### Issue 10 / C-4: SOC_min vs battery_reserve_pct Relationship

**Action Item:** Clarify SOC_min (0.10 hardware) vs battery_reserve_pct (0.20 policy) relationship. Add note that effective floor = max(SOC_min, battery_reserve_pct).

**Severity:** IMPORTANT

**Summary:** calculations.md defines `SOC_min = 0.10` (10%) as a hardware constraint for LFP batteries to protect longevity. The `batteries-toy.csv` data file confirms `soc_min = 0.10`. Separately, the energy policy in simulation_flow.md Section 5.2 returns a `battery_reserve_pct` field (a float 0-1) that represents the policy's desired minimum SOC. The dispatch pseudocode (Section 5.4, line 567) uses `battery_reserve_pct` as the floor for discharge calculations: `available_discharge = (battery_soc - allocation.battery_reserve_pct) * battery_capacity_kwh`. The relationship between these two constraints is not documented. If a policy sets `battery_reserve_pct = 0.05` (below the hardware SOC_min of 0.10), the dispatch would attempt to discharge below the safe hardware limit.

**Proposed Solution:**

Add a clarifying note to both documents:

**In ****`calculations.md`****, Section 3 (Battery Storage Dynamics), after the SOC\_min constraint block, add:**

```markdown
**Hardware vs. policy SOC floor:**

The battery has two independent SOC floor constraints:

1. `SOC_min` = 0.10 (10%) -- Hardware protection limit from battery management system (BMS). Discharging below this level accelerates degradation and risks cell damage. This is a physical property of the battery, defined in `batteries-toy.csv`.

2. `battery_reserve_pct` -- Policy-configurable reserve target returned by the energy policy. This allows policies to maintain a higher reserve (e.g., 0.20 = 20%) for resilience or emergency backup.

The effective discharge floor is:

    effective_soc_floor = max(SOC_min, battery_reserve_pct)

The dispatch function must enforce: `available_discharge = (battery_soc - effective_soc_floor) * battery_capacity_kwh`. The hardware limit is always respected regardless of policy configuration; the policy can only raise the floor above the hardware minimum, never lower it.
```

**In ****`simulation_flow.md`****, Section 5.4, update line 567 from:**

```
available_discharge = (battery_soc - allocation.battery_reserve_pct) * battery_capacity_kwh
```

**To:**

```
effective_soc_floor = max(SOC_min, allocation.battery_reserve_pct)
available_discharge = (battery_soc - effective_soc_floor) * battery_capacity_kwh
```

**In ****`simulation_flow.md`****, Section 5.2, add a note under ****`battery_reserve_pct`****:**

```
battery_reserve_pct: float     # Minimum battery SOC to maintain (0-1); effective floor is max(SOC_min, battery_reserve_pct) where SOC_min is the hardware limit from battery data (default 0.10)
```

**Rationale:** The hardware SOC_min is a physical safety constraint that must never be violated. The policy reserve is an operational preference that layers on top. This is standard practice in battery management -- the BMS enforces a hard cutoff regardless of what the control system requests.

**Files to edit:**
- `docs/arch/calculations.md`: Add note in Battery Storage Dynamics section
- `docs/arch/simulation_flow.md`: Update dispatch pseudocode (Section 5.4) and EnergyAllocation definition (Section 5.2)

**Confidence:** 5 -- This follows standard battery management system design where hardware limits are inviolable and software/policy limits are additive.

---

**Owner Response: **Implement proposed solution

[blank]

---

### Issue 17 / C-5: Blended vs Cash Cost Distinction

**Action Item:** Clarify blended cost vs cash cost distinction. Note that dispatch cost is cash; LCOE-inclusive cost is economic metric only.

**Severity:** IMPORTANT

**Summary:** calculations.md Section 3 (Blended Electricity Cost) includes `LCOE_renewable` in the total electricity cost formula: `Total_electricity_cost = (Grid_import x grid_price) + (Generator_output x SFC x diesel_price) + (E_renewable_used x LCOE_renewable) - (Grid_export x export_price)`. However, the dispatch cost calculation in simulation_flow.md Section 5.4 only includes cash costs: `total_energy_cost = grid_cost + generator_cost - export_revenue`. Renewable self-consumption has zero marginal cash cost. These two formulations serve different purposes but the distinction is not documented, which could lead a developer to either double-count renewable costs or omit them from economic metrics.

**Proposed Solution:**

Add a clarifying note to `calculations.md` in the Blended Electricity Cost section, immediately after the formula block:

```markdown
**Cash cost vs. economic (blended) cost distinction:**

The simulation tracks two distinct cost measures for electricity:

1. **Cash cost (dispatch cost)** -- The actual out-of-pocket expenditure on a given day. This includes only grid import charges, diesel fuel, and grid export credits. Renewable self-consumption has zero marginal cash cost. This is the cost used in daily accounting (simulation_flow.md Step 7) and in policy cost comparisons.

    daily_energy_cash_cost = grid_imported * grid_price + generator_fuel_L * diesel_price - grid_exported * export_price

2. **Economic cost (blended cost)** -- The fully-loaded cost including amortized renewable infrastructure investment (LCOE). This attributes a shadow cost to each kWh of renewable energy consumed, reflecting the capital investment required to produce it. This is used ONLY in economic metrics (NPV, IRR, LCOE reporting) and comparative analysis. It is NOT used in daily operational decisions or cash flow tracking.

    total_economic_energy_cost = daily_energy_cash_cost + (renewable_used_kwh * LCOE_renewable)

The LCOE_renewable term is an accounting construct, not a cash outflow. Including it in blended cost enables fair comparison between scenarios with different renewable penetration levels (e.g., comparing a heavily-PV community against a grid-dependent one). Without it, the PV scenario would appear to have near-zero electricity cost, masking the capital investment required.

**Implementation guidance:** The dispatch function returns cash costs only. The blended cost is computed at metrics calculation time (yearly boundary or end of simulation), not during daily dispatch.
```

**Files to edit:**
- `docs/arch/calculations.md`: Add clarifying note in Blended Electricity Cost section

**Confidence:** 5 -- The distinction between marginal cash cost and fully-loaded economic cost is standard in energy economics. The dispatch must use cash cost for operational decisions; the blended cost is for economic evaluation only.

---

**Owner Response: **Implement proposed solution

[blank]

---

### Issue 18 / C-7: Salinity Yield Reduction Absent from simulation_flow.md

**Action Item:** Reconcile salinity yield reduction. Either add salinity_factor to simulation_flow.md harvest formula or explicitly exclude for MVP.

**Severity:** IMPORTANT

**Summary:** calculations.md Section 4 (Soil Salinity Yield Reduction) provides a detailed FAO-29 threshold-slope model and a combined yield formula: `Y_actual = Y_potential x water_stress_factor x salinity_factor x yield_factor`. However, simulation_flow.md Section 4.2 (Harvest Yield Calculation) uses: `raw_yield_kg = Y_potential x water_stress_factor x yield_factor x effective_area_ha`, which omits `salinity_factor`. calculations.md itself notes: "For MVP: Can be omitted if simulation <= 3 years."

**Proposed Solution:**

**Explicitly exclude salinity\_factor from simulation\_flow.md for MVP, with a documented path to inclusion.**

In `simulation_flow.md` Section 4.2, add a note after the harvest yield formula:

```markdown
**Salinity yield reduction (deferred for MVP):**

The combined yield model in calculations.md Section 4 includes a `salinity_factor` for progressive salt accumulation in the root zone:

    Y_actual = Y_potential x water_stress_factor x salinity_factor x yield_factor x effective_area_ha

For MVP, the salinity_factor is omitted (treated as 1.0). This is acceptable for simulations of 3 years or less. For simulations exceeding 5 years with brackish groundwater sources, salt accumulation becomes a first-order yield effect and salinity_factor MUST be included. The implementation path is:

1. Track cumulative irrigation EC per crop across seasons (ECe accumulation model in calculations.md)
2. Lookup crop salinity tolerance parameters from `crop_salinity_tolerance-toy.csv`
3. Compute salinity_factor = max(0, 1 - b x max(0, ECe - ECe_threshold) / 100)
4. Multiply into the harvest yield formula

The data file `data/parameters/crops/crop_salinity_tolerance-toy.csv` already exists with FAO-29 parameters for all 5 crops.
```

In `calculations.md` Section 4 (Soil Salinity Yield Reduction), add a note at the top:

```markdown
> **MVP status:** This calculation is fully specified but excluded from the MVP simulation loop (simulation_flow.md Section 4.2). For MVP, salinity_factor = 1.0 (no salinity reduction). Include when simulation horizon exceeds 5 years.
```

**Rationale:** The MVP simulation runs 2015-2020 (6 years per settings.yaml), which is borderline. However, salt accumulation depends on the fraction of brackish groundwater used for irrigation. Under the `cheapest_source` or `max_municipal` policies, little or no brackish water reaches crops. Excluding salinity for MVP is acceptable with the understanding that it becomes critical for longer runs or groundwater-heavy policies.

**Files to edit:**
- `docs/arch/simulation_flow.md`: Add note in Section 4.2 after harvest yield formula
- `docs/arch/calculations.md`: Add MVP status note at top of Soil Salinity Yield Reduction section

**Confidence:** 4 -- The exclusion for MVP is defensible, but the 6-year default simulation length is borderline. If the owner intends to run groundwater-heavy 15-year scenarios, salinity should be included sooner.

**Alternative Solutions:** Include salinity_factor immediately in the MVP harvest formula. This would require tracking per-crop cumulative ECe and adding leaching fraction logic to the daily water balance. The data infrastructure exists (crop_salinity_tolerance-toy.csv) but the simulation state tracking does not yet exist.

---

**Owner Response: **Implement proposed solution, but allow the user to turn this off if they desire. This is a complication that we do not yet have enough data to properly model.

[blank]

---

### Issue 22 / C-9: E_treatment vs E_desal Naming Inconsistency

**Action Item:** Rename E_treatment to E_desal consistently (or vice versa) across all documents.

**Severity:** MINOR

**Summary:** calculations.md consistently uses `E_treatment` (6 occurrences: in the Water Treatment Energy section heading, formula, output, total demand formula, and water cost formula). simulation_flow.md uses `E_desal` (3 occurrences: Step 3 demand aggregation, Section 5.5 total demand formula, and the WHERE clause). The underlying physical process is brackish water reverse osmosis (BWRO) desalination. The term collision is confusing because "treatment" is a broader term (could include any water processing) while "desal" (desalination) is more specific to the actual process.

**Proposed Solution:**

**Standardize on ****`E_desal`**** across all documents.**

Rationale: "Desalination" (or "desal" for short) is more precise for the actual process being modeled (BWRO). "Treatment" is ambiguous -- it could refer to chlorination, filtration, UV treatment, or other processes. Since the model specifically models energy for reverse osmosis desalination of brackish groundwater, `E_desal` communicates the physical process more clearly to both developers and community stakeholders.

**Occurrences to update in ****`calculations.md`****:**

1. Section heading "### Water Treatment Energy (BWRO)" -- rename to "### Water Desalination Energy (BWRO)" or keep heading but change variable name
2. Line 114: `E_treatment = f(tds_ppm, recovery_rate, membrane_type)` --> `E_desal = f(...)`
3. Line 140: `**Output:** E_treatment in kWh/m3` --> `**Output:** E_desal in kWh/m3`
4. Line 815: `E_demand(t) = E_pump(t) + E_treatment(t) + ...` --> `E_demand(t) = E_pump(t) + E_desal(t) + ...`
5. Line 951: Same formula, same change
6. Line 958: Component description `E_treatment(t) [kWh/day]: BWRO desalination energy` --> `E_desal(t) [kWh/day]: BWRO desalination energy`
7. Line 1570: Water cost formula `E_treatment [kWh/m3]` --> `E_desal [kWh/m3]`

**No changes needed in simulation\_flow.md** (already uses `E_desal`).

**No changes needed in policies.md** (uses `treatment_kwh_per_m3` as a context field name, which is a field name not a formula variable -- the field name can stay as-is since it describes the data source).

**Files to edit:**
- `docs/arch/calculations.md`: 7 occurrences of `E_treatment` renamed to `E_desal`

**Confidence:** 5 -- This is a straightforward find-and-replace with no semantic ambiguity. The variable name change has no impact on formulas or logic.

---

**Owner Response: **Implement proposed solution

[blank]

---

### Issue 37 / (minor): Water Pricing Tier Dependencies

**Action Item:** Fix calculations.md water pricing dependencies (agricultural tier_pricing reference where only domestic uses tiers).

**Severity:** MINOR

**Summary:** In calculations.md Section 5 (Tiered Municipal Water Pricing), the Dependencies block references `water_pricing.agricultural.subsidized.tier_pricing` alongside `water_pricing.domestic.subsidized.tier_pricing`. However, the settings.yaml schema and simulation_flow.md Section 3.3 make clear that tiered pricing applies ONLY to domestic water. Agricultural water uses flat rates with optional annual escalation (subsidized or unsubsidized). The agricultural pricing section in settings.yaml has no `tier_pricing` key. Referencing an agricultural tier creates confusion: a developer might implement tier logic for agricultural water that does not exist.

**Proposed Solution:**

In `calculations.md`, Section 5 (Tiered Municipal Water Pricing), replace the Dependencies block from:

```
- Configuration: `water_pricing.agricultural.subsidized.tier_pricing` or `water_pricing.domestic.subsidized.tier_pricing` (bracket definitions, per consumer type)
- Configuration: `water_pricing.[agricultural|domestic].subsidized.tier_pricing.wastewater_surcharge_pct`
```

To:

```
- Configuration: `water_pricing.domestic.subsidized.tier_pricing` (bracket definitions for domestic consumers only)
- Configuration: `water_pricing.domestic.subsidized.wastewater_surcharge_pct` (surcharge on domestic tiered water bills)
```

Add a clarifying note:

```markdown
> **Note:** Tiered pricing applies to domestic water consumption only. Agricultural water uses flat-rate pricing (subsidized or unsubsidized) with optional annual escalation. See simulation_flow.md Section 3.3 for the full price resolution logic by consumer type.
```

**Rationale:** The settings.yaml schema defines agricultural water pricing as a single flat rate per m3 (with escalation). Only domestic water has the 5-tier increasing block tariff structure modeled on the Egyptian HCWW system. The dependency reference to agricultural tiers is simply a documentation error -- the tier pricing function is never called with agricultural consumer type.

**Files to edit:**
- `docs/arch/calculations.md`: Update dependencies in Tiered Municipal Water Pricing section

**Confidence:** 5 -- Verified against settings.yaml (no agricultural tier_pricing key exists) and simulation_flow.md Section 3.3 (agricultural uses flat rate, domestic uses tiers).

---

**Owner Response: **Implement proposed solution

[blank]

---

### Issue -- / C-1: Post-Harvest Loss Contradiction

**Action Item:** Resolve post-harvest loss contradiction. Decide whether fresh produce has a 10% handling loss (calculations.md) or 0% loss (simulation_flow.md weight-loss model).

**Severity:** CRITICAL

**Summary:** Two conflicting models exist for fresh produce losses:

1. **calculations.md Section 4 (Post-Harvest Losses):** States `loss_rate = 0.10` (10%) for fresh produce, applied as `Marketable_yield_kg = harvest_yield_kg x (1 - loss_rate)`. The Fresh Revenue formula (Section 5) also includes `(1 - loss_rate)`: `Fresh_revenue = fresh_yield_kg x fresh_price_per_kg x (1 - loss_rate)`.

2. **simulation\_flow.md Section 4.5 (Weight Loss):** States fresh weight_loss_pct = 0% (confirmed in processing_specs-toy.csv: `tomato,fresh,0.0,...`). The chain overview (Section 4.1) explicitly states: "Post-harvest handling losses are applied per pathway, NOT as a separate pre-processing step."

3. **handling\_loss\_rates-toy.csv:** Has `fresh,10.0` for all crops, confirming that a 10% handling loss rate exists in the data.

The contradiction is between the "weight loss per pathway" model (where fresh = 0%) and the "handling loss" model (where fresh = 10%). These are different physical phenomena being conflated:
- **Weight loss during processing** (processing_specs-toy.csv): Physical mass reduction from dehydration, trimming, etc. Fresh produce undergoes no processing, so weight loss = 0%.
- **Handling losses** (handling_loss_rates-toy.csv): Spoilage, bruising, dropped produce, and transport damage between harvest and sale. Fresh produce is most vulnerable, so handling loss = 10%.

**Proposed Solution:**

**Keep both loss types, but apply them at different points in the chain.** They model distinct physical phenomena and should not be merged or eliminated.

1. **Weight loss (processing\_specs):** Applied during food processing (Step 4). Fresh = 0%, packaged = 3%, canned = 15%, dried = 78-92%. This is correct as-is in simulation_flow.md Section 4.5.

2. **Handling loss (handling\_loss\_rates):** Applied AFTER processing weight loss but BEFORE revenue calculation. This represents spoilage and damage that occurs between production and sale for ALL product types, not just fresh.

Update `simulation_flow.md` Section 4.5 to add a handling loss step after weight loss:

```markdown
### 4.5b Handling Losses

After weight loss from processing, handling losses are applied to all product types:

    saleable_kg = output_kg * (1 - handling_loss_pct / 100)

Handling loss rates are loaded from `handling_loss_rates-toy.csv` (per crop, per pathway):

| Pathway | Handling Loss |
|---------|--------------|
| fresh | 10% |
| packaged | 4% |
| canned | 4% |
| dried | 4% |

The saleable_kg (not output_kg) is what enters storage as the tranche quantity. Revenue is based on saleable_kg.
```

Update `simulation_flow.md` Section 4.1 (Chain Overview) to include the handling loss step:

```
harvest_yield_kg
    -> food policy split (fractions by pathway)
    -> capacity clipping (shared post-processing)
    -> weight loss per pathway (physical transformation during processing)
    -> handling loss per pathway (spoilage/damage between production and sale)
    -> saleable_kg per product type
    -> create StorageTranches (with saleable_kg)
    -> check forced sales (umbrella rule)
    -> market policy decision (sell/store remaining)
    -> revenue calculation (sold_kg * price_per_kg per product type)
```

Update `calculations.md` Section 4 (Post-Harvest Losses) to clarify that handling losses are distinct from processing weight losses:

```markdown
> **Clarification:** Handling losses and processing weight losses are distinct physical phenomena applied at different stages. Processing weight loss (from processing_specs-toy.csv) models mass reduction during transformation (e.g., 88% water removal for dried tomatoes). Handling loss (from handling_loss_rates-toy.csv) models spoilage, bruising, and transport damage that occurs regardless of processing. Both are applied sequentially: weight_loss first (during Step 4), then handling_loss (Step 4.5b), before the product enters storage.
```

Update `calculations.md` Section 5 (Crop Revenue Calculation) to remove the `(1 - loss_rate)` from the Fresh Revenue formula, since handling loss is now applied upstream (before storage):

Replace:
```
Fresh_revenue [USD] = fresh_yield_kg [kg] x fresh_price_per_kg [USD/kg] x (1 - loss_rate)
```
With:
```
Fresh_revenue [USD] = saleable_fresh_kg [kg] x fresh_price_per_kg [USD/kg]
```

Where `saleable_fresh_kg` already reflects both the 0% processing weight loss and the 10% handling loss applied in the production chain.

**Rationale:** This resolves the contradiction by properly separating two distinct loss mechanisms. The existing data files already support this: processing_specs-toy.csv for weight loss and handling_loss_rates-toy.csv for handling losses. Fresh produce correctly has 0% weight loss (no processing) but 10% handling loss (highest spoilage rate). Processed products have processing-specific weight loss AND a lower 4% handling loss.

**Files to edit:**
- `docs/arch/simulation_flow.md`: Add Section 4.5b; update Section 4.1 chain overview; update Section 4.2 or 4.5 to clarify the sequential application
- `docs/arch/calculations.md`: Clarify Section 4 (Post-Harvest Losses); update Section 5 (Fresh Revenue formula)

**Confidence:** 4 -- The two-stage loss model is physically correct and supported by existing data files. However, the owner should confirm that the 10% fresh handling loss is intended to reduce the tranche quantity entering storage (reducing both the stored volume and the eventual revenue), rather than being a revenue-time discount. If losses are modeled as tranche reduction, storage costs are also reduced (less kg to store), which is the more accurate physical model.

**Alternative Solutions:** Eliminate the handling_loss_rates-toy.csv file entirely and set fresh weight_loss_pct to 10% in processing_specs-toy.csv. This would merge both loss types into a single processing weight loss, simplifying the chain but conflating two distinct phenomena. This approach cannot model differential handling losses by pathway (e.g., if fresh has 10% loss but canned has only 2%).

---

**Owner Response: **Implement proposed solution

[blank]

---

### Issue -- / C-6: Fresh Revenue Formula Includes (1-loss_rate)

**Action Item:** Reconcile fresh revenue formula between calculations.md and simulation_flow.md.

**Severity:** IMPORTANT

**Summary:** calculations.md Section 5 (Crop Revenue Calculation) specifies: `Fresh_revenue = fresh_yield_kg x fresh_price_per_kg x (1 - loss_rate)`. simulation_flow.md Section 4.9 specifies: `sale_revenue = sold_kg x current_price_per_kg` with no loss_rate term. This is related to Issue C-1 (post-harvest loss contradiction) and shares the same root cause.

**Proposed Solution:**

**This issue is resolved by the C-1 fix above.** Once handling losses are applied at production time (Step 4.5b) to reduce the tranche quantity before it enters storage, the revenue formula correctly uses the sold quantity without any additional loss adjustment:

```
sale_revenue = sold_kg x current_price_per_kg(crop_name, product_type)
```

The `sold_kg` already reflects handling losses because the tranche was created with `saleable_kg` (after handling loss), not `output_kg` (before handling loss). The simulation_flow.md revenue formula (Section 4.9) is correct as written. The calculations.md fresh revenue formula needs to be updated per the C-1 fix to remove the `(1 - loss_rate)` term.

The unified revenue formula applies identically to ALL product types (fresh, packaged, canned, dried):

```
sale_revenue = sold_kg x current_price_per_kg(crop_name, product_type)
```

No product-type-specific loss adjustment at sale time. All losses are upstream.

**Files to edit:**
- `docs/arch/calculations.md`: Update Fresh Revenue formula (already covered by C-1 fix above)

**Confidence:** 5 -- This is a direct consequence of the C-1 resolution. Once losses are applied upstream, the revenue formula is clean and uniform.

---

**Owner Response: **Implement proposed solution

[blank]

---

### Issue -- / C-8: Total Energy Demand 6 vs 7 Components

**Action Item:** Add E_community_bldg to calculations.md total demand formula. Update from 6 to 7 components.

**Severity:** IMPORTANT

**Summary:** simulation_flow.md Section 5.5 lists 7 energy demand components including `E_community_bldg`. calculations.md Section 3 (Total Energy Demand) lists only 6 components, omitting `E_community_bldg`. The section heading even says "(full model -- all 6 demand components)". The data infrastructure exists: `community_buildings.energy` is registered and precomputed data files exist.

**Proposed Solution:**

Update `calculations.md` Section 3 (Total Energy Demand) in three places:

1. Change the section description from "all 6 demand components" to "all 7 demand components".

2. Update the formula from:

```
E_demand(t) [kWh/day] = E_pump(t) + E_desal(t) + E_convey(t)
                      + E_household(t) + E_processing(t) + E_irrigation_pump(t)
```

To:

```
E_demand(t) [kWh/day] = E_pump(t) + E_desal(t) + E_convey(t)
                      + E_household(t) + E_community_bldg(t) + E_processing(t)
                      + E_irrigation_pump(t)
```

(Note: also applying the E_treatment -> E_desal rename from Issue 22.)

3. Add a component description for `E_community_bldg`:

```
- `E_community_bldg(t) [kWh/day]`: Community building electricity demand (offices, warehouses, meeting hall, workshop). Loaded from precomputed data via registry `community_buildings.energy`, providing per-m2 daily rates with temperature-adjusted seasonal variation. Scaled by building areas configured in `community_structure.community_buildings`.
```

4. Update the dispatch section formula (also in calculations.md) where it reads:

```
E_demand(t) [kWh] = E_pump(t) + E_treatment(t) + E_convey(t)
                  + E_household(t) + E_processing(t) + E_irrigation_pump(t)
```

To match the 7-component version.

**Rationale:** The community buildings (office, warehouse, meeting hall, workshop) total 2,000 m2 in the default scenario. Even at modest energy intensity (e.g., 0.02-0.05 kWh/m2/day for lighting, ventilation, and equipment), this could be 40-100 kWh/day -- a non-trivial fraction of community energy demand. Omitting it from the formula in calculations.md would cause a developer implementing from that document alone to undersize the energy system.

**Files to edit:**
- `docs/arch/calculations.md`: Update Total Energy Demand section (formula, component count, component list) and the dispatch section formula

**Confidence:** 5 -- simulation_flow.md already includes this component with full documentation. calculations.md simply needs to match.

---

**Owner Response: **Implement proposed solution

[blank]

---

## Cross-Reference Matrix

The following table maps each issue to the specific files and line ranges that require edits:

| Issue | calculations.md | simulation_flow.md | policies.md | data files |
| --- | --- | --- | --- | --- |
| #2 E_irrigation_pump | ADD new section after Water Conveyance Energy | No change | No change | No change |
| #3 Storage costs | ADD new section in Section 5 | No change | No change | No change (file exists) |
| #4 Labor costs | REPLACE TBD Section 7 | Optional cross-ref in Step 7 | No change | No change (files exist) |
| #8 Battery eta | Optional clarifying note | UPDATE Section 5.4 dispatch pseudocode | No change | No change |
| #9 Generator min load | UPDATE Section 3 pseudocode | No change (already correct) | No change | No change |
| #10 SOC_min/reserve | ADD note in Section 3 | UPDATE Sections 5.2, 5.4 | No change | No change |
| #17 Blended/cash cost | ADD note in Blended Electricity Cost | No change | No change | No change |
| #18 Salinity yield | ADD MVP status note in Section 4 | ADD note in Section 4.2 | No change | No change (file exists) |
| #22 E_treatment->E_desal | RENAME 7 occurrences | No change (already uses E_desal) | No change | No change |
| #37 Water pricing tiers | UPDATE dependencies in Section 5 | No change | No change | No change |
| C-1 Post-harvest loss | UPDATE Sections 4-5 | ADD Section 4.5b; UPDATE 4.1 | No change | No change (files exist) |
| C-6 Fresh revenue formula | UPDATE Section 5 (covered by C-1) | No change | No change | No change |
| C-8 E_community_bldg | UPDATE Section 3 (2 formula blocks) | No change (already correct) | No change | No change |

**Total edits required:**
- `calculations.md`: 10 changes (3 new sections, 4 updates, 3 renames)
- `simulation_flow.md`: 4 changes (1 new section, 3 updates)
- `policies.md`: 0 changes
- Data files: 0 changes

---

*Fix proposals generated by Agent D for documentation review process.*
