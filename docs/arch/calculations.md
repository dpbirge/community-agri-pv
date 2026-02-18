# Community Farm Model Calculation Methodologies 

## 1. Overview

This document defines HOW configuration parameters from `structure.md` are used in calculations throughout the simulation. It provides formulas, data sources, units, and references to scientific literature. Sections marked **TBD** have conceptual formulas but require further research or design decisions before implementation.

For WHAT parameters exist and their valid options, see `structure.md`. For the full list of output metrics these calculations feed into, see Section 4 (Metrics) of `structure.md`.

> **Implementation status:** Most sections are fully implemented. Two documented features are pending code implementation: **Section 2.9 (Aquifer Drawdown Feedback)** and **Section 4.5 (Crop Diversity Index — revenue weighting)**. See `docs/codereview/calculations-vs-code-review-2026-02-05.md` for the active tracker.

For implementation code, see `src/settings/calculations.py` and respective policy modules.

**Sections:**

1. Overview
2. Water System Calculations
3. Energy System Calculations
4. Crop Growth and Yield Calculations
5. Economic Calculations
6. Food Processing Calculations
7. Labor Calculations*(TBD)*
8. Resilience and Monte Carlo Calculations*(TBD)*
9. Units and Conversions
10. References

## 2. Water System Calculations

### Groundwater Pumping Energy

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

- `h` (`well_depth_m`): Total dynamic head in meters — includes static water level depth plus drawdown (from config; see Aquifer Drawdown Feedback for time-varying component)
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
- Parameter file:`data/parameters/water/pump_equipment_parameters.csv` (efficiency values)

**Sources:**

- Standard hydraulic pumping energy calculation (P = ρgQh)
- Typical submersible pump efficiencies: 55-75% depending on scale and age (using 60% for community-scale wells)
- Efficiency degrades with age; consider 0.55 for pumps >10 years old
- Darcy-Weisbach friction factor: 0.02 typical for PVC pipes (smooth bore)

### Water Treatment Energy (BWRO)

**Purpose:** Calculate energy required for brackish water reverse osmosis desalination

**Formula (reference — future granular model):**

```
E_treatment = f(tds_ppm, recovery_rate, membrane_type)
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

**Output:** E_treatment in kWh/m³

**Dependencies:**

- Configuration:`water_system.water_treatment.salinity_level`
- Configuration:`water_system.water_treatment.system_capacity_m3_day`
- Precomputed data:`data/precomputed/water_treatment/treatment_kwh_per_m3-toy.csv` (via registry `water_treatment.energy`)
- Equipment specs:`data/parameters/equipment/water_treatment-toy.csv` (via registry `water_treatment.equipment`)

**Sources:**

- Desalination industry standards (Voutchkov 2018)
- Energy consumption for BWRO systems: 1.5-3.0 kWh/m³ typical range

### Water Conveyance Energy

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

### Irrigation Water Demand

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

- Precomputed data:`data/precomputed/irrigation/crop_water_requirements-toy.csv`
- Configuration:`water_system.irrigation_system.type`
- Configuration:`farms[].crops[].area_fraction`
- Parameter file:`data/parameters/crops/crop_parameters-toy.csv` (K_c values)

**Sources:**

- FAO Irrigation and Drainage Paper No. 56 (Allen et al., 1998)
- Crop coefficient values from FAO guidelines and regional studies

### Water Storage Dynamics

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

### Water Use Efficiency

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

### Water Self-Sufficiency

**Purpose:** Fraction of total water sourced from community-owned groundwater

**Formula:**

```
Self_sufficiency_pct = (groundwater_m3 / total_water_m3) × 100
```

**Output:** Percentage (0–100%). Higher values indicate greater independence from municipal supply.

**Notes:**

- Implemented in`src/simulation/metrics.py` as`self_sufficiency_pct`
- Computed at daily, monthly, and yearly granularity

### Water Allocation Policies

> **MVP implementation note:** The water simulation implements water allocation policies in `src/policies/water_policies.py`. Each policy class inherits from `BaseWaterPolicy` and implements `allocate_water(ctx: WaterPolicyContext) → WaterAllocation`. See `policies.md` Section 2 for full policy specifications. The policies are:
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
> All policies apply physical infrastructure constraints (well capacity, treatment throughput, energy availability) and track decision metadata for visualization. For calculation details of groundwater cost, see Water Cost Calculation in Section 5.
>
> **TDS Blending Formula (`min_water_quality`):**
>
> The `min_water_quality` policy targets a maximum TDS by mixing groundwater and municipal water. The required groundwater fraction is:
>
> ```
> gw_fraction = (target_tds - municipal_tds) / (groundwater_tds - municipal_tds)
> gw_fraction = clip(gw_fraction, 0, 1)
> ```
>
> [OWNER: verify TDS blending formula]
>
> Where `target_tds` is the maximum acceptable TDS for the mixed water (set per policy instance), `municipal_tds` is the TDS of municipal supply, and `groundwater_tds` is the TDS of raw groundwater. If groundwater TDS is below the target, groundwater is used preferentially (gw_fraction = 1.0). If groundwater is too saline for any blending to achieve the target, 100% municipal is used (gw_fraction = 0.0). Physical constraints (well capacity, treatment throughput) may further reduce the groundwater fraction, which always improves water quality (municipal water is the cleaner source). See `policies.md` Section 2.3 for full pseudocode.

### Aquifer Depletion Rate

> **MVP simplification:** Aquifer depletion is tracked for reporting and resilience analysis but does not trigger allocation changes or modify water policy behavior in MVP. The aquifer drawdown feedback (below) affects pumping energy costs only.

**Purpose:** Estimate the rate of groundwater drawdown and remaining aquifer lifespan, with feedback to pumping energy costs

**Formula (volume balance — base model):**

```
Annual_extraction_m3 = Σ daily_groundwater_use  over one year
Net_depletion_m3_yr = Annual_extraction_m3 - aquifer_recharge_rate_m3_yr
Remaining_volume_m3(t) = aquifer_exploitable_volume_m3 - Σ Net_depletion_m3_yr(y)  for y = 1..t
Years_remaining = Remaining_volume_m3 / Net_depletion_m3_yr
```

### Aquifer Drawdown Feedback

**Purpose:** Model the increasing pumping depth (and therefore energy cost) as the water table drops over years of extraction. This creates a critical positive feedback loop: extraction → deeper water table → higher energy cost per m³ → higher operating expenses.

**Simplified drawdown model (linearized):**

```
Cumulative_extraction_m3(year) = Σ Annual_extraction_m3(y)  for y = 1..year
Fraction_depleted(year) = Cumulative_extraction_m3(year) / aquifer_exploitable_volume_m3

