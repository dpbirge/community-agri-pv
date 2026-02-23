# Configuration Schema and Data Structures

## 1. Overview

This document defines WHAT EXISTS in the simulation: configuration schema (Section 2), runtime state dataclasses (Section 3), and data file schemas (Section 4). It is the single source of truth for parameter definitions, valid options, dataclass fields, and data formats.

Related documents:

- `simulation_flow.md` — WHEN things happen (execution sequence)
- `policies.md` — WHY decisions are made (policy logic and pseudocode)
- `calculations.md` — HOW calculations work (formulas and methodologies)
- `reference_settings.yaml` — Complete example scenario configuration

**Cross-reference convention:** Throughout this document, pointers to other specs use the format `→ spec_file.md § Section_Number`.

---

## 2. System Configurations

System configurations are static settings that define initial conditions for a simulation scenario. Configuration parameters are listed as:

**Category** — parameter_name [valid options] (notes)

When units are obvious, they are appended to the parameter name (e.g., `community_area_km2`).

### 2.1 System Financing

All community-owned systems include a `financing_status` parameter that indicates the financial profile for capital costs (CAPEX) and operating costs (OPEX).

**Financing status options:** [existing_owned, grant_full, grant_capex, purchased_cash, loan_standard, loan_concessional]

| Profile | CAPEX | OPEX |
|---------|-------|------|
| `existing_owned` | Already depreciated | O&M only |
| `grant_full` | Grant covers | Grant covers |
| `grant_capex` | Grant covers | Community pays |
| `purchased_cash` | Community paid cash | Community pays |
| `loan_standard` | Commercial loan (6%, 10yr) | Community pays |
| `loan_concessional` | Development loan (3.5%, 15yr) | Community pays |

Financial parameters (interest rates, loan terms, cost multipliers) for each profile are defined in `data/parameters/economic/financing_profiles-toy.csv`.

→ calculations_economic.md § 1 for financing cost formulas

**Configuration sections use `_system` suffix:** In YAML files, use `water_system`, `energy_system`, and `food_processing_system` as section names.

### 2.2 Water System

**Groundwater wells:**

- well_depth_m
- salinity_level: [low, moderate, high] (must match rows in `treatment_kwh_per_m3-toy.csv`)
- well_flow_rate_m3_day
- number_of_wells
- financing_status

**Water treatment:**

- treatment_type: [bwro, swro, ro, none]
- system_capacity_m3_day
- number_of_units
- tds_ppm (loader-consumed field; raw groundwater TDS, static; also aliased as groundwater_tds_ppm in YAML for documentation)
- municipal_tds_ppm (municipal supply TDS, static; informational — not parsed by loader)
- financing_status

**TDS data flow:**

- `tds_ppm` (aliased as `groundwater_tds_ppm`): Raw groundwater salinity. Determines treatment energy (via `salinity_level` lookup) and input to `min_water_quality` blending.
- `municipal_tds_ppm`: Municipal supply salinity. Always cleaner than raw groundwater.
- Mixed water TDS: Weighted average — `(gw_m3 * gw_tds + muni_m3 * muni_tds) / (gw_m3 + muni_m3)`.
- → policies.md § 4 (`min_water_quality`) for the mixing formula.

**Water conveyance:**

- conveyance_kwh_per_m3 (fixed energy for pipe conveyance. Default 0.2 kWh/m3.)
- → calculations_water.md § 3 for derivation

**Derived at initialization:**

- gw_maintenance_per_m3 (USD/m3; computed from annual O&M / (capacity × 365); stored on scenario water system object for use in WaterPolicyContext construction)
  - → calculations_economic.md § 3 for derivation formula

**Irrigation water storage:**

- capacity_m3
- type: [reservoir, tank, pond]
- financing_status

**Irrigation system:**

- type: [drip_irrigation, sprinkler, surface, subsurface_drip]
- financing_status

### 2.3 Energy System

**PV (agri-PV, fixed-tilt):**

- sys_capacity_kw
- tilt_angle
- percent_over_crops
- density: [low, medium, high]
- height_m
- financing_status

PV output uses nameplate `sys_capacity_kw` throughout. No degradation modeled.

**Wind:**

- sys_capacity_kw
- type: [small, medium, large]
- financing_status

**Battery:**

