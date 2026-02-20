# Fix Proposals: Flow Completeness (Section 3)

**Generated:** 2026-02-18  
**Scope:** Section 3 (Flow Completeness) and Section 7 action items #1, 4-5, 7-16, 35-36  
**Source:** `docs/codereview/systematic_doc_review_report.md`

---

### Issue 1 / F-1: Post-Harvest Loss Contradiction

**Action Item:** Resolve post-harvest loss contradiction. Decide whether fresh produce has a 10% handling loss (calculations.md) or 0% loss (simulation_flow.md weight-loss model). Update the superseded document.

**Severity:** CRITICAL

**Summary:** calculations.md Section 4 (Post-Harvest Losses) defines a 10% default handling loss for fresh produce and 4% for processed, applied as a deduction before revenue calculation. simulation_flow.md Section 4.5 defines per-pathway weight loss using data from `processing_specs-toy.csv`, where fresh weight_loss_pct = 0%. These two models are physically describing different phenomena but are being conflated in the revenue formula, leading to double-counting or omission depending on which doc the implementer follows.

**Proposed Solution:**

These are two distinct physical phenomena and should both be modeled, but at different stages of the chain:

1. **Weight loss during processing** (simulation_flow.md Section 4.5): This is the physical mass transformation during processing -- water removal in drying (88% for tomato), trimming in packaging (3%), etc. Fresh produce undergoes no processing transformation, so weight_loss_pct = 0% is correct. This is already correctly specified in simulation_flow.md and confirmed by `processing_specs-toy.csv`.
2. **Post-harvest handling loss** (calculations.md Section 4): This represents physical losses from bruising, spoilage during transport, rejected product at market, and general handling damage between harvest and the point of sale or processing intake. This is a real phenomenon -- FAO estimates 10-15% fresh produce losses in developing economies during handling and transport. It occurs BEFORE the food enters any processing pathway.

**Resolution: Keep both, apply sequentially, clarify in both docs.**

**Edit `simulation_flow.md` Section 4.2** -- Add handling loss before the food policy split:

Replace the current harvest yield block with:

```
raw_yield_kg = Y_potential * water_stress_factor * yield_factor * effective_area_ha

water_stress_factor = 1 - K_y * (1 - water_ratio)
water_ratio = clamp(cumulative_water_received / expected_total_water, 0, 1)
effective_area_ha = plantable_area_ha * area_fraction * percent_planted

# Post-harvest handling loss (bruising, transport damage, rejected product)
# Applied BEFORE processing split -- this is physical loss, not processing transformation
handling_loss_rate = lookup from crop parameters (default 0.10 for fresh, 0.04 for processed intake)
harvest_available_kg = raw_yield_kg * (1 - handling_loss_rate)

# harvest_available_kg enters the food processing pipeline
```

**Edit `simulation_flow.md` Section 4.1 chain overview** to insert the handling loss step:

```
harvest_yield_kg
    -> post-harvest handling loss (bruising, transport, rejected product)
    -> harvest_available_kg
    -> food policy split (fractions by pathway)
    -> capacity clipping (shared post-processing)
    -> weight loss per pathway (physical transformation)
    -> processed_output_kg per product type
    ...
```

**Edit `simulation_flow.md` Section 4.5 comment** to clarify the distinction:

Add a note:

```
Note: Weight loss here is the PROCESSING transformation (water removal, trimming).
Post-harvest HANDLING losses (bruising, transport damage) are applied upstream in
Section 4.2 before the food policy split. Fresh weight_loss_pct = 0% is correct
because fresh produce undergoes no processing transformation.
```

**Edit `calculations.md` Section 4 (Post-Harvest Losses)** -- Clarify that the 10% loss is a handling loss applied before the processing split, not a weight-loss-during-processing:

Replace `Loss_kg = harvest_yield_kg * loss_rate` with:

```
# Post-harvest handling loss (applied before food processing split)
handling_loss_kg = raw_yield_kg * handling_loss_rate
harvest_available_kg = raw_yield_kg - handling_loss_kg

# handling_loss_rate defaults:
#   - 0.10 (10%) for all crops at harvest point (before any processing)
#   - Crop-specific rates may be defined in crop parameter files
#
# This is distinct from processing weight loss (Section 4, Processed Product Output),
# which represents physical mass change during drying, canning, etc.
```

**Edit `calculations.md` Section 5 (Crop Revenue Calculation)** -- Remove the `(1 - loss_rate)` from the fresh revenue formula since the handling loss is now applied upstream:

Change:

```
Fresh_revenue [USD] = fresh_yield_kg [kg] * fresh_price_per_kg [USD/kg] * (1 - loss_rate)
```

To:

```
Fresh_revenue [USD] = fresh_output_kg [kg] * fresh_price_per_kg [USD/kg]
```

Add note: `fresh_output_kg already reflects both the upstream handling loss and the processing weight loss (0% for fresh). No further loss deduction at the revenue stage.`

**Rationale:** This resolution preserves both physical phenomena, eliminates double-counting, and aligns the two documents. The handling loss is real (FAO data supports 10-15% in developing-economy supply chains) and occurs before any processing decision. The processing weight loss is a separate mass transformation. The single handling_loss_rate parameter (default 0.10) simplifies the implementation while remaining physically accurate.

**Data dependency:** The handling_loss_rate should be added to `crop_coefficients-toy.csv` or a dedicated column in `processing_specs-toy.csv`. Alternatively, it can be a single scalar parameter in settings.

**Confidence:** 5 -- Both phenomena are well-documented in agricultural engineering literature (FAO-33, FAO post-harvest loss guides). The sequential application is the standard modeling approach.

---

**Owner Response:** Implement proposed solution. However, fresh food is processed on site and so spoilage from transport and handling is reduced to get to the processing facility. Reduce the FAO estimate and make it a parameter that users config in the settings.yaml. Update all files as needed to include this new parameter. The loss of food through the harvesting to processing to market chain should be made very clear for each specific crop type and end product type. A table in the structure.md file should explicitly state the assumed loss rates and whether they are hardcoded or configurable.

[blank]

---

### Issue 5 / F-2: E_community_bldg Missing from calculations.md

**Action Item:** Add E_community_bldg to calculations.md total demand formula. Update from 6 to 7 components.

**Severity:** CRITICAL

**Summary:** simulation_flow.md Section 5.5 correctly lists 7 energy demand components including E_community_bldg. calculations.md Section 3 (Total Energy Demand) lists only 6 components, omitting E_community_bldg. This inconsistency means a developer following calculations.md will undercount total energy demand, producing incorrect dispatch results and energy cost calculations.

**Proposed Solution:**

**Edit `calculations.md` Section 3, "Total Energy Demand"** -- Update the formula from 6 to 7 components.

Replace:

```
E_demand(t) [kWh/day] = E_pump(t) + E_treatment(t) + E_convey(t)
                      + E_household(t) + E_processing(t) + E_irrigation_pump(t)
```

With:

```
E_demand(t) [kWh/day] = E_pump(t) + E_treatment(t) + E_convey(t)
                      + E_irrigation_pump(t) + E_processing(t)
                      + E_household(t) + E_community_bldg(t)
```

Add a new bullet to the "Where" list:

