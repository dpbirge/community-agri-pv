# Energy System Calculations

Extracted from the consolidated calculations specification. For other domain calculations see: [calculations_water.md](calculations_water.md), [calculations_crop.md](calculations_crop.md), [calculations_economic.md](calculations_economic.md). For the index, units, references, and resilience/Monte Carlo calculations see: [calculations.md](calculations.md).

## 1. PV Power Generation

**Purpose:** Calculate solar photovoltaic power output under crop cover, accounting for shading and temperature effects

**Formula:**

```
P_pv(t) = sys_capacity_kw × CF_pv(t) × shading_factor × temp_derate(t)
```

> **Simplification:** PV degradation (annual capacity loss) has been removed from the model. Nameplate capacity is used throughout the simulation. For community-scale planning horizons (5-15 years), the ~3-7% cumulative output reduction from panel aging is small relative to other uncertainties (weather variation, price volatility). This avoids tracking `degradation_factor` and `degradation_rate` parameters.

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
- γ: Temperature coefficient of power (from parameter file, default -0.004 /°C)

**Output:** P_pv in kW at each time step

**Dependencies:**

- Precomputed data:`data/precomputed/pv_power/pv_normalized_kwh_per_kw_daily-toy.csv`
- Precomputed data: daily temperature and irradiance from weather data (for temp derating)
- Configuration:`energy_system.pv.sys_capacity_kw`
- Configuration:`energy_system.pv.density`
- Configuration:`energy_system.pv.height_m`

**Sources:**

- Normalized PV output from PVWatts or System Advisor Model (SAM)
- Agri-PV shading effects from Dupraz et al. (2011) and regional studies
- Temperature derating: IEC 61215 standard test conditions; NOCT model from PVWatts documentation

## 2. Wind Power Generation

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

> **Note on hub\_height\_m:** This is **not a user-configurable parameter**. The user selects a wind turbine `type` (small, medium, or large) in the scenario YAML. The `hub_height_m` is then looked up from the wind turbine equipment data file (`data/parameters/equipment/wind_turbines-toy.csv`) based on the selected turbine type. Configuration reference is for documentation purposes only.

**Output:** P_wind in kW at each time step

**Dependencies:**

- Precomputed data:`data/precomputed/wind_power/wind_normalized_kwh_per_kw_daily-toy.csv`
- Configuration:`energy_system.wind.sys_capacity_kw`
- Configuration:`energy_system.wind.hub_height_m`

**Sources:**

- Wind power curve data from manufacturer specifications
- Wind shear profile from IEC 61400-1 wind turbine design standards
- Logarithmic profile: Stull (1988), "An Introduction to Boundary Layer Meteorology"

## 3. Battery Storage Dynamics

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
- SOC_max: Maximum state of charge = 0.95 (95%)

**Output:** SOC (state of charge) at each time step

**Dependencies:**

- Configuration:`energy_system.battery.sys_capacity_kwh`
- Configuration:`energy_system.battery.chemistry`

> **Simplification:** Battery capacity degradation (calendar fade and cycle fade) has been removed from the model. The dual aging model (alpha_cal, alpha_cyc, EFC tracking, end-of-life threshold) added complexity disproportionate to its impact on community-level planning decisions. Battery capacity is treated as fixed at nameplate throughout the simulation. Equipment replacement costs are covered by the flat equipment replacement reserve (see calculations_economic.md § 2).

**Fixed battery parameters (set once at initialization, never change):**

- SOC_min = 0.10 (hardware floor, protects battery longevity)
- SOC_max = 0.95
- η_charge = 0.95 (LFP round-trip charging efficiency)
- η_discharge = 0.95 (LFP round-trip discharging efficiency)
- self_discharge_rate_daily = 0.0005 (0.05%/day for LFP, ~1.5%/month)

**Self-discharge:**

```
SOC_loss_per_day = SOC(t) × self_discharge_rate_daily
```

**Assumptions:**

- Round-trip efficiency: 90% for LFP batteries (0.95 x 0.95)
- Initial SOC: 50% of capacity
- Battery capacity is fixed at nameplate for the entire simulation

## 4. Backup Generator Fuel Consumption

**Purpose:** Calculate diesel fuel consumption for backup power, accounting for load-dependent efficiency