- sys_capacity_kwh
- units
- chemistry: [LFP, NMC, lead_acid]
- soc_min (minimum SOC fraction; e.g. 0.10)
- soc_max (maximum SOC fraction; e.g. 0.95)
- charge_efficiency (fraction; e.g. 0.95 for LFP)
- discharge_efficiency (fraction; e.g. 0.95 for LFP)
- self_discharge_rate_per_day (daily fraction; 0.0005 for LFP)
- financing_status

Battery capacity is fixed at initialization. No degradation modeled.

→ calculations_energy.md § 3 for battery dynamics formulas

**Backup generator:**

- capacity_kw
- type: [diesel]
- max_runtime_hours (daily runtime limit. Default 18.)
- financing_status

→ calculations_energy.md § 4 for fuel consumption model

### 2.4 Community Structure

- community_area_km2
- total_farms
- total_farming_area_ha (loader also accepts total_area_ha as fallback)
- community_population
- houses
- community_buildings_m2 (aggregate; loader-consumed field)
- industrial_buildings_m2 (aggregate; loader-consumed field; default 0.0)
- community_buildings: informational breakdown by type (not parsed by loader)
  - office_admin_m2
  - storage_warehouse_m2
  - meeting_hall_m2
  - workshop_maintenance_m2

Community building energy and water demands are loaded from precomputed files as per-m2 daily rates, then scaled by `community_buildings_m2`.

→ simulation_flow.md § 2.2 for demand calculation

### 2.5 Food Processing System

**Fresh food packaging:**

- equipment: list of {type, fraction}
  - type: [washing_sorting_line, simple_wash_station]
- storage_capacity_kg_total
- financing_status

**Drying:**

- equipment: list of {type, fraction}
  - type: [solar_tunnel_dryer, simple_dehydrator, electric_dryer]
- storage_capacity_kg_total
- financing_status

**Canning:**

- equipment: list of {type, fraction}
  - type: [simple_retort, pressure_canner, industrial_retort]
- storage_capacity_kg_total
- financing_status

**Packaging:**

- equipment: list of {type, fraction}
  - type: [packaged, vacuum_sealed, modified_atmosphere]
- storage_capacity_kg_total
- financing_status

Shelf life (days before forced sale) is defined per crop × product_type in `data/parameters/crops/storage_spoilage_rates-toy.csv`, not in the scenario YAML. This allows crop-specific shelf lives (e.g., fresh tomato = 3 days, fresh potato = 14 days) rather than a single value per product type.

**Storage capacity mapping:**

| Configuration Section | `storage_capacities_kg` Key |
|-----------------------|-----------------------------|
| `fresh_food_packaging` | `"fresh"` |
| `packaging` | `"packaged"` |
| `canning` | `"canned"` |
| `drying` | `"dried"` |

**Post-harvest and processing loss rates:**

Losses are applied sequentially: handling loss first (harvest to intake), then processing weight loss (during drying, canning, etc.). Revenue is computed on the final output quantity.

*Stage 1 — Post-harvest handling loss (before food policy split):*

| Crop | Handling Loss Rate | Source | Configurable? |
|------|--------------------|--------|---------------|
| All crops (uniform) | 5% (default) | `settings.yaml` `post_harvest_handling_loss_rate` | Yes |

The 5% default reflects reduced losses from on-site processing. FAO estimates 10-15% for typical developing-economy supply chains with external transport.

*Stage 2 — Processing weight loss (per pathway, after food policy split):*

Weight loss represents physical mass transformation during processing (water removal, trimming). Values from `processing_specs-toy.csv`:

| Crop | Fresh | Packaged | Canned | Dried |
|------|-------|----------|--------|-------|
| Tomato | 0% | 3% | 15% | 88% |
| Potato | 0% | 3% | 15% | 78% |
| Onion | 0% | 3% | 15% | 80% |
| Kale | 0% | 3% | 15% | 82% |
| Cucumber | 0% | 3% | 15% | 92% |

Processing weight loss rates are hardcoded in `processing_specs-toy.csv` and are not user-configurable. Fresh weight_loss_pct = 0% because fresh produce undergoes no processing transformation.

*Combined loss example (tomato, dried pathway):*

```
raw_yield_kg = 1000 kg
handling_loss = 1000 * 0.05 = 50 kg
harvest_available_kg = 950 kg
dried_fraction = 0.15 (from food policy)
dried_input_kg = 950 * 0.15 = 142.5 kg
dried_output_kg = 142.5 * (1 - 0.88) = 17.1 kg  (revenue based on this quantity)
```

