# Water System Calculations

Extracted from the consolidated calculations specification. For other domain calculations see: [calculations_energy.md](calculations_energy.md), [calculations_crop.md](calculations_crop.md), [calculations_economic.md](calculations_economic.md). For the index, units, references, and resilience/Monte Carlo calculations see: [calculations.md](calculations.md).

## 1. Groundwater Pumping Energy

**Purpose:** Calculate energy required to pump groundwater from wells

**Derivation:**

Hydraulic power to lift water through height h at flow rate Q:

```
P_hydraulic [W] = ρ × g × h × Q [m³/s]
P_shaft [W] = P_hydraulic / η_pump
```

Converting to daily energy with Q in m³/day and output in kWh:

```
E_pump_daily [kWh/day] = (ρ × g × h × Q_daily) / (η_pump × 3,600,000)
```

**Specific energy (per m³ pumped):**

```
E_pump [kWh/m³] = (ρ × g × h) / (η_pump × 3,600,000)
```

Or equivalently (substituting ρ = 1000, g = 9.81):

```
E_pump [kWh/m³] = h / (367.0 × η_pump)
```

> **Note:** The 367.0 constant is only valid for fresh water (ρ = 1000 kg/m³). For brackish water (ρ = 1025 kg/m³), the constant becomes ~358.1. The full formula `(ρ × g × h) / (η × 3.6×10⁶)` is preferred for accuracy.

**Total daily pumping energy:**

```
E_pump_daily [kWh/day] = E_pump [kWh/m³] × flow_rate_m3_day
```

**Parameters:**

- `h` (`well_depth_m`): Total dynamic head in meters — static water level depth (from config)
- `flow_rate_m3_day` (`well_flow_rate_m3_day`): Well flow rate in m³/day (from config)
- ρ: Water density = 1025 kg/m³ (brackish groundwater; fresh water is 1000 kg/m³)
- g: Gravitational acceleration = 9.81 m/s²
- η_pump: Pump efficiency = 0.60 (community-scale submersible pumps; conservative estimate)
- 3,600,000: Conversion factor from joules to kilowatt-hours (1 kWh = 3.6 × 10⁶ J)

**Friction losses (Darcy-Weisbach):**

> **MVP implementation note:** The code (`calculations.py:calculate_pumping_energy`) also computes horizontal pipe friction losses using the Darcy-Weisbach equation:
>
> ```
> h_friction = f × (L / D) × (v² / 2g)
> ```
>
> Where f = 0.02 (PVC pipes), L = horizontal pipe distance (m), D = pipe diameter (m), v = flow velocity (m/s). This friction head is added to the vertical lift head to compute the total pumping energy. Typical friction losses for the community layout add 5–15% to the vertical lift energy.

**Worked example (sanity check):**

- Well depth h = 50 m, η_pump = 0.60, ρ = 1025 kg/m³
- E_pump = (1025 × 9.81 × 50) / (0.60 × 3,600,000) = **0.233 kWh/m³** (lift only, before friction)
- At 100 m³/day: E_pump_daily = 0.233 × 100 = 23.3 kWh/day (plus friction losses)

**Output:** E_pump in kWh/m³; E_pump_daily in kWh/day

**Dependencies:**

- Configuration:`water_system.groundwater_wells.well_depth_m`
- Configuration:`water_system.groundwater_wells.well_flow_rate_m3_day`
- Parameter file: `data/parameters/equipment/pump_systems-toy.csv` (pump specs including depth, flow rate, costs; via registry `equipment.pump_systems`)

**Sources:**

- Standard hydraulic pumping energy calculation (P = ρgQh)
- Typical submersible pump efficiencies: 55-75% depending on scale and age (using 60% for community-scale wells)
- Efficiency degrades with age; consider 0.55 for pumps >10 years old
- Darcy-Weisbach friction factor: 0.02 typical for PVC pipes (smooth bore)