```
- `E_community_bldg(t) [kWh/day]`: Community building electricity demand = SUM over building_types:
    (per_m2_kwh_per_day(building_type, date) * configured_area_m2(building_type))
    Building types: office_admin, storage_warehouse, meeting_hall, workshop_maintenance.
    Loaded from precomputed data via registry `community_buildings.energy`, scaled by
    building areas from `community_structure.community_buildings` in settings YAML.
```

Also update the dispatch section formula in calculations.md (Energy Dispatch, "Total demand (full model)") from:

```
E_demand(t) [kWh] = E_pump(t) + E_treatment(t) + E_convey(t)
                  + E_household(t) + E_processing(t) + E_irrigation_pump(t)
```

To:

```
E_demand(t) [kWh] = E_pump(t) + E_treatment(t) + E_convey(t) + E_irrigation_pump(t)
                  + E_processing(t) + E_household(t) + E_community_bldg(t)
```

Update any accompanying text that says "6 components" to "7 components".

**Rationale:** simulation_flow.md is authoritative for the daily loop sequence and already includes E_community_bldg with a clear definition. calculations.md must match.

**Confidence:** 5 -- This is a straightforward omission. simulation_flow.md Section 5.5 and Section 8.1 fully specify the component. The fix is additive with no ambiguity.

---

**Owner Response: **Implement proposed solution

[blank]

---

### Issue 7 / F-3, F-4, F-5: Crop State Machine (Overview)

**Action Item:** Write unified crop state machine specification. Unified algorithm: planting date resolution, growth stage tracking, harvest trigger, fallow to replanting, year-boundary handling.

**Severity:** IMPORTANT

**Summary:** Crop lifecycle logic is fragmented across three documents: calculations.md defines growth stages and K_c values, policies.md mentions crop policies that adjust irrigation, and simulation_flow.md references "Retrieve crop growth stages" and "Determine if today is a harvest day" without specifying the algorithm. No document provides a complete state machine for planting, growth stage transitions, harvest triggering, fallow periods, or year-boundary handling.

**Proposed Solution:**

Add a new **Section 4a: Crop Lifecycle State Machine** to `simulation_flow.md`, placed between the current Section 4 (Food Processing) and Section 5 (Energy Policy Integration). Alternatively, it could be a subsection of Section 2 after the daily loop pseudocode, since it is consulted in Step 0 and Step 1. Placing it as a standalone section is recommended for clarity.

The complete specification follows:

---

**New section text for `**simulation_flow.md**`:**

```markdown
## 4a. Crop Lifecycle State Machine

This section specifies the complete algorithm for crop planting, growth stage
tracking, harvest triggering, and replanting. This state machine is consulted
in Step 0 (retrieve crop growth stages, determine harvest day) and drives
Step 1 (crop policy irrigation demand).

### 4a.1 Crop States

Each crop on each farm has exactly one active state at any time:

    DORMANT -> INITIAL -> DEVELOPMENT -> MID_SEASON -> LATE_SEASON -> HARVEST_READY -> DORMANT

State definitions:
- DORMANT: No active growth cycle. No water demand. Waiting for next planting date.
- INITIAL: Seedling establishment. Kc = kc_initial (from crop_coefficients).
- DEVELOPMENT: Vegetative growth. Kc transitions linearly from kc_initial to kc_mid.
- MID_SEASON: Full canopy. Kc = kc_mid (peak water demand).
- LATE_SEASON: Maturation/senescence. Kc transitions linearly from kc_mid to kc_end.
- HARVEST_READY: Crop is mature. Harvest occurs on this day.

### 4a.2 Growth Stage Duration

Stage durations are derived from the total season_length_days (from
crop_coefficients-toy.csv) using FAO-56 standard proportions:

    initial_days     = round(season_length_days * 0.15)
    development_days = round(season_length_days * 0.25)
    mid_season_days  = round(season_length_days * 0.40)
    late_season_days = season_length_days - initial_days - development_days - mid_season_days

Example for tomato (season_length_days = 135):
    initial = 20, development = 34, mid_season = 54, late_season = 27

These proportions can be overridden per crop if a crop-specific stage duration
file is provided. For MVP, the 15/25/40/20 split is adequate for all 5 crops.

### 4a.3 Planting Date Resolution

Planting dates are specified per crop per farm as a list of MM-DD strings
(e.g., ["02-15", "11-01"]). Resolution rules:

1. On simulation start, resolve all planting dates to absolute dates within
   the simulation period.

2. For each crop, planting_dates are interpreted as SEQUENTIAL plantings on
   the SAME field area. Only one growth cycle is active at a time per crop
   per farm (see 10.10 resolved flag).

3. A planting occurs on the specified date IF the crop is currently DORMANT.
   If the previous cycle has not completed (still in LATE_SEASON), the planting
   is DEFERRED to the day after harvest of the current cycle.

4. Mid-simulation start: If the simulation start_date falls between two
   planting dates, the crop begins in DORMANT state and waits for its next
   planting date. No partial-cycle initialization.

5. percent_planted applies to all plantings for that crop uniformly.

### 4a.4 Daily State Transition Algorithm

    FOR each farm:
        FOR each crop:
            IF crop.state == DORMANT:
                IF today matches a planting_date for this crop:
                    crop.state = INITIAL
                    crop.days_in_stage = 0
                    crop.cycle_start_date = today
                    crop.cumulative_water_received = 0
                    crop.expected_total_water = precomputed irrigation total for this cycle
                CONTINUE to next crop

            # Advance day counter
            crop.days_in_stage += 1

            # Check for state transition
            IF crop.state == INITIAL AND crop.days_in_stage > initial_days:
                crop.state = DEVELOPMENT
                crop.days_in_stage = 0
            ELSE IF crop.state == DEVELOPMENT AND crop.days_in_stage > development_days:
                crop.state = MID_SEASON
                crop.days_in_stage = 0
            ELSE IF crop.state == MID_SEASON AND crop.days_in_stage > mid_season_days:
                crop.state = LATE_SEASON
                crop.days_in_stage = 0
            ELSE IF crop.state == LATE_SEASON AND crop.days_in_stage > late_season_days:
                crop.state = HARVEST_READY

            # Compute daily Kc for this crop
            IF crop.state == INITIAL:
                crop.kc = kc_initial
            ELSE IF crop.state == DEVELOPMENT:
                progress = crop.days_in_stage / development_days
                crop.kc = kc_initial + progress * (kc_mid - kc_initial)
            ELSE IF crop.state == MID_SEASON:
                crop.kc = kc_mid
            ELSE IF crop.state == LATE_SEASON:
                progress = crop.days_in_stage / late_season_days
                crop.kc = kc_mid + progress * (kc_end - kc_mid)
            ELSE IF crop.state == HARVEST_READY:
                crop.kc = 0  # No water demand on harvest day

### 4a.5 Harvest Trigger

Harvest occurs when crop.state transitions to HARVEST_READY:

    IF crop.state == HARVEST_READY:
        Execute harvest yield calculation (Section 4.2)
        Execute food processing pipeline (Section 4.3-4.9)
        crop.state = DORMANT
        crop.days_in_stage = 0

Harvest is deterministic: it occurs exactly season_length_days after planting.
There is no early harvest or delayed harvest mechanism in MVP.

### 4a.6 Year-Boundary Handling

Crops do NOT reset at year boundaries. A crop planted in November with a
135-day season will be harvested in March of the following year. The yearly
boundary operations (Section 7.2, item 4 "Reinitialize farm crops") apply
only to resetting the planting schedule for the NEW year:

    At year boundary:
        FOR each farm:
            FOR each crop:
                IF crop.state == DORMANT:
                    # Ready for new year planting dates -- no action needed,
                    # daily transition algorithm will pick up the next planting date
                    PASS
                ELSE:
                    # Crop is mid-cycle from previous year -- let it complete
                    # Do NOT interrupt or reset
                    PASS

        Reset cumulative_water_received only for DORMANT crops (active crops
        retain their running total for the current cycle)

This ensures crops spanning year boundaries are tracked correctly for yield
calculation and water stress accounting.

### 4a.7 Irrigation Demand During Crop Lifecycle

Only crops in states INITIAL through LATE_SEASON generate irrigation demand.
DORMANT and HARVEST_READY states produce zero demand.

    base_demand_m3 = ET0 * crop.kc * effective_area_ha * 10 / eta_irrigation

This value is passed to the crop policy (Step 1) which may adjust it based
on the selected policy (fixed_schedule, deficit_irrigation, weather_adaptive).
The adjusted demand then flows to the water policy (Step 2).

Cumulative water tracking:
    crop.cumulative_water_received += water_actually_delivered_m3

This is used at harvest for the water stress factor:
    water_ratio = clamp(cumulative_water_received / expected_total_water, 0, 1)
```