### 2.6 Farm Configurations

**Per farm:**

- id
- name
- area_ha
- yield_factor (relative to soil profile)
- starting_capital_usd (initial working capital; runtime `current_capital_usd` is initialized from this and updated daily)

**Crops (per farm):**

- name: [tomato, potato, onion, kale, cucumber]
- area_fraction
- planting_dates: list of MM-DD strings (e.g., ["02-15", "11-01"])
- percent_planted

### 2.7 Pricing Configuration

All prices (water, energy, crop, diesel) come from **historical time-series CSV files**. The scenario YAML contains only regime selectors that determine which CSV file to load. No price values or escalation rates are stored in the YAML.

**Water pricing:**

- municipal_source: [seawater_desalination, piped_groundwater]
- agricultural:
  - pricing_regime: [subsidized, unsubsidized] (selects which historical price CSV to load)
- community:
  - pricing_regime: [subsidized, unsubsidized] (independent from agricultural pricing)

Price data: `data/prices/water/historical_municipal_water_prices-research.csv`

**Energy pricing:**

- agricultural:
  - pricing_regime: [subsidized, unsubsidized] (selects which historical price CSV to load)
- community:
  - pricing_regime: [subsidized, unsubsidized] (independent from agricultural pricing)
- net_metering_ratio (default 0.70; export price = grid_import_price * this value)

Price data (subsidized): `data/prices/electricity/historical_grid_electricity_prices-research.csv`
Price data (unsubsidized): `data/prices/electricity/historical_grid_electricity_prices_unsubsidized-research.csv`

Tiered pricing (Egyptian 5-tier IBT with wastewater surcharge) is deferred. Flat rate is used for MVP.

→ simulation_flow.md § 5 for pricing resolution algorithm

### 2.8 Economic Configuration

- currency: [USD, EGP, EUR]
- exchange_rate_egp_per_usd (fixed for simulation run; all EGP values converted to USD at load time)
- discount_rate
- cost_allocation_method: [equal, area_proportional, usage_proportional]

**Cost allocation methods** (how shared infrastructure OPEX is split across farms):

| Method | Formula | Use when |
|--------|---------|----------|
| equal | shared_opex / num_farms | Similar-sized farms, simplicity valued |
| area_proportional | shared_opex * (farm_area / total_area) | Farms differ in size |
| usage_proportional | shared_opex * (farm_usage / total_usage) | Emphasize actual consumption |

→ simulation_flow.md § 8 for full cost allocation details

### 2.9 Simulation Period

- start_date: YYYY-MM-DD (first simulation day)
- end_date: YYYY-MM-DD (last simulation day, inclusive)
- time_step: [daily] (MVP supports daily only)

Price, weather, and PV/wind data must cover the full simulation period. If data is shorter, the last available value is used for extrapolation.

### 2.10 Enumerated Types

The following types appear as fields in dataclasses. Implementations MUST use Python `Enum` (or `Literal`) types to prevent typo-related logic failures.

**CropStage** — Growth stage of an active crop:

| Value | Description |
|-------|-------------|
| `DORMANT` | Between seasons, not actively growing |
| `INITIAL` | Germination and early establishment |
| `DEVELOPMENT` | Vegetative growth, canopy expanding |
| `MID_SEASON` | Full canopy, peak water demand |
| `LATE_SEASON` | Ripening, declining water demand |
| `HARVEST_READY` | Mature, awaiting harvest |

→ simulation_flow.md § 4 for state machine transitions

**ProductType** — Processing pathway for harvested crop:

| Value | Description |
|-------|-------------|
| `FRESH` | Unprocessed, washed/sorted only |
| `PACKAGED` | Fresh-packaged (MAP or vacuum sealed) |
| `CANNED` | Thermal-processed and canned |
| `DRIED` | Dehydrated / sun-dried |

Values use UPPER_CASE member names with lowercase string values (e.g., `FRESH = "fresh"`).

**ConstraintHit** — Which physical constraint limited a groundwater allocation:

| Value | Description |
|-------|-------------|
| `WELL_LIMIT` | Well extraction capacity was binding |
| `TREATMENT_LIMIT` | Treatment plant throughput was binding |
| `NONE` | No constraint hit; full allocation delivered |