Drawdown_m(year) = max_drawdown_m × Fraction_depleted(year)
Effective_head_m(year) = well_depth_m + Drawdown_m(year)
```

This feeds back into pumping energy (see Groundwater Pumping Energy):

```
E_pump(year) [kWh/m³] = (ρ × g × Effective_head_m(year)) / (η_pump × 3,600,000)
```

(Using ρ = 1025 kg/m³, g = 9.81, η_pump = 0.60 per the updated pumping energy parameters.)

**Parameters:**

- `aquifer_exploitable_volume_m3`: Total exploitable groundwater volume accessible to the community's wells (from config)
- `aquifer_recharge_rate_m3_yr`: Natural recharge rate — negligible in arid Sinai but configurable for other locations (from config)
- `max_drawdown_m`: Maximum expected drawdown at full depletion (from config or estimated as aquifer thickness)
- `Annual_extraction_m3`: Computed from simulation daily groundwater records

**Advanced drawdown model (Cooper-Jacob approximation — future):**

For scenarios requiring more physical accuracy, the Cooper-Jacob equation provides drawdown as a function of aquifer hydraulic properties:

```
s(t) = (Q / (4π T)) × ln(2.25 T t / (r_w² S))
```

Where:

- s: Drawdown at the well (m)
- Q: Pumping rate (m³/day)
- T: Aquifer transmissivity (m²/day) — typically 50-500 m²/day for fractured rock in Sinai
- S: Storativity (dimensionless) — typically 0.001-0.1
- r_w: Well radius (m)
- t: Time since pumping began

This model also captures well interference (multiple wells creating overlapping cones of depression), which reduces effective yield when wells are close together.

**Output:**

- Net depletion rate in m³/yr
- Estimated years remaining at current extraction rate
- Remaining volume as percentage of initial
- Effective pumping head per year (for energy cost feedback)

**Dependencies:**

- Configuration:`water_system.groundwater_wells.aquifer_exploitable_volume_m3`
- Configuration:`water_system.groundwater_wells.aquifer_recharge_rate_m3_yr`
- Configuration:`water_system.groundwater_wells.max_drawdown_m` (new parameter)
- Simulation output: daily groundwater allocation records

**Assumptions:**

- Exploitable volume is a fixed estimate configured per scenario — not a dynamic hydrogeological model
- Recharge is treated as a constant annual rate (no seasonal variation)
- No interaction with neighboring aquifer users or saltwater intrusion effects
- Linearized drawdown assumes uniform aquifer geometry (adequate for community-scale planning)
- For research-grade data, see`data/parameters/water/aquifer_parameters.md`

**Notes:**

- This is a *(resilience)* metric
- If`Net_depletion_m3_yr ≤ 0` (recharge exceeds extraction), aquifer is sustainable and`Years_remaining = ∞`
- The exploitable volume is intentionally a simple scalar — the community likely cannot survey a full aquifer model, but can get a rough volume estimate from a hydrogeological assessment
- The energy feedback loop is the key long-range planning insight: even modest drawdown (10-20m over 15 years) can increase pumping costs by 20-40%
- For MVP: Use the linearized drawdown model; Cooper-Jacob is a future enhancement for scenarios that require well-spacing optimization

### Days Without Municipal Water

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

### Water Storage Utilization

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

### Irrigation Demand vs Delivery

**Purpose:** Quantify the gap between crop water requirements and actual water delivered

**Formula:**

```
Demand_gap_m3 = irrigation_demand_m3 - actual_delivery_m3
Delivery_ratio = actual_delivery_m3 / irrigation_demand_m3
Unmet_demand_pct = (Demand_gap_m3 / irrigation_demand_m3) × 100
```

**Output:** Demand gap in m³/day; delivery ratio (0–1); unmet demand as percentage

**Notes:**

- `irrigation_demand_m3` comes from FAO Penman-Monteith calculation (see Irrigation Water Demand)
- `actual_delivery_m3` is the water policy allocation result
- Persistent unmet demand triggers yield reduction via the FAO-33 water deficit formula at harvest (see Crop Yield Estimation). Water stress ratio is not tracked as a daily policy input in MVP.
- Can be aggregated to monthly/yearly for trend analysis

## 3. Energy System Calculations

### PV Power Generation

**Purpose:** Calculate solar photovoltaic power output under crop cover, accounting for panel degradation and temperature effects

**Formula:**

```
P_pv(t) = sys_capacity_kw × CF_pv(t) × shading_factor × degradation_factor(year) × temp_derate(t)
```

**Panel Degradation (annual capacity loss):**

```
degradation_factor(year) = (1 - degradation_rate) ^ year
```

Typical degradation rates:

- Mono-crystalline Si: 0.005/yr (0.5%/yr)
- Poly-crystalline Si: 0.007/yr (0.7%/yr)
- Thin-film: 0.005-0.010/yr

Over a 15-year simulation at 0.5%/yr: year-15 output = 92.8% of year-1. This is a standard manufacturer warranty assumption (IEC 61215) and should not be omitted for simulations longer than ~3 years.

**Temperature Derating (hot climate correction):**

```
temp_derate(t) = 1 + γ × (T_cell(t) - T_STC)
```

Where T_cell is estimated using the NOCT model:

```
T_cell(t) = T_ambient(t) + (NOCT - 20) / 800 × GHI(t)
```

Parameters:

- γ: Temperature coefficient of power = -0.004 /°C (typical crystalline Si; range -0.003 to -0.005)
- T_STC: Standard test condition temperature = 25°C
- NOCT: Nominal operating cell temperature = 45°C (typical; range 42-48°C)
- GHI(t): Global horizontal irradiance (W/m²) from weather data

In Sinai summer, T_cell can reach 55-65°C, producing a 12-16% output penalty on peak days. Annual average temperature derate for hot arid climates is typically 5-8%.

**Shading Factor (agri-PV microclimate effect):**

Current implementation uses a static density-based approximation. Note: actual shading losses vary with sun angle (time of day and season); the static value represents an annual average.

**Approximation by Density:**

- low (30% coverage): shading_factor ≈ 0.95
- medium (50% coverage): shading_factor ≈ 0.90
- high (80% coverage): shading_factor ≈ 0.85

**Parameters:**

- `sys_capacity_kw`: Total PV system capacity (from config)
- CF_pv(t): Capacity factor at time t (from precomputed data)
- `density`: Panel density configuration
- `height_m`: Panel height above crops
- `degradation_rate`: Annual capacity degradation rate (from parameter file, default 0.005). **Note:** This value comes from equipment parameter files, not from user scenario configuration.
- γ: Temperature coefficient of power (from parameter file, default -0.004 /°C)

**Output:** P_pv in kW at each time step

**Dependencies:**

- Precomputed data:`data/precomputed/power/pv_power_output_normalized-toy.csv`
- Precomputed data: daily temperature and irradiance from weather data (for temp derating)
- Configuration:`energy_system.pv.sys_capacity_kw`
- Configuration:`energy_system.pv.density`
- Configuration:`energy_system.pv.height_m`

**Sources:**

- Normalized PV output from PVWatts or System Advisor Model (SAM)
- Agri-PV shading effects from Dupraz et al. (2011) and regional studies
- PV degradation rates: Jordan & Kurtz (2013), "Photovoltaic Degradation Rates — An Analytical Review", NREL
- Temperature derating: IEC 61215 standard test conditions; NOCT model from PVWatts documentation

### Wind Power Generation

**Purpose:** Calculate wind turbine power output

**Formula:**

```
P_wind(t) = sys_capacity_kw × CF_wind(t, hub_height_m)
```

**Hub Height Correction (two approaches):**

**Power law (current — adequate for community planning):**

```
v_hub = v_ref × (hub_height_m / h_ref)^α
```

- α: Wind shear exponent = 0.143 (1/7 power law, typical for open flat terrain)
- Simple and widely used; accuracy decreases when extrapolating above 2× reference height

**Logarithmic wind profile (more physically grounded):**

```
v_hub = v_ref × ln(hub_height_m / z_0) / ln(h_ref / z_0)
```

- z_0: Surface roughness length (m)
  - Open agricultural land (low crops): z_0 ≈ 0.03 m
  - Agricultural land with crops: z_0 ≈ 0.10 m
  - Agri-PV installation with panels: z_0 ≈ 0.10-0.30 m (panels increase roughness)
- Preferred in wind engineering as it is derived from atmospheric boundary layer physics (Monin-Obukhov similarity theory)
- More accurate for height extrapolation, especially when hub height differs significantly from reference measurement height

For this project, either approach is defensible. The log-law is recommended if reference wind data is measured at heights significantly different from hub height (e.g., 10m measurement, 30-50m hub).

**Parameters:**

- `sys_capacity_kw`: Total wind system capacity (from config)
- CF_wind(t): Capacity factor at time t (from precomputed data)
- `hub_height_m`: Hub height in meters
- α: Wind shear exponent = 0.143 (power law), or z_0: surface roughness length (log law)

> **Note on hub_height_m:** This is **not a user-configurable parameter**. The user selects a wind turbine `type` (small, medium, or large) in the scenario YAML. The `hub_height_m` is then looked up from the wind turbine equipment data file (`data/parameters/equipment/wind_turbines-toy.csv`) based on the selected turbine type. Configuration reference is for documentation purposes only.

**Output:** P_wind in kW at each time step

**Dependencies:**

- Precomputed data:`data/precomputed/power/wind_power_output_normalized-toy.csv`
- Configuration:`energy_system.wind.sys_capacity_kw`
- Configuration:`energy_system.wind.hub_height_m`

**Sources:**

- Wind power curve data from manufacturer specifications
- Wind shear profile from IEC 61400-1 wind turbine design standards
- Logarithmic profile: Stull (1988), "An Introduction to Boundary Layer Meteorology"

### Battery Storage Dynamics

**Purpose:** Track battery state of charge and throughput

**Formula:**

```
SOC(t+1) = SOC(t) + (P_charge(t) × η_charge - P_discharge(t) / η_discharge) × Δt / capacity_kwh
```

> **Note:** In the dispatch implementation, all charge/discharge values are in kWh (dt = 1 day is absorbed into the values). The formula simplifies to `SOC(t+1) = SOC(t) + (energy_stored_kwh - energy_removed_kwh) / capacity_kwh`.

**Constraints:**

```
SOC_min ≤ SOC(t) ≤ SOC_max
P_charge(t) ≤ P_charge_max
P_discharge(t) ≤ P_discharge_max
```

**Parameters:**

- `capacity_kwh`: Total battery capacity (from config)
- η_charge: Charging efficiency = 0.95 (LFP)
- η_discharge: Discharging efficiency = 0.95 (LFP)
- SOC_min: Minimum state of charge = 0.10 (10%)
- SOC_max: Maximum state of charge = 0.90 (90%)

**Output:** SOC (state of charge) at each time step

**Dependencies:**

- Configuration:`energy_system.battery.sys_capacity_kwh`
- Configuration:`energy_system.battery.chemistry`

**Battery Capacity Degradation:**

For simulations longer than ~3 years, capacity fade must be modeled. LFP batteries experience two independent aging mechanisms:

```
Effective_capacity(year) = capacity_kwh × (1 - fade_calendar(year)) × (1 - fade_cycle(year))
```

**Calendar aging** (time-dependent, regardless of use):

```
fade_calendar(year) = α_cal × year
```

- α_cal ≈ 0.015/yr (1.5%/yr) for LFP at 25-35°C ambient
- Accelerated at higher temperatures: roughly doubles per 10°C above 25°C
- For Sinai climate (mean ~25°C, peaks 40°C+), use α_cal ≈ 0.018-0.020/yr

**Cycle aging** (throughput-dependent):

```
fade_cycle(year) = α_cyc × EFC_cumulative(year) / EFC_rated
```

- EFC_cumulative: Cumulative equivalent full cycles from simulation start
- EFC_rated: Rated cycle life to 80% capacity ≈ 4000-6000 for LFP
- α_cyc ≈ 0.20 (total cycle-driven fade at rated life)

**End-of-life threshold:** Battery is typically considered for replacement when effective capacity drops below 70-80% of nameplate. At ~2%/yr combined fade, this occurs around year 10-15 for LFP.

**Self-discharge:**

```
SOC_loss_per_day = SOC(t) × self_discharge_rate_daily
```

- Self-discharge rate: ~0.05%/day for LFP (≈1.5%/month)
- Small effect on daily dispatch but accumulates over weekends/low-demand periods

**Assumptions:**

- Round-trip efficiency: 90% for LFP batteries
- Initial SOC: 50% of capacity
- MVP simplification: Capacity degradation can be approximated as a linear annual fade of ~2%/yr combined (calendar + cycle) if detailed cycle tracking is not yet implemented
- Self-discharge can be omitted for MVP daily time-step if battery cycles most days

### Backup Generator Fuel Consumption

**Purpose:** Calculate diesel fuel consumption for backup power, accounting for load-dependent efficiency

Diesel generators have highly nonlinear fuel consumption — at low loads, specific fuel consumption (L/kWh) increases substantially because a significant fraction of fuel goes to overcoming friction and maintaining idle speed regardless of electrical output.

**Formula (constant SFC — MVP simplification):**

```
Fuel(t) = P_gen(t) × SFC × Δt
```

This is adequate when the generator consistently runs near rated load (>60%).

**Formula (Willans line model — recommended for accuracy):**

The Willans line is the standard engineering model for diesel generator fuel consumption:

```
Fuel(t) = (a × P_rated + b × P_gen(t)) × Δt
```

Where:

- a: No-load fuel coefficient = 0.05-0.08 L/kWh (fuel consumed at zero electrical load)
- b: Incremental fuel coefficient = 0.18-0.22 L/kWh (additional fuel per kWh of electrical output)
- P_rated: Generator nameplate capacity (kW)
- P_gen(t): Actual electrical output at time t (kW)

**Effective SFC by load fraction (using a = 0.06, b = 0.20):**

Effective SFC = (a × P_rated + b × P_gen) / P_gen = a / load_fraction + b

| Load Fraction | Constant SFC Model | Willans Line Model | Error |
| ------------- | ------------------ | ------------------ | ----- |
| 100%          | 0.25 L/kWh        | 0.26 L/kWh        | -4%   |
| 75%           | 0.25 L/kWh        | 0.28 L/kWh        | -11%  |
| 50%           | 0.25 L/kWh        | 0.32 L/kWh        | -22%  |
| 25%           | 0.25 L/kWh        | 0.44 L/kWh        | -43%  |

At 25% load, the constant SFC model underestimates fuel consumption by ~43%. This matters significantly in hybrid renewable systems where the generator often runs at partial load to cover small deficits.

**Minimum load constraint:**

Most diesel generators should not run below 30% of rated capacity for extended periods (wet stacking, carbon buildup). The dispatch algorithm should enforce:

```
P_gen(t) = 0                          if deficit < P_rated × min_load_fraction
P_gen(t) = max(P_rated × 0.30, deficit)   otherwise
```

**Parameters:**

- P_gen(t): Generator power output at time t (kW)
- P_rated: Generator nameplate capacity (kW)
- a: No-load fuel coefficient (from parameter file, default 0.06 L/kWh)
- b: Incremental fuel coefficient (from parameter file, default 0.20 L/kWh)
- SFC: Specific fuel consumption = 0.25 L/kWh (MVP constant, equivalent to Willans at ~100% load)
- Δt: Time step (hours)
- min_load_fraction: Minimum load = 0.30 (30%)

**Output:** Fuel consumption in liters

**Dependencies:**

- Configuration:`energy_system.backup_generator.capacity_kw`
- Parameter file:`data/parameters/energy/generator_parameters.csv`

**Sources:**

- Typical diesel generator SFC: 0.20-0.30 L/kWh at 75% load
- Willans line coefficients: Derived from manufacturer fuel curves; validated in Barley & Winn (1996) and HOMER Energy documentation
- Minimum load recommendations: Generator manufacturer guidelines (Caterpillar, Cummins)

### Energy Dispatch (Load Balance)

> **Status: Implemented** — `src/simulation/simulation.py:dispatch_energy()` (lines 578-751). The dispatch function must consume the boolean flags returned by the energy policy object to determine which sources are available. See `policies.md` Section 5 for the full policy specifications.

**Purpose:** Determine how generation sources meet demand at each time step, including battery charge/discharge decisions, grid import/export, and curtailment. The dispatch algorithm is parameterized by the energy policy's boolean flags (`use_renewables`, `use_battery`, `grid_import`, `grid_export`, `use_generator`, `sell_renewables_to_grid`).

**PV generation (within dispatch):**

```
pv_kwh [kWh] = sys_capacity_kw × pv_kwh_per_kw(date, density) × degradation_factor × shading_factor