Diesel generators have highly nonlinear fuel consumption — at low loads, specific fuel consumption (L/kWh) increases substantially because a significant fraction of fuel goes to overcoming friction and maintaining idle speed regardless of electrical output.

**Active model: Willans line.** The constant SFC approximation is documented for reference but is not used in the simulation.

**Formula (constant SFC — reference only):**

```
Fuel(t) = P_gen(t) × SFC × Δt
```

This is adequate when the generator consistently runs near rated load (>60%).

**Formula (Willans line model — active):**

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
| --- | --- | --- | --- |
| 100% | 0.25 L/kWh | 0.26 L/kWh | -4% |
| 75% | 0.25 L/kWh | 0.28 L/kWh | -11% |
| 50% | 0.25 L/kWh | 0.32 L/kWh | -22% |
| 25% | 0.25 L/kWh | 0.44 L/kWh | -43% |

At 25% load, the constant SFC model underestimates fuel consumption by ~43%. This matters significantly in hybrid renewable systems where the generator often runs at partial load to cover small deficits.

**Minimum load constraint:**

Most diesel generators should not run below 30% of rated capacity for extended periods (wet stacking, carbon buildup). The dispatch algorithm enforces:

```
# Generator minimum load behavior:
# The generator always starts when there is unmet demand and use_generator=true.
# If demand is below the 30% minimum load threshold, the generator runs at
# minimum load and excess output is curtailed. This wastes some fuel but ensures
# no unmet demand when the community has no grid fallback (microgrid policy).
#
P_gen(t) = 0                                       if deficit == 0 or use_generator == false
P_gen(t) = max(P_rated × min_load_fraction, deficit)   otherwise
generator_curtailed = max(0, P_gen(t) - deficit)
```

Note: The "always start" behavior applies specifically to the `microgrid` policy where grid import is unavailable. Under `renewable_first` or `all_grid` policies, the generator is not dispatched (`use_generator=false`) because grid import serves as the fallback. See simulation_flow.md § 3 (Step 6) and policies.md § 5 for policy-specific dispatch behavior.

**Parameters:**

- P_gen(t): Generator power output at time t (kW)
- P_rated: Generator nameplate capacity (kW)
- a: No-load fuel coefficient (from parameter file, default 0.06 L/kWh)
- b: Incremental fuel coefficient (from parameter file, default 0.20 L/kWh)
- SFC: Specific fuel consumption = 0.25 L/kWh (MVP constant, equivalent to Willans at ~100% load)
- Δt: Time step (hours)
- min_load_fraction: Minimum load = 0.30 (30%)
- `max_runtime_hours`: Maximum daily generator runtime from `energy_system.backup_generator.max_runtime_hours` (default 18; reserves 6h for maintenance/cooling). Generator energy output in a single day cannot exceed `P_rated × max_runtime_hours`.

**Output:** Fuel consumption in liters

**Dependencies:**

- Configuration:`energy_system.backup_generator.capacity_kw`
- Parameter file: `data/parameters/equipment/generators-toy.csv` (diesel generator specs and fuel coefficients; via registry `equipment.generators`)

**Sources:**

- Typical diesel generator SFC: 0.20-0.30 L/kWh at 75% load
- Willans line coefficients: Derived from manufacturer fuel curves; validated in Barley & Winn (1996) and HOMER Energy documentation
- Minimum load recommendations: Generator manufacturer guidelines (Caterpillar, Cummins)

## 5. Energy Dispatch (Load Balance)

> **Status: Implemented** — `src/simulation/simulation.py:dispatch_energy()` (lines 578-751). The dispatch function must consume the boolean flags returned by the energy policy object to determine which sources are available. See `policies.md` Energy Policies for the full policy specifications.

**Purpose:** Determine how generation sources meet demand at each time step, including battery charge/discharge decisions, grid import/export, and curtailment. The dispatch algorithm is parameterized by the energy policy's boolean flags (`use_renewables`, `use_battery`, `grid_import`, `grid_export`, `use_generator`, `sell_renewables_to_grid`).

**PV generation (within dispatch):**

```
pv_kwh [kWh] = sys_capacity_kw × pv_kwh_per_kw(date, density) × shading_factor

shading_factor = {low: 0.95, medium: 0.90, high: 0.85}
```

> **Note:** PV degradation has been removed; nameplate capacity is used throughout. See PV Power Generation section above.

**Total demand (full model, all 7 components):**