Values use UPPER_CASE member names with lowercase string values (e.g., `WELL_LIMIT = "well_limit"`).

### 2.11 Policy Configuration

Policies operate at three levels. The **collective farm override** is the default mechanism.

- **Level 1 — Farm level:** Per-farm policies via `farms[i].policies.<domain>`.
- **Level 2 — Collective override (default):** `collective_farm_override.policies` stamps uniform policies into all farms. Overwrites farm-level settings.
- **Level 3 — Community level:** Non-farm operations (households, buildings) use limited water/energy policies via `household_policies`.

Crop plans (selection, area, planting dates) are ALWAYS per-farm regardless of policy level.

→ policies.md § 2 for policy hierarchy, override resolution, and parameter wiring

**Policy domains and defaults:**

| Domain | Default Policy | Status |
|--------|---------------|--------|
| water | `max_groundwater` | Active |
| energy | `renewable_first` | Active |
| crop | `fixed_schedule` | Active |
| food | `all_fresh` | Active |
| market | `sell_all_immediately` | Active |
| economic | `balanced_finance` | DEFERRED |

**Policy parameter wiring:** All configurable policy parameters live under `community_policy_parameters` in the scenario YAML, keyed by policy name. The loader resolves which policy each farm uses, looks up parameters by policy name, and passes them as keyword arguments to the factory function.

```yaml
community_policy_parameters:
  conserve_groundwater:
    price_threshold_multiplier: 1.5
    max_gw_ratio: 0.30
  hold_for_peak:
    price_threshold_multiplier: 1.2
  deficit_irrigation:
    deficit_fraction: 0.80
```

→ policies.md § 2 for full parameter wiring pipeline and factory function pattern

---

## 3. Runtime State Dataclasses

These dataclasses define the simulation's runtime state. They are initialized during pre-loop setup and updated throughout the daily loop. All fields list type, initial value, and the spec section where semantics are defined.

### 3.1 SimulationState (top-level container)

```
SimulationState:
    scenario: Scenario                          # Loaded scenario config
    farms: list[FarmState]                      # One per farm
    system_constraints: dict                    # {farm_id: {max_gw_per_farm, max_treatment_per_farm}}; set at Step 5, read-only thereafter
    water_storage: WaterStorageState            # Shared water storage
    energy: EnergyState                         # Shared energy system
    economic: EconomicState                     # Community-level finances
    community_storage: list[StorageTranche]     # Pooled food inventory (FIFO ordered)
    storage_capacities_kg: dict                 # {product_type: kg total}
    daily_farm_records: list[DailyFarmRecord]    # One per farm per day
    daily_community_records: list[DailyCommunityRecord]  # One per day
    start_date: date
    end_date: date
    current_date: date                          # Advances each loop iteration
    cumulative_gw_extraction_m3: float          # Lifetime total groundwater extraction; init = 0
```

→ simulation_flow.md § 2 for initialization sequence

### 3.2 FarmState

```
FarmState:
    id: str                         # Farm identifier from scenario
    name: str                       # Farm name
    plantable_area_ha: float        # Total plantable area
    yield_factor: float             # Relative yield factor
    starting_capital_usd: float     # Initial capital from YAML
    current_capital_usd: float      # Runtime cash; init = starting - capex_share
    capex_share: float              # Share of CAPEX allocated to this farm (set at initialization)
    crops: list[CropState]          # One per crop configured for this farm
    policy_instances: dict          # {domain: policy_object}
    contribution_kg: dict           # {crop_name: cumulative_kg} — lifetime harvest tracker
    cumulative_gw_month_m3: float   # Monthly extraction; reset on 1st of month
    cumulative_gw_year_m3: float    # Yearly extraction; reset on 1st of year
    daily_revenue: float            # Accumulated from sales within current day
    daily_costs: float              # Accumulated from Step 7 within current day
```

### 3.3 CropState

```
CropState:
    crop_name: str                  # e.g., "tomato"
    area_fraction: float            # Fraction of farm area for this crop
    planting_dates: list[str]       # MM-DD strings from scenario
    percent_planted: float          # Fraction actually planted (0-1)
    state: CropStage                # Current lifecycle stage; init = DORMANT
    days_in_stage: int              # Days in current stage; reset on transition
    kc: float                       # Current crop coefficient; computed daily; init = 0
    cycle_start_date: date | None   # Set on DORMANT → INITIAL transition
    cumulative_water_received: float # m3 this growth cycle; reset when DORMANT
    expected_total_water: float     # Total m3 expected for this cycle
    effective_area_ha: float        # = plantable_area * area_fraction * percent_planted
```