## 2. Water Desalination Energy (BWRO)

**Purpose:** Calculate energy required for brackish water reverse osmosis desalination

**Formula (reference — future granular model):**

```
E_desal = f(tds_ppm, recovery_rate, membrane_type)
```

**Specific Energy by TDS Level (reference ranges):**

- TDS < 2,000 ppm: 0.5-1.0 kWh/m³
- TDS 2,000-5,000 ppm: 1.0-1.5 kWh/m³
- TDS 5,000-10,000 ppm: 1.5-2.5 kWh/m³
- TDS 10,000-15,000 ppm: 2.5-3.5 kWh/m³

> **MVP implementation note:** The current implementation uses a categorical `salinity_level` lookup (low / moderate / high) from a precomputed CSV file, rather than computing treatment energy as a continuous function of `tds_ppm`. The `SimulationDataLoader` loads treatment energy via:
>
> ```
> registry["water_treatment"]["energy"]
>   → data/precomputed/water_treatment/treatment_kwh_per_m3-toy.csv
> ```
>
> Each row provides `energy_kwh_per_m3_typical` indexed by `salinity_level`. The scenario specifies the salinity level and the simulation looks up the corresponding energy value. This is a reasonable MVP simplification; the TDS-based continuous model above is retained for future enhancement when more granular treatment modeling is needed.

**Parameters:**

- `salinity_level`: Categorical salinity level from scenario config (low / moderate / high)
- `tds_ppm`: Total dissolved solids in ppm (from config; used for reference, not directly in MVP lookup)
- `recovery_rate`: Fraction of feed water recovered as permeate = 0.75 (typical for BWRO; future use)
- `system_capacity_m3_day`: Maximum daily treatment capacity (from config)

**Output:** E_desal in kWh/m³

**Dependencies:**

- Configuration:`water_system.water_treatment.salinity_level`
- Configuration:`water_system.water_treatment.system_capacity_m3_day`
- Precomputed data:`data/precomputed/water_treatment/treatment_kwh_per_m3-toy.csv` (via registry `water_treatment.energy`)
- Equipment specs:`data/parameters/equipment/water_treatment-toy.csv` (via registry `water_treatment.equipment`)

**Sources:**

- Desalination industry standards (Voutchkov 2018)
- Energy consumption for BWRO systems: 1.5-3.0 kWh/m³ typical range

## 3. Water Conveyance Energy

**Purpose:** Calculate energy for moving water through pipes (well→treatment, treatment→storage)

**Formula (specific energy per m³):**

```
E_convey [kWh/m³] = ΔP / (η_pump × 3,600,000)
```

Where ΔP is total pressure drop in the pipe network (Pa), accounting for friction losses and any elevation change between source and destination. For total daily energy:

```
E_convey_daily [kWh/day] = E_convey [kWh/m³] × Q_daily [m³/day]
```

**Simplified Estimation:**

```
E_convey ≈ 0.1-0.3 kWh/m³ (depends on distance and elevation)
```

**Parameters:**

- ΔP: Total pressure loss in pipes (Pa), including friction (Darcy-Weisbach or Hazen-Williams) and static head
- η_pump: Booster pump efficiency = 0.75
- 3,600,000: Conversion from J/m³ to kWh/m³

**Output:** E_convey in kWh/m³

**Dependencies:**

- Implicit from community layout (distances between wells, treatment plant, storage)

**Assumptions:**

- For MVP: Use fixed value of 0.2 kWh/m³ for total conveyance
- Future: Calculate based on actual pipe network design

## 4. Irrigation Pressurization Energy

**Purpose:** Calculate energy required to pressurize treated water for drip irrigation delivery. This is distinct from groundwater pumping energy (which lifts water from the aquifer) and conveyance energy (which moves water horizontally through pipes). Drip irrigation systems require a minimum operating pressure at the emitter to ensure uniform distribution.

**Formula (specific energy per m3):**