```
E_demand(t) [kWh] = E_pump(t) + E_desal(t) + E_convey(t) + E_irrigation_pump(t)
                  + E_processing(t) + E_household(t) + E_community_bldg(t)
```

See Total Energy Demand section below for component descriptions. For water-related energy components (E_pump, E_desal, E_convey, E_irrigation_pump), see [calculations_water.md](calculations_water.md). For processing energy (E_processing), see [calculations_economic.md](calculations_economic.md).

> **Note:** There is no one-day lag for food processing energy. All demands (including E_processing) are known same-day because food processing runs before energy dispatch in the daily simulation loop (see simulation_flow.md).

**Total renewable generation:**

```
E_renewable(t) [kWh] = P_pv(t) [kWh] + P_wind(t) [kWh]
```

**Policy-conditioned dispatch:**

The energy policy returns boolean flags that control the dispatch algorithm. Each policy type produces a different merit order:

**`microgrid`**** policy** — PV -> Wind -> Battery -> Generator (NO grid connection)

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

**`renewable_first`**** policy** — PV -> Wind -> Battery -> Grid import (standard merit order)

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

**`all_grid`**** policy** — Grid import for all demand; renewables exported

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

**Battery SOC update (applies when \****`use_battery=true`**\*\*):**

> **Note:** Dispatch uses kWh values directly (dt is absorbed into the energy values since the simulation uses a daily time step where dt = 1 day and all generation/demand values are already in kWh/day).

```
energy_stored [kWh] = Battery_charge(t) × η_charge
energy_removed [kWh] = Battery_discharge(t) / η_discharge
SOC(t+1) = SOC(t) + (energy_stored - energy_removed) / capacity_kwh
SOC(t+1) = clamp(SOC(t+1), SOC_min, SOC_max)
```

Note: `Battery_discharge(t)` represents energy DELIVERED to the load (after efficiency losses). Dividing by `η_discharge` recovers the larger amount of energy actually removed from the battery's stored charge. This convention is consistent with `simulation_flow.md` dispatch, where `available_discharge` is computed as `stored_energy * η_discharge` (energy at the load).

**Relationship between SOC_min and battery_reserve_pct:**

`SOC_min` (0.10 for LFP) is a HARDWARE constraint protecting battery longevity. `battery_reserve_pct` is a POLICY parameter set by the energy policy (e.g., 0.20 for microgrid). The effective discharge floor used in dispatch is:

```
effective_soc_floor = max(SOC_min, battery_reserve_pct)
```

The policy cannot override the hardware floor. If `battery_reserve_pct < SOC_min`, the hardware floor governs. Validation at scenario load time should warn if `battery_reserve_pct < SOC_min` (configuration error).

**Generator fuel (Willans line, at full rated load for shortest run time):**

```
hours = Generator_kwh [kWh] / P_rated [kW]
fuel_L [L] = (a [L/kWh] × P_rated [kW] + b [L/kWh] × P_rated [kW]) × hours
```

Running at full load is the most fuel-efficient operating point per the Backup Generator Fuel Consumption section above.

**Daily accumulators:** Cumulative PV, wind, grid import, grid export, generator, battery charge/discharge, and curtailment are tracked per year and reset at year boundaries. Daily records are appended to `energy_state.daily_energy_records`.

**Current MVP simplifications:**

- **The grid acts as an infinite backstop** — energy supply never constrains activities. The simulation tracks energy costs but does not restrict operations due to energy shortfalls. Any unmet demand after renewables, battery, and generator is covered by grid import at the applicable price.
- Grid import and export are unlimited (no capacity constraints)
- No time-of-use price optimization -- dispatch is fixed merit-order regardless of TOU pricing

## 6. Total Energy Demand

> **Status: Partially implemented** — Two demand components are aggregated in the simulation loop (`simulation.py` line 1004). Processing energy is not yet included.

**Purpose:** Sum all energy demand components for load balance

**Formula (full model — all 7 demand components):**

```
E_demand(t) [kWh/day] = E_pump(t) + E_desal(t) + E_convey(t)
                      + E_irrigation_pump(t) + E_processing(t)
                      + E_household(t) + E_community_bldg(t)
```

**Where (all units kWh/day):**