Derived at call time: `days_since_planting = (current_date - cycle_start_date).days`, `total_growing_days` from crop_coefficients `season_length_days`.

→ simulation_flow.md § 4 for crop lifecycle state machine

*AquiferState removed. Groundwater extraction is tracked as `cumulative_gw_extraction_m3` on SimulationState. Pumping energy is a static configuration value (`water_system.pumping_kwh_per_m3`). Aquifer level modeling (depletion, drawdown, dynamic pumping cost) is deferred to a future phase.*

### 3.5 WaterStorageState

```
WaterStorageState:
    capacity_m3: float              # From scenario
    current_m3: float               # Init = capacity * 0.50
```

### 3.6 EnergyState

```
EnergyState:
    pv_capacity_kw: float           # Nameplate; fixed (no degradation)
    wind_capacity_kw: float         # Nameplate; fixed
    battery_capacity_kwh: float     # Fixed (no degradation)
    battery_soc: float              # State of charge (0-1); init = 0.50
    generator_capacity_kw: float
    max_runtime_hours: float        # Default 18
    soc_min: float                  # Hardware minimum (0.10)
    soc_max: float                  # Hardware maximum (0.95)
    eta_charge: float               # Charge efficiency (0.95)
    eta_discharge: float            # Discharge efficiency (0.95)
    self_discharge_rate_daily: float # Daily self-discharge (0.0005)
```

→ calculations_energy.md § 3 for battery dynamics
→ calculations_energy.md § 5 for dispatch algorithm

### 3.7 StorageTranche

Each processed batch is tracked as a discrete tranche for FIFO inventory management:

```
StorageTranche:
    product_type: str               # "fresh", "packaged", "canned", "dried"
    crop_name: str                  # e.g., "tomato"
    kg: float                       # Output kg after weight loss; decremented on partial sales
    harvest_date: date              # Date of harvest
    expiry_date: date               # harvest_date + shelf_life_days
    sell_price_at_entry: float      # Price at storage time (tracking only, not for sale)
    farm_shares: dict               # {farm_id: fraction} — ownership at creation; sums to 1.0
```

- `shelf_life_days` from `storage_spoilage_rates-toy.csv` (per crop, per product type)
- Tranches ordered by `harvest_date` (oldest first = FIFO)
- `farm_shares` computed from per-batch contributions at harvest time

→ simulation_flow.md § 6.2 for revenue attribution via farm_shares
→ policies.md § 7 for forced sales (expiry and overflow)

### 3.8 EconomicState

```
EconomicState:
    total_capex_invested: float     # SUM(capital_cost) all subsystems; for IRR/NPV
    capex_cash_outflow: float       # SUM(capital_cost * multiplier) for cash systems only
    initial_cash: float             # SUM(starting_capital) - capex_cash_outflow
    daily_replacement_reserve: float # Flat % of CAPEX / 365. Simplified from per-component sinking fund to flat percentage for MVP.
    monthly_debt_service: float     # Total across all loan-financed subsystems
    infrastructure_annual_opex: float # Total infrastructure O&M per year
    discount_rate: float            # From scenario economics
    debt_schedules: list[DebtSchedule]
    total_debt_usd: float           # SUM(remaining_principal); updated monthly
```

→ calculations_economic.md § 1-2 for financing and replacement reserve formulas

### 3.9 DebtSchedule

```
DebtSchedule:
    subsystem: str                  # e.g., "water_treatment", "pv", "battery"
    principal: float                # Original loan amount
    annual_interest_rate: float     # From financing_profiles CSV
    loan_term_months: int           # From financing_profiles CSV
    monthly_payment: float          # Fixed amortization payment
    remaining_principal: float      # Init = principal; decremented monthly
    remaining_months: int           # Init = loan_term_months; decremented monthly
    start_date: date                # Simulation start date
```

→ calculations_economic.md § 7 for amortization formula

### 3.10 DailyFarmRecord

The single source of truth for per-farm daily data. All monthly, yearly, and lifetime metrics are aggregated from these records. One record per farm per day.