```
E_irrigation_pump [kWh/m3] = ΔP_drip / (eta_booster x 3,600,000)
```

Where:

- ΔP_drip: Required operating pressure for drip emitters (Pa)
- eta_booster: Booster pump efficiency (dimensionless)
- 3,600,000: Conversion factor from J to kWh (1 kWh = 3.6 x 10^6 J)

**Daily total:**

```
E_irrigation_pump_daily [kWh/day] = E_irrigation_pump [kWh/m3] x total_irrigation_m3 [m3/day]
```

Where total_irrigation_m3 includes water delivered to ALL crops on ALL farms for the day (both groundwater-sourced and municipal-sourced water requires pressurization at the field).

**Default parameters:**

- ΔP_drip = 1.5 bar = 150,000 Pa (typical operating pressure for drip emitter systems; range 1.0-2.5 bar depending on emitter type, lateral length, and terrain)
- eta_booster = 0.75 (small booster pump efficiency; range 0.65-0.85 for fractional-HP centrifugal pumps)

**Worked example:**

```
E_irrigation_pump = 150,000 / (0.75 x 3,600,000) = 0.0556 kWh/m3 (rounded to 0.056)
```

At 200 m3/day total irrigation: E_irrigation_pump_daily = 0.056 x 200 = 11.1 kWh/day

**Note:** This energy is applied to ALL irrigated water regardless of source (groundwater or municipal). Groundwater has already been pumped to the surface and treated; municipal water arrives at low pressure from the mains. Both require pressurization for drip delivery. This is NOT double-counted with the groundwater pumping energy (E_pump), which covers vertical lift only, or conveyance energy (E_convey), which covers horizontal transport losses. The irrigation pressurization pump is a separate physical device located at the field header.

**Output:** E_irrigation_pump in kWh/m3; E_irrigation_pump_daily in kWh/day

**Dependencies:**

- Configuration: `water_system.irrigation_system.type` (determines required pressure; drip = 1.5 bar, sprinkler = 2.5-4.0 bar)
- Parameter file: `data/parameters/equipment/irrigation_systems-toy.csv` (operating pressure, pump efficiency)

**Sources:**

- Drip irrigation operating pressure: Netafim design guides (1.0-2.5 bar at emitter); FAO Irrigation Manual
- Booster pump efficiency: Small centrifugal pumps 0.65-0.85 (lower for fractional HP units)

## 5. Irrigation Water Demand

**Purpose:** Calculate daily crop water requirements

**Formula (FAO Penman-Monteith):**

```
ET_crop = ET_0 × K_c
Water_demand = (ET_crop × Area × 10) / η_irrigation
```

**Parameters:**

- ET_0: Reference evapotranspiration (mm/day) from precomputed weather data
- K_c: Crop coefficient (varies by crop and growth stage)
- Area: Planted area (ha)
- 10: Unit conversion factor — 1 mm of water over 1 ha = 10 m³ (since 1 ha = 10,000 m² and 1 mm = 0.001 m)
- η_irrigation: Irrigation system efficiency

**Irrigation Efficiency by System Type:**

- drip_irrigation: 0.90
- subsurface_drip: 0.95
- sprinkler: 0.75
- surface: 0.60

> **MVP implementation note — efficiency already in precomputed data:** The precomputed irrigation demand files (Layer 1) already account for irrigation system efficiency (η = 0.90 for drip irrigation) in the `irrigation_m3_per_ha_per_day` values. **Do not divide by η again at runtime** — this would double-count efficiency losses and overestimate water demand by ~11%. The formula `Water_demand = (ET_crop × Area × 10) / η_irrigation` describes the Layer 1 pre-computation; at Layer 3 runtime, the simulation uses the precomputed values directly. The function `calculate_irrigation_demand_adjustment()` in `calculations.py` exists for Layer 2 configuration purposes but is not applied during simulation execution.