degradation_factor = (1 - degradation_rate)^years_since_start
shading_factor = {low: 0.95, medium: 0.90, high: 0.85}
```

> **Note:** `degradation_rate` comes from parameter files (default 0.005/yr), not user configuration. See PV Power Generation section above.

**Total demand (full model, all 6 components):**

```
E_demand(t) [kWh] = E_pump(t) + E_treatment(t) + E_convey(t)
                  + E_household(t) + E_processing(t) + E_irrigation_pump(t)
```

See Total Energy Demand section below for component descriptions.

**Total renewable generation:**

```
E_renewable(t) [kWh] = P_pv(t) [kWh] + P_wind(t) [kWh]
```

**Policy-conditioned dispatch:**

The energy policy returns boolean flags that control the dispatch algorithm. Each policy type produces a different merit order:

**`microgrid` policy** — PV -> Wind -> Battery -> Generator (NO grid connection)

Flags: `use_renewables=true`, `use_battery=true`, `grid_import=false`, `grid_export=false`, `use_generator=true`, `sell_renewables_to_grid=false`

```
// Step 1: Use PV + wind to meet demand
used_renewable [kWh] = min(E_renewable(t), E_demand(t))
remaining_demand [kWh] = E_demand(t) - used_renewable

// Step 2: Charge battery from surplus renewables
surplus [kWh] = E_renewable(t) - used_renewable
Battery_charge(t) [kWh] = min(surplus, available_room / η_charge)

// Step 3: Discharge battery for remaining demand
Battery_discharge(t) [kWh] = min(remaining_demand, available_stored [kWh] × η_discharge)
remaining_demand = remaining_demand - Battery_discharge(t)

// Step 4: Generator for any remaining shortfall
Generator(t) [kWh] = min(remaining_demand, P_rated [kW] × hours_available)
remaining_demand = remaining_demand - Generator(t)

// Step 5: No grid import/export
Grid_import(t) = 0
Grid_export(t) = 0

// Step 6: Curtailment — surplus that cannot be stored
Curtailment(t) [kWh] = surplus - Battery_charge(t)

// Step 7: Unmet demand (if generator insufficient)
Unmet_demand(t) [kWh] = remaining_demand
```

**`renewable_first` policy** — PV -> Wind -> Battery -> Grid import (standard merit order)

Flags: `use_renewables=true`, `use_battery=true`, `grid_import=true`, `grid_export=true`, `use_generator=false`, `sell_renewables_to_grid=false`

```
// Step 1: Use PV + wind to meet demand
used_renewable [kWh] = min(E_renewable(t), E_demand(t))
remaining_demand [kWh] = E_demand(t) - used_renewable

// Step 2: Charge battery from surplus renewables
surplus [kWh] = E_renewable(t) - used_renewable
Battery_charge(t) [kWh] = min(surplus, available_room / η_charge)

// Step 3: Discharge battery for remaining demand
Battery_discharge(t) [kWh] = min(remaining_demand, available_stored [kWh] × η_discharge)
remaining_demand = remaining_demand - Battery_discharge(t)

// Step 4: Grid import for remaining shortfall
Grid_import(t) [kWh] = remaining_demand    // Unlimited for MVP

// Step 5: Export surplus renewable generation to grid
Grid_export(t) [kWh] = surplus - Battery_charge(t)    // Unlimited for MVP

// Step 6: No generator dispatch (grid is fallback)
Generator(t) = 0

// Step 7: Curtailment = 0 (grid absorbs all surplus)
Curtailment(t) = 0
```

**`all_grid` policy** — Grid import for all demand; renewables exported

Flags: `use_renewables=false`, `use_battery=false`, `grid_import=true`, `grid_export=true`, `use_generator=false`, `sell_renewables_to_grid=true`

```
// Step 1: Import all demand from grid
Grid_import(t) [kWh] = E_demand(t)    // Unlimited for MVP

// Step 2: Route all renewable generation to grid export (net metering revenue)
Grid_export(t) [kWh] = E_renewable(t)

// Step 3: No battery usage
Battery_charge(t) = 0
Battery_discharge(t) = 0

// Step 4: No generator
Generator(t) = 0

// Step 5: No curtailment (all goes to grid)
Curtailment(t) = 0
```

**Battery SOC update (applies when `use_battery=true`):**

> **Note:** Dispatch uses kWh values directly (dt is absorbed into the energy values since the simulation uses a daily time step where dt = 1 day and all generation/demand values are already in kWh/day).

```
energy_stored [kWh] = Battery_charge(t) × η_charge
energy_removed [kWh] = Battery_discharge(t) / η_discharge
SOC(t+1) = SOC(t) + (energy_stored - energy_removed) / capacity_kwh
SOC(t+1) = clamp(SOC(t+1), SOC_min, SOC_max)
```

**Generator fuel (Willans line, at full rated load for shortest run time):**

```
hours = Generator_kwh [kWh] / P_rated [kW]
fuel_L [L] = (a [L/kWh] × P_rated [kW] + b [L/kWh] × P_rated [kW]) × hours
```

Running at full load is the most fuel-efficient operating point per Section 3 (Backup Generator Fuel Consumption).

**Daily accumulators:** Cumulative PV, wind, grid import, grid export, generator, battery charge/discharge, and curtailment are tracked per year and reset at year boundaries. Daily records are appended to `energy_state.daily_energy_records`.

**Current MVP simplifications:**

- Grid import and export are unlimited (no capacity constraints)
- No time-of-use price optimization -- dispatch is fixed merit-order regardless of TOU pricing

### Total Energy Demand

> **Status: Partially implemented** — Two demand components are aggregated in the simulation loop (`simulation.py` line 1004). Processing energy is not yet included.

**Purpose:** Sum all energy demand components for load balance

**Formula (full model — all 6 demand components):**

```
E_demand(t) [kWh/day] = E_pump(t) + E_treatment(t) + E_convey(t)
                      + E_household(t) + E_processing(t) + E_irrigation_pump(t)
```

**Where (all units kWh/day):**

- `E_pump(t) [kWh/day]`: Groundwater pumping energy = E_pump [kWh/m3] x groundwater_m3 (Section 2)
- `E_treatment(t) [kWh/day]`: BWRO desalination energy = treatment_kwh_per_m3 x groundwater_m3 (Section 2)
- `E_convey(t) [kWh/day]`: Water conveyance energy = E_convey [kWh/m3] x total_water_m3 (Section 2)
- `E_household(t) [kWh/day]`: Household electricity demand (from `calculations.py:calculate_household_demand`)
- `E_processing(t) [kWh/day]`: Food processing energy = processing_kwh_per_kg x processed_kg (Section 6)
- `E_irrigation_pump(t) [kWh/day]`: Pressurization energy for drip irrigation system

**All 6 components must be included in the dispatch Total_demand calculation.** The dispatch section (above) references this full formula.

**Current implementation:**

```
total_energy_demand_kwh = day_total_water_energy_kwh + daily_household_kwh
```

Where `day_total_water_energy_kwh` is the sum of `allocation.energy_used_kwh` across all farms (includes pumping + treatment energy from the water policy), and `daily_household_kwh` is computed once before the simulation loop by `calculate_household_demand()`.

**Not yet included:**
- `E_processing(t)`: Food processing energy — noted in code as "Gap 4", to be added when food processing is fully integrated with energy tracking
- `E_convey(t)`: Water conveyance energy — currently uses a fixed 0.2 kWh/m³ estimate embedded in the water policy energy calculation
- `E_irrigation_pump(t)`: Drip irrigation pressurization energy — not separately tracked

**Output:** E_demand in kWh/day

### Total Renewable Generation

**Purpose:** Sum all renewable generation for reporting and self-sufficiency calculations

**Formula:**

```
E_renewable(t) = P_pv(t) × Δt + P_wind(t) × Δt
E_renewable_yr = Σ E_renewable(t)  over all time steps in year
```

**Output:** kWh/yr

### Grid Electricity Import and Export

**Purpose:** Track electricity exchanged with the grid

**Formula:**

```
Grid_import_yr = Σ Grid_import(t) × Δt  [kWh/yr]
Grid_export_yr = Σ Grid_export(t) × Δt  [kWh/yr]
```

**Notes:**

- Depends on the energy dispatch algorithm (see above)
- Export is only counted if grid export is enabled in the scenario configuration

### Battery Throughput

**Purpose:** Measure annual battery cycling for degradation and cost tracking

**Formula:**

```
Battery_throughput_yr = Σ (Battery_charge(t) + Battery_discharge(t)) × Δt  [kWh/yr]
Equivalent_full_cycles = Battery_throughput_yr / (2 × capacity_kwh)
```

**Output:** kWh/yr throughput; equivalent full cycle count

**Note on cycle counting:** The denominator `2 × capacity_kwh` counts a full charge *plus* a full discharge as one equivalent cycle (since throughput sums both directions). This is the standard convention used by battery manufacturers for cycle life ratings. Some references count charge and discharge as separate half-cycles — ensure consistency when comparing to manufacturer datasheets.

### Energy Self-Sufficiency

**Purpose:** Fraction of total energy consumption met by community-owned renewable generation

**Formula:**

```
Total_consumption = E_renewable_used + Grid_import + Generator_output
E_renewable_used = E_renewable - Curtailment - Grid_export
Self_sufficiency_pct = (E_renewable_used / Total_consumption) × 100
```

**Output:** Percentage (0–100%). Higher values indicate greater energy independence.

**Notes:**

- This is a *(resilience)* metric
- Battery round-trip losses affect this metric: energy stored in the battery is counted as renewable when generated, but only ~90% is recovered on discharge. The `E_renewable_used` term includes energy that entered the battery but subtracts curtailment and export — battery losses are implicitly absorbed as reduced useful output. This means self-sufficiency slightly overstates the fraction of demand met by renewables when battery cycling is heavy

### Days Without Grid Electricity

**Purpose:** Count days the community operated entirely off-grid

**Formula:**

```
Days_off_grid = count(days where Grid_import == 0 AND Total_demand > 0)
```

**Output:** Integer count per year

**Notes:**

- This is a*(resilience)* metric
- High values may indicate strong renewable capacity OR grid outage events

### Curtailment

**Purpose:** Quantify excess renewable generation that cannot be used or stored

**Formula:**

```
Curtailment(t) = max(0, Total_generation(t) - Total_demand(t) - Battery_charge(t) - Grid_export(t))
Curtailment_yr = Σ Curtailment(t) × Δt  [kWh/yr]
Curtailment_pct = (Curtailment_yr / E_renewable_yr) × 100
```

**Output:** kWh/yr; percentage of total renewable generation curtailed

### Blended Electricity Cost

**Purpose:** Calculate the weighted average cost of electricity across all sources

**Formula:**

```
Blended_cost = Total_electricity_cost / Total_consumption

Total_electricity_cost = (Grid_import × grid_price)
                       + (Generator_output × SFC × diesel_price)
                       + (E_renewable_used × LCOE_renewable)
                       - (Grid_export × export_price)

LCOE_renewable = (annual_infrastructure_cost_pv + annual_infrastructure_cost_wind + annual_battery_cost)
               / E_renewable_yr
```

**Grid Electricity Pricing Regimes:**

The simulation supports dual electricity pricing regimes — one for agricultural use (water pumping, processing) and one for domestic use (households, community buildings). Each regime is configured independently in the scenario YAML under `energy_pricing`. See `structure.md` Pricing Configuration for the canonical schema.

1. **Agricultural regime** (`energy_pricing.agricultural.pricing_regime`):
   - `subsidized`: Uses preferential agricultural/irrigation electricity tariffs. Based on Egyptian agricultural rates (~15% discount vs commercial). Data: `historical_grid_electricity_prices-research.csv` (200 pt/kWh Aug 2024). Appropriate for communities with agricultural electricity access.
   - `unsubsidized`: Uses full-cost commercial/industrial tariffs without subsidy. Approximately 16.5% higher than subsidized agricultural rates. Data: `historical_grid_electricity_prices_unsubsidized-research.csv` (233 pt/kWh Aug 2024).

2. **Domestic regime** (`energy_pricing.domestic.pricing_regime`):
   - `subsidized`: Flat rate for domestic electricity (households, community buildings).
   - `unsubsidized`: Full-cost domestic electricity tariff.

The pricing regime for each consumer type is specified in scenario configuration and determines which price dataset is loaded during simulation initialization. The simulation resolves the applicable price upstream based on consumer type before passing it to energy and water policies.

**Configuration:**

- `energy_pricing.agricultural.pricing_regime`: [subsidized, unsubsidized]
- `energy_pricing.agricultural.subsidized.price_usd_per_kwh`: Flat rate for subsidized agricultural electricity [USD/kWh]
- `energy_pricing.agricultural.unsubsidized.price_usd_per_kwh`: Flat rate for unsubsidized agricultural electricity [USD/kWh]
- `energy_pricing.domestic.pricing_regime`: [subsidized, unsubsidized]
- `energy_pricing.domestic.subsidized.price_usd_per_kwh`: Flat rate for subsidized domestic electricity [USD/kWh]
- `energy_pricing.domestic.unsubsidized.price_usd_per_kwh`: Flat rate for unsubsidized domestic electricity [USD/kWh]
- `use_peak_offpeak`: Optional flag for peak/offpeak rates (per regime)
- `annual_escalation_pct`: Annual price escalation rate (per regime)

**Dependencies:**

- Price data (subsidized): `data/prices/electricity/historical_grid_electricity_prices-research.csv`
- Price data (unsubsidized): `data/prices/electricity/historical_grid_electricity_prices_unsubsidized-research.csv`
- Configuration: `energy_pricing.agricultural.pricing_regime`, `energy_pricing.domestic.pricing_regime`

**Output:** $/kWh blended cost

**Notes:**

- Infrastructure costs use the financing cost model (see Section 5: Infrastructure Financing Costs)
- LCOE for renewables is an internal accounting cost, not a market price
- Grid electricity pricing follows Egyptian tariff structures (see `docs/research/egyptian_utility_pricing.md`)
- Commercial/industrial differential of 16.5% verified from EgyptERA Aug 2024 tariff schedules

## 4. Crop Growth and Yield Calculations

### Crop Yield Estimation

**Purpose:** Calculate expected crop yield based on water availability and other factors

**Formula (simplified water production function):**

```
Y_actual = Y_potential × (1 - K_y × (1 - ET_actual / ET_crop))
```

**Parameters:**

- Y_potential: Maximum yield under optimal conditions (kg/ha)
- K_y: Yield response factor (crop-specific sensitivity to water stress)
- ET_actual: Actual evapotranspiration achieved
- ET_crop: Crop water requirement

**K_y values by crop (FAO-33, single-season):**

| Crop     | K_y  | Notes |
| -------- | ---- | ----- |
| Tomato   | 1.05 | FAO-33; sensitive to deficit during flowering |
| Potato   | 1.10 | FAO-33; tuber formation is water-critical |
| Onion    | 1.10 | FAO-33; shallow root system amplifies stress |
| Kale     | 0.95 | Approximate; based on leafy green analogues (lettuce/spinach) |
| Cucumber | 0.90 | FAO-33; moderate tolerance to short deficits |

K_y > 1.0 means a given percentage of water deficit causes a *larger* percentage of yield loss (amplified response). These values are hardcoded in `simulation.py:process_harvests()` as `KY_VALUES`. The water ratio proxy `ET_actual / ET_crop` is computed as `cumulative_water_m3 / expected_total_water_m3`, clamped to [0, 1].

**Output:** Y_actual in kg/ha

**Dependencies:**

- Precomputed data:`data/precomputed/yields/crop_yields-toy.csv`
- Configuration:`farms[].crops[].area_fraction`
- Configuration:`farms[].yield_factor` (farm management quality)

**Growth-stage-sensitive variant (Stewart multiplicative model):**

The single-season FAO-33 formula above applies a uniform K_y across the entire season. For more accurate long-range yield estimation, the Stewart multiplicative model accounts for differing water stress sensitivity across growth stages:

```
Y_actual / Y_potential = Π_i (1 - Ky_i × (1 - ETa_i / ETc_i))
```

Where i = each growth stage (initial, development, mid-season, late). This matters because water stress during flowering (high Ky) has a much larger yield impact than the same deficit during vegetative growth (low Ky). Stage-specific Ky values are available in FAO-33 Table 2 for the modeled crops.

### Soil Salinity Yield Reduction

**Purpose:** Account for progressive salt accumulation in the root zone when irrigating with imperfectly desalinated water. This is a critical long-range concern for any arid-climate system using brackish groundwater, even after BWRO treatment.

**Formula (FAO-29 threshold-slope model):**

```
Y_salinity / Y_potential = 1.0                                   when ECe ≤ ECe_threshold
Y_salinity / Y_potential = 1 - b × (ECe - ECe_threshold)         when ECe > ECe_threshold
Y_salinity / Y_potential = 0                                      when ECe ≥ ECe_zero_yield
```

**Crop salinity tolerance parameters (FAO-29):**

| Crop     | ECe Threshold (dS/m) | Slope b (%/dS/m) | ECe at Zero Yield (dS/m) |
| -------- | -------------------- | ----------------- | ------------------------ |
| Tomato   | 2.5                  | 9.9               | 12.6                     |
| Potato   | 1.7                  | 12.0              | 10.0                     |
| Onion    | 1.2                  | 16.0              | 7.5                      |
| Kale     | 1.8*                 | 12.0*             | 10.2*                    |
| Cucumber | 2.5                  | 13.0              | 10.2                     |

*Kale values estimated from leafy green analogues (lettuce/spinach); crop-specific data limited.

**Root zone salinity accumulation model:**

```
ECe(season) = ECe(season-1) + EC_irrigation × concentration_factor - leaching_removal

concentration_factor = 1 / (1 - ET_fraction)
  where ET_fraction = fraction of applied water consumed by ET (typically 0.7-0.9 for drip)

leaching_removal = ECe(season-1) × leaching_fraction
  where leaching_fraction = excess water applied beyond ET requirement / total applied
```

BWRO permeate typically has EC of 0.1-0.5 dS/m (from TDS 50-300 ppm), but even this accumulates over seasons in arid climates with no rainfall leaching.

**Leaching requirement:**

```
LR = EC_irrigation / (5 × ECe_threshold - EC_irrigation)
```

The leaching requirement is the minimum fraction of extra water that must pass through the root zone to prevent salt buildup. For drip irrigation with BWRO permeate, LR is typically 0.05-0.15 (5-15% extra water).

**Combined yield model:**

```
Y_actual = Y_potential × water_stress_factor × salinity_factor × yield_factor