```
DailyFarmRecord:
    date: date
    farm_id: str

    # Water (from Step 2)
    groundwater_m3: float
    municipal_m3: float
    total_water_m3: float           # groundwater + municipal
    water_cost_usd: float           # Cash cost (maintenance + municipal)
    water_energy_kwh: float         # GW pumping + conveyance + treatment energy

    # Irrigation (from Step 1)
    irrigation_demand_m3: float     # Adjusted demand from crop policy
    irrigation_delivered_m3: float  # Actual delivered (may differ if pro-rata)

    # Energy (from Step 6, attributed per Step 6c)
    energy_demand_kwh: float        # This farm's share of community total
    energy_cost_usd: float          # Attributed share of dispatch cost
    export_revenue_usd: float       # Attributed share of grid export revenue

    # Crop (from Steps 1, 4)
    harvest_kg: float               # Raw harvest yield (0 on non-harvest days)
    processed_kg: float             # Output kg after weight loss

    # Revenue (from Steps 3, 5a, 5b)
    crop_revenue_usd: float         # Attributed sales revenue (forced + voluntary)
    forced_sale_revenue_usd: float
    voluntary_sale_revenue_usd: float

    # Costs (from Step 7)
    labor_cost_usd: float              # Event-driven daily labor (field + processing + logistics)
    labor_hours_total: float           # Total labor hours this day (all categories); needed for FTE and person-hour metrics
    input_cost_usd: float
    storage_cost_usd: float
    farm_specific_cost_usd: float   # Sum of farm-specific costs
    allocated_shared_cost_usd: float # Farm's share of community shared OPEX
    debt_service_cost_usd: float
    total_cost_usd: float           # farm_specific + allocated_shared + debt_service
    total_revenue_usd: float        # crop_revenue + export_revenue
    net_income_usd: float           # total_revenue - total_cost
    cash_position_usd: float        # Cash after today (may be negative)
```

### 3.11 DailyCommunityRecord

One record per day capturing community-level system state.

```
DailyCommunityRecord:
    date: date

    # Energy dispatch (from Step 6)
    total_energy_demand_kwh: float
    pv_generated_kwh: float
    wind_generated_kwh: float
    pv_used_kwh: float
    wind_used_kwh: float
    battery_discharged_kwh: float
    battery_charged_kwh: float
    grid_imported_kwh: float
    grid_exported_kwh: float
    generator_used_kwh: float
    generator_curtailed_kwh: float  # Fuel burned at minimum load, not delivered to demand
    curtailed_kwh: float
    unmet_demand_kwh: float
    total_energy_cost_usd: float
    grid_cost_usd: float
    generator_cost_usd: float
    generator_fuel_L: float
    export_revenue_usd: float
    battery_soc: float

    # Energy demand breakdown
    E_water_system_kwh: float
    E_irrigation_pump_kwh: float
    E_processing_kwh: float
    E_household_kwh: float
    E_community_bldg_kwh: float

    # Water system (from Step 2)
    total_groundwater_m3: float
    total_municipal_m3: float
    water_storage_m3: float
    community_water_demand_m3: float
    community_water_cost_usd: float

    # Groundwater (from Step 2c)
    cumulative_gw_extraction_m3: float

    # Food inventory (from Steps 3-5)
    total_storage_kg: float
    storage_by_type: dict           # {product_type: kg}
    forced_expiry_sales_kg: float
    forced_overflow_sales_kg: float
    voluntary_sales_kg: float

    # Community economics
    total_shared_opex_usd: float
    total_debt_remaining_usd: float
```

### 3.12 DispatchResult

Returned by `dispatch_energy()` each day:

```
DispatchResult:
    pv_used_kwh: float
    wind_used_kwh: float
    battery_discharged_kwh: float
    battery_charged_kwh: float
    grid_imported_kwh: float
    grid_exported_kwh: float
    generator_used_kwh: float
    generator_curtailed_kwh: float  # Fuel burned at minimum load, not delivered to demand
    curtailed_kwh: float            # Renewable surplus not used/stored/exported
    unmet_demand_kwh: float         # Not met by any source (microgrid only)
    grid_cost_usd: float
    generator_cost_usd: float
    generator_fuel_L: float
    export_revenue_usd: float
    total_energy_cost_usd: float    # grid + generator - export
    battery_soc_after: float        # SOC after dispatch + self-discharge
```

→ calculations_energy.md § 5 for dispatch algorithm
→ simulation_flow.md § 3 (Step 6) for dispatch integration