---

**Additionally, edit `simulation_flow.md` Section 7.2 item 4** to clarify that "Reinitialize farm crops" does NOT mean interrupting active cycles:

Replace:

```
4. **Crop reinitialization:**
  - Reset crop states for new year planting schedule.
  - Reset cumulative water tracking per crop.
```

With:

```
4. **Crop reinitialization:**
  - Reset planting schedule index for new year dates (dormant crops only).
  - Reset cumulative water tracking for dormant crops only.
  - Active crops (mid-cycle spanning year boundary) continue uninterrupted;
    their cumulative water tracking is retained for the current growth cycle.
```

**Confidence:** 4 -- The FAO-56 growth stage model and sequential cropping model are well-established. The 15/25/40/20 stage duration split is a reasonable default but may need crop-specific tuning. The year-boundary handling follows standard agronomic practice (crops do not respect calendar years).

**Alternative Solutions:** An alternative is to use absolute planting-to-harvest day counts from `crop_coefficients-toy.csv` without decomposing into 4 stages. This would simplify the state machine but lose the ability to compute daily Kc values and per-stage water stress (needed for the Stewart multiplicative model). The 4-stage model is recommended as it directly maps to FAO-56 methodology.

---

**Owner Response:** Implement proposed solution

---

### Issue 8 / C-2 (cross-ref): Battery Discharge Efficiency

**Action Item:** Standardize battery discharge efficiency. Choose `* eta` or `/ eta` and update inconsistent doc.

**Severity:** IMPORTANT

**Summary:** simulation_flow.md Section 5.4 dispatch pseudocode computes available discharge as `available_discharge = max(0, available_energy) * eta_discharge`, which REDUCES the energy delivered to the load. calculations.md Section 3 (Battery Storage Dynamics) SOC update formula uses `P_discharge(t) / eta_discharge`, which means dividing the energy REMOVED from the battery by efficiency to get the SOC decrease. These are actually describing the same physics from different perspectives, but the simulation_flow.md dispatch code is incorrect.

**Proposed Solution:**

The physics of battery discharge efficiency:

- When discharging, more energy must be removed from the battery than is delivered to the load (losses occur in the power electronics and chemistry).
- If you want to deliver X kWh to the load, you must remove X / eta_discharge kWh from the battery.
- Equivalently, if the battery has Y kWh of available stored energy, it can deliver Y * eta_discharge kWh to the load.

Both formulations are valid depending on which direction you compute from:

- **From battery to load:** `energy_delivered = energy_from_battery * eta_discharge` (simulation_flow.md approach)
- **From load to battery:** `energy_from_battery = energy_delivered / eta_discharge` (calculations.md SOC update approach)

The contradiction is specifically in the SOC update. calculations.md says:

```
energy_removed [kWh] = Battery_discharge(t) / eta_discharge
SOC(t+1) = SOC(t) + (energy_stored - energy_removed) / capacity_kwh
```

Here `Battery_discharge(t)` represents the energy DELIVERED to the load. Dividing by eta gives the larger amount removed from the battery. This is correct.

simulation_flow.md Section 5.4 says:

```
available_discharge = (battery_soc - allocation.battery_reserve_pct) * battery_capacity_kwh
available_discharge = max(0, available_discharge) * eta_discharge
battery_discharged = min(available_discharge, remaining_demand)
remaining_demand -= battery_discharged
```

Here, `available_discharge` starts as the energy STORED in the battery above the reserve, then is multiplied by eta to get the deliverable energy. `battery_discharged` is then the energy DELIVERED to the load. This is correct for the demand-side accounting.

But then the SOC update in simulation_flow.md (Section 5.4 is in the dispatch, but calculations.md has the SOC update) uses:

```
energy_removed [kWh] = Battery_discharge(t) / eta_discharge
```

This is consistent IF `Battery_discharge(t)` means "energy delivered to load." The two docs agree on the physics but use `Battery_discharge` to mean different things in different contexts.

**Resolution: Standardize the variable naming and add clarifying comments.**

**Edit `simulation_flow.md` Section 5.4** -- Rename variables for clarity:

```
# --- Battery discharge ---
IF allocation.use_battery AND remaining_demand > 0:
    stored_energy_above_reserve = (battery_soc - allocation.battery_reserve_pct) * battery_capacity_kwh
    stored_energy_above_reserve = max(0, stored_energy_above_reserve)
    max_deliverable_kwh = stored_energy_above_reserve * eta_discharge  # Energy available at the load
    battery_discharged = min(max_deliverable_kwh, remaining_demand)   # Energy delivered to load
    remaining_demand -= battery_discharged
    # Note: SOC update uses battery_discharged / eta_discharge to get energy removed from battery
```

**Edit `calculations.md` Section 3, Battery SOC update** -- Add clarifying note:

After the existing SOC update formula, add:

```
Note: Battery_discharge(t) represents energy DELIVERED to the load (after
efficiency losses). Dividing by eta_discharge recovers the larger amount
of energy actually removed from the battery's stored charge. This convention
is consistent with simulation_flow.md dispatch, where available_discharge
is computed as stored_energy * eta_discharge (energy at the load).
```

**Rationale:** The two documents are actually consistent in their physics but use ambiguous variable names. The fix clarifies the naming convention rather than changing any formula. The convention "Battery_discharge = energy delivered to load" is the more natural choice since it matches what appears in the demand balance equation.

**Confidence:** 5 -- The physics of round-trip efficiency is unambiguous. The proposed clarification eliminates the apparent contradiction without changing any calculation.

---

**Owner Response: **Implement proposed solution

[blank]

---

### Issue 9 / C-3 (cross-ref): Generator Minimum Load

**Action Item:** Resolve generator minimum load behavior. Update calculations.md to match simulation_flow.md resolved behavior (always start, run at minimum).

**Severity:** IMPORTANT

**Summary:** calculations.md Section 3 (Backup Generator Fuel Consumption) says `P_gen(t) = 0 if deficit < P_rated * min_load_fraction` (do not start the generator if demand is below minimum load). simulation_flow.md Section 5.4 and resolved flag 10.9 say the generator ALWAYS starts when there is unmet demand under `microgrid` policy, running at minimum load (30%) even if demand is below that threshold, with excess generation curtailed. These are contradictory operating philosophies.