water_stress_factor = (1 - K_y × (1 - ET_actual / ET_crop))
salinity_factor = max(0, 1 - b × max(0, ECe - ECe_threshold) / 100)
```

**Dependencies:**

- Parameter file: `data/parameters/crops/crop_salinity_tolerance.csv` (to be created)
- Configuration: BWRO permeate quality (derived from `water_system.water_treatment.tds_ppm` and recovery rate)
- Simulation output: cumulative irrigation records per crop

**Notes:**

- For MVP: Can be omitted if simulation is ≤3 years. For simulations >5 years with brackish water sources, salinity accumulation is a first-order yield effect
- Onion and potato are most salt-sensitive among the modeled crops — these will show yield decline first
- Periodic leaching events (applying extra water beyond ET) are the standard management practice and should be factored into water demand calculations

**Sources:**

- FAO Irrigation and Drainage Paper No. 33 (Doorenbos & Kassam, 1979)
- FAO Irrigation and Drainage Paper No. 29 Rev.1 (Ayers & Westcot, 1985) — Water quality for agriculture
- Regional yield data for Sinai Peninsula and similar arid climates
- Maas & Hoffman (1977) — Crop salt tolerance: current assessment (original threshold-slope data)

### Crop Growth Stages

**Purpose:** Track crop development and adjust water requirements

**Stages:** Initial → Development → Mid-season → Late season

**Duration:** Crop and climate-specific (from parameter files)

**K_c by Stage (example for tomato):**

- Initial: 0.6
- Development: 0.6 → 1.15 (linear increase)
- Mid-season: 1.15
- Late season: 1.15 → 0.7 (linear decrease)

**Dependencies:**

- Parameter file:`data/parameters/crops/crop_parameters-toy.csv`
- Configuration:`farms[].crops[].planting_dates`

**Sources:**

- FAO-56 crop coefficient tables
- Regional crop calendars for Egypt

### Post-Harvest Losses

**Purpose:** Calculate quantity and value of crop lost between harvest and sale/processing

**Formula:**

```
Loss_kg = harvest_yield_kg × loss_rate
Marketable_yield_kg = harvest_yield_kg - Loss_kg
Loss_pct = loss_rate × 100
```

**Loss rates by pathway:**

- Fresh sale (unprocessed): default 10% (typical range 10-15% for handling, transport, spoilage in arid developing-economy contexts)
- Processed (dried, canned, packaged): default 4% (typical range 3-5% for processing waste)

**Parameters:**

- `loss_rate`: Default = 0.10 (10%) for fresh produce, 0.04 (4%) for processed. The 10-15% range for fresh losses reflects variation by crop type and supply chain quality, but the simulation uses 10% as the single default.
- Crop-specific loss rates may be defined in `data/parameters/crops/crop_parameters-toy.csv`

**Output:** Loss in kg/yr and as percentage of harvest

**Notes:**

- Currently embedded as`loss_rate` in the crop revenue formula; should be tracked as a standalone metric for reporting

### Processed Product Output

**Purpose:** Calculate output quantity of processed products from raw harvest input

**Formula:**

```
Processed_output_kg = raw_input_kg × (1 - weight_loss_pct / 100)
```

**Per-crop, per-processing-type weight loss (from `data/parameters/crops/processing_specs-toy.csv`):**

| Crop     | Fresh | Packaged | Canned | Dried |
| -------- | ----- | -------- | ------ | ----- |
| Tomato   | 0%    | 3%       | 15%    | 88%   |
| Potato   | 0%    | 3%       | 15%    | 78%   |
| Onion    | 0%    | 3%       | 15%    | 80%   |
| Kale     | 0%    | 3%       | 15%    | 82%   |
| Cucumber | 0%    | 3%       | 15%    | 92%   |

**Value-add multiplier** (processed price = fresh price × multiplier):

- Packaged: 1.25×
- Canned: 1.80×
- Dried: 3.50×

**Allocation logic:**

The food processing policy determines what fraction of each crop goes to each processing pathway. See `policies.md` Section 3 for full allocation rules for all four policies (`all_fresh`, `maximize_storage`, `balanced`, `market_responsive`), including capacity clipping logic and the forced-sale umbrella rule.

**Policy-specific allocation fractions:**

See `policies.md` Section 3 for the authoritative fraction tables for all policies (`all_fresh`, `maximize_storage`, `balanced`, `market_responsive`), including the `market_responsive` price-trigger logic (Section 3.4). Fractions are not duplicated here to avoid divergence.

**Dependencies:**

- Parameter file:`data/parameters/crops/processing_specs-toy.csv` (weight loss, value multipliers)
- Configuration:`food_processing_system.[type].equipment` (processing capacity limits)
- Food processing policy selection (allocation fractions)
- Crop yield output from simulation

**Notes:**

- Current data is toy-grade; see research plan at`docs/planning/processed_product_research_plan.md`
- Processing capacity constrains throughput — if harvest exceeds capacity, excess goes to fresh sale or spoils

### Processing Utilization

**Purpose:** Measure how much of available processing capacity is actually used

**Formula:**

```
Processing_utilization_pct = (actual_throughput_kg_day / processing_capacity_kg_day) × 100
```

**Where:**

- `actual_throughput_kg_day`: Raw harvest available for processing on a given day
- `processing_capacity_kg_day`: From processing capacity calculation (see Section 6)

**Output:** Percentage (0–100%) per processing category, averaged over the period

**Notes:**

- Utilization varies seasonally — high during harvest months, near zero between harvests
- Storage capacity acts as a buffer, smoothing throughput vs harvest peaks
- Can be reported per processing type (drying, canning, fresh packaging, packaging)

### Crop Diversity Index

**Purpose:** Quantify the diversity of crops grown as a measure of revenue resilience

**Formula (Shannon Diversity Index):**

```
H = -Σ (p_i × ln(p_i))  for all crops where p_i > 0
```

**Where:**

- `p_i`: Proportion from crop i (see basis note below)
- `p_i = yield_crop_i / total_yield` (or revenue-weighted variant; see note)

**Complementary metric — crop count:**

```
Crop_count = count of crops with area_fraction > 0
```

**Output:** Shannon index H (dimensionless, higher = more diverse); crop count (integer)

**Interpretation:**

- H = 0: Monoculture (one crop only)
- H = ln(n): Maximum diversity (all n crops equally represented)
- For 5 crops: H_max = ln(5) ≈ 1.61

**Notes:**

- This is a*(resilience)* metric
- Can be computed on yield basis or revenue basis; revenue-weighted is more meaningful for economic resilience

> **MVP implementation note:** The current implementation in `metrics.py:_compute_spec_metrics()` computes the Shannon index using **area-based proportions** (`p_i = crop_area_ha / total_area_ha`), aggregated across all farms for each year. This is simpler and more stable than yield-based or revenue-based weighting, since area is known at planting time regardless of harvest outcomes. Yield-weighted and revenue-weighted variants are planned as future enhancements for economic resilience analysis.

### PV Microclimate Yield Protection

> **Status: TBD** — Requires crop-specific heat stress thresholds and agri-PV microclimate data. Research plan at `docs/planning/microclimate_yield_research_plan.md`. Target data file: `data/parameters/crops/microclimate_yield_effects-research.csv`.

**Purpose:** Estimate the fraction of crop yield protected from extreme heat by agri-PV shading

**Formula (once data is available):**

```
On days where T_max > heat_stress_threshold_C:
  Yield_modifier = 1 + (net_yield_effect_pct / 100)

On days where T_max ≤ heat_stress_threshold_C:
  Yield_modifier = 1 - (par_reduction_pct / 100) × light_sensitivity_factor

Yield_protection_pct = (Y_shaded - Y_unshaded) / Y_unshaded × 100
```

**Where:**

- `Y_shaded`: Yield under agri-PV panels (reduced ET demand, lower leaf temperature)
- `Y_unshaded`: Yield in open field (full solar exposure, higher heat stress)
- `net_yield_effect_pct`: Net yield change from shading, per crop and PV density (from data file)
- `par_reduction_pct`: Reduction in photosynthetically active radiation (from data file)
- `heat_stress_threshold_C`: Per-crop temperature threshold (from data file)

**Parameters needed (per crop × PV density):**

- Temperature reduction under panels (°C): typically 1.5–4.5°C depending on density
- ET reduction (%): typically 5–30% depending on density
- PAR reduction (%): 15–50% depending on density
- Net yield effect (%): can be positive (shade benefit > light loss) in hot climates
- Heat stress threshold (°C): crop-specific, typically 30–35°C

**Dependencies:**

- Configuration:`energy_system.pv.density`,`energy_system.pv.height_m`
- Precomputed data: daily maximum temperatures from weather data
- Parameter file:`data/parameters/crops/microclimate_yield_effects-research.csv` (to be created)

**Sources:**

- Dupraz et al. (2011) — Land Equivalent Ratio under agri-PV
- Barron-Gafford et al. (2019) — Agrivoltaics provide mutual benefits across the food-energy-water nexus in a hot arid climate
- Marrou et al. (2013) — Productivity and radiation use efficiency of lettuces grown under agrivoltaic systems
- Weselek et al. (2019) — Review of agri-PV effects on crop production

## 5. Economic Calculations

### Infrastructure Financing Costs

**Purpose:** Calculate annual costs to community for infrastructure based on financing category

**Formula:**

```
Annual_cost = CAPEX_component + OPEX_component

CAPEX_component = 
  if has_debt_service:
    Monthly_payment × 12
  else if capex_cost_multiplier > 0:
    (capital_cost × capex_cost_multiplier) / depreciation_years
  else:
    0

OPEX_component = annual_om_cost × opex_cost_multiplier

Monthly_payment = P × [r(1 + r)^n] / [(1 + r)^n - 1]
  where P = capital_cost, r = monthly interest rate, n = months
```

**Parameters by Financing Category:**

| Category          | CAPEX Mult. | Debt? | Term (yrs) | Rate  | OPEX Mult. |
| ----------------- | ----------- | ----- | ---------- | ----- | ---------- |
| existing_owned    | 0.0         | No    | 0          | 0.000 | 1.0        |
| grant_full        | 0.0         | No    | 0          | 0.000 | 0.0        |
| grant_capex       | 0.0         | No    | 0          | 0.000 | 1.0        |
| purchased_cash    | 1.0         | No    | 0          | 0.000 | 1.0        |
| loan_standard     | 0.0         | Yes   | 10         | 0.060 | 1.0        |
| loan_concessional | 0.0         | Yes   | 15         | 0.035 | 1.0        |

**Output:** Annual cost in USD per infrastructure subsystem

**Dependencies:**

- Configuration:`[system].[subsystem].financing_status`
- Parameter file:`data/parameters/economic/financing_profiles.csv`
- Capital costs: From equipment parameter files or capital_costs.csv
- O&M costs: From operating_costs.csv

### Equipment Replacement Costs

**Purpose:** Account for mid-simulation replacement of components with shorter lifespans than the simulation horizon. Critical for any simulation longer than ~5 years.

**Component lifespans and replacement costs:**

| Component | Typical Lifespan | Replacement Cost (% of original CAPEX) | Replacements in 15-yr Sim |
| --------- | ---------------- | --------------------------------------- | ------------------------- |
| RO membranes | 5-7 years | 30-40% | 2-3 |
| Pumps (submersible) | 10-15 years | 60-80% | 0-1 |
| Drip emitters/lines | 5-10 years | 20-30% of irrigation CAPEX | 1-2 |
| Battery pack | 10-15 years | 50-70% (declining with technology cost curves) | 0-1 |
| PV panels | 25-30 years | N/A (outlasts simulation) | 0 |
| PV inverters | 10-15 years | 15-20% of PV CAPEX | 0-1 |
| Wind turbines | 20-25 years | N/A (outlasts simulation) | 0 |

**Formula:**

```
Replacement_cost(year) = Σ replacement_cost_i   for each component i due for replacement in that year

Annual_replacement_reserve = Σ (replacement_cost_i / lifespan_i)   across all components
                           (sinking fund approach — smooth annual provision)
```

**Sinking fund approach (recommended for planning):**

Rather than modeling lumpy replacement events, provision an annual reserve fund:

```
Annual_reserve_i = replacement_cost_i / lifespan_years_i
Total_annual_reserve = Σ Annual_reserve_i
```

This provides a realistic annual cost that smooths replacement shocks and should be included in Total Operating Expense.

**Dependencies:**

- Parameter file: `data/parameters/economic/equipment_lifespans.csv` (to be created)
- Capital costs from equipment parameter files
- Replacement cost ratios by component type

**Notes:**

- RO membrane replacement is the most frequent and impactful — at 30-40% of BWRO CAPEX every 5-7 years, it can equal or exceed annual O&M costs
- Battery replacement cost is declining ~8-10%/yr with technology improvements; use year-of-replacement projected cost for accuracy
- For MVP: Use the sinking fund approach as a fixed annual cost adder; for later phases, model discrete replacement events

**Sources:**

- Standard financial amortization formulas
- Typical commercial loan rates: 5-7% annual
- Typical concessional loans (development banks): 2-4% annual
- Equipment depreciation: 10-20 years typical
- RO membrane replacement: Voutchkov (2018); typical BWRO plant operating data
- Battery replacement: BloombergNEF Lithium-Ion Battery Price Survey (annual)

### Water Cost Calculation

**Purpose:** Calculate daily water costs based on source and pricing regime

**Groundwater Cost (full system):**

```
Cost_gw [USD/day] = (E_pump [kWh/m3] + E_convey [kWh/m3] + E_treatment [kWh/m3])
                  × electricity_price [USD/kWh] × volume_m3 [m3]
                  + O&M_cost [USD/day]
```

**Municipal Water Cost:**

```
Cost_municipal [USD/day] = volume_m3 [m3] × price_per_m3 [USD/m3] (tier, regime)
```

**Parameters:**

- `electricity_price [USD/kWh]`: Grid electricity price from pricing data
- `price_per_m3 [USD/m3]`: Municipal water price from configuration (resolved by consumer type)
- O&M costs [USD/day] from parameter files

**Output:** Daily water cost in USD

**Dependencies:**

- Configuration: `water_pricing.municipal_source`
- Configuration: `water_pricing.agricultural.pricing_regime` [subsidized, unsubsidized] (for farm water demands)
- Configuration: `water_pricing.domestic.pricing_regime` [subsidized, unsubsidized] (for household/facility water demands)
- Price data: `data/prices/electricity/historical_grid_electricity_prices-research.csv`
- Price data: `data/prices/water/municipal_water_prices-research.csv`

**Note:** Water pricing uses dual agricultural/domestic regimes configured independently. The simulation resolves the applicable regime based on consumer type before passing the price to the water policy. See `structure.md` Pricing Configuration for the canonical schema.

**Sources:**

- Egyptian HCWW tiered water pricing (see`docs/research/egyptian_water_pricing.md`)
- Desalination cost studies for Egypt (Ettouney & Wilf, 2009)

### Tiered Municipal Water Pricing

**Purpose:** Calculate municipal water costs under Egyptian-style progressive bracket pricing, where the per-unit price increases with cumulative monthly consumption

> **MVP implementation note:** This feature is fully implemented in `data_loader.py` (`calculate_tiered_cost`, `get_marginal_tier_price`) but not yet documented in the original calculations spec. The implementation follows the Egyptian HCWW (Holding Company for Water and Wastewater) tiered pricing structure.

**Methodology:**

Each unit of consumption is charged at the rate for the bracket it falls into, based on cumulative monthly consumption:

```
For each consumption event within a billing period:
  1. Determine current position = cumulative_consumption
  2. For each tier bracket [min_units, max_units, price_per_unit]:
     - Calculate units falling in this bracket
     - Add units × price_per_unit to total cost
  3. Apply wastewater surcharge if configured:
     total_cost += total_cost × (wastewater_surcharge_pct / 100)
```

**Key functions:**

- `calculate_tiered_cost(consumption, cumulative_consumption, tier_config)` — Returns total cost, effective average cost per unit, tier breakdown, and marginal tier number
- `get_marginal_tier_price(cumulative_consumption, tier_config)` — Returns the price for the *next* unit of consumption. Used by water allocation policies for cost comparison decisions (e.g., `cheapest_source` comparing GW cost vs marginal municipal cost)

**Example (Egyptian-style tiers):**

```
Tier 1:  0-10 m³/month  → 0.65 EGP/m³
Tier 2: 11-20 m³/month  → 1.60 EGP/m³
Tier 3: 21-40 m³/month  → 2.75 EGP/m³
Tier 4:   >40 m³/month  → 4.50 EGP/m³

If cumulative = 8 m³ and new consumption = 5 m³:
  - 2 m³ at Tier 1 (0.65) = 1.30 EGP
  - 3 m³ at Tier 2 (1.60) = 4.80 EGP
  - Total: 6.10 EGP, effective rate: 1.22 EGP/m³
  - Marginal tier: 2
```

**Wastewater surcharge:** An additional percentage surcharge applied to the total water cost, representing wastewater treatment fees collected by HCWW alongside water tariffs.

**Dependencies:**

- Configuration: `water_pricing.agricultural.subsidized.tier_pricing` or `water_pricing.domestic.subsidized.tier_pricing` (bracket definitions, per consumer type)
- Configuration: `water_pricing.[agricultural|domestic].subsidized.tier_pricing.wastewater_surcharge_pct`

**Sources:**

- Egyptian HCWW official tariff schedules (see`docs/research/egyptian_water_pricing.md`)

### Crop Revenue Calculation

**Purpose:** Calculate revenue from crop sales across all product types

**Fresh Crop Revenue:**

```
Fresh_revenue [USD] = fresh_yield_kg [kg] × fresh_price_per_kg [USD/kg] × (1 - loss_rate)
```

Where `loss_rate` = 0.10 (10% default; see Post-Harvest Losses in Section 4) and `fresh_yield_kg` is the fresh fraction of the harvest after the food processing policy split.

**Total Crop Revenue (unified formula across all product types):**

```
Total_revenue [USD] = Σ (product_kg(product_type) × price_per_kg(product_type))
```

Where `product_type` is one of [fresh, packaged, canned, dried], and `product_kg` is the output quantity AFTER weight loss from processing (see Processed Product Output in Section 4). This avoids double counting: the food processing policy splits the raw harvest into fractions, each fraction undergoes weight loss during processing, and the resulting product weight is multiplied by the product-type-specific price.

**Parameters:**

- `fresh_yield_kg [kg]`: Fresh fraction of harvest from food processing policy
- `product_kg [kg]`: Output kg per product type after processing weight loss
- `price_per_kg [USD/kg]`: Per-product-type price from historical price data
- `loss_rate`: Post-harvest losses = 0.10 (10% default for fresh produce; 0.04 for processed)

**Output:** Revenue in USD per crop per season (fresh and processed combined)

**Dependencies:**

- Price data: `data/prices/crops/historical_crop_prices-research.csv` (fresh prices)
- Processing data: `data/prices/crops/historical_processed_crop_prices-research.csv` (processed prices)
- Processing specs: `data/parameters/crops/processing_specs-toy.csv` (weight loss, value multipliers)

**Assumptions:**

- For MVP: No inventory or storage costs
- Future: Add processing costs, storage costs, market timing strategies

### Debt Service Calculation

**Purpose:** Calculate monthly loan payments

> **MVP simplification:** Debt service is fixed monthly payments per financing profile. No accelerated repayment or debt pay-down policies in MVP.

**Formula (fixed-rate amortization):**

```
Payment = P × [r(1 + r)^n] / [(1 + r)^n - 1]
```

**Parameters:**

- P: Principal amount
- r: Monthly interest rate = annual_rate / 12
- n: Number of payments = term_years × 12

**Output:** Monthly payment in USD

**Dependencies:**

- Configuration: `[system].[subsystem].financing_status` — per-subsystem financing category (determines whether debt service applies)
- Parameter file: `data/parameters/economic/financing_profiles.csv` — contains principal amounts, loan terms, and interest rates per financing profile

> **MVP simplification:** Debt service is fixed monthly payments per financing profile. No accelerated repayment or debt pay-down policies in MVP. There is no single `economics.debt` configuration — debt parameters are resolved per subsystem from `financing_status` and `financing_profiles.csv`.

### Diesel Fuel Cost

**Purpose:** Calculate cost of diesel fuel for backup generator operation

**Formula:**

```
Diesel_cost(t) = Fuel(t) × diesel_price_per_L(t)
Diesel_cost_yr = Σ Diesel_cost(t)
Diesel_cost_per_kwh = Diesel_cost_yr / Generator_output_yr
```

**Dependencies:**

- Fuel consumption from backup generator calculation (Section 3)
- Price data:`data/prices/diesel/historical_diesel_prices-research.csv`

**Output:** $/yr total; $/L effective price; $/kWh marginal generation cost

### Fertilizer and Input Cost

> **Status: TBD** — Input cost model and data sources not yet defined.

**Purpose:** Calculate cost of agricultural inputs (fertilizer, seed, chemicals) per hectare

**Conceptual formula:**

```
Input_cost_ha = fertilizer_cost_ha + seed_cost_ha + chemical_cost_ha
Input_cost_total = Σ (Input_cost_ha × farm_area_ha)  across all farms
```

**Missing parameters:**

- Per-crop fertilizer requirements (kg/ha by nutrient: N, P, K)
- Fertilizer prices ($/kg by type)
- Seed costs per hectare per crop
- Pesticide/herbicide costs per hectare per crop

**Notes:**

- For MVP, may use a flat per-hectare input cost rate from literature
- Future: Itemized input tracking with seasonal price variation

### Processed Product Revenue

**Purpose:** Calculate revenue from processed crop products

**Formula:**

```
Processed_revenue = Σ (processed_output_kg × processed_price_per_kg)  by product type

processed_price_per_kg = fresh_price_per_kg × value_add_multiplier
```

**Where:**

- `processed_output_kg`: From processed product output calculation (Section 4)
- `fresh_price_per_kg`: From historical crop price data
- `value_add_multiplier`: From`data/parameters/crops/processing_specs-toy.csv`

**Dependencies:**

- Processed product output (see Crop section)
- Price data:`data/prices/crops/historical_crop_prices-research.csv` (base fresh prices)
- Price data:`data/prices/crops/historical_processed_crop_prices-research.csv` (or derived from value_add_multiplier)
- Parameter file:`data/parameters/crops/processing_specs-toy.csv`

**Notes:**

- Processed products command higher per-kg prices but have lower yield-to-product weight ratios
- Net revenue effect:`value_add_multiplier × (1 - weight_loss_pct/100)` relative to selling fresh
  - Packaged: 1.25 × 0.97 = 1.21× (21% more revenue per kg harvested)
  - Canned: 1.80 × 0.85 = 1.53× (53% more revenue)
  - Dried: 3.50 × 0.12 = 0.42× for tomato (58%*less* revenue per kg harvested, but much longer shelf life)
- Revenue timing differs from fresh sales (processed products can be stored and sold strategically)

### Grid Electricity Export Revenue

**Purpose:** Calculate revenue from selling surplus electricity to the grid

**Formula:**

```
Export_revenue_yr = Σ Grid_export(t) × export_price(t) × Δt  [$/yr]
```

**Dependencies:**

- Grid export volume from energy dispatch (Section 3)
- Export price: may differ from import price (feed-in tariff or wholesale rate)
- Configuration: whether grid export is enabled

**Notes:**

- Export may not be available in all scenarios (depends on grid connection and regulatory regime)
- Egyptian net metering policies are evolving; export price is often below retail import price

### Total Gross Revenue

**Purpose:** Aggregate all revenue streams

**Formula:**

```
Total_gross_revenue = Fresh_crop_revenue + Processed_product_revenue + Grid_export_revenue
```

**Output:** $/yr

### Total Operating Expense

**Purpose:** Aggregate all operating costs

**Formula:**

```
Total_opex = Infrastructure_OM + Debt_service + Equipment_replacement_reserve
           + Labor_costs + Input_costs + Water_costs + Energy_costs + Diesel_costs

Infrastructure_OM = Σ OPEX_component  across all subsystems (water, energy, processing)
Equipment_replacement_reserve = Σ Annual_reserve_i  (see Equipment Replacement Costs)
```

**Output:** $/yr

**Notes:**

- Water and energy costs that are internally produced (groundwater, renewables) include only O&M and debt service — not market price
- Purchased water (municipal) and purchased energy (grid) are at market price

### Operating Margin

**Purpose:** Measure profitability as a fraction of revenue

**Formula:**

```
Operating_margin_pct = ((Total_gross_revenue - Total_opex) / Total_gross_revenue) × 100
```

**Output:** Percentage (can be negative if costs exceed revenue)

### Cost Volatility

**Purpose:** Measure month-to-month variability in operating costs as a resilience indicator

**Formula:**

```
CV = σ(monthly_opex) / μ(monthly_opex)
```

**Where:**

- σ: Standard deviation of monthly operating expenses over the year
- μ: Mean monthly operating expense over the year

**Output:** Coefficient of variation (dimensionless, lower = more stable)

**Notes:**

- This is a*(resilience)* metric
- High CV indicates unpredictable cost structure, making budgeting difficult
- Infrastructure ownership typically reduces CV by converting variable energy/water costs into fixed debt service + O&M

### Revenue Concentration

**Purpose:** Measure how dependent the farm's revenue is on a single dominant crop. High concentration indicates vulnerability to price or yield shocks for that crop.

**Formula:**

```
Revenue_concentration_pct = (max(crop_revenue_i) / Σ crop_revenue_i) × 100
```

**Output:** Percentage (0–100%). Lower values indicate more diversified revenue.

**Notes:**

- This is a *(resilience)* metric — complements the Crop Diversity Index (Section 4) which measures area-based diversity
- Implemented in `src/simulation/metrics.py` as `compute_revenue_concentration()`
- Also reports `dominant_crop`: the crop name with the highest revenue
- 100% concentration = monoculture revenue; for 5 equal crops, minimum concentration = 20%

### Net Farm Income

**Purpose:** Calculate bottom-line profitability

**Formula:**

```
Net_income = Total_gross_revenue - Total_opex
```

**Per-farm variant:**

```
Net_income_farm_i = Revenue_farm_i - (allocated_opex_farm_i)
```

**Output:** $/yr (can be negative)

**Notes:**

- Cost allocation to individual farms depends on the community cost-sharing policy (e.g., proportional to area, equal split, usage-based)
- Community-level net income = sum of all farm net incomes

### Payback Period

**Purpose:** Time required for cumulative net cash flow to recover infrastructure investment

**Formula:**

```
Payback_years = min(t) such that Σ(Net_income(y), y=1..t) ≥ Total_CAPEX
```

**Simplified (uniform income):**

```
Payback_years ≈ Total_CAPEX / avg_annual_net_income
```

**Output:** Years (fractional)

**Notes:**

- Only meaningful for scenarios with significant capital investment
- For grant-funded infrastructure, payback is effectively zero

### Return on Investment

**Purpose:** Annualized return relative to total investment

**Formula (simple ROI):**

```
ROI_pct = (avg_annual_net_income / Total_CAPEX) × 100
```

**Output:** Percentage per year

**Limitation:** Simple ROI does not account for the time value of money — a project returning $100K/year starting in year 1 scores identically to one starting in year 5. Use IRR (below) for time-sensitive investment comparison.

### Internal Rate of Return (IRR)

**Purpose:** The discount rate at which the net present value of all cash flows equals zero — provides a single rate-of-return metric that accounts for the timing of cash flows

**Formula:**

```
0 = -Initial_CAPEX + Σ (Net_income(t) / (1 + IRR)^t)  for t = 1 to N
```

Solved numerically (no closed-form solution). Standard implementation uses Newton-Raphson or bisection method.

**Interpretation:**

- IRR > discount_rate → Project creates value (NPV > 0)
- IRR < discount_rate → Project destroys value (NPV < 0)
- IRR = discount_rate → Breakeven (NPV = 0)
- Typical thresholds: IRR > 8-12% for commercial viability in developing economies; lower thresholds (5-8%) acceptable for community/development projects

**Output:** Percentage (annualized)

**Notes:**

- IRR may not exist or may have multiple solutions if cash flows change sign more than once (e.g., major replacement cost in mid-simulation). In such cases, use Modified IRR (MIRR) or rely on NPV
- For grant-funded projects with zero CAPEX, IRR is undefined (infinite return on zero investment) — use NPV and ROI instead
- IRR and NPV should always be reported together; IRR provides intuitive comparison across project sizes while NPV gives absolute value

### Net Present Value

**Purpose:** Discounted value of all future cash flows from community operations

**Formula:**

```
NPV = Σ (Net_income(t) / (1 + r)^t)  for t = 1 to N
     - Initial_CAPEX
```

**Parameters:**

- `r`: Discount rate (from config:`economics.discount_rate`)
- `N`: Number of simulation years
- `Net_income(t)`: Net income in year t

**Output:** NPV in USD (positive = value-creating investment)

### Inflation and Real vs Nominal Values

**Purpose:** Ensure economic projections over multi-year simulations are not distorted by ignoring the time-value of money in prices and costs

**Approach:** The simulation should operate in one of two consistent frameworks:

**Option A — Real (constant-year) terms (recommended for MVP):**

All prices, costs, and revenues are held constant at base-year values. The discount rate used in NPV must be a *real* discount rate (net of inflation):

```
r_real = (1 + r_nominal) / (1 + inflation_rate) - 1
```

Approximate: `r_real ≈ r_nominal - inflation_rate`

This is the simpler approach and is appropriate when the goal is to compare infrastructure configurations rather than forecast nominal cash flows.

**Option B — Nominal terms (future implementation):**

Prices and costs escalate annually at category-specific rates:

```
Price(year) = Price_base × (1 + escalation_rate) ^ year
```

Typical escalation rates for Egypt:

- General inflation: 5-15%/yr (historically volatile; 10-30% in 2022-2024)
- Electricity tariffs: May increase faster than general inflation due to subsidy reform
- Diesel prices: Tied to global oil markets plus subsidy removal
- Agricultural input costs: Roughly track general inflation
- Crop prices: May lag or lead inflation depending on market dynamics
- Labor costs: Roughly track inflation in the medium term

With nominal prices, use the nominal discount rate for NPV.

**Current assumption:** The model uses **real (constant-year) terms**. All prices in data files are base-year values and are not escalated. The discount rate in `economics.discount_rate` should be interpreted as a real rate (typically 3-8% for infrastructure projects in developing economies, vs 8-15% nominal).

**Parameters:**

- Configuration: `economics.discount_rate` — must be real rate if using Option A
- Configuration (future): `economics.inflation_rate`, per-category escalation rates

**Notes:**

- Failing to specify real-vs-nominal is one of the most common errors in long-range infrastructure planning models — it can distort NPV by 30-50% over a 15-year horizon
- Even in real terms, *relative* price changes matter (e.g., electricity prices rising faster than crop prices) — these can be modeled as real escalation differentials without full nominal modeling

### Debt-to-Revenue Ratio

**Purpose:** Measure financial leverage relative to income

**Formula:**

```
Debt_to_revenue = Total_annual_debt_service / Total_gross_revenue
```

**Output:** Ratio (dimensionless). Values > 0.30 typically indicate high financial stress.

### Cash Reserves

**Purpose:** Track community bank balance over time

**Formula:**

```
Cash(t+1) = Cash(t) + Revenue(t) - Expenses(t)
Cash(0) = Σ starting_capital_usd  across all farms
```

**Output:** USD balance at end of each period

**Notes:**

- Insolvency occurs when Cash(t) < 0
- Used as input to Monte Carlo survivability analysis

### Cash Reserve Adequacy

**Purpose:** Measure how many months of expenses the community can cover from reserves

**Formula:**

```
Adequacy_months = Cash_reserves / avg_monthly_opex
```

**Output:** Months of runway

**Notes:**

- This is a*(resilience)* metric
- Values < 3 months indicate high vulnerability to income disruption
- Values > 12 months indicate strong financial buffer

## 6. Food Processing Calculations

### Processing Capacity

**Purpose:** Calculate daily processing throughput

**Formula:**

```
Capacity = Σ(equipment_capacity_i × fraction_i × availability)
```

**Parameters:**

- equipment_capacity_i: From equipment parameter files
- fraction_i: Equipment mix fraction (from config)
- availability: Equipment uptime = 0.90 (90%)

**Output:** Daily processing capacity in kg/day

**Dependencies:**

- Configuration:`food_processing_system.[type].equipment`
- Parameter file:`data/parameters/processing/food_processing_equipment-toy.csv`

### Processing Energy Requirements

**Purpose:** Calculate energy needed for food processing operations

**Energy by Processing Type:**

- Fresh packaging: 0.05-0.10 kWh/kg (washing, sorting, packaging)
- Drying: 0.5-2.0 kWh/kg (depends on solar vs electric dryer)
- Canning: 0.3-0.5 kWh/kg (retort processing)
- Packaging: 0.02-0.05 kWh/kg (vacuum sealing, labeling)

**Dependencies:**

- Parameter file:`data/parameters/processing/food_processing_equipment-toy.csv`
- Configuration:`food_processing_system.[type].equipment`

**Sources:**

- Industrial food processing energy benchmarks
- Solar dryer performance studies for arid climates

## 7. Labor Calculations

> **Status: Implemented** — `src/settings/calculations.py:calculate_labor_requirements()` (lines 805–869) and `compute_peak_labor_demand()` (lines 872+). Labor metrics are computed in `src/simulation/metrics.py` (lines 690–731). Uses simplified per-hectare and per-unit estimates; not yet growth-stage-sensitive.

### Total Employment

**Purpose:** Calculate total person-hours of labor required per year

**Formula (as implemented):**

```
Total_labor_hrs = Field_labor + Processing_labor + Maintenance_labor + Admin_labor
```

**Field labor (crop-specific):**

```
Field_labor = Σ (base_hrs_per_ha × crop_multiplier × crop_area_ha)  for each crop on each farm
```

| Parameter | Value | Source |
|---|---|---|
| base_hrs_per_ha | 200 hrs/ha/yr | FAO estimates for irrigated agriculture |
| tomato multiplier | 1.3 | High-labor crop (staking, pruning, multiple harvests) |
| potato multiplier | 0.9 | Mechanizable harvest |
| onion multiplier | 1.0 | Baseline |
| kale multiplier | 1.1 | Multiple harvests |
| cucumber multiplier | 1.2 | Trellising and frequent picking |

**Processing labor:**

```
Processing_labor = processed_output_kg × 0.02 hrs/kg
```

**Maintenance labor (per infrastructure unit):**

| Infrastructure | Hours/yr | Notes |
|---|---|---|
| PV (per 100 kW) | 40 | Panel cleaning, inverter checks |
| Wind (per 100 kW) | 60 | Mechanical inspection |
| BWRO (per unit) | 200 | Membrane maintenance, chemical dosing |
| Wells (per well) | 80 | Pump service, water quality |
| Battery (per unit) | 20 | Monitoring, connections |
| Generator (total) | 100 | Oil changes, testing |

**Administrative overhead:**

```
Admin_labor = 0.05 × (Field_labor + Processing_labor + Maintenance_labor)
```

**FTE and cost:**

```
FTE = Total_labor_hrs / 2,240 hrs/yr  (8 hrs/day × 280 days/yr)
Labor_cost = Total_labor_hrs × $3.50/hr  (Egyptian agricultural rate)
```

**Output:** Dict with field_labor_hrs, processing_labor_hrs, maintenance_labor_hrs, admin_labor_hrs, total_labor_hrs, fte_count, labor_cost_usd

**Dependencies:**

- Configuration: `scenario.farms` (area, crops)
- Configuration: `scenario.infrastructure` (PV, wind, wells, BWRO, battery, generator capacities)
- Simulation output: `processed_output_kg` (for processing labor)

### Peak Labor Demand

> **Status: Implemented** — `src/settings/calculations.py:compute_peak_labor_demand()`. Uses a 3x harvest multiplier for months with non-zero yield.

**Purpose:** Identify months with highest labor requirements for workforce planning

**Formula:**

```
monthly_base = field_labor_hrs / 12
For each month:
  If harvest occurs (total_yield_kg > 0): monthly_labor = monthly_base × 3.0
  Else: monthly_labor = monthly_base