### 3.13 FinalState (written as final_state.json)

Snapshot of key state at the end of the last simulation day.

```
FinalState:
    water_storage_m3: float             # WaterStorageState.current_m3
    battery_soc: float                  # EnergyState.battery_soc
    cumulative_gw_extraction_m3: float  # SimulationState.cumulative_gw_extraction_m3
    cash_positions: dict                # {farm_id: FarmState.current_capital_usd}
    total_debt_remaining_usd: float     # EconomicState.total_debt_usd
    terminal_inventory_value_usd: float # SUM(tranche.kg * last_day_price) — not a sale
    in_progress_crops: list             # [{farm_id, crop_name, state, days_in_stage,
                                        #   cumulative_water_received_m3}]
                                        # One entry per crop not in DORMANT state
```

→ simulation_flow.md § 10.1 for how this snapshot is computed
→ simulation_flow.md § 10.4 item 9 for file output

### 3.14 Monthly Summary Schema (monthly_summary.csv)

One row per (farm_id, year, month). Aggregated from DailyFarmRecord by summing all
daily values within the month. One additional row per month with `farm_id = "community"`
aggregates DailyCommunityRecord fields.

Minimum columns (farm rows): `farm_id, year, month, total_water_m3, groundwater_m3,
municipal_m3, total_energy_demand_kwh, crop_revenue_usd, total_cost_usd,
net_income_usd, harvest_kg`.

Minimum columns (community row): `farm_id, year, month, total_groundwater_m3,
total_energy_demand_kwh, pv_generated_kwh, wind_generated_kwh, total_energy_cost_usd,
cumulative_gw_extraction_m3, total_storage_kg`.

→ simulation_flow.md § 10.4 item 3 for write order

### 3.15 Simulation Summary Schema (simulation_summary.json)

Top-level JSON object with two keys: `lifetime` (Stage 3 metrics) and `financial`
(Stage 4 metrics).

```
simulation_summary:
    lifetime:
        total_water_m3: float
        total_groundwater_m3: float
        total_energy_kwh: float
        total_renewable_kwh: float
        total_crop_revenue_usd: float
        total_net_income_usd: float
        avg_annual_net_income_usd: float
        net_income_trend_slope: float   # least-squares slope of yearly net income
        cost_volatility_cv: float       # CV of monthly total costs
    financial:
        npv_usd: float
        irr_pct: float | null           # null if no real solution
        payback_years: float | null     # null if not recovered within simulation
        roi_pct: float
        terminal_inventory_value_usd: float
```

→ simulation_flow.md § 10.2 Stages 3-4 for computation
→ simulation_flow.md § 10.4 item 5 for write order

---

## 4. Data File Schemas

Minimum columns required by the simulation engine. Actual files may contain additional columns.

### Equipment and Infrastructure

**`data/parameters/equipment/processing_equipment-toy.csv`:**
`pathway, equipment_type, throughput_kg_per_day, energy_kwh_per_kg, availability_factor`

**`data/parameters/equipment/equipment_lifespans-toy.csv`:**
`component, lifespan_years, replacement_cost_pct`
Retained for reference. Not consumed by simplified flat-percentage replacement reserve (§ 3.8).

**`data/parameters/equipment/wells-toy.csv`:**
`parameter, value` (key-value pairs: pump_efficiency, specific_yield, etc.)

### Costs

**`data/parameters/crops/food_storage_costs-toy.csv`:**
`product_type, cost_usd_per_kg_per_day`

**`data/parameters/costs/operating_costs-toy.csv`:**
`system, annual_om_usd` (water_treatment, pv, wind, battery, generator, processing)

**`data/parameters/costs/input_costs-toy.csv`:**
`crop, annual_cost_usd_per_ha`

### Economic

**`data/parameters/economic/financing_profiles-toy.csv`:**
`financing_status, capex_cost_multiplier, annual_interest_rate, loan_term_years, om_included`

### Crops

**`data/parameters/crops/crop_coefficients-toy.csv`:**
`crop, kc_initial, kc_mid, kc_end, season_length_days, yield_response_factor`

**`data/parameters/crops/processing_specs-toy.csv`:**
`crop, product_type, weight_loss_pct`

**`data/parameters/crops/storage_spoilage_rates-toy.csv`:**
`crop_name, product_type, shelf_life_days`

### Labor