**Proposed Solution:**

simulation_flow.md's resolved behavior (10.9) is the correct choice for this model. The rationale:

1. Under the `microgrid` policy, there is no grid fallback. If the generator does not start, the demand goes unmet. Unmet demand for water treatment or irrigation has physical consequences (crop stress, missed irrigation).
2. The "don't start below minimum" rule from calculations.md is a fuel economy optimization that makes sense when grid backup exists (why waste fuel when you can import cheaply?). It does not make sense when the generator is the last resort.
3. simulation_flow.md 10.9 explicitly resolved this as a design decision.

**Edit `calculations.md` Section 3 (Backup Generator Fuel Consumption)** -- Replace the minimum load constraint block:

Replace:

```
P_gen(t) = 0                          if deficit < P_rated * min_load_fraction
P_gen(t) = max(P_rated * 0.30, deficit)   otherwise
```

With:

```
# Generator minimum load behavior (resolved in simulation_flow.md 10.9):
# The generator always starts when there is unmet demand and use_generator=true.
# If demand is below the 30% minimum load threshold, the generator runs at
# minimum load and excess output is curtailed. This wastes some fuel but ensures
# no unmet demand when the community has no grid fallback (microgrid policy).
#
P_gen(t) = 0                                  if deficit == 0 or use_generator == false
P_gen(t) = max(P_rated * min_load_fraction, deficit)   otherwise
generator_curtailed = max(0, P_gen(t) - deficit)
```

Add a note below:

```
Note: The "always start" behavior applies specifically to the microgrid policy
where grid import is unavailable. Under renewable_first or all_grid policies,
the generator is not dispatched (use_generator=false) because grid import
serves as the fallback. See simulation_flow.md Section 5.3 for policy-specific
dispatch behavior.
```

**Confidence:** 5 -- This is a resolved design decision (simulation_flow.md 10.9). The fix aligns calculations.md to the authoritative resolution.

---

**Owner Response: **Implement proposed solution

[blank]

---

### Issue 10 / C-4 (cross-ref): SOC_min vs battery_reserve_pct

**Action Item:** Clarify SOC_min (0.10 hardware) vs battery_reserve_pct (0.20 policy) relationship. Add note that effective floor = max(SOC_min, battery_reserve_pct).

**Severity:** IMPORTANT

**Summary:** calculations.md defines SOC_min = 0.10 (10%) as a hardware constraint on battery depth of discharge. policies.md defines battery_reserve_pct as a policy parameter (default 0.20 for microgrid, varying by policy). The relationship between these two constraints is never specified: which one governs? Can a policy set battery_reserve_pct below SOC_min?

**Proposed Solution:**

These are two different concerns at two different layers:

1. **SOCmin (hardware floor):** This is a physical constraint protecting the battery from deep discharge damage. It is set by battery chemistry (LFP: 10%, lead-acid: 50%). It should never be violated regardless of policy decisions.
2. **batteryreservepct (policy floor):** This is an operational policy decision to keep additional reserve above the hardware minimum. Under `microgrid` policy (no grid), maintaining a 20% reserve provides a safety buffer for unexpected demand spikes. Under `renewable_first` (grid available), a lower reserve is acceptable since grid import can cover shortfalls.

The effective discharge floor is always `max(SOC_min, battery_reserve_pct)`.

**Edit `calculations.md` Section 3, Battery Storage Dynamics** -- Add after the constraints block:

```
**Relationship between SOC_min and battery_reserve_pct:**

SOC_min (0.10 for LFP) is a HARDWARE constraint protecting battery longevity.
battery_reserve_pct is a POLICY parameter set by the energy policy (e.g., 0.20
for microgrid). The effective discharge floor used in dispatch is:

    effective_soc_floor = max(SOC_min, battery_reserve_pct)

The policy cannot override the hardware floor. If battery_reserve_pct < SOC_min,
the hardware floor governs. Validation at scenario load time should warn if
battery_reserve_pct < SOC_min (configuration error).
```

**Edit `simulation_flow.md` Section 5.4** -- Update the battery discharge block to reference both constraints:

Replace:

```
available_discharge = (battery_soc - allocation.battery_reserve_pct) * battery_capacity_kwh
```

With:

```
effective_soc_floor = max(SOC_min, allocation.battery_reserve_pct)
available_discharge = (battery_soc - effective_soc_floor) * battery_capacity_kwh
```

**Edit `policies.md` Energy Policies** -- Add a note to the `battery_reserve_pct` field:

```
battery_reserve_pct: float  # Minimum battery SOC to maintain (0-1).
                            # Effective floor = max(SOC_min_hardware, battery_reserve_pct).
                            # Cannot override hardware SOC_min (0.10 for LFP).
```

**Rationale:** This is standard practice in battery management systems. The BMS enforces a hard floor; the energy management system may impose a softer, higher floor for operational reasons. The two are independent concerns and the max() operator correctly composes them.

**Confidence:** 5 -- This is standard battery system engineering. The max() composition is the universal approach.

---

**Owner Response: **Implement proposed solution

[blank]

---

### Issue 11 / F-3: Crop State Machine Spec

**Action Item:** Write crop state machine specification. Unified algorithm: planting date resolution, growth stage tracking, harvest trigger, fallow to replanting, year-boundary handling.

**Severity:** IMPORTANT

**Summary:** This is the same issue as Issue 7 above. The complete unified specification is provided in the Issue 7 proposal.

**Proposed Solution:**