**Output:** Water_demand in m³/day per farm

**Dependencies:**

- Precomputed data:`data/precomputed/irrigation_demand/irrigation_m3_per_ha_<crop>-toy.csv`
- Configuration:`water_system.irrigation_system.type`
- Configuration:`farms[].crops[].area_fraction`
- Parameter file:`data/parameters/crops/crop_coefficients-toy.csv` (K_c values)

**Sources:**

- FAO Irrigation and Drainage Paper No. 56 (Allen et al., 1998)
- Crop coefficient values from FAO guidelines and regional studies

## 6. Water Storage Dynamics

**Purpose:** Track water storage levels over time

**Formula:**

```
Storage(t+1) = Storage(t) + Inflow(t) - Outflow(t)
```

**Constraints:**

```
0 ≤ Storage(t) ≤ capacity_m3
Inflow(t) = min(treatment_capacity, well_capacity)
Outflow(t) = irrigation_demand(t)
```

**Parameters:**

- `capacity_m3`: Storage capacity (from config)
- treatment_capacity: From`water_system.water_treatment.system_capacity_m3_day`
- well_capacity: From`water_system.groundwater_wells.well_flow_rate_m3_day × number_of_wells`

**Output:** Storage level in m³ at each time step

**Dependencies:**

- Configuration:`water_system.irrigation_water_storage.capacity_m3`

**Assumptions:**

- No evaporation losses (arid climate, covered storage)
- No inflow/outflow rate limits (simplified for MVP)
- Initial storage: 50% of capacity

## 7. Water Use Efficiency

**Purpose:** Calculate water consumed per unit of crop output

**Formula:**

```
WUE = total_water_m3 / total_yield_kg
```

**Per-crop variant:**

```
WUE_crop_i = water_allocated_to_crop_i_m3 / yield_crop_i_kg
```

**Output:** WUE in m³/kg (lower is better)

**Notes:**

- Implemented in`src/simulation/metrics.py` as`water_per_yield_m3_kg`
- Water allocated per crop is proportional to crop area fraction and crop-specific Kc demand

## 8. Water Self-Sufficiency

**Purpose:** Fraction of total water sourced from community-owned groundwater

**Formula:**

```
Self_sufficiency_pct = (groundwater_m3 / total_water_m3) × 100
```

**Output:** Percentage (0–100%). Higher values indicate greater independence from municipal supply.

**Notes:**

- Implemented in`src/simulation/metrics.py` as`self_sufficiency_pct`
- Computed at daily, monthly, and yearly granularity

## 9. Water Allocation Policies