**`data/parameters/labor/labor_rates-toy.csv`:**
`activity, hours_per_unit, unit, wage_usd_per_hour`
Activities: field_work (ha/day), harvest (kg), processing (kg), admin (year)

### Prices

**`data/prices/crops/<crop>-toy.csv`:**
`date, price_usd_per_kg` (daily farmgate / fresh product price)

**`data/prices/processed/<crop>_<product_type>-toy.csv`:**
`date, price_usd_per_kg` (daily processed product price)

**`data/prices/diesel/diesel-toy.csv`:**
`date, price_usd_per_L`

**`data/prices/water/historical_municipal_water_prices-research.csv`:**
`date, usd_per_m3, egp_per_m3_original, usd_egp_exchange_rate, rate_category`
Rate category distinguishes agricultural_bulk from community retail. Lookup uses `usd_per_m3` (already converted).

**`data/prices/electricity/historical_grid_electricity_prices-research.csv`:**
`date, usd_per_kwh_offpeak, usd_per_kwh_peak, usd_per_kwh_avg_daily, rate_schedule, egp_per_kwh_original, usd_egp_exchange_rate`
Simulation uses `usd_per_kwh_avg_daily` as the daily flat rate. Unsubsidized variant has the same schema.

### Precomputed

**`data/precomputed/weather/daily_weather_scenario_001-*.csv`:**
`date, temp_max_c, temp_min_c, solar_irradiance_kwh_m2, wind_speed_ms, precip_mm, weather_scenario_id`
One row per day. Loaded at initialization; indexed by date for Step 0 daily lookup.

**`data/precomputed/irrigation_demand/irrigation_m3_per_ha_<crop>-toy.csv`:**
`weather_scenario_id, planting_date, crop_day, calendar_date, growth_stage, kc, et0_mm, etc_mm, irrigation_m3_per_ha_per_day`
One row per crop day per planting cycle. Indexed by (planting_date, crop_day) for Step 1 lookup.

**`data/precomputed/pv_power/pv_normalized_kwh_per_kw_daily-toy.csv`:**
`weather_scenario_id, date, density_variant, kwh_per_kw_per_day, capacity_factor`
One row per date per density variant. Multiply by `sys_capacity_kw` to get daily PV generation.

**`data/precomputed/wind_power/wind_normalized_kwh_per_kw_daily-toy.csv`:**
`weather_scenario_id, date, turbine_variant, kwh_per_kw_per_day, capacity_factor`
One row per date per turbine variant. Multiply by `sys_capacity_kw` to get daily wind generation.

**`data/precomputed/household/household_energy_kwh_per_day-toy.csv`:**
`date, small_household_kwh, medium_household_kwh, large_household_kwh, total_community_kwh`
Simulation uses `total_community_kwh` as `E_household` for Step 0.

**`data/precomputed/household/household_water_m3_per_day-toy.csv`:**
`date, small_household_m3, medium_household_m3, large_household_m3, total_community_m3`
Simulation uses `total_community_m3` as `hw_demand` for Step 0.

**`data/precomputed/community_buildings/community_buildings_energy_kwh_per_day-toy.csv`:**
`date, office_admin_kwh_per_m2, storage_warehouse_kwh_per_m2, meeting_hall_kwh_per_m2, workshop_maintenance_kwh_per_m2, total_kwh_per_m2`
Simulation multiplies `total_kwh_per_m2` by `community_buildings_m2` for `E_community`.

**`data/precomputed/community_buildings/community_buildings_water_m3_per_day-toy.csv`:**
`date, office_admin_m3_per_m2, storage_warehouse_m3_per_m2, meeting_hall_m3_per_m2, workshop_maintenance_m3_per_m2, total_m3_per_m2`
Simulation multiplies `total_m3_per_m2` by `community_buildings_m2` for `cw_demand`.

**`data/precomputed/microclimate/pv_shade_adjustments-toy.csv`:**
`density_variant, ground_coverage_pct, temp_adjustment_c, irradiance_multiplier, wind_speed_multiplier, evapotranspiration_multiplier`
Static lookup keyed by `density_variant`. Applied to raw weather to compute adjusted conditions under agri-PV canopy.

### Water Treatment

**`data/precomputed/water_treatment/treatment_kwh_per_m3-toy.csv`:**
`salinity_level, treatment_kwh_per_m3` (rows: low, moderate, high)

---

*End of specification.*