- `E_pump(t) [kWh/day]`: Groundwater pumping energy = E_pump [kWh/m3] x groundwater_m3 (see [calculations_water.md](calculations_water.md))
- `E_desal(t) [kWh/day]`: BWRO desalination energy = treatment_kwh_per_m3 x groundwater_m3 (see [calculations_water.md](calculations_water.md))
- `E_convey(t) [kWh/day]`: Water conveyance energy = E_convey [kWh/m3] x total_water_m3 (see [calculations_water.md](calculations_water.md))
- `E_irrigation_pump(t) [kWh/day]`: Pressurization energy for drip irrigation system (see [calculations_water.md](calculations_water.md) Irrigation Pressurization Energy)
- `E_processing(t) [kWh/day]`: Food processing energy = processing_kwh_per_kg x processed_kg (see [calculations_economic.md](calculations_economic.md) Processing Energy Requirements)
- `E_household(t) [kWh/day]`: Household electricity demand (from `calculations.py:calculate_household_demand`)
- `E_community_bldg(t) [kWh/day]`: Community building electricity demand = SUM over building_types:
    (per_m2_kwh_per_day(building_type, date) * configured_area_m2(building_type))
    Building types: office_admin, storage_warehouse, meeting_hall, workshop_maintenance.
    Loaded from precomputed data via registry `community_buildings.energy`, scaled by
    building areas from `community_structure.community_buildings` in settings YAML.

**All 7 components must be included in the dispatch Total\_demand calculation.** The dispatch section (above) references this full formula.

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

## 7. Total Renewable Generation

**Purpose:** Sum all renewable generation for reporting and self-sufficiency calculations

**Formula:**

```
E_renewable(t) = P_pv(t) × Δt + P_wind(t) × Δt
E_renewable_yr = Σ E_renewable(t)  over all time steps in year
```

**Output:** kWh/yr

## 8. Grid Electricity Import and Export

**Purpose:** Track electricity exchanged with the grid

**Formula:**

```
Grid_import_yr = Σ Grid_import(t) × Δt  [kWh/yr]
Grid_export_yr = Σ Grid_export(t) × Δt  [kWh/yr]
```

**Notes:**

- Depends on the energy dispatch algorithm (see above)
- Export is only counted if grid export is enabled in the scenario configuration

## 9. Battery Throughput

**Purpose:** Measure annual battery cycling for reporting and cost tracking

**Formula:**

```
Battery_throughput_yr = Σ (Battery_charge(t) + Battery_discharge(t)) × Δt  [kWh/yr]
Equivalent_full_cycles = Battery_throughput_yr / (2 × capacity_kwh)
```

**Output:** kWh/yr throughput; equivalent full cycle count

**Note on cycle counting:** The denominator `2 × capacity_kwh` counts a full charge *plus* a full discharge as one equivalent cycle (since throughput sums both directions). This is the standard convention used by battery manufacturers for cycle life ratings. Some references count charge and discharge as separate half-cycles — ensure consistency when comparing to manufacturer datasheets.

## 10. Energy Self-Sufficiency

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

## 11. Days Without Grid Electricity

**Purpose:** Count days the community operated entirely off-grid

**Formula:**

```
Days_off_grid = count(days where Grid_import == 0 AND Total_demand > 0)
```

**Output:** Integer count per year

**Notes:**

- This is a*(resilience)* metric
- High values may indicate strong renewable capacity OR grid outage events

## 12. Curtailment

**Purpose:** Quantify excess renewable generation that cannot be used or stored

**Formula:**

```
Curtailment(t) = max(0, Total_generation(t) - Total_demand(t) - Battery_charge(t) - Grid_export(t))
Curtailment_yr = Σ Curtailment(t) × Δt  [kWh/yr]
Curtailment_pct = (Curtailment_yr / E_renewable_yr) × 100
```

**Output:** kWh/yr; percentage of total renewable generation curtailed

## 13. Blended Electricity Cost

**Purpose:** Calculate the weighted average cost of electricity across all sources

**Formula:**

```
Blended_cost = Total_electricity_cost / Total_consumption

Total_electricity_cost = (Grid_import × grid_price)
                       + generator_fuel_L × diesel_price_per_L
                       + (E_renewable_used × LCOE_renewable)
                       - (Grid_export × export_price)

LCOE_renewable = (annual_infrastructure_cost_pv + annual_infrastructure_cost_wind + annual_battery_cost)
               / E_renewable_yr
```