See Issue 7 / F-3, F-4, F-5 above for the complete crop state machine specification. This action item (Section 7 #11) and Issue 7 (Section 7 #7) address the same underlying gap and should be resolved by the single unified specification proposed there.

**Confidence:** 4 -- See Issue 7 confidence note.

---

**Owner Response: **Implement proposed solution in issue 7

[blank]

---

### Issue 12 / F-6 (related): Battery EFC Accumulator

**Action Item:** Add battery EFC accumulator to daily loop. Needed for cycle-based degradation model at yearly boundary.

**Severity:** IMPORTANT

**Summary:** calculations.md defines a battery capacity degradation model with both calendar aging and cycle aging components. Cycle aging depends on `EFC_cumulative` (equivalent full cycles since simulation start). However, the daily simulation loop in simulation_flow.md does not track an EFC accumulator, and the yearly boundary operations (Section 7.2) reference "Update battery capacity degradation" without specifying how EFC_cumulative is computed from daily records.

**Proposed Solution:**

**Edit `simulation_flow.md` Section 2, Daily Loop, Step 3** -- Add EFC accumulator update after battery SOC update:

After the line `Update battery SOC`, add:

```
    Update battery EFC accumulator:
        daily_throughput_kwh = battery_charged_kwh + battery_discharged_kwh
        daily_efc = daily_throughput_kwh / (2 * battery_capacity_kwh)
        energy_state.efc_cumulative += daily_efc
```

**Edit `simulation_flow.md` Section 7.2, item 3 (Equipment degradation)** -- Expand the battery degradation bullet:

Replace:

```
- Battery: Update effective capacity per calendar + cycle aging model.
```

With:

```
- Battery: Update effective capacity using dual aging model:
    fade_calendar = alpha_cal * years_elapsed
        (alpha_cal = 0.018/yr for LFP in hot arid climate)
    fade_cycle = alpha_cyc * efc_cumulative / EFC_rated
        (alpha_cyc = 0.20, EFC_rated = 5000 for LFP)
    effective_capacity = nameplate_capacity_kwh * (1 - fade_calendar) * (1 - fade_cycle)

    Update battery_capacity_kwh used in dispatch with effective_capacity.
    Log warning if effective_capacity < 0.80 * nameplate (end-of-life threshold).
```

**Rationale:** The EFC accumulator is a simple daily counter that divides total throughput by twice the nameplate capacity (one full cycle = one full charge + one full discharge). This is the standard convention used by battery manufacturers and is already defined in calculations.md Section 3 (Battery Throughput). The daily accumulation ensures the yearly degradation calculation has accurate data without requiring re-aggregation of daily records.

**Data dependency:** `alpha_cal`, `alpha_cyc`, and `EFC_rated` should come from equipment parameter files. The values 0.018/yr, 0.20, and 5000 are appropriate defaults for LFP in hot arid climates per calculations.md.

**Confidence:** 5 -- EFC counting is the standard method for tracking battery cycle aging. The formula is already defined in calculations.md; this proposal simply adds the daily accumulation step to the simulation loop.

---

**Owner Response: **Implement proposed solution

[blank]

---

### Issue 13 / F-6: Battery Self-Discharge

**Action Item:** Add battery self-discharge to dispatch or explicitly exclude. Currently documented in calculations.md but absent from flow.

**Severity:** IMPORTANT

**Summary:** calculations.md Section 3 documents battery self-discharge at ~0.05%/day for LFP (approximately 1.5%/month) but notes it "can be omitted for MVP daily time-step if battery cycles most days." simulation_flow.md does not include self-discharge in the daily loop or dispatch algorithm.

**Proposed Solution:**

Self-discharge for LFP batteries at 0.05%/day is a small effect (~1.5% per month, ~18% per year if the battery sat idle). In an active community microgrid where the battery cycles most days, the daily self-discharge loss (0.05% of current SOC) is dwarfed by charge/discharge throughput (often 20-80% of capacity per day). However, for completeness and correctness in scenarios with low renewable penetration or seasonal patterns where the battery may sit idle for extended periods, self-discharge should be included.

**Edit `simulation_flow.md` Section 2, Daily Loop** -- Add self-discharge as part of the battery SOC update in Step 3, or as a daily boundary operation.

Add after the battery SOC update line in Step 3:

```
    # Battery self-discharge (applied after dispatch SOC update)
    IF allocation.use_battery:
        battery_soc -= battery_soc * self_discharge_rate_daily
        battery_soc = max(battery_soc, SOC_min)
        # self_discharge_rate_daily = 0.0005 (0.05%/day) for LFP
```

**Edit `simulation_flow.md` Section 5.4** -- Add a note in the dispatch pseudocode comments:

```
# Note: Self-discharge is applied AFTER dispatch completes, not within the
# dispatch algorithm. This prevents self-discharge from affecting the dispatch
# merit-order logic (which should see the battery as it was at start of day).
# Self-discharge loss is small (~0.05%/day for LFP) but accumulates during
# idle periods. See calculations.md Battery Storage Dynamics.
```

**Rationale:** Applying self-discharge after the dispatch (rather than before or during) is the cleanest approach: the dispatch sees the battery at its actual SOC from the previous day, makes decisions, updates SOC, and then self-discharge is applied as an end-of-day correction. This avoids complicating the dispatch logic while correctly modeling the physical loss. The 0.05%/day rate is well-established for LFP chemistry.

**Confidence:** 5 -- The physics is straightforward and the implementation is a single line of code. The post-dispatch placement is standard in energy system simulations.

---

**Owner Response: **Implement proposed solution

[blank]

---

### Issue 14 / F-7: Equipment Replacement Costs

**Action Item:** Add equipment replacement costs to yearly boundary operations. Sinking fund reserve or discrete replacement events.

**Severity:** IMPORTANT

**Summary:** calculations.md Section 5 (Equipment Replacement Costs) defines a sinking fund approach for annual replacement reserves and lists component lifespans (RO membranes: 6 years, drip emitters: 7 years, etc.). The data file `equipment_lifespans-toy.csv` exists with all component data. However, simulation_flow.md's yearly boundary operations (Section 7.2) do not include equipment replacement reserves or discrete replacement events. The Total OPEX formula in calculations.md includes `Equipment_replacement_reserve` but the simulation flow never computes or deducts it.

**Proposed Solution:**

Use the sinking fund approach (recommended by calculations.md) rather than discrete replacement events. The sinking fund is simpler, produces smoother cash flows (more realistic for community budgeting), and avoids the complexity of tracking individual component ages.

**Edit `simulation_flow.md` Section 2, Pre-Loop Initialization** -- Add a step to compute the annual replacement reserve:

After item 10 ("Compute infrastructure annual costs from financing profiles"), add:

```
11. Compute annual equipment replacement reserve:
    FOR each component in equipment_lifespans data:
        component_capex = lookup capital cost for this component
        annual_reserve_i = component_capex * (replacement_cost_pct / 100) / lifespan_years
    total_annual_replacement_reserve = SUM(annual_reserve_i)
    daily_replacement_reserve = total_annual_replacement_reserve / 365
```

(Renumber subsequent items.)

**Edit `simulation_flow.md` Section 2, Step 7 (Daily Accounting)** -- Add replacement reserve to daily costs:

Change:

```
Aggregate daily costs (water, energy, labor, inputs, storage)
```

To:

```
Aggregate daily costs (water, energy, labor, inputs, storage, replacement_reserve)
    replacement_reserve_cost = daily_replacement_reserve (from pre-loop calculation)
```

**Edit `simulation_flow.md` Section 7.2 (Yearly Boundary Operations)** -- Add replacement reserve reporting:

After item 3 (Equipment degradation), add:

```
3b. **Equipment replacement reserve tracking:**
  - Record cumulative replacement reserve contributions for the year.
  - Log annual_replacement_reserve in yearly metrics.
  - Note: For MVP, the sinking fund is a cost provision only (no discrete
    replacement events). The reserve is deducted from cash flow but does not
    trigger equipment state changes. Future enhancement: model discrete
    replacement events when cumulative reserve exceeds component replacement cost.
```

**Data dependencies:**

- `data/parameters/economic/equipment_lifespans-toy.csv` (already exists, contains lifespan_years and replacement_cost_pct_of_capex)
- Capital cost data from equipment parameter files (already loaded)

**Rationale:** The sinking fund approach is recommended by calculations.md and is the standard approach for community infrastructure budgeting. It produces a constant daily cost adder that represents the true economic cost of equipment wearing out, even if replacement has not yet occurred. This gives more realistic NPV/IRR calculations than ignoring replacement costs entirely.

**Confidence:** 5 -- The data file exists, the formula is defined in calculations.md, and the sinking fund approach is straightforward. This is purely a matter of wiring the existing specification into the simulation flow.

---

**Owner Response: **Implement proposed solution

[blank]

---

### Issue 15 / F-9: Conveyance Energy Double-Counting

**Action Item:** Clarify conveyance energy source. Is E_convey decomposed from water policy output or independently computed by dispatch? Prevent double-counting.

**Severity:** IMPORTANT

**Summary:** The water policy's `energy_used_kwh` output includes conveyance energy (the shared logic in policies.md computes `energy_used = groundwater_m3 * (pumping_kwh_per_m3 + conveyance_kwh_per_m3 + treatment_kwh_per_m3)`). simulation_flow.md Step 3 independently lists `E_convey = sum of conveyance energy across all farms` as a separate component of total_demand_kwh. If E_convey is computed independently AND the water policy's energy_used_kwh already includes conveyance, then conveyance energy is double-counted in the dispatch.

**Proposed Solution:**

The water policy output `energy_used_kwh` serves a dual purpose: (1) it is used for cost comparison within the policy (groundwater cost vs municipal cost), and (2) it reports the total energy consumed by the water system for that farm. The dispatch needs the total energy demand from all sources, decomposed into components for reporting.

The correct approach is: **the water policy computes and reports the total water-system energy, and the dispatch uses that reported value directly rather than re-computing components.**

**Edit `simulation_flow.md` Section 2, Step 3** -- Clarify that water-system energy components come from the water policy output, not from independent computation:

Replace:

```
    Aggregate all energy demand components:
        E_desal = sum of treatment energy across all farms
        E_pump = sum of pumping energy across all farms
        E_convey = sum of conveyance energy across all farms
        E_irrigation_pump = sum of irrigation pressurization energy
```

With:

```
    Aggregate all energy demand components:
        # Water-system energy: extracted from water policy outputs (already computed in Step 2)
        E_water_system = sum of allocation.energy_used_kwh across all farms
            # This includes E_desal + E_pump + E_convey per farm (no double-counting)
            # For reporting decomposition:
            #   E_desal = groundwater_m3 * treatment_kwh_per_m3
            #   E_pump = groundwater_m3 * pumping_kwh_per_m3
            #   E_convey = groundwater_m3 * conveyance_kwh_per_m3
            # These sub-components are computed for metrics only, not re-added to demand
        E_irrigation_pump = sum of irrigation pressurization energy
            # irrigation_pressure_kwh_per_m3 * total_irrigation_m3 (all sources, not just GW)
```

Update the total demand formula:

```
        total_demand_kwh = E_water_system + E_irrigation_pump
                         + E_processing + E_household + E_community_bldg
```

**Edit `simulation_flow.md` Section 5.5** -- Update the WHERE clause to match:

Replace the 7-component formula with a decomposition that makes the relationship clear:

```
total_demand_kwh = E_water_system + E_irrigation_pump
                 + E_processing + E_household + E_community_bldg

WHERE:
    E_water_system = SUM(allocation.energy_used_kwh) across all farms + household water
        Decomposed for reporting (not re-summed):
        E_desal = groundwater_m3 * treatment_kwh_per_m3
        E_pump = groundwater_m3 * pumping_kwh_per_m3
        E_convey = groundwater_m3 * conveyance_kwh_per_m3
    E_irrigation_pump = total_irrigation_m3 * 0.056 kWh/m3
        (drip irrigation pressurization, applied to ALL irrigation water regardless of source)
    E_processing = sum(throughput_kg * energy_per_kg) by pathway (from previous day)
    E_household = from precomputed data: registry `household.energy`
    E_community_bldg = from precomputed data: registry `community_buildings.energy`
```

**Rationale:** The water policy already computes the correct total water-system energy including conveyance. Re-computing components independently in the dispatch creates double-counting risk. Using the policy output directly eliminates this risk. The sub-component decomposition is retained for metrics and reporting but is not added to the demand total separately.

Note: `E_irrigation_pump` is correctly kept separate because it applies to ALL irrigation water (both groundwater and municipal) and is not part of the water policy's energy calculation (which only covers groundwater-related energy).

**Confidence:** 4 -- The physics is clear but the implementation requires care to ensure the water policy's energy_used_kwh is the sole source of water-system energy in the dispatch. The E_irrigation_pump separation is slightly nuanced (it applies to total irrigation, not just groundwater).

**Alternative Solutions:** An alternative is to have the water policy NOT include conveyance in energy_used_kwh, and have the dispatch compute all sub-components independently. This is cleaner for reporting but duplicates the calculation logic. Either approach works as long as it is consistent and documented.

---

**Owner Response: **Implement proposed solution. However, double check that all water energy needs are properly calculated by specificying clearly what each term refers to in the chain of water use. Just as an example, does groundwater pumping refer to just getting water from the aquifer to the surface, or does it also include pumping the water to the treatment site? A table might be helpful that has the terms used universally and then a description of what is included and the equations used for each. The confusion will lie when water is being pulled from municipal water vs. groundwater. For now, we can assume that the community water system always includes desalination or some kind of treatment before water goes to storage and then onwards into irrigation systems.

[blank]

---

### Issue 16 / F-10: CAPEX Initial Outflow

**Action Item:** Add CAPEX initial outflow to pre-loop initialization. Required for IRR/NPV computation.

**Severity:** IMPORTANT

**Summary:** The financial metrics IRR and NPV require the initial capital expenditure (CAPEX) as the time-zero cash outflow. simulation_flow.md's pre-loop initialization computes annual infrastructure costs from financing profiles but does not record the total CAPEX as a day-0 or year-0 outflow. Without this, IRR computation (which needs the initial investment) and NPV computation (which subtracts Initial_CAPEX) cannot be performed.

**Proposed Solution:**

**Edit `simulation_flow.md` Section 2, Pre-Loop Initialization** -- Add CAPEX recording after the infrastructure cost computation:

After item 10 ("Compute infrastructure annual costs from financing profiles"), add:

```
10b. Record initial CAPEX outflow for financial metrics:
    total_capex = SUM over all subsystems:
        capital_cost from equipment parameter files
        × capex_cost_multiplier from financing profile
        (only for financing_status with capex_cost_multiplier > 0: purchased_cash)

    # For loan-financed systems, CAPEX is not a cash outflow at time zero
    # (the loan provides the capital). Instead, debt service payments are
    # the cash outflows over the loan term. But for NPV/IRR calculation,
    # the TOTAL capital cost (regardless of financing method) should be
    # recorded as the "investment" being evaluated.

    # Two perspectives:
    # (a) Community cash flow perspective: Only record cash actually spent
    #     at time zero (purchased_cash systems only). Loan-financed systems
    #     show up as monthly debt service.
    # (b) Investment analysis perspective: Record total capital deployed
    #     regardless of financing source, to evaluate whether the investment
    #     creates value.
    #
    # Record BOTH for different metrics:
    economic_state.total_capex_invested = SUM(capital_cost) for all subsystems
    economic_state.capex_cash_outflow = SUM(capital_cost * capex_cost_multiplier)

    # For IRR/NPV: Use total_capex_invested as Initial_CAPEX
    # For cash flow tracking: Deduct capex_cash_outflow from initial cash reserves
    economic_state.initial_cash = SUM(farm.starting_capital_usd) - capex_cash_outflow
```

**Edit `simulation_flow.md` Section 7.2** -- Add a note about how yearly metrics reference CAPEX for IRR/NPV:

Add to the yearly metrics snapshot:

```
    Compute IRR and NPV using economic_state.total_capex_invested as the
    year-0 outflow and yearly net_income as the annual cash flows.
    See calculations.md Section 5 (IRR, NPV) for formulas.
```

**Rationale:** IRR and NPV are standard investment analysis metrics that require an initial outflow. The two-perspective approach (investment analysis vs cash flow) is standard in project finance. For a community evaluating whether to invest in infrastructure, the total capital deployed is the relevant denominator regardless of whether it comes from cash, loans, or grants.

For grant-funded projects (capex_cost_multiplier = 0), total_capex_invested still reflects the real investment value but capex_cash_outflow = 0, which correctly shows that the community had no cash outlay. IRR on the grant portion is undefined (infinite return on zero cash), which is the correct interpretation.

**Confidence:** 4 -- The need for CAPEX recording is clear. The two-perspective approach adds slight complexity but is standard practice. The owner may prefer to use only one perspective for MVP.

**Alternative Solutions:** For MVP simplicity, record only `total_capex_invested` and use it for both IRR/NPV and as a reporting metric. Skip the cash-outflow deduction from initial reserves (assume capital is externally sourced). This simplifies initialization at the cost of less accurate cash flow tracking in the early simulation period.

---

**Owner Response: **Implement proposed solution

[blank]

---

### Issue 35 / (minor): Water Storage Balance in Pseudocode

**Action Item:** Add water storage balance update location to daily loop pseudocode.

**Severity:** MINOR

**Summary:** The daily loop pseudocode in simulation_flow.md Step 2 says "Update water storage state" but does not specify the storage balance equation. calculations.md defines `Storage(t+1) = Storage(t) + Inflow(t) - Outflow(t)` but the daily loop does not show where inflow and outflow are resolved relative to the water policy output.

**Proposed Solution:**

**Edit `simulation_flow.md` Section 2, Step 2 (Water Policy)** -- Expand the "Update water storage state" line:

Replace:

```
        Update water storage state
```

With:

```
        Update water storage state:
            # Inflow: treated groundwater produced today
            inflow_m3 = allocation.groundwater_m3
            # Outflow: total irrigation demand served (from all sources, already allocated)
            outflow_m3 = farm_total_demand_m3
            # Balance update
            water_storage_m3 = clamp(
                water_storage_m3 + inflow_m3 - outflow_m3,
                0, water_storage_capacity_m3
            )
```

Add a note:

```
        # Note: Municipal water does not pass through community storage -- it is
        # delivered directly. Only groundwater enters the storage system
        # (well -> treatment -> storage -> irrigation). Storage acts as a buffer
        # between treatment capacity and irrigation demand timing.
```

**Rationale:** The storage balance is straightforward but the pseudocode should explicitly show it to avoid ambiguity about what counts as inflow and outflow. The note about municipal water not entering storage is important for physical correctness -- municipal water is delivered via a separate pipeline and does not interact with the community's storage infrastructure.

**Confidence:** 4 -- The basic balance equation is clear. The treatment of municipal water as bypassing storage is a reasonable simplification for MVP. The owner should confirm that treated groundwater enters storage before being distributed (as opposed to being distributed directly from the treatment plant).

**Alternative Solutions:** An alternative model has treated water going directly to irrigation (no storage buffer), with storage only used for excess treatment capacity. This changes the dynamics significantly and is a design decision for the owner.

---

**Owner Response: **Implement proposed solution. Yes, groundwater treated will enter some kind of storage first, even if very small. Municipal water can be assumed to bypass this as it is always available and the farm will only pull a small overall percentage even under irrigation loads.

[blank]

---

### Issue 36 / (minor): Monthly vs Yearly Groundwater Reset

**Action Item:** Clarify monthly vs yearly groundwater tracking reset scope.

**Severity:** MINOR

**Summary:** simulation_flow.md monthly boundary operations reset "monthly cumulative groundwater tracking" and yearly boundary operations reset "yearly cumulative groundwater tracking." The water policy context includes both `cumulative_gw_year_m3` and `cumulative_gw_month_m3`. The pseudocode does not explicitly state the relationship between these accumulators or confirm that the yearly reset does NOT affect the monthly accumulator (or vice versa).

**Proposed Solution:**

**Edit `simulation_flow.md` Section 7.1 (Monthly Boundaries)** -- Clarify the reset scope:

Replace:

```
1. **Economic policy execution:** [...]
2. **Domestic water tier reset:**
  - Reset `cumulative_monthly_domestic_water_m3` to 0 for tiered pricing calculation.
3. **Monthly metrics snapshot:** [...]
```

With:

```
1. **Economic policy execution:** [...]
2. **Monthly resets:**
  - Reset `cumulative_gw_month_m3` to 0 (groundwater tracking for quota_enforced policy).
  - Reset `cumulative_monthly_domestic_water_m3` to 0 (tiered pricing calculation).
  - Note: `cumulative_gw_year_m3` is NOT reset at monthly boundaries -- it accumulates
    across the entire year and is reset only at yearly boundaries.
3. **Monthly metrics snapshot:** [...]
```

**Edit `simulation_flow.md` Section 7.2 (Yearly Boundaries)** -- Clarify the yearly reset:

Replace:

```
5. **Reset yearly accumulators:**
  - Reset `cumulative_gw_year_m3` to 0.
  - Reset yearly energy accumulators (PV, wind, grid, generator, curtailment).
```

With:

```
5. **Reset yearly accumulators:**
  - Reset `cumulative_gw_year_m3` to 0.
  - Reset yearly energy accumulators (PV, wind, grid, generator, curtailment).
  - Note: `cumulative_gw_month_m3` is NOT reset at yearly boundaries -- it follows
    its own monthly reset cycle (Section 7.1). On January 1, the monthly accumulator
    was already reset when the December→January month boundary triggered.
```

**Edit `simulation_flow.md` Section 2, Step 2** -- Add accumulator update after water allocation:

After "Update aquifer cumulative extraction tracking", add:

```
        cumulative_gw_month_m3 += allocation.groundwater_m3
        cumulative_gw_year_m3 += allocation.groundwater_m3
```

**Rationale:** The two accumulators serve different purposes: monthly tracking supports the `quota_enforced` policy's monthly variance control; yearly tracking supports the annual quota limit and aquifer depletion calculations. Making the independence of their reset cycles explicit prevents subtle bugs where one reset inadvertently affects the other.

**Confidence:** 5 -- This is a documentation clarification, not a design decision. The behavior is already implicit in the current text; the fix makes it explicit.

---

**Owner Response: **Implement proposed solution

[blank]

---

### Issue 4 / F-8: Daily Labor Cost Formula

**Action Item:** Add daily labor cost formula. Specify how annual labor estimates translate to daily costs (fixed daily rate? harvest-day multiplier?).

**Severity:** CRITICAL

**Summary:** Labor is listed as a daily cost in simulation_flow.md Step 7 (Daily Accounting) but calculations.md Section 7 is marked "TBD" and only provides annual aggregate estimates. The data files `labor_requirements-toy.csv` and `labor_wages-toy.csv` exist with detailed activity-level requirements and wage rates, but no document specifies how to compute a daily labor cost from these inputs.

**Proposed Solution:**

The labor data files provide two levels of granularity:

1. **Activity-level detail** (labor_requirements-toy.csv): hours_per_hectare for field work, hours_per_kg for processing, hours_per_day for management
2. **Aggregate model parameters** (bottom of labor_requirements-toy.csv): base_field_labor per ha per year, crop multipliers, processing labor per kg, maintenance hours

The daily labor cost should use a **hybrid approach**: fixed daily overhead for year-round activities plus event-driven costs for seasonal activities (harvesting, processing).

**Add a new section to ****`calculations.md`** -- Replace the "TBD" Section 7 with:

```markdown
## 7. Labor Calculations

### Daily Labor Cost

**Purpose:** Calculate daily labor costs for community operations. Labor is modeled
as a cost input, not a constraint -- labor supply is assumed unlimited (see overview.md).

**Formula (hybrid: fixed overhead + event-driven):**

    daily_labor_cost = daily_overhead_cost + daily_field_cost + daily_harvest_cost
                     + daily_processing_cost

**Component 1: Fixed daily overhead (year-round, all days)**

    overhead_hours = management_planning + management_coordination
                   + management_sales + management_administration
                   + logistics_transport + logistics_inventory
    # From labor_requirements-toy.csv: 4 + 2 + 3 + 4 + 8 + 3 = 24 hours/day

    daily_overhead_cost = overhead_hours * blended_wage_usd_per_hour
    # blended_wage from labor_wages-toy.csv: $3.50/hr (blended_agricultural rate)

**Component 2: Field labor (seasonal, proportional to planted area)**

    # Active growing season only (crops in INITIAL through LATE_SEASON states)
    active_area_ha = SUM over all farms, all crops in active growth states:
        plantable_area_ha * area_fraction * percent_planted

    base_field_hours_per_day = (base_field_labor_per_ha_per_year * active_area_ha)
                             / working_days_per_year
    # base_field_labor = 200 hrs/ha/yr, working_days = 280/yr
    # Includes: weeding, irrigation management, pest scouting, fertilizer application

    # Crop mix adjustment
    weighted_multiplier = SUM(crop_area_ha * crop_multiplier) / active_area_ha
    adjusted_field_hours = base_field_hours_per_day * weighted_multiplier

    daily_field_cost = adjusted_field_hours * field_worker_wage_usd_per_hour
    # field_worker_wage from labor_wages-toy.csv: $1.10/hr (unskilled)

**Component 3: Harvest labor (event-driven, harvest days only)**

    IF any farm has a harvest today:
        harvest_hours = SUM over harvesting farms:
            harvesting_hours_per_ha(crop) * effective_area_ha
            * harvest_multiplier  # 3.0x base (peak labor demand)
        # harvesting_hours_per_ha from labor_requirements-toy.csv
        # (320 for tomato, 180 for potato, etc.)

        daily_harvest_cost = harvest_hours * seasonal_harvester_wage
        # seasonal_harvester_wage from labor_wages-toy.csv: $1.00/hr
    ELSE:
        daily_harvest_cost = 0

**Component 4: Processing labor (event-driven, processing days only)**

    IF E_processing > 0 (processing occurred yesterday, per one-day lag):
        processing_hours = SUM over processing pathways:
            input_kg * labor_hours_per_kg(pathway)
        # labor_hours_per_kg from processing_specs-toy.csv

        daily_processing_cost = processing_hours * processing_worker_wage
        # processing_worker_wage from labor_wages-toy.csv: $1.43/hr (semi-skilled)
    ELSE:
        daily_processing_cost = 0

**Maintenance labor** is included in infrastructure O&M costs (from operating_costs
parameter files) and is NOT separately counted here to avoid double-counting.

**Admin overhead adjustment:**
    daily_labor_cost *= (1 + admin_overhead_fraction)
    # admin_overhead = 0.05 (5%) from labor_requirements-toy.csv

**Parameters:**
- labor_requirements-toy.csv: Activity hours, crop multipliers, aggregate parameters
- labor_wages-toy.csv: Wage rates by worker category
- processing_specs-toy.csv: Processing labor hours per kg

**Output:** daily_labor_cost in USD/day

**Dependencies:**
- Crop state machine output (which crops are active, which are harvesting)
- Food processing output (processing throughput from previous day)
- Farm configuration (areas, crop assignments)
```

**Edit `simulation_flow.md` Section 2, Step 7 (Daily Accounting)** -- Reference the labor formula:

Replace:

```
Aggregate daily costs (water, energy, labor, inputs, storage)
```

With:

```
Aggregate daily costs:
    water_cost = SUM(allocation.cost_usd) across all farms + household water cost
    energy_cost = dispatch_result.total_energy_cost
    labor_cost = daily_overhead_cost + daily_field_cost + daily_harvest_cost
               + daily_processing_cost  (see calculations.md Section 7)
    input_cost = fertilizer_and_inputs_daily  (TBD, fixed per-hectare for MVP)
    storage_cost = SUM(tranche.kg * storage_cost_per_kg_per_day) across all farms
    replacement_reserve = daily_replacement_reserve (from pre-loop)
    total_daily_cost = water_cost + energy_cost + labor_cost + input_cost
                     + storage_cost + replacement_reserve
```

**Rationale:** The hybrid approach (fixed overhead + event-driven seasonal) matches the physical reality: management and logistics run every day, but harvesting and processing labor are concentrated on specific days. The data files already contain all needed parameters. The blended_agricultural wage rate ($3.50/hr) from labor_wages-toy.csv is used for overhead to account for the mix of skill levels in management activities.

**Confidence:** 4 -- The approach is sound and all data files exist. The specific aggregation formula (especially the crop multiplier weighting) may need refinement during implementation. The harvest_multiplier of 3.0x is from the data file but may produce high peak costs that need validation against total annual labor benchmarks.

**Alternative Solutions:** A simpler approach is to compute annual labor cost from the aggregate parameters and divide by 365 for a flat daily rate. This loses the harvest-day labor spikes (which are physically important for cash flow modeling) but is much simpler to implement. For MVP, the flat daily approach may be sufficient, with the event-driven model as a Phase 2 enhancement.

---

**Owner Response: **Implement proposed solution. We need labor costs at the daily and monthly timestep to understand cashflows. Laborers needs to be paid shortly after is performs work. A key part of this model is understanding daily and monthly cash flows and the resulting need to have savings and benefits of stable costs for energy and water inputs (that reduces cost spikes from government changes to costs).

[blank]

---

## Summary of All Proposed Changes by File


| File                 | Changes                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| -------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `simulation_flow.md` | Section 2 pre-loop: Add CAPEX recording (#16), replacement reserve (#14). Section 2 Step 2: Expand water storage update (#35), add GW accumulators (#36). Section 2 Step 3: Add EFC accumulator (#12), self-discharge (#13), SOC floor (#10). Section 2 Step 7: Expand cost aggregation (#4, #14). Section 4.1-4.2: Add handling loss before processing split (#1). New Section 4a: Crop lifecycle state machine (#7, #11). Section 5.4: Clarify battery discharge naming (#8), add SOC floor (#10). Section 5.5: Restructure demand components (#5, #15). Section 7.1/7.2: Clarify resets (#36), expand degradation (#12), add replacement reserve (#14), fix crop reinit (#7). |
| `calculations.md`    | Section 3 Total Energy Demand: Add E_community_bldg (#5). Section 3 Battery: Add SOC_min/reserve_pct note (#10), clarify discharge convention (#8). Section 3 Generator: Update minimum load behavior (#9). Section 4 Post-Harvest Losses: Reframe as handling loss (#1). Section 5 Crop Revenue: Remove (1-loss_rate) from fresh formula (#1). New Section 7: Daily labor cost formula (#4).                                                                                                                                                                                                                                                                                    |
| `policies.md`        | Energy policy: Add note on battery_reserve_pct vs SOC_min (#10).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |


---

*End of fix proposals.*