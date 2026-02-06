# Community Farm Model Policy Specifications

## 1. Overview

This document defines the **policy decision rules** implemented in `src/policies/`. Policies are Layer 2 configuration components that determine how the simulation makes decisions about resource allocation, infrastructure use, and operational strategies.

For **calculation methodologies** (formulas, parameters, dependencies), see `mvp-calculations.md`.  
For **configuration structure** (what parameters exist and their valid options), see `mvp-structure.md`.

**Policy Pattern:**
- Each policy domain has a base class (`BaseWaterPolicy`, `BaseEnergyPolicy`, etc.)
- Policies take a context dataclass as input (e.g., `WaterPolicyContext`)
- Policies return an allocation/decision dataclass (e.g., `WaterAllocation`)
- Policies are instantiated via factory functions: `get_water_policy(name, **kwargs)`

**Sections:**
1. Overview
2. Water Allocation Policies
3. Energy Dispatch Policies
4. Food Processing Policies
5. Crop Management Policies
6. Economic Policies
7. Market/Sales Policies
8. Policy Integration

---

## 2. Water Allocation Policies

**Location:** `src/policies/water_policies.py`

**Purpose:** Determine how much water to source from groundwater (treated) vs municipal supply each day. Each farm selects a water source allocation strategy that is instantiated during scenario loading and called daily in the simulation loop via `execute_water_policy()`.

### 2.0 Implementation Status

| Component | Status | Notes |
|-----------|--------|-------|
| `WaterPolicyContext` dataclass | Fully implemented | All 13 fields defined with defaults |
| `WaterAllocation` dataclass | Fully implemented | Includes optional `WaterDecisionMetadata` |
| `WaterDecisionMetadata` dataclass | Fully implemented | Tracks decision reasons and constraints |
| `BaseWaterPolicy` class | Fully implemented | Includes 5 helper methods |
| `AlwaysGroundwater` policy | Fully implemented and integrated | Active in daily simulation loop |
| `AlwaysMunicipal` policy | Fully implemented and integrated | Active in daily simulation loop |
| `CheapestSource` policy | Fully implemented and integrated | Active in daily simulation loop |
| `ConserveGroundwater` policy | Fully implemented and integrated | Active in daily simulation loop |
| `QuotaEnforced` policy | Fully implemented and integrated | Active in daily simulation loop |
| `WATER_POLICIES` registry | Implemented | Dict mapping names to classes |
| `get_water_policy()` factory | Implemented | Registered in `src/policies/__init__.py` |

**Integration:** Water policies are fully wired into the simulation loop in `src/simulation/simulation.py`. The policy is called daily via `execute_water_policy()` which builds the `WaterPolicyContext` from farm state and infrastructure constraints, then applies the policy's `allocate_water()` method.

### 2.1 Available Policies

| Policy | Scenario Name | Behavior |
|--------|---------------|----------|
| `AlwaysGroundwater` | `always_groundwater` | 100% groundwater with onsite desalination; municipal fallback if physically constrained |
| `AlwaysMunicipal` | `always_municipal` | 100% municipal water; no treatment energy needed |
| `CheapestSource` | `cheapest_source` | Daily cost comparison: groundwater (pumping + treatment energy cost) vs municipal (marginal tier price) |
| `ConserveGroundwater` | `conserve_groundwater` | Prefers municipal; uses groundwater only when municipal price exceeds a configurable threshold multiplier |
| `QuotaEnforced` | `quota_enforced` | Hard annual groundwater limit with monthly variance controls; forces 100% municipal when quota exhausted |

### 2.2 Context Input (`WaterPolicyContext`)

All fields are defined as dataclass attributes with sensible defaults where appropriate:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `demand_m3` | float | (required) | Total water demand in cubic meters |
| `available_energy_kwh` | float | (required) | Energy available for water treatment |
| `treatment_kwh_per_m3` | float | (required) | Energy required to treat 1 m³ of groundwater (desalination) |
| `gw_maintenance_per_m3` | float | (required) | Maintenance cost per m³ of groundwater treatment (USD) |
| `municipal_price_per_m3` | float | (required) | Current municipal water price (USD/m³) |
| `energy_price_per_kwh` | float | (required) | Current energy price (USD/kWh) |
| `pumping_kwh_per_m3` | float | 0.0 | Energy to pump 1 m³ from well to surface |
| `conveyance_kwh_per_m3` | float | 0.0 | Energy to convey 1 m³ from well/treatment to farm |
| `max_groundwater_m3` | float | inf | Maximum groundwater extraction (well capacity / num_farms) |
| `max_treatment_m3` | float | inf | Maximum treatment throughput (treatment capacity / num_farms) |
| `cumulative_gw_year_m3` | float | 0.0 | Cumulative groundwater used this year (for quota policies) |
| `cumulative_gw_month_m3` | float | 0.0 | Cumulative groundwater used this month (for quota policies) |
| `current_month` | int | 1 | Current month (1-12) for monthly quota calculations |

### 2.3 Output (`WaterAllocation`)

| Field | Type | Description |
|-------|------|-------------|
| `groundwater_m3` | float | Volume allocated from treated groundwater |
| `municipal_m3` | float | Volume allocated from municipal supply |
| `energy_used_kwh` | float | Energy consumed for groundwater treatment |
| `cost_usd` | float | Total cost of water allocation |
| `metadata` | Optional[WaterDecisionMetadata] | Decision explanation (see below) |

### 2.4 Decision Metadata (`WaterDecisionMetadata`)

Enables tracking and visualization of policy decision patterns:

| Field | Type | Description |
|-------|------|-------------|
| `decision_reason` | str | Human-readable reason for allocation choice |
| `gw_cost_per_m3` | float | Groundwater cost at decision time (energy + maintenance) |
| `muni_cost_per_m3` | float | Municipal water cost at decision time |
| `constraint_hit` | Optional[str] | Which constraint limited GW allocation: `"well_limit"`, `"treatment_limit"`, `"energy_limit"`, or `None` |

**Decision reason values by policy:**
- `AlwaysGroundwater`: `"gw_preferred"`, `"gw_preferred_partial"`, `"gw_preferred_but_{constraint}"`
- `AlwaysMunicipal`: `"muni_only"`
- `CheapestSource`: `"gw_cheaper"`, `"muni_cheaper"`, `"gw_cheaper_but_{constraint}"`
- `ConserveGroundwater`: `"threshold_exceeded"`, `"threshold_not_met"`, `"threshold_exceeded_but_{constraint}"`
- `QuotaEnforced`: `"quota_available"`, `"quota_available_partial"`, `"quota_exhausted"`, `"quota_monthly_limit"`, `"quota_available_but_{constraint}"`

### 2.5 Base Class Helper Methods

`BaseWaterPolicy` provides five helper methods used by all policy implementations:

| Method | Description |
|--------|-------------|
| `_calc_gw_cost_per_m3(ctx)` | Calculate total groundwater cost: `(E_pump + E_convey + E_treatment) * electricity_price + O&M_cost` |
| `_calc_allocation_cost(gw_m3, muni_m3, ctx)` | Calculate total cost for a given allocation |
| `_calc_energy_used(gw_m3, ctx)` | Calculate total energy used for groundwater (pumping + conveyance + treatment) |
| `_max_treatable_m3(ctx)` | Calculate maximum groundwater volume processable with available energy |
| `_apply_constraints(requested_gw_m3, ctx)` | Apply physical infrastructure constraints, returns `(constrained_gw_m3, constraint_hit)` |

The `_apply_constraints()` method clips requested groundwater to the minimum of:
1. Energy-limited treatment capacity
2. Well extraction capacity (`max_groundwater_m3`)
3. Treatment plant throughput (`max_treatment_m3`)

### 2.6 Policy Implementations

#### 2.6.1 AlwaysGroundwater

**Policy Name:** `always_groundwater`

**Purpose:** Use 100% groundwater, fall back to municipal only if constrained.

**Pseudocode:**
```
FUNCTION allocate_water(ctx):
    gw_cost_per_m3 = calculate_gw_cost(ctx)
    muni_cost_per_m3 = ctx.municipal_price_per_m3
    
    // Request full demand as groundwater
    requested_gw = ctx.demand_m3
    
    // Apply physical constraints (energy, well capacity, treatment capacity)
    gw_m3, constraint_hit = apply_constraints(requested_gw, ctx)
    muni_m3 = ctx.demand_m3 - gw_m3
    
    // Determine decision reason
    IF constraint_hit:
        reason = "gw_preferred_but_" + constraint_hit
    ELSE IF muni_m3 > 0:
        reason = "gw_preferred_partial"
    ELSE:
        reason = "gw_preferred"
    
    RETURN WaterAllocation(
        groundwater_m3 = gw_m3,
        municipal_m3 = muni_m3,
        energy_used_kwh = calculate_energy_used(gw_m3, ctx),
        cost_usd = calculate_total_cost(gw_m3, muni_m3, ctx),
        metadata = WaterDecisionMetadata(reason, gw_cost_per_m3, muni_cost_per_m3, constraint_hit)
    )
END FUNCTION
```

**Helper Functions:**
- `calculate_gw_cost(ctx)`: Returns `(pumping + conveyance + treatment) * energy_price + maintenance`
- `apply_constraints(requested, ctx)`: Returns `(min(requested, energy_limit, well_limit, treatment_limit), constraint_name)`

#### 2.6.2 AlwaysMunicipal

**Policy Name:** `always_municipal`

**Purpose:** Use 100% municipal water, no treatment energy needed.

**Pseudocode:**
```
FUNCTION allocate_water(ctx):
    gw_cost_per_m3 = calculate_gw_cost(ctx)
    muni_cost_per_m3 = ctx.municipal_price_per_m3
    
    RETURN WaterAllocation(
        groundwater_m3 = 0.0,
        municipal_m3 = ctx.demand_m3,
        energy_used_kwh = 0.0,
        cost_usd = ctx.demand_m3 * muni_cost_per_m3,
        metadata = WaterDecisionMetadata("muni_only", gw_cost_per_m3, muni_cost_per_m3, None)
    )
END FUNCTION
```

#### 2.6.3 CheapestSource

**Policy Name:** `cheapest_source`

**Purpose:** Dynamically select water source based on daily cost comparison.

**Parameters:**
- `include_energy_cost` (bool, default=True): Whether to include energy cost in comparison

**Pseudocode:**
```
FUNCTION allocate_water(ctx):
    gw_cost_per_m3 = calculate_gw_cost(ctx)
    muni_cost_per_m3 = ctx.municipal_price_per_m3
    
    // For comparison, optionally exclude energy cost
    IF include_energy_cost:
        gw_compare_cost = gw_cost_per_m3
    ELSE:
        gw_compare_cost = ctx.gw_maintenance_per_m3
    
    constraint_hit = None
    IF gw_compare_cost < muni_cost_per_m3:
        // Groundwater is cheaper - use as much as constraints allow
        gw_m3, constraint_hit = apply_constraints(ctx.demand_m3, ctx)
        muni_m3 = ctx.demand_m3 - gw_m3
        IF constraint_hit:
            reason = "gw_cheaper_but_" + constraint_hit
        ELSE:
            reason = "gw_cheaper"
    ELSE:
        gw_m3 = 0.0
        muni_m3 = ctx.demand_m3
        reason = "muni_cheaper"
    
    RETURN WaterAllocation(
        groundwater_m3 = gw_m3,
        municipal_m3 = muni_m3,
        energy_used_kwh = calculate_energy_used(gw_m3, ctx),
        cost_usd = calculate_total_cost(gw_m3, muni_m3, ctx),
        metadata = WaterDecisionMetadata(reason, gw_cost_per_m3, muni_cost_per_m3, constraint_hit)
    )
END FUNCTION
```

#### 2.6.4 ConserveGroundwater

**Policy Name:** `conserve_groundwater`

**Purpose:** Prefer municipal water to conserve aquifer. Use GW only when municipal price exceeds threshold.

**Parameters:**
- `price_threshold_multiplier` (float, default=1.5): Municipal price must exceed GW cost × this multiplier
- `max_gw_ratio` (float, default=0.30): Maximum fraction of demand from groundwater

**Pseudocode:**
```
FUNCTION allocate_water(ctx):
    gw_cost_per_m3 = calculate_gw_cost(ctx)
    threshold = gw_cost_per_m3 * price_threshold_multiplier
    muni_cost_per_m3 = ctx.municipal_price_per_m3
    
    constraint_hit = None
    IF muni_cost_per_m3 > threshold:
        // Municipal expensive - use GW up to max ratio
        gw_demand = ctx.demand_m3 * max_gw_ratio
        gw_m3, constraint_hit = apply_constraints(gw_demand, ctx)
        muni_m3 = ctx.demand_m3 - gw_m3
        IF constraint_hit:
            reason = "threshold_exceeded_but_" + constraint_hit
        ELSE:
            reason = "threshold_exceeded"
    ELSE:
        gw_m3 = 0.0
        muni_m3 = ctx.demand_m3
        reason = "threshold_not_met"
    
    RETURN WaterAllocation(
        groundwater_m3 = gw_m3,
        municipal_m3 = muni_m3,
        energy_used_kwh = calculate_energy_used(gw_m3, ctx),
        cost_usd = calculate_total_cost(gw_m3, muni_m3, ctx),
        metadata = WaterDecisionMetadata(reason, gw_cost_per_m3, muni_cost_per_m3, constraint_hit)
    )
END FUNCTION
```

#### 2.6.5 QuotaEnforced

**Policy Name:** `quota_enforced`

**Purpose:** Enforce hard annual groundwater quota with monthly variance controls.

**Parameters:**
- `annual_quota_m3` (float): Maximum groundwater extraction per year
- `monthly_variance_pct` (float, default=0.15): Allowed deviation from equal monthly distribution (15% = ±15%)

**Pseudocode:**
```
FUNCTION allocate_water(ctx):
    gw_cost = calculate_gw_cost(ctx)
    muni_cost = ctx.municipal_price_per_m3
    
    // Calculate quota constraints
    remaining_annual = MAX(0.0, annual_quota - ctx.cumulative_gw_year_m3)
    monthly_target = annual_quota / 12.0
    monthly_max = monthly_target * (1 + monthly_variance_pct)
    remaining_monthly = MAX(0.0, monthly_max - ctx.cumulative_gw_month_m3)
    
    // Effective quota limit is minimum of annual and monthly remaining
    quota_limit = MIN(remaining_annual, remaining_monthly)
    
    constraint_hit = None
    IF remaining_annual <= 0:
        // Annual quota exhausted - force 100% municipal
        gw_m3 = 0.0
        muni_m3 = ctx.demand_m3
        reason = "quota_exhausted"
    ELSE IF remaining_monthly <= 0:
        // Monthly limit exceeded - force municipal for rest of month
        gw_m3 = 0.0
        muni_m3 = ctx.demand_m3
        reason = "quota_monthly_limit"
    ELSE:
        // Quota available - try to use groundwater up to quota limit
        requested_gw = MIN(ctx.demand_m3, quota_limit)
        
        // Apply physical constraints (well, treatment, energy)
        gw_m3, constraint_hit = apply_constraints(requested_gw, ctx)
        muni_m3 = ctx.demand_m3 - gw_m3
        
        IF constraint_hit:
            reason = "quota_available_but_" + constraint_hit
        ELSE IF gw_m3 < ctx.demand_m3:
            IF gw_m3 < quota_limit:
                reason = "quota_available"
            ELSE:
                reason = "quota_available_partial"
        ELSE:
            reason = "quota_available"
    
    RETURN WaterAllocation(
        groundwater_m3 = gw_m3,
        municipal_m3 = muni_m3,
        energy_used_kwh = calculate_energy_used(gw_m3, ctx),
        cost_usd = calculate_total_cost(gw_m3, muni_m3, ctx),
        metadata = WaterDecisionMetadata(reason, gw_cost, muni_cost, constraint_hit)
    )
END FUNCTION
```

### 2.7 Registry and Factory

**Policy Registry:**

```python
WATER_POLICIES = {
    "always_groundwater": AlwaysGroundwater,
    "always_municipal": AlwaysMunicipal,
    "cheapest_source": CheapestSource,
    "conserve_groundwater": ConserveGroundwater,
    "quota_enforced": QuotaEnforced,
}
```

**Factory Function:**

```python
def get_water_policy(name, **kwargs):
    """Get a water policy instance by name.

    Args:
        name: Policy name as string (e.g., "cheapest_source")
        **kwargs: Parameters to pass to policy constructor

    Returns:
        Instantiated policy object

    Raises:
        ValueError: If policy name not found
    """
```

**Base Class Methods:**

All water policies inherit from `BaseWaterPolicy` which provides:

- `allocate_water(ctx: WaterPolicyContext) -> WaterAllocation` - Main decision method (must be implemented)
- `get_parameters() -> dict` - Returns policy parameters for serialization
- `describe() -> str` - Returns human-readable policy description

**Usage Example:**

```python
# Get policy instance with custom parameters
policy = get_water_policy("conserve_groundwater",
                          price_threshold_multiplier=1.5,
                          max_gw_ratio=0.30)

# Create context from simulation state
ctx = WaterPolicyContext(
    demand_m3=100.0,
    available_energy_kwh=500.0,
    treatment_kwh_per_m3=3.5,
    gw_maintenance_per_m3=0.05,
    municipal_price_per_m3=0.80,
    energy_price_per_kwh=0.10,
    max_groundwater_m3=150.0,
    max_treatment_m3=200.0,
)

# Get allocation decision
allocation = policy.allocate_water(ctx)
# allocation.groundwater_m3, allocation.municipal_m3, allocation.cost_usd, etc.
```

---

## 3. Energy Dispatch Policies

**Location:** `src/policies/energy_policies.py`

**Purpose:** Determine energy dispatch strategy parameters (which sources to use, battery reserve, grid export).

**Note:** These policies do NOT perform dispatch themselves. They return strategy flags and thresholds that guide the `dispatch_energy()` function in `simulation.py`. The policies influence the merit-order algorithm but do not execute dispatch logic directly.

### 3.0 Implementation Status

| Component | Status | Notes |
|-----------|--------|-------|
| `EnergyPolicyContext` dataclass | Fully implemented | All 9 context fields defined with defaults |
| `EnergyAllocation` dataclass | Fully implemented | 10 output fields (4 flags, 4 strategy params, 2 metadata) |
| `BaseEnergyPolicy` class | Fully implemented | Base class with `allocate_energy()`, `get_parameters()`, `describe()` |
| `PvFirstBatteryGridDiesel` policy | Fully implemented | Renewable-first merit order |
| `GridFirst` policy | Fully implemented | Grid-only, no renewables |
| `CheapestEnergy` policy | Fully implemented | Dynamic LCOE vs grid comparison |
| Policy registry (`ENERGY_POLICIES`) | Fully implemented | Maps scenario names to policy classes |
| Factory function (`get_energy_policy`) | Fully implemented | Instantiates policies by name |
| **Simulation integration** | **Not wired** | `dispatch_energy()` uses hardcoded merit-order; does not consume `EnergyAllocation` flags |

**Integration gap:** The `dispatch_energy()` function in `src/simulation/simulation.py` currently implements a fixed renewable-first merit order. To integrate these policies:
1. Instantiate the energy policy during scenario loading
2. Call `policy.allocate_energy(ctx)` each simulation step to get an `EnergyAllocation`
3. Modify `dispatch_energy()` to respect the allocation flags (e.g., skip renewables if `use_renewables=False`, use `battery_reserve_pct` instead of hardcoded SOC minimum)

### 3.1 Available Policies

| Policy | Scenario Name | Class | Behavior |
|--------|---------------|-------|----------|
| PvFirstBatteryGridDiesel | `all_renewable`, `hybrid` | `PvFirstBatteryGridDiesel` | Renewable-first merit order, 20% battery reserve, grid export allowed |
| GridFirst | `all_grid` | `GridFirst` | Grid primary, generator backup; renewables and battery disabled |
| CheapestEnergy | `cost_minimize` | `CheapestEnergy` | Compares renewable LCOE to grid price each period; dynamically switches strategy |

### 3.2 Context Input (`EnergyPolicyContext`)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `total_demand_kwh` | float | 0.0 | Total energy demand (irrigation, processing, housing, etc.) |
| `pv_available_kwh` | float | 0.0 | PV generation available this period |
| `wind_available_kwh` | float | 0.0 | Wind generation available this period |
| `battery_soc` | float | 0.0 | Current battery state of charge (0-1 fraction) |
| `battery_capacity_kwh` | float | 0.0 | Total battery capacity |
| `grid_price_per_kwh` | float | 0.0 | Current grid electricity price (USD/kWh) |
| `diesel_price_per_L` | float | 0.0 | Current diesel fuel price (USD/L) |
| `generator_capacity_kw` | float | 0.0 | Backup generator nameplate capacity (kW) |
| `renewable_lcoe_per_kwh` | float | 0.0 | Levelized cost of energy for renewables (USD/kWh), from scenario config |

### 3.3 Output (`EnergyAllocation`)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `use_renewables` | bool | True | Whether to use PV/wind generation |
| `use_battery` | bool | True | Whether to use battery charge/discharge |
| `use_grid` | bool | True | Whether to import from / export to grid |
| `use_generator` | bool | True | Whether to use backup diesel generator |
| `battery_reserve_pct` | float | 0.10 | Minimum SOC to keep in reserve (0-1) |
| `max_grid_import_pct` | float | 1.0 | Max fraction of demand from grid (1.0 = unlimited) |
| `prefer_grid_over_generator` | bool | True | Grid before generator in merit order? |
| `allow_grid_export` | bool | True | Can sell excess generation to grid? |
| `policy_name` | str | "" | Name of the policy that produced this allocation |
| `decision_reason` | str | "" | Human-readable explanation of the dispatch strategy |

### 3.4 Policy Implementations

#### 3.4.1 PvFirstBatteryGridDiesel

**Class Name:** `PvFirstBatteryGridDiesel`
**Internal Name:** `pv_first_battery_grid_diesel`
**Scenario Names:** `all_renewable`, `hybrid`

**Purpose:** Standard renewable-first merit order: PV -> Wind -> Battery -> Grid -> Diesel. Prioritizes renewable energy, uses battery to smooth supply, grid as backup, generator as last resort. Keeps a 20% battery reserve for evening/nighttime demand. Allows grid export of surplus renewable generation.

**Pseudocode:**
```
FUNCTION allocate_energy(ctx):
    RETURN EnergyAllocation(
        use_renewables = TRUE,
        use_battery = TRUE,
        use_grid = TRUE,
        use_generator = TRUE,
        battery_reserve_pct = 0.20,  // Keep 20% reserve
        max_grid_import_pct = 1.0,   // Unlimited grid import
        prefer_grid_over_generator = TRUE,
        allow_grid_export = TRUE,
        policy_name = "pv_first_battery_grid_diesel",
        decision_reason = "Merit order: renewables → battery → grid → diesel"
    )
END FUNCTION
```

#### 3.4.2 GridFirst

**Class Name:** `GridFirst`
**Internal Name:** `grid_first`
**Scenario Name:** `all_grid`

**Purpose:** Always use grid when available, renewables and battery disabled. Relies on grid as primary source with generator as emergency backup only. Does not use renewables or battery — represents a community that hasn't invested in on-site generation. No grid export (not producing surplus to sell).

**Pseudocode:**
```
FUNCTION allocate_energy(ctx):
    RETURN EnergyAllocation(
        use_renewables = FALSE,
        use_battery = FALSE,
        use_grid = TRUE,
        use_generator = TRUE,  // Emergency backup only
        battery_reserve_pct = 0.0,
        max_grid_import_pct = 1.0,
        prefer_grid_over_generator = TRUE,
        allow_grid_export = FALSE,  // Not producing surplus
        policy_name = "grid_first",
        decision_reason = "Grid primary, generator backup"
    )
END FUNCTION
```

#### 3.4.3 CheapestEnergy

**Class Name:** `CheapestEnergy`
**Internal Name:** `cheapest_energy`
**Scenario Name:** `cost_minimize`

**Purpose:** Dynamic selection based on current costs. Arbitrage between sources. Compares the renewable LCOE to the current grid price each period. If the grid is cheaper than renewables, signals grid-first dispatch; otherwise uses the standard renewable-first merit order. Always uses battery when it saves money and exports to grid when profitable.

**Helper Method:**
- `get_parameters()`: Returns `{"strategy": "dynamic_cost_comparison"}`

**Pseudocode:**
```
FUNCTION allocate_energy(ctx):
    IF ctx.grid_price_per_kwh < ctx.renewable_lcoe_per_kwh:
        // Grid is cheaper - prefer grid, use renewables for battery/export
        RETURN EnergyAllocation(
            use_renewables = TRUE,  // Still enabled for charging battery / export
            use_battery = TRUE,
            use_grid = TRUE,
            use_generator = TRUE,
            battery_reserve_pct = 0.10,  // Lower reserve when grid is cheap
            max_grid_import_pct = 1.0,
            prefer_grid_over_generator = TRUE,
            allow_grid_export = TRUE,
            policy_name = "cheapest_energy",
            decision_reason = "Grid cheaper ({grid_price:.3f}) than LCOE ({lcoe:.3f}), prefer grid"
        )
    ELSE:
        // Renewables cheaper - standard merit order
        RETURN EnergyAllocation(
            use_renewables = TRUE,
            use_battery = TRUE,
            use_grid = TRUE,
            use_generator = TRUE,
            battery_reserve_pct = 0.15,  // Higher reserve when using renewables
            max_grid_import_pct = 1.0,
            prefer_grid_over_generator = TRUE,
            allow_grid_export = TRUE,
            policy_name = "cheapest_energy",
            decision_reason = "LCOE ({lcoe:.3f}) <= grid ({grid_price:.3f}), prefer renewables"
        )
    END IF
END FUNCTION
```

### 3.5 Registry and Factory

**Policy Registry:**

```python
ENERGY_POLICIES = {
    "all_renewable": PvFirstBatteryGridDiesel,
    "hybrid": PvFirstBatteryGridDiesel,  # Same as all_renewable for now
    "all_grid": GridFirst,
    "cost_minimize": CheapestEnergy,
}
```

**Factory Function:**

```python
def get_energy_policy(name, **kwargs):
    """Get an energy policy instance by name.

    Args:
        name: Policy name as string (e.g., "all_renewable", "cost_minimize")
        **kwargs: Parameters to pass to policy constructor

    Returns:
        Instantiated policy object

    Raises:
        ValueError: If policy name not found
    """
```

**Base Class Methods:**

All energy policies inherit from `BaseEnergyPolicy` which provides:

- `allocate_energy(ctx: EnergyPolicyContext) -> EnergyAllocation` - Main decision method (must be implemented)
- `get_parameters() -> dict` - Returns policy parameters for serialization
- `describe() -> str` - Returns human-readable policy description

---

## 4. Food Processing Policies

**Location:** `src/policies/food_policies.py`

**Purpose:** Determine how harvested crops are allocated across processing pathways (fresh, packaged, canned, dried).

### 4.0 Implementation Status

| Component | Status | Notes |
|-----------|--------|-------|
| `FoodProcessingContext` dataclass | Implemented | Context with harvest, pricing, and capacity info |
| `ProcessingAllocation` dataclass | Implemented | Output with fraction allocations |
| `BaseFoodPolicy` base class | Implemented | Abstract base with `allocate()` method |
| `AllFresh` policy | Implemented + Integrated | Default behavior, backward compatible |
| `MaximizeStorage` policy | Implemented + Integrated | Fixed allocation favoring shelf life |
| `Balanced` policy | Implemented + Integrated | 50/20/15/15 split |
| `MarketResponsive` policy | Implemented + Integrated | Dynamic based on fresh prices |
| `get_food_policy()` factory | Implemented | Lookup by name with kwargs |
| `FOOD_POLICIES` registry | Implemented | Maps names to policy classes |
| **Simulation integration** | **Yes** | Called via `process_harvests()` in `simulation.py` |

**Integration Details:**
- Food policies are instantiated during scenario loading when `farm_config.food_policy` is set
- Called in `process_harvests()` function during daily simulation loop
- When no policy is configured, defaults to `AllFresh` behavior (100% fresh sale)
- Allocation fractions are applied to daily harvest yield

**Summary Table:**

| Policy | Fresh | Packaged | Canned | Dried |
|--------|-------|----------|--------|-------|
| `all_fresh` | 100% | 0% | 0% | 0% |
| `maximize_storage` | 20% | 10% | 35% | 35% |
| `balanced` | 50% | 20% | 15% | 15% |
| `market_responsive` | 30-65% | 15-20% | 10-25% | 10-25% |

Note: `market_responsive` shifts toward processing when fresh prices fall below 80% of reference farmgate prices.

### 4.1 Context and Output Dataclasses

**Context Input (`FoodProcessingContext`):**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `harvest_yield_kg` | float | (required) | Total harvest yield before processing (kg) |
| `crop_name` | str | (required) | Name of crop being processed |
| `fresh_price_per_kg` | float | (required) | Current fresh farmgate price (USD/kg) |
| `fresh_packaging_capacity_kg` | float | `inf` | Daily fresh packaging capacity limit (kg) |
| `drying_capacity_kg` | float | `inf` | Daily drying capacity limit (kg) |
| `canning_capacity_kg` | float | `inf` | Daily canning capacity limit (kg) |
| `packaging_capacity_kg` | float | `inf` | Daily packaging capacity limit (kg) |

Note: Capacity limits default to `float('inf')` when not specified, meaning no constraint is applied.

**Output (`ProcessingAllocation`):**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `fresh_fraction` | float | `1.0` | Fraction sold as fresh produce (0-1) |
| `packaged_fraction` | float | `0.0` | Fraction sent to fresh packaging (0-1) |
| `canned_fraction` | float | `0.0` | Fraction sent to canning (0-1) |
| `dried_fraction` | float | `0.0` | Fraction sent to drying (0-1) |
| `policy_name` | str | `""` | Name of the policy that produced this allocation |

**Constraint:** Fractions must sum to 1.0

### 4.2 Base Class and Factory

**BaseFoodPolicy:**
```python
class BaseFoodPolicy:
    name: str = "base"

    def allocate(self, ctx: FoodProcessingContext) -> ProcessingAllocation:
        """Allocate harvest across processing pathways.

        Args:
            ctx: FoodProcessingContext with harvest and pricing info

        Returns:
            ProcessingAllocation with fractions for each pathway
        """
        raise NotImplementedError
```

**Registry:**
```python
FOOD_POLICIES = {
    "all_fresh": AllFresh,
    "maximize_storage": MaximizeStorage,
    "balanced": Balanced,
    "market_responsive": MarketResponsive,
}
```

**Factory Function:**
```python
def get_food_policy(name, **kwargs):
    """Get a food processing policy instance by name.

    Args:
        name: Policy name (e.g., "all_fresh", "balanced")
        **kwargs: Parameters to pass to policy constructor

    Returns:
        Instantiated policy object

    Raises:
        KeyError: If policy name not found
    """
```

### 4.3 AllFresh

**Policy Name:** `all_fresh`

**Purpose:** 100% fresh sale — no processing. This is the default policy and must produce identical revenue to the pre-food-processing code path (backward compatible).

**Pseudocode:**
```
FUNCTION allocate(ctx):
    RETURN ProcessingAllocation(
        fresh_fraction = 1.0,
        packaged_fraction = 0.0,
        canned_fraction = 0.0,
        dried_fraction = 0.0,
        policy_name = "all_fresh"
    )
END FUNCTION
```

### 4.4 MaximizeStorage

**Policy Name:** `maximize_storage`

**Purpose:** Maximize shelf life by processing most of harvest. Sends only 20% to fresh sale; the rest is split between dried (35%), canned (35%), and packaged (10%) for long-term storage.

**Pseudocode:**
```
FUNCTION allocate(ctx):
    RETURN ProcessingAllocation(
        fresh_fraction = 0.20,       // 20% fresh
        packaged_fraction = 0.10,    // 10% packaged
        canned_fraction = 0.35,      // 35% canned
        dried_fraction = 0.35,       // 35% dried
        policy_name = "maximize_storage"
    )
END FUNCTION
```

### 4.5 Balanced

**Policy Name:** `balanced`

**Purpose:** Balanced mix of fresh and processed per mvp-calculations.md specifications. Provides a moderate level of value-add processing while keeping half the harvest for immediate fresh sale.

**Pseudocode:**
```
FUNCTION allocate(ctx):
    RETURN ProcessingAllocation(
        fresh_fraction = 0.50,       // 50% fresh
        packaged_fraction = 0.20,    // 20% packaged
        canned_fraction = 0.15,      // 15% canned
        dried_fraction = 0.15,       // 15% dried
        policy_name = "balanced"
    )
END FUNCTION
```

### 4.6 MarketResponsive

**Policy Name:** `market_responsive`

**Purpose:** Adjust processing mix based on current fresh prices. When fresh prices are below 80% of reference farmgate prices, shifts more harvest into processing (higher value-add pathways). When prices are normal or high, sells more fresh.

**Reference Prices (USD/kg):**
```python
REFERENCE_PRICES = {
    "tomato": 0.30,
    "potato": 0.25,
    "onion": 0.20,
    "kale": 0.40,
    "cucumber": 0.35,
}
# Default fallback for unknown crops: 0.30
```

**Pseudocode:**
```
FUNCTION allocate(ctx):
    ref_price = REFERENCE_PRICES.get(ctx.crop_name, 0.30)  // Default 0.30 if crop not found

    IF ctx.fresh_price_per_kg < ref_price * 0.80:
        // Low prices - process more to capture value-add
        RETURN ProcessingAllocation(
            fresh_fraction = 0.30,
            packaged_fraction = 0.20,
            canned_fraction = 0.25,
            dried_fraction = 0.25,
            policy_name = "market_responsive"
        )
    ELSE:
        // Normal/high prices - sell more fresh
        RETURN ProcessingAllocation(
            fresh_fraction = 0.65,
            packaged_fraction = 0.15,
            canned_fraction = 0.10,
            dried_fraction = 0.10,
            policy_name = "market_responsive"
        )
    END IF
END FUNCTION
```

---

## 5. Crop Management Policies

**Location:** `src/policies/crop_policies.py`

**Purpose:** Determine irrigation demand adjustments based on crop conditions and growth stage.

### Implementation Status

| Component | Status | Notes |
|-----------|--------|-------|
| `CropPolicyContext` dataclass | Implemented | Full input context for policy decisions |
| `CropDecision` dataclass | Implemented | Decision output with multiplier tracking |
| `BaseCropPolicy` base class | Implemented | `decide()`, `get_parameters()`, `describe()` methods |
| `FixedSchedule` policy | Implemented | Apply full demand every day |
| `DeficitIrrigation` policy | Implemented | Stage-based water reduction (80%/72%) |
| `WeatherAdaptive` policy | Implemented | Temperature-responsive adjustment |
| `get_crop_policy()` factory | Implemented | Registry lookup with kwargs |
| **Simulation integration** | **Not integrated** | Policies not called in simulation loop |

**Integration requirement:** Currently, irrigation demand is used directly from precomputed Layer 1 data without policy adjustment. To integrate, call the crop policy before `calculate_farm_demand()` or apply the returned multiplier to the base demand before passing to the water policy.

### Policy Summary

| Policy | Behavior |
|--------|----------|
| `fixed_schedule` | Apply full standard irrigation demand every day |
| `deficit_irrigation` | Reduce water to 80% during mid-season, 72% during late season; full water during establishment |
| `weather_adaptive` | +15% above 40°C, +5% above 35°C, -15% below 20°C |

### Context and Output Dataclasses

**Context Input (`CropPolicyContext`):**
- `crop_name` (str, default=""): Name of crop
- `growth_stage` (str, default=""): Current stage ("initial", "development", "mid_season", "late_season")
- `days_since_planting` (int, default=0): Days since planting
- `total_growing_days` (int, default=0): Total days in growing cycle
- `base_demand_m3` (float, default=0.0): Standard irrigation demand for today (m³)
- `water_stress_ratio` (float, default=1.0): Cumulative water received / expected water (0-1)
- `soil_moisture_estimate` (float, default=0.5): Soil moisture estimate 0-1 (unused for now)
- `temperature_c` (float, default=25.0): Ambient temperature (°C)
- `available_water_m3` (float, default=inf): How much water is available today (m³)

**Output (`CropDecision`):**
- `adjusted_demand_m3` (float, default=0.0): How much water to request (m³)
- `demand_multiplier` (float, default=1.0): Multiplier applied to base demand (for tracking)
- `priority` (float, default=1.0): Crop priority (higher = more important to water)
- `decision_reason` (str, default=""): Human-readable explanation
- `policy_name` (str, default=""): Policy identifier

### Base Class

**`BaseCropPolicy`** defines the interface:
- `name`: Class attribute for policy identification
- `decide(ctx: CropPolicyContext) -> CropDecision`: Main decision method (abstract)
- `get_parameters() -> dict`: Return configurable parameters (default: empty dict)
- `describe() -> str`: Return human-readable policy description

### 5.1 FixedSchedule

**Policy Name:** `fixed_schedule`

**Purpose:** Apply full standard irrigation demand every day, regardless of conditions.

**Pseudocode:**
```
FUNCTION decide(ctx):
    RETURN CropDecision(
        adjusted_demand_m3 = ctx.base_demand_m3,
        demand_multiplier = 1.0,
        priority = 1.0,
        decision_reason = "Fixed schedule: full irrigation demand",
        policy_name = "fixed_schedule"
    )
END FUNCTION
```

### 5.2 DeficitIrrigation

**Policy Name:** `deficit_irrigation`

**Purpose:** Apply controlled water deficit during less sensitive growth stages.

**Parameters:**
- `deficit_fraction` (float, default=0.80): Fraction of full demand during deficit periods

**Pseudocode:**
```
FUNCTION decide(ctx):
    IF ctx.growth_stage == "mid_season":
        multiplier = deficit_fraction
        reason = "Deficit irrigation at " + deficit_fraction + " during mid-season"
    ELSE IF ctx.growth_stage == "late_season":
        multiplier = deficit_fraction * 0.9  // Even less in late season
        reason = "Deficit irrigation at " + (deficit_fraction * 0.9) + " during late season"
    ELSE:
        // Full water during initial establishment and development
        multiplier = 1.0
        reason = "Full irrigation during " + ctx.growth_stage
    END IF
    
    RETURN CropDecision(
        adjusted_demand_m3 = ctx.base_demand_m3 * multiplier,
        demand_multiplier = multiplier,
        priority = 1.0,
        decision_reason = reason,
        policy_name = "deficit_irrigation"
    )
END FUNCTION
```

### 5.3 WeatherAdaptive

**Policy Name:** `weather_adaptive`

**Purpose:** Adjust irrigation based on temperature conditions.

**Pseudocode:**
```
FUNCTION decide(ctx):
    IF ctx.temperature_c > 40:
        multiplier = 1.15  // 15% extra on extreme heat days
        reason = "Heat stress adjustment: +15% (T=" + ctx.temperature_c + "°C)"
    ELSE IF ctx.temperature_c > 35:
        multiplier = 1.05  // 5% extra on hot days
        reason = "Warm day adjustment: +5% (T=" + ctx.temperature_c + "°C)"
    ELSE IF ctx.temperature_c < 20:
        multiplier = 0.85  // 15% less on cool days
        reason = "Cool day adjustment: -15% (T=" + ctx.temperature_c + "°C)"
    ELSE:
        multiplier = 1.0
        reason = "Normal irrigation (T=" + ctx.temperature_c + "°C)"
    END IF
    
    RETURN CropDecision(
        adjusted_demand_m3 = ctx.base_demand_m3 * multiplier,
        demand_multiplier = multiplier,
        priority = 1.0,
        decision_reason = reason,
        policy_name = "weather_adaptive"
    )
END FUNCTION
```

### Factory and Registry

**Registry (`CROP_POLICIES`):**
```python
CROP_POLICIES = {
    "fixed_schedule": FixedSchedule,
    "deficit_irrigation": DeficitIrrigation,
    "weather_adaptive": WeatherAdaptive,
}
```

**Factory Function:**
```
FUNCTION get_crop_policy(name, **kwargs):
    IF name NOT IN CROP_POLICIES:
        RAISE ValueError("Unknown crop policy: " + name)
    END IF
    RETURN CROP_POLICIES[name](**kwargs)
END FUNCTION
```

**Usage Example:**
```python
# Get policy instance
policy = get_crop_policy("deficit_irrigation", deficit_fraction=0.75)

# Create context from simulation state
ctx = CropPolicyContext(
    crop_name="tomato",
    growth_stage="mid_season",
    base_demand_m3=50.0,
    temperature_c=38.0,
)

# Get decision
decision = policy.decide(ctx)
# decision.adjusted_demand_m3 = 37.5 (50.0 * 0.75)
```

---

## 6. Economic Policies

**Location:** `src/policies/economic_policies.py`

**Purpose:** Determine spending limits, reserve targets, and investment approval based on financial position.

### Implementation Status

| Component | Status | Notes |
|-----------|--------|-------|
| `EconomicPolicyContext` dataclass | Implemented | Full input context for policy decisions |
| `EconomicDecision` dataclass | Implemented | Decision output with spending limits and flags |
| `BaseEconomicPolicy` base class | Implemented | `decide()`, `get_parameters()`, `describe()` methods |
| `Balanced` policy | Implemented | Adaptive risk based on reserve levels |
| `AggressiveGrowth` policy | Implemented | Minimal reserves, maximize reinvestment |
| `Conservative` policy | Implemented | High reserves, limit spending when low |
| `RiskAverse` policy | Implemented | Maximum caution, large reserves |
| `get_economic_policy()` factory | Implemented | Registry lookup with kwargs |
| **Simulation integration** | **Not integrated** | Policies not called in simulation loop |

**Integration requirement:** Currently, year-boundary economic updates use a simple `cash += revenue - costs` calculation. To integrate, call the economic policy at year boundaries (or monthly) and use its output to:
- Constrain operational spending via `max_spending_usd`
- Trigger inventory liquidation via `sell_inventory` flag (requires market policy coordination)
- Gate capital expenditure decisions via `investment_allowed` flag

**Prerequisites for integration:**
- Per-farm P&L tracking (revenue, costs by category)
- `months_of_reserves` calculation (cash / average monthly operating costs)
- Community pooling mechanism (if financial decisions are aggregated)

### Policy Summary

| Policy | Reserve Target | Investment Allowed | Spending Limit | Inventory |
|--------|---------------|-------------------|----------------|-----------|
| `balanced` | 3 months | When reserves > target | Unlimited | Sell if reserves < 1 month |
| `aggressive_growth` | 1 month | When reserves > 0.5 months | Unlimited | Always sell |
| `conservative` | 6 months | When reserves > 9 months | 50% of revenue when low | Hold |
| `risk_averse` | 6+ months | Only with 12+ months reserves | Essential payments only when critical | Always sell |

### Context and Output Dataclasses

**Context Input (`EconomicPolicyContext`):**
- `cash_reserves_usd` (float, default=0.0): Current cash on hand
- `monthly_revenue_usd` (float, default=0.0): Revenue this period
- `monthly_operating_cost_usd` (float, default=0.0): Operating costs this period
- `total_debt_usd` (float, default=0.0): Outstanding debt principal
- `debt_service_monthly_usd` (float, default=0.0): Required monthly debt payment
- `crop_inventory_kg` (float, default=0.0): Current stored/unsold inventory
- `months_of_reserves` (float, default=0.0): Cash / average monthly costs
- `current_month` (int, default=1): Current month (1-12)

**Output (`EconomicDecision`):**
- `max_spending_usd` (float, default=inf): Spending limit this period
- `reserve_target_months` (float, default=3.0): Target months of cash reserves
- `investment_allowed` (bool, default=True): Whether to approve new investments
- `sell_inventory` (bool, default=False): Whether to sell stored inventory now
- `spending_priority` (str, default="maintenance"): Priority ("maintenance", "growth", "survival")
- `decision_reason` (str, default=""): Human-readable rationale
- `policy_name` (str, default=""): Policy identifier

### Base Class

**`BaseEconomicPolicy`** defines the interface:
- `name`: Class attribute for policy identification
- `decide(ctx: EconomicPolicyContext) -> EconomicDecision`: Main decision method (abstract)
- `get_parameters() -> dict`: Return configurable parameters (default: empty dict)
- `describe() -> str`: Return human-readable policy description

### 6.1 Balanced

**Policy Name:** `balanced`

**Purpose:** Adaptive risk based on current financial position.

**Pseudocode:**
```
FUNCTION decide(ctx):
    reserve_target = 3.0  // 3 months target
    investment_ok = ctx.months_of_reserves > reserve_target
    
    IF ctx.months_of_reserves < 1.0:
        priority = "survival"
        reason = "Low reserves (" + ctx.months_of_reserves + " months), survival mode"
    ELSE IF ctx.months_of_reserves < reserve_target:
        priority = "maintenance"
        reason = "Building reserves (" + ctx.months_of_reserves + "/" + reserve_target + " months target)"
    ELSE:
        priority = IF investment_ok THEN "growth" ELSE "maintenance"
        reason = "Healthy reserves (" + ctx.months_of_reserves + " months), balanced approach"
    END IF
    
    RETURN EconomicDecision(
        reserve_target_months = reserve_target,
        investment_allowed = investment_ok,
        sell_inventory = ctx.months_of_reserves < 1.0,
        spending_priority = priority,
        decision_reason = reason,
        policy_name = "balanced"
    )
END FUNCTION
```

### 6.2 AggressiveGrowth

**Policy Name:** `aggressive_growth`

**Purpose:** Hold minimal reserves, maximize reinvestment.

**Parameters:**
- `min_cash_months` (int, default=1): Minimum cash reserve target
- `max_inventory_months` (int, default=6): Maximum inventory holding period

**Pseudocode:**
```
FUNCTION decide(ctx):
    reserve_target = min_cash_months
    investment_ok = ctx.months_of_reserves > 0.5
    
    // Sell inventory aggressively to free up capital
    sell = ctx.crop_inventory_kg > 0
    
    RETURN EconomicDecision(
        reserve_target_months = reserve_target,
        investment_allowed = investment_ok,
        sell_inventory = sell,
        spending_priority = "growth",
        decision_reason = "Aggressive: " + min_cash_months + " month reserve target, invest everything above",
        policy_name = "aggressive_growth"
    )
END FUNCTION
```

### 6.3 Conservative

**Policy Name:** `conservative`

**Purpose:** Maintain high cash reserves, limit spending when low.

**Parameters:**
- `min_cash_months` (int, default=6): Minimum cash reserve target

**Pseudocode:**
```
FUNCTION decide(ctx):
    reserve_target = min_cash_months
    investment_ok = ctx.months_of_reserves > reserve_target * 1.5
    
    IF ctx.months_of_reserves < reserve_target:
        max_spend = ctx.monthly_revenue_usd * 0.5  // Cap spending at 50% of revenue
        reason = "Conservative: under " + reserve_target + " months reserves, limiting spending"
    ELSE:
        max_spend = INFINITY
        reason = "Conservative: " + ctx.months_of_reserves + " months reserves, adequate"
    END IF
    
    RETURN EconomicDecision(
        max_spending_usd = max_spend,
        reserve_target_months = reserve_target,
        investment_allowed = investment_ok,
        sell_inventory = FALSE,
        spending_priority = "maintenance",
        decision_reason = reason,
        policy_name = "conservative"
    )
END FUNCTION
```

### 6.4 RiskAverse

**Policy Name:** `risk_averse`

**Purpose:** Maximum caution, build large reserves, minimize risk.

**Parameters:**
- `min_cash_months` (int, default=3): Minimum cash reserve (but policy enforces at least 6)

**Pseudocode:**
```
FUNCTION decide(ctx):
    reserve_target = MAX(min_cash_months, 6.0)  // At least 6 months always
    investment_ok = ctx.months_of_reserves > 12.0  // Only invest with 12+ months
    
    // Sell inventory immediately to lock in revenue
    sell = ctx.crop_inventory_kg > 0
    
    IF ctx.months_of_reserves < 3.0:
        max_spend = ctx.debt_service_monthly_usd * 1.2  // Only essential payments
        reason = "Risk averse: critically low reserves (" + ctx.months_of_reserves + " months)"
    ELSE:
        max_spend = INFINITY
        reason = "Risk averse: " + ctx.months_of_reserves + " months reserves, target " + reserve_target
    END IF
    
    RETURN EconomicDecision(
        max_spending_usd = max_spend,
        reserve_target_months = reserve_target,
        investment_allowed = investment_ok,
        sell_inventory = sell,
        spending_priority = IF ctx.months_of_reserves < 3 THEN "survival" ELSE "maintenance",
        decision_reason = reason,
        policy_name = "risk_averse"
    )
END FUNCTION
```

### Factory and Registry

**Registry (`ECONOMIC_POLICIES`):**
```python
ECONOMIC_POLICIES = {
    "balanced": Balanced,
    "aggressive_growth": AggressiveGrowth,
    "conservative": Conservative,
    "risk_averse": RiskAverse,
}
```

**Factory Function:**
```
FUNCTION get_economic_policy(name, **kwargs):
    IF name NOT IN ECONOMIC_POLICIES:
        RAISE ValueError("Unknown economic policy: " + name)
    END IF
    RETURN ECONOMIC_POLICIES[name](**kwargs)
END FUNCTION
```

**Usage Example:**
```python
# Get policy instance
policy = get_economic_policy("conservative", min_cash_months=6)

# Create context from simulation state
ctx = EconomicPolicyContext(
    cash_reserves_usd=50000.0,
    monthly_operating_cost_usd=10000.0,
    months_of_reserves=5.0,
    crop_inventory_kg=1000.0,
)

# Get decision
decision = policy.decide(ctx)
# decision.investment_allowed = False (5.0 < 6 * 1.5 = 9.0)
# decision.max_spending_usd = 5000.0 (50% of revenue when low)
```

---

## 7. Market/Sales Policies

**Location:** `src/policies/market_policies.py`

**Purpose:** Determine when to sell crops, hold in storage, or send to processing.

### 7.0 Implementation Status

| Component | Status | Notes |
|---|---|---|
| `MarketPolicyContext` dataclass | Implemented | All 9 context fields defined with defaults |
| `MarketDecision` dataclass | Implemented | All 6 output fields defined with defaults |
| `BaseMarketPolicy` base class | Implemented | `decide()`, `get_parameters()`, `describe()` methods |
| `SellImmediately` policy | Implemented | No parameters, always sells 100% |
| `HoldForPeak` policy | Implemented | `price_threshold_multiplier` parameter (default 1.20) |
| `ProcessWhenLow` policy | Implemented | `price_floor_multiplier` parameter (default 0.80) |
| `AdaptiveMarketing` policy | Implemented | No parameters, uses hardcoded thresholds |
| `MARKET_POLICIES` registry | Implemented | Dict mapping names to classes |
| `get_market_policy()` factory | Implemented | Raises `ValueError` for unknown policies |
| Integration in simulation loop | **Not implemented** | Crops are sold immediately at harvest |

**Integration Requirements:**

Currently, the `process_harvests()` function in `simulation.py` sells harvested crops immediately at the current farmgate price. Food processing policies ARE integrated (determining fresh/packaged/canned/dried split), but market timing policies are NOT called. To integrate market policies:

1. **Inventory tracking state** - Requires new state fields for stored quantities, days in storage, and spoilage tracking (not yet in `FarmState` or `CropState`)
2. **Price trend calculation** - Requires rolling average and trend computation from historical prices
3. **Storage infrastructure** - Storage capacity needs to be defined per farm in scenario configuration
4. **Daily inventory loop** - Simulation needs a daily check for stored inventory decisions, separate from harvest processing

**Policy Summary:**

| Policy | Behavior |
|---|---|
| `sell_immediately` | Sell 100% at harvest at current market price |
| `hold_for_peak` | Hold in storage if price < 1.2x average; sell when price rises or shelf life expires |
| `process_when_low` | Send to processing if price < 0.8x average; sell fresh otherwise |
| `adaptive_marketing` | Dynamic mix: sell above average, hold if rising, process if well below average |

### 7.1 Context and Output Dataclasses

**Context Input (`MarketPolicyContext`):**

| Field | Type | Default | Description |
|---|---|---|---|
| `crop_name` | str | `""` | Crop to sell |
| `available_kg` | float | `0.0` | Harvest or inventory available |
| `current_price_per_kg` | float | `0.0` | Today's farmgate price |
| `avg_price_per_kg` | float | `0.0` | Average price this season |
| `price_trend` | float | `0.0` | Positive = rising, negative = falling |
| `days_in_storage` | int | `0` | How long crop has been stored |
| `shelf_life_days` | int | `7` | Fresh crop shelf life |
| `storage_capacity_kg` | float | `0.0` | Available storage space |
| `processing_capacity_kg` | float | `0.0` | Available processing capacity |

**Output (`MarketDecision`):**

| Field | Type | Default | Description |
|---|---|---|---|
| `sell_fraction` | float | `1.0` | Fraction to sell now (0-1) |
| `store_fraction` | float | `0.0` | Fraction to store (0-1) |
| `process_fraction` | float | `0.0` | Fraction to send to processing (0-1) |
| `target_price_per_kg` | float | `0.0` | Minimum acceptable price (0 = any price) |
| `decision_reason` | str | `""` | Human-readable rationale |
| `policy_name` | str | `""` | Policy identifier |

**Constraint:** Fractions (sell + store + process) should sum to approximately 1.0.

### 7.2 SellImmediately

**Policy Name:** `sell_immediately`

**Purpose:** Sell all production immediately at market price. No inventory risk.

**Pseudocode:**
```
FUNCTION decide(ctx):
    RETURN MarketDecision(
        sell_fraction = 1.0,
        store_fraction = 0.0,
        process_fraction = 0.0,
        decision_reason = "Sell immediately at market price",
        policy_name = "sell_immediately"
    )
END FUNCTION
```

### 7.3 HoldForPeak

**Policy Name:** `hold_for_peak`

**Purpose:** Hold inventory waiting for price above threshold. Risk spoilage.

**Parameters:**
- `price_threshold_multiplier` (float, default=1.20): Wait for price > average × multiplier

**Pseudocode:**
```
FUNCTION decide(ctx):
    target_price = ctx.avg_price_per_kg * price_threshold_multiplier
    
    IF ctx.current_price_per_kg >= target_price:
        // Price is above target -- sell now
        RETURN MarketDecision(
            sell_fraction = 1.0,
            target_price_per_kg = target_price,
            decision_reason = "Price $" + ctx.current_price_per_kg + " >= target $" + target_price + ", selling",
            policy_name = "hold_for_peak"
        )
    ELSE IF ctx.days_in_storage >= ctx.shelf_life_days - 1:
        // About to spoil -- sell at any price
        RETURN MarketDecision(
            sell_fraction = 1.0,
            decision_reason = "Storage limit reached (" + ctx.days_in_storage + " days), forced sale",
            policy_name = "hold_for_peak"
        )
    ELSE IF ctx.storage_capacity_kg > ctx.available_kg:
        // Store and wait for better price
        RETURN MarketDecision(
            sell_fraction = 0.0,
            store_fraction = 1.0,
            target_price_per_kg = target_price,
            decision_reason = "Price $" + ctx.current_price_per_kg + " < target $" + target_price + ", storing",
            policy_name = "hold_for_peak"
        )
    ELSE:
        // No storage space -- sell now
        RETURN MarketDecision(
            sell_fraction = 1.0,
            decision_reason = "No storage capacity, selling at current price",
            policy_name = "hold_for_peak"
        )
    END IF
END FUNCTION
```

### 7.4 ProcessWhenLow

**Policy Name:** `process_when_low`

**Purpose:** Process fresh produce when prices are low. Preserves value, extends shelf life.

**Parameters:**
- `price_floor_multiplier` (float, default=0.80): Process when price < average × multiplier

**Pseudocode:**
```
FUNCTION decide(ctx):
    price_floor = ctx.avg_price_per_kg * price_floor_multiplier
    
    IF ctx.current_price_per_kg < price_floor AND ctx.processing_capacity_kg > 0:
        // Price is low -- process instead of selling fresh
        processable = MIN(ctx.available_kg, ctx.processing_capacity_kg)
        process_frac = processable / ctx.available_kg IF ctx.available_kg > 0 ELSE 0.0
        sell_frac = 1.0 - process_frac
        RETURN MarketDecision(
            sell_fraction = sell_frac,
            process_fraction = process_frac,
            decision_reason = "Low price $" + ctx.current_price_per_kg + " < floor $" + price_floor + ", processing " + process_frac,
            policy_name = "process_when_low"
        )
    ELSE:
        // Price is acceptable -- sell fresh
        RETURN MarketDecision(
            sell_fraction = 1.0,
            decision_reason = "Price $" + ctx.current_price_per_kg + " >= floor $" + price_floor + ", selling fresh",
            policy_name = "process_when_low"
        )
    END IF
END FUNCTION
```

### 7.5 AdaptiveMarketing

**Policy Name:** `adaptive_marketing`

**Purpose:** Combine immediate sales, holding, and processing based on conditions.

**Pseudocode:**
```
FUNCTION decide(ctx):
    IF ctx.current_price_per_kg > ctx.avg_price_per_kg * 1.10:
        // Above average -- sell everything
        RETURN MarketDecision(
            sell_fraction = 1.0,
            decision_reason = "Price above average, sell all",
            policy_name = "adaptive_marketing"
        )
    ELSE IF ctx.price_trend > 0 AND ctx.days_in_storage < ctx.shelf_life_days / 2:
        // Price is rising and we have storage time -- hold some
        store_frac = MIN(0.50, ctx.storage_capacity_kg / MAX(ctx.available_kg, 1))
        RETURN MarketDecision(
            sell_fraction = 1.0 - store_frac,
            store_fraction = store_frac,
            decision_reason = "Rising prices, holding " + store_frac + " in storage",
            policy_name = "adaptive_marketing"
        )
    ELSE IF ctx.current_price_per_kg < ctx.avg_price_per_kg * 0.85:
        // Well below average -- process if possible
        IF ctx.processing_capacity_kg > 0:
            process_frac = MIN(0.60, ctx.processing_capacity_kg / MAX(ctx.available_kg, 1))
            RETURN MarketDecision(
                sell_fraction = 1.0 - process_frac,
                process_fraction = process_frac,
                decision_reason = "Low price, processing " + process_frac,
                policy_name = "adaptive_marketing"
            )
        ELSE:
            RETURN MarketDecision(
                sell_fraction = 1.0,
                decision_reason = "Low price but no processing capacity, selling",
                policy_name = "adaptive_marketing"
            )
        END IF
    ELSE:
        // Normal price range -- sell now
        RETURN MarketDecision(
            sell_fraction = 1.0,
            decision_reason = "Normal price range, selling at $" + ctx.current_price_per_kg,
            policy_name = "adaptive_marketing"
        )
    END IF
END FUNCTION
```

### 7.6 Registry and Factory

**Policy Registry:**

```python
MARKET_POLICIES = {
    "sell_immediately": SellImmediately,
    "hold_for_peak": HoldForPeak,
    "process_when_low": ProcessWhenLow,
    "adaptive_marketing": AdaptiveMarketing,
}
```

**Factory Function:**

```python
def get_market_policy(name, **kwargs):
    """Get a market policy instance by name.

    Args:
        name: Policy name as string (e.g., "sell_immediately")
        **kwargs: Parameters to pass to policy constructor

    Returns:
        Instantiated policy object

    Raises:
        ValueError: If policy name not found
    """
```

**Base Class Methods:**

All market policies inherit from `BaseMarketPolicy` which provides:

- `decide(ctx: MarketPolicyContext) -> MarketDecision` - Main decision method (must be implemented)
- `get_parameters() -> dict` - Returns policy parameters for serialization
- `describe() -> str` - Returns human-readable policy description

---

## 8. Policy Integration

### 8.1 Policy Factory Pattern

All policies are instantiated via factory functions:

```python
# Water policies
water_policy = get_water_policy("cheapest_source", include_energy_cost=True)

# Energy policies
energy_policy = get_energy_policy("cost_minimize")

# Food policies
food_policy = get_food_policy("balanced")

# Crop policies
crop_policy = get_crop_policy("deficit_irrigation", deficit_fraction=0.80)

# Economic policies
economic_policy = get_economic_policy("conservative", min_cash_months=6)

# Market policies
market_policy = get_market_policy("hold_for_peak", price_threshold_multiplier=1.20)
```

### 8.2 Policy Execution Order

In the simulation loop, policies are called in this order:

1. **Crop Management Policy** → Determines irrigation demand adjustments
2. **Water Allocation Policy** → Allocates water sources (GW vs municipal)
3. **Energy Dispatch Policy** → Sets energy dispatch strategy parameters
4. **Food Processing Policy** → Allocates harvest across processing pathways
5. **Market Policy** → Determines when to sell/store/process crops
6. **Economic Policy** → Sets spending limits and investment approval

### 8.3 Policy Dependencies

- **Water policies** depend on energy availability (from energy dispatch)
- **Food processing policies** depend on processing capacity (from infrastructure config)
- **Market policies** depend on storage capacity and processing capacity
- **Economic policies** depend on revenue (from crop sales) and costs (from all systems)

### 8.4 Policy Metadata

All policies return metadata explaining their decisions:
- `decision_reason`: Human-readable explanation
- `policy_name`: Policy identifier for tracking
- `constraint_hit`: Which constraint limited allocation (water policies)
- `target_price_per_kg`: Price thresholds (market policies)

This metadata enables:
- Visualization of policy decision patterns
- Debugging of unexpected allocations
- Comparison of policy behaviors across scenarios

---

## 9. References

**Implementation Files:**
- `src/policies/water_policies.py` - Water allocation (5 policies)
- `src/policies/energy_policies.py` - Energy dispatch (3 policies)
- `src/policies/food_policies.py` - Food processing (4 policies)
- `src/policies/crop_policies.py` - Crop management (3 policies)
- `src/policies/economic_policies.py` - Economic strategy (4 policies)
- `src/policies/market_policies.py` - Market timing (4 policies)

**Related Documentation:**
- `mvp-structure.md` - Configuration schema and policy structure
- `mvp-calculations.md` - Calculation methodologies (formulas, parameters)
- `community-model-plan.md` - Complete model domain specifications

**Total Policies:** 23 policies across 6 domains