Where `generator_fuel_L` is computed via the Willans line model (see § 4).

**Cash cost vs. economic (blended) cost distinction:**

The simulation tracks two distinct cost measures for electricity:

1. **Cash cost (dispatch cost)** -- The actual out-of-pocket expenditure on a given day. This includes only grid import charges, diesel fuel, and grid export credits. Renewable self-consumption has zero marginal cash cost. This is the cost used in daily accounting (simulation_flow.md Step 7) and in policy cost comparisons.

    ```
    daily_energy_cash_cost = grid_imported * grid_price + generator_fuel_L * diesel_price - grid_exported * export_price
    ```

2. **Economic cost (blended cost)** -- The fully-loaded cost including amortized renewable infrastructure investment (LCOE). This attributes a shadow cost to each kWh of renewable energy consumed, reflecting the capital investment required to produce it. This is used ONLY in economic metrics (NPV, IRR, LCOE reporting) and comparative analysis. It is NOT used in daily operational decisions or cash flow tracking.

    ```
    total_economic_energy_cost = daily_energy_cash_cost + (renewable_used_kwh * LCOE_renewable)
    ```

The LCOE_renewable term is an accounting construct, not a cash outflow. Including it in blended cost enables fair comparison between scenarios with different renewable penetration levels (e.g., comparing a heavily-PV community against a grid-dependent one). Without it, the PV scenario would appear to have near-zero electricity cost, masking the capital investment required.

**Implementation guidance:** The dispatch function returns cash costs only. The blended cost is computed at metrics calculation time (yearly boundary or end of simulation), not during daily dispatch.

**Grid Electricity Pricing Regimes:**

The simulation supports dual electricity pricing regimes — one for agricultural use (water pumping, processing) and one for community use (households, community buildings). Each regime is configured independently in the scenario YAML under `energy_pricing`. See `structure.md` Pricing Configuration for the canonical schema.

1. **Agricultural regime** (`energy_pricing.agricultural.pricing_regime`):
  - `subsidized`: Uses preferential agricultural/irrigation electricity tariffs. Based on Egyptian agricultural rates (~15% discount vs commercial). Data: `historical_grid_electricity_prices-research.csv` (200 pt/kWh Aug 2024). Appropriate for communities with agricultural electricity access.
  - `unsubsidized`: Uses full-cost commercial/industrial tariffs without subsidy. Approximately 16.5% higher than subsidized agricultural rates. Data: `historical_grid_electricity_prices_unsubsidized-research.csv` (233 pt/kWh Aug 2024).

2. **Community regime** (`energy_pricing.community.pricing_regime`):
  - `subsidized`: Flat rate for community electricity (households, community buildings).
  - `unsubsidized`: Full-cost community electricity tariff.

The pricing regime for each consumer type is specified in scenario configuration and determines which price dataset is loaded during simulation initialization. The simulation resolves the applicable price upstream based on consumer type before passing it to energy and water policies.

**Configuration:**

- `energy_pricing.agricultural.pricing_regime`: [subsidized, unsubsidized] — selects which historical price CSV to load
- `energy_pricing.community.pricing_regime`: [subsidized, unsubsidized] — selects which historical price CSV to load
- `energy_pricing.net_metering_ratio`: export price = grid_import_price × this value (default 0.70)

All price values come from historical CSV files, not from the scenario YAML. The `pricing_regime` selector determines which CSV is loaded. No escalation logic is applied — the CSV data already encodes real-world tariff changes over time.

**Dependencies:**

- Price data (subsidized): `data/prices/electricity/historical_grid_electricity_prices-research.csv`
- Price data (unsubsidized): `data/prices/electricity/historical_grid_electricity_prices_unsubsidized-research.csv`
- Configuration: `energy_pricing.agricultural.pricing_regime`, `energy_pricing.community.pricing_regime`

**Output:** $/kWh blended cost

**Notes:**

- Infrastructure costs use the financing cost model (see [calculations_economic.md](calculations_economic.md) Infrastructure Financing Costs)
- LCOE for renewables is an internal accounting cost, not a market price
- Grid electricity pricing follows Egyptian tariff structures (see metadata headers in `data/prices/electricity/historical_grid_electricity_prices-research.csv` for full EgyptERA source documentation and tariff reform timeline)
- Commercial/industrial differential of 16.5% verified from EgyptERA Aug 2024 tariff schedules