Peak_labor_month = max(monthly_labor)  across all months
```

**Notes:**

- Harvest months receive a 3× labor multiplier (reflects intensive picking, transport, and processing)
- Multiple crops with staggered planting dates smooth peak demand
- Uses `monthly_metrics` from the simulation to identify harvest months

### Community vs External Labor

> **Status: Not yet implemented** — Tracked as a metric category in `structure.md` but no calculation exists.

**Purpose:** Measure local employment benefit

**Conceptual formula:**

```
Community_labor_ratio = community_labor_hrs / total_labor_hrs × 100
```

**Missing parameters:**

- Community available labor supply (working-age population × available hours)
- Skill requirements vs community skill profile

### Jobs Supported

**Purpose:** Convert total labor hours to full-time equivalent positions

**Formula (as implemented):**

```
FTE = Total_labor_hrs / 2,240
```

Where 2,240 = 8 hours/day × 280 working days/year.

**Output:** FTE count per year

**Not yet implemented:**

- Transport labor (trips, loading time, travel time to market)
- Growth-stage-specific field labor (e.g., higher labor during planting and harvest weeks vs maintenance weeks)
- Seasonal labor demand curves (currently uses annual totals divided by 12 with a harvest multiplier)

## 8. Resilience and Monte Carlo Calculations

> **Status: Implemented** — `src/simulation/monte_carlo.py` provides a full Monte Carlo runner. `src/simulation/sensitivity.py` provides one-at-a-time sensitivity analysis. Both use the simulation engine and metrics pipeline. Some resilience metrics (Gini, maximum drawdown, crop failure probability) are defined conceptually below but not yet computed.

### Monte Carlo Simulation Framework

> **Implemented:** `src/simulation/monte_carlo.py:run_monte_carlo()`. Supports configurable N runs, random seed, and per-parameter coefficient of variation overrides. CLI: `python -m src.simulation.monte_carlo <scenario.yaml> [n_runs]`

**Purpose:** Evaluate community survivability under stochastic conditions by running many simulation instances with randomized parameters

**Algorithm (as implemented):**

```
For run = 1 to N_runs:
  1. Sample price multipliers from N(1.0, CV) for each parameter, floored at 0.5
  2. Sample yield_factor from N(base, base × CV) per farm, floored at 0.1
  3. Deep-copy scenario, apply sampled yield factors
  4. Create SimulationDataLoader with sampled price_multipliers
  5. Run full simulation: run_simulation(scenario, data_loader)
  6. Compute all metrics: compute_all_metrics(state, data_loader, scenario)
  7. Extract outcomes: total revenue, yield, water cost, net income, NPV, cash reserves, self-sufficiency

Aggregate via compute_monte_carlo_summary():
  - Survival rate, income percentiles, NPV percentiles, P(negative income)
```

**Default stochastic parameters (coefficient of variation):**

| Parameter | CV | Notes |
|---|---|---|
| municipal_water | 0.15 | ±15% water price volatility |
| electricity | 0.20 | ±20% electricity price volatility |
| diesel | 0.25 | ±25% diesel price volatility (global oil) |
| fertilizer | 0.15 | ±15% fertilizer cost volatility |
| crop_tomato | 0.25 | ±25% crop price volatility |
| crop_potato | 0.20 | |
| crop_onion | 0.20 | |
| crop_kale | 0.15 | |
| crop_cucumber | 0.25 | |
| yield_factor | 0.10 | ±10% yield variation (weather, pests) |

**Sampling method:** Normal distribution with mean 1.0 and standard deviation = CV. Multipliers floored at 0.5 to prevent unrealistically low values. Yield factors floored at 0.1.

**Output from `compute_monte_carlo_summary()`:**

- `n_runs`: Number of runs executed
- `survival_rate_pct`: % of runs with final cash reserves >= 0
- `probability_of_negative_income_pct`: % of runs with negative average annual income
- `avg_net_income_usd`, `std_net_income_usd`: Mean and std of annual net income across runs
- `worst_case_income_usd`: 5th percentile annual income
- `net_income_percentiles`: {p5, p25, p50, p75, p95}
- `npv_percentiles`: {p5, p25, p50, p75, p95}
- `elapsed_seconds`: Total computation time

**Not yet implemented:**

- Weather scenario variation (currently all runs use the same weather time-series; price and yield are varied)
- Equipment failure events (random outage days)
- Correlation structure between parameters (all sampled independently)
- Convergence testing (no automatic check for statistical stability)

### Survival Rate

**Formula:**

```
Survival_rate = count(runs where Cash(t) ≥ 0 for all t) / N_runs × 100
```

### Probability of Crop Failure

**Formula:**

```
P_crop_failure = count(runs with at least one season where yield_loss > 50%) / N_runs × 100
```

### Probability of Insolvency

**Formula:**

```
P_insolvency = count(runs where Cash(t) < 0 for any t) / N_runs × 100
P_insolvency = 100 - Survival_rate
```

### Median Years to Insolvency

**Formula:**

```
Among runs where insolvency occurs:
  Years_to_insolvency(run) = min(t) such that Cash(t) < 0
  Median_years = median(Years_to_insolvency)
```

### Worst-Case Net Income

**Formula:**

```
Worst_case_income = percentile_5(annual_net_income)  across all runs
```

### Net Income Distribution

**Formula:**

```
Income_percentiles = percentile([5, 25, 50, 75, 95], annual_net_income)  across all runs
```

### Income Inequality (Gini Coefficient)

**Purpose:** Measure spread of outcomes across farms within a single run

**Formula:**

```
Gini = (Σ_i Σ_j |income_i - income_j|) / (2 × n² × μ_income)
```

**Where:**

- n: Number of farms
- income_i: Net income of farm i
- μ_income: Mean farm income

**Output:** Gini coefficient (0 = perfect equality, 1 = maximum inequality)

### Maximum Drawdown

**Formula:**

```
Drawdown = max(Peak_cash - Trough_cash)  over all peak-to-trough sequences
```

**Where:**

- Peak: Local maximum of cumulative cash reserves
- Trough: Subsequent local minimum before cash exceeds previous peak

### Sensitivity Analysis

> **Status: Implemented** — `src/simulation/sensitivity.py:run_sensitivity_analysis()`. One-at-a-time price perturbation of 10 parameters at ±20%. Full tornado charts are generated in `results.py` plotting. Breakeven thresholds are future work.

**Purpose:** Identify which input prices have the greatest impact on net farm income

**Algorithm (as implemented):**

```
1. Run base case simulation (no perturbation) → base_income
2. For each parameter P in [10 parameters]:
   a. Run simulation with P × 0.80 → low_income
   b. Run simulation with P × 1.20 → high_income
   c. Record: low_delta = low_income - base_income
              high_delta = high_income - base_income
              total_swing = |high_delta| + |low_delta|
3. Rank parameters by total_swing
```

**Parameters tested:**

| Parameter | Label |
|-----------|-------|
| `municipal_water` | Municipal Water Price |
| `electricity` | Grid Electricity Price |
| `diesel` | Diesel Fuel Price |
| `fertilizer` | Fertilizer Cost |
| `labor` | Labor Cost |
| `crop_tomato` | Tomato Price |
| `crop_potato` | Potato Price |
| `crop_onion` | Onion Price |
| `crop_kale` | Kale Price |
| `crop_cucumber` | Cucumber Price |

**Output:** Dict with `base_income` and per-parameter `{label, low_income, high_income, low_delta, high_delta, total_swing}`. Results visualized as a tornado chart (Plot 6 in Section 5 of `structure.md`).

**Implementation detail:** Price perturbation is applied via the `SimulationDataLoader(price_multipliers={param: multiplier})` mechanism, which scales the relevant price series before the simulation consumes them. Each perturbation requires a full simulation run (21 total: 1 base + 2 × 10 parameters).

**Not yet implemented:**

- Breakeven thresholds (binary search for critical parameter values)
- Multi-parameter interaction effects
- Non-price parameter sensitivity (infrastructure sizing, policy selection)
- Monte Carlo-based sensitivity ranking (Sobol indices or similar)

## 9. Units and Conversions

### Water

- Volume: m³ (cubic meters)
- Flow rate: m³/day
- Pressure: Pa (Pascals) or bar
- TDS: ppm (parts per million) or mg/L
- Conversion: 1 m³ = 1,000 liters

### Energy

- Power: kW (kilowatts)
- Energy: kWh (kilowatt-hours)
- Capacity: kWh (battery), kW (generation/load)
- Conversion: 1 kWh = 3.6 MJ

### Agriculture

- Area: ha (hectares)
- Yield: kg/ha or tonnes/ha
- Water use: m³/ha
- Conversion: 1 ha = 10,000 m²

### Currency

- Primary: USD
- Alternative: EGP (Egyptian Pounds)
- Conversion: Use historical exchange rates from data files

## 10. References

### Water and Irrigation

- Allen, R.G., Pereira, L.S., Raes, D., & Smith, M. (1998). Crop evapotranspiration: Guidelines for computing crop water requirements. FAO Irrigation and Drainage Paper 56.
- Ayers, R.S., & Westcot, D.W. (1985). Water quality for agriculture. FAO Irrigation and Drainage Paper 29 Rev.1.
- Doorenbos, J., & Kassam, A.H. (1979). Yield response to water. FAO Irrigation and Drainage Paper 33.
- Maas, E.V., & Hoffman, G.J. (1977). Crop salt tolerance — current assessment. Journal of the Irrigation and Drainage Division, 103(2), 115-134.

### Desalination

- Voutchkov, N. (2018). Energy use for membrane seawater desalination – current status and trends. Desalination, 431, 2-14.
- Ettouney, H., & Wilf, M. (2009). Commercial desalination technologies. In Desalination: Water from Water (pp. 77-144).

### Agri-PV

- Barron-Gafford, G.A., et al. (2019). Agrivoltaics provide mutual benefits across the food-energy-water nexus in drylands. Nature Sustainability, 2, 848-855.
- Dupraz, C., et al. (2011). Combining solar photovoltaic panels and food crops for optimising land use: Towards new agrivoltaic schemes. Renewable Energy, 36(10), 2725-2732.
- Marrou, H., et al. (2013). Productivity and radiation use efficiency of lettuces grown in the partial shade of photovoltaic panels. European Journal of Agronomy, 44, 54-66.
- Weselek, A., et al. (2019). Agrophotovoltaic systems: Applications, challenges, and opportunities. A review. Agronomy for Sustainable Development, 39, 35.

### Energy Systems

- IEC 61400-1: Wind turbines design standards
- IEC 61215: Crystalline silicon terrestrial photovoltaic modules — Design qualification and type approval
- Jordan, D.C., & Kurtz, S.R. (2013). Photovoltaic degradation rates — An analytical review. Progress in Photovoltaics, 21(1), 12-29.
- NREL PVWatts Calculator documentation
- Stull, R.B. (1988). An Introduction to Boundary Layer Meteorology. Kluwer Academic Publishers.
- System Advisor Model (SAM) technical documentation

### Diesel Generators

- Barley, C.D., & Winn, C.B. (1996). Optimal dispatch strategy in remote hybrid power systems. Solar Energy, 58(4-6), 165-179.
- HOMER Energy documentation — Generator fuel curve modeling

### Battery Storage

- BloombergNEF Lithium-Ion Battery Price Survey (annual)
- LFP calendar and cycle aging data from manufacturer datasheets (CATL, BYD)

### Economic Methods

- Standard financial formulas for NPV, IRR, amortization
- Egyptian water pricing: HCWW (Holding Company for Water and Wastewater) official tariffs