> **MVP implementation note:** The water simulation implements water allocation policies in `src/policies/water_policies.py`. Each policy class inherits from `BaseWaterPolicy` and implements `allocate_water(ctx: WaterPolicyContext) → WaterAllocation`. See `policies.md` Water Policies for full policy specifications. The policies are:
>
> 1. **`max_groundwater`** — 100% groundwater, municipal fallback if constrained
> 2. **`max_municipal`** — 100% municipal, no treatment energy needed
> 3. **`min_water_quality`** — Mix groundwater and municipal water to achieve target TDS (see TDS blending formula below)
> 4. **`cheapest_source`** — Dynamic daily cost comparison (GW vs municipal)
> 5. **`conserve_groundwater`** — Prefers municipal; uses GW only when municipal price exceeds a configurable threshold multiplier
> 6. **`quota_enforced`** — Hard annual groundwater limit with monthly variance controls. Parameters:
>    - `annual_quota_m3`: Maximum groundwater extraction per year
>    - `monthly_variance_pct`: Allowed deviation from equal monthly distribution (default 15%)
>    - Example: 12,000 m³/year quota → 1,000 m³/month target, allowed range 850–1,150 m³/month
>    - When annual quota is exhausted, forces 100% municipal water for the remainder of the year
>    - When monthly limit is exceeded, forces municipal for the remainder of the month
>
> All policies apply physical infrastructure constraints (well capacity, treatment throughput, energy availability) and track decision metadata for visualization. For calculation details of groundwater cost, see Water Cost Calculation in [calculations_economic.md](calculations_economic.md).
>
> **TDS Blending Formula (****`min_water_quality`****):**
>
> The `min_water_quality` policy targets a maximum TDS by mixing groundwater and municipal water. The canonical formula solves for the required municipal fraction (consistent with `policies.md` `min_water_quality` policy):
>
> ```
> required_municipal_fraction = (groundwater_tds - target_tds) / (groundwater_tds - municipal_tds)
> required_municipal_fraction = clip(required_municipal_fraction, 0, 1)
> gw_fraction = 1 - required_municipal_fraction
> ```
>
> Where `target_tds` is the maximum acceptable TDS for the mixed water (set per policy instance), `municipal_tds` is the TDS of municipal supply, and `groundwater_tds` is the TDS of raw groundwater. If groundwater TDS is below the target, groundwater is used preferentially (gw_fraction = 1.0, municipal_fraction = 0.0). If groundwater is too saline for any blending to achieve the target, 100% municipal is used (municipal_fraction = 1.0). Physical constraints (well capacity, treatment throughput) may further reduce the groundwater fraction, which always improves water quality (municipal water is the cleaner source). The `gw_fraction` is used for groundwater extraction tracking and self-sufficiency metrics. See `policies.md` `min_water_quality` policy for full pseudocode.

*Sections 10-11 (Aquifer Depletion Rate, Aquifer Drawdown Feedback) removed. Aquifer level modeling is deferred to a future phase. Pumping energy uses a static `well_depth_m` value. Cumulative groundwater extraction is tracked on SimulationState for reporting.*

## 12. Days Without Municipal Water

**Purpose:** Count days when the farm operated entirely on groundwater (municipal supply not used)

**Formula:**

```
Days_without_municipal = count(days where municipal_m3 == 0 AND total_water_m3 > 0)
```

**Output:** Integer count per year

**Notes:**

- This is a*(resilience)* metric — measures ability to operate independently
- Tracked from daily water records: each day's`municipal_m3` allocation is available in simulation output
- High values indicate strong self-sufficiency; also flags potential vulnerability if groundwater-only operation is involuntary (municipal supply disruption)

## 13. Water Storage Utilization

**Purpose:** Measure how effectively water storage capacity is being used

**Formula:**

```
Storage_utilization_pct = (avg_daily_storage_level / capacity_m3) × 100
```

**Where:**

```
avg_daily_storage_level = Σ Storage(t) / N_days
```

**Output:** Percentage (0–100%)

**Notes:**

- Very high utilization (>90%) suggests storage is undersized and frequently at capacity
- Very low utilization (<20%) suggests storage is oversized for current demand
- Requires tracking`Storage(t)` at each time step (see Water Storage Dynamics)

## 14. Irrigation Demand vs Delivery

**Purpose:** Quantify the gap between crop water requirements and actual water delivered

**Formula:**

```
Demand_gap_m3 = irrigation_demand_m3 - actual_delivery_m3
Delivery_ratio = actual_delivery_m3 / irrigation_demand_m3
Unmet_demand_pct = (Demand_gap_m3 / irrigation_demand_m3) × 100
```

**Output:** Demand gap in m³/day; delivery ratio (0–1); unmet demand as percentage

**Notes:**

- `irrigation_demand_m3` comes from FAO Penman-Monteith calculation (see Irrigation Water Demand above)
- `actual_delivery_m3` is the water policy allocation result
- Persistent unmet demand triggers yield reduction via the FAO-33 water deficit formula at harvest (see [calculations_crop.md](calculations_crop.md) Crop Yield Estimation). Water stress ratio is not tracked as a daily policy input in MVP.
- Can be aggregated to monthly/yearly for trend analysis
