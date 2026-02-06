# Settings Implementation Plan

## Overview

Create the `settings/` folder structure with a toy model scenario for comparative policy testing. The toy model uses 4 equal-sized farms, each with a different policy mix, enabling direct comparison of policy outcomes. This establishes Layer 2 (Design Layer) infrastructure for configuring simulations.

## Design Philosophy

- **4 farms, 4 policy sets**: Each farm operates under a distinct combination of policies, enabling comparative analysis
- **Equal farm sizes**: Removes farm size as a variable, isolating policy effects
- **Shared infrastructure**: All farms share community PV, battery, and water treatment systems
- **Policy differentiation**: Farms differentiated primarily by economic policy (risk tolerance), with water/energy policies potentially varying

## Deliverables

1. **Toy model scenario YAML** - 4-farm configuration with distinct policy assignments
2. **Water policy module** - Four functional policies for comparative testing
3. **Simple validation** - Basic checks that referenced data files exist

## File Structure

```
settings/
├── scenarios/
│   └── toy_4farm.yaml          # 4-farm comparative scenario
├── policies/
│   ├── __init__.py
│   ├── water_policies.py       # 4 water policies (functional)
│   ├── energy_policies.py      # Stub for future
│   ├── crop_policies.py        # Stub for future
│   ├── economic_policies.py    # Stub for future
│   └── market_policies.py      # Stub for future
├── validation.py               # Simple data file existence checks
└── README.md                   # Settings usage documentation
```

## Implementation Details

### 1. Toy Model Scenario (`settings/scenarios/toy_4farm.yaml`)

**Simulation config:**
- start_date: 2015-01-01 (matches price data availability)
- duration_years: 10 (2015-2024)
- weather_scenario: "001"

**Infrastructure (shared by all farms):**
- PV: 500 kW, medium density
- Battery: 1000 kWh (2x large LFP units)
- Wind: 0 kW (disabled for toy model)
- Water treatment: 2000 m³/day, moderate salinity (6500 ppm)
- Diesel backup: 100 kW

**Community structure:**
- 4 farms, equal size (125 ha each = 500 ha total)
- Equal yield factors (1.0)
- Equal starting capital
- Crops: tomato, potato, onion, kale, cucumber (same mix per farm)

**Farm policy assignments:**

| Farm | Economic Policy | Water Policy | Energy Policy |
|------|-----------------|--------------|---------------|
| Farm 1 | conservative | always_groundwater | pv_first (stub) |
| Farm 2 | moderate | always_municipal | pv_first (stub) |
| Farm 3 | aggressive | cheapest_source | pv_first (stub) |
| Farm 4 | balanced | conserve_groundwater | pv_first (stub) |

**Economic parameters:**
- discount_rate: 6%
- debt_principal: $500,000 (shared)
- debt_term: 15 years
- interest_rate: 4.5%

### 2. Water Policies (`settings/policies/water_policies.py`)

Four functional policies for comparative testing. All policies share:
- Common interface: `allocate_water(demand_m3, context) -> WaterAllocation`
- Energy constraint checking: If insufficient energy for treatment, shift to municipal
- Municipal water always available on demand (modeling assumption)

**Policy 1: AlwaysGroundwater**
```
Use groundwater for 100% of demand.
Energy constraint: If energy unavailable for treatment, fall back to municipal.

Parameters: None
Logic:
  required_energy = demand_m3 * treatment_kwh_per_m3
  if available_energy >= required_energy:
      return (demand_m3, 0)  # all groundwater
  else:
      treatable = available_energy / treatment_kwh_per_m3
      return (treatable, demand_m3 - treatable)  # remainder from municipal
```

**Policy 2: AlwaysMunicipal**
```
Use municipal water for 100% of demand.
No energy required for treatment.

Parameters: None
Logic:
  return (0, demand_m3)  # all municipal
```

**Policy 3: CheapestSource**
```
Select water source based on current cost comparison.
Dynamically switches based on daily prices.

Parameters:
  - include_energy_cost: True (add treatment energy to GW cost)

Logic:
  gw_cost_per_m3 = (treatment_kwh_per_m3 * energy_price) + gw_maintenance_per_m3
  municipal_cost_per_m3 = municipal_price

  if gw_cost_per_m3 < municipal_cost_per_m3:
      # prefer groundwater if cheaper
      required_energy = demand_m3 * treatment_kwh_per_m3
      if available_energy >= required_energy:
          return (demand_m3, 0)
      else:
          treatable = available_energy / treatment_kwh_per_m3
          return (treatable, demand_m3 - treatable)
  else:
      return (0, demand_m3)  # municipal is cheaper
```

**Policy 4: ConserveGroundwater**
```
Prefer municipal water to conserve aquifer.
Only use groundwater when municipal price exceeds threshold.

Parameters:
  - price_threshold_multiplier: 1.5 (use GW only if municipal > 1.5x GW cost)
  - max_gw_ratio: 0.30 (never exceed 30% groundwater even if cheaper)

Logic:
  gw_cost_per_m3 = (treatment_kwh_per_m3 * energy_price) + gw_maintenance_per_m3

  if municipal_price > gw_cost_per_m3 * price_threshold_multiplier:
      # municipal is expensive, use some groundwater
      gw_demand = min(demand_m3 * max_gw_ratio, demand_m3)
      required_energy = gw_demand * treatment_kwh_per_m3
      if available_energy >= required_energy:
          return (gw_demand, demand_m3 - gw_demand)
      else:
          treatable = available_energy / treatment_kwh_per_m3
          return (treatable, demand_m3 - treatable)
  else:
      return (0, demand_m3)  # use municipal to conserve aquifer
```

**Common interface:**

```python
class WaterAllocation:
    groundwater_m3: float
    municipal_m3: float
    energy_used_kwh: float
    cost_usd: float

class WaterPolicyContext:
    demand_m3: float
    available_energy_kwh: float
    treatment_kwh_per_m3: float
    gw_maintenance_per_m3: float
    municipal_price_per_m3: float
    energy_price_per_kwh: float

class BaseWaterPolicy:
    name: str

    def allocate_water(self, context: WaterPolicyContext) -> WaterAllocation
    def get_parameters(self) -> dict
    def describe(self) -> str
```

### 3. Simple Validation (`settings/validation.py`)

Basic existence checks:

```python
def validate_scenario(scenario_path):
    """Check that all referenced data files exist."""
    # Load YAML
    # For each data_files reference, check os.path.exists()
    # For each precomputed reference, check files exist
    # Return list of missing files (empty = valid)
```

### 4. Policy Stubs

Other policy modules as placeholders with interface:

```python
class PvFirstBatteryGridDiesel:
    """Energy dispatch priority: PV -> Battery -> Grid -> Diesel"""
    name = "pv_first_battery_grid_diesel"

    def allocate_energy(self, demand_kwh, pv_available, battery_soc, ...):
        raise NotImplementedError("Energy policy implementation pending")
```

## Critical Files to Create

| File | Purpose |
|------|---------|
| settings/scenarios/toy_4farm.yaml | 4-farm comparative scenario |
| settings/policies/__init__.py | Policy module exports |
| settings/policies/water_policies.py | 4 functional water policies |
| settings/policies/energy_policies.py | Stub |
| settings/policies/crop_policies.py | Stub |
| settings/policies/economic_policies.py | Stub |
| settings/policies/market_policies.py | Stub |
| settings/validation.py | Data file existence checks |
| settings/README.md | Usage documentation |

## Data Dependencies

Water policies need these files at runtime:
- `data/precomputed/water_treatment/treatment_kwh_per_m3-toy.csv` (energy per m³ by salinity)
- `data/parameters/equipment/water_treatment-toy.csv` (maintenance costs)
- `data/prices/water/historical_municipal_water_prices-toy.csv` (municipal prices)
- `data/prices/electricity/historical_grid_electricity_prices-toy.csv` (energy costs)

## Verification

1. **Syntax check**: Load toy_4farm.yaml with PyYAML, confirm no parse errors
2. **Validation check**: Run `validate_scenario()` - expect empty missing list
3. **Policy tests**: Test each water policy with identical inputs, verify distinct allocations
4. **Energy constraint test**: Verify all policies correctly fall back to municipal when energy insufficient

## Test Commands

```bash
# Validate YAML syntax
python -c "import yaml; yaml.safe_load(open('settings/scenarios/toy_4farm.yaml'))"

# Run validation
python -c "from settings.validation import validate_scenario; print(validate_scenario('settings/scenarios/toy_4farm.yaml'))"

# Test all water policies with same context
python -c "
from settings.policies.water_policies import (
    AlwaysGroundwater, AlwaysMunicipal, CheapestSource, ConserveGroundwater,
    WaterPolicyContext
)

ctx = WaterPolicyContext(
    demand_m3=1000,
    available_energy_kwh=5000,
    treatment_kwh_per_m3=2.2,
    gw_maintenance_per_m3=0.25,
    municipal_price_per_m3=0.65,
    energy_price_per_kwh=0.07
)

for Policy in [AlwaysGroundwater, AlwaysMunicipal, CheapestSource, ConserveGroundwater]:
    policy = Policy()
    result = policy.allocate_water(ctx)
    print(f'{policy.name}: GW={result.groundwater_m3:.0f}, Muni={result.municipal_m3:.0f}, Cost=\${result.cost_usd:.2f}')
"
```

## Sequence

1. Create folder structure
2. Write toy_4farm.yaml scenario
3. Write water_policies.py (4 functional policies)
4. Write policy stubs (energy, crop, economic, market)
5. Write validation.py
6. Write README.md
7. Run verification tests

## Comparative Analysis Setup

With 4 farms running different water policies over 10 years, the simulation will produce:

- **Cost comparison**: Total water costs by policy
- **Energy consumption**: Treatment energy by policy
- **Groundwater usage**: Aquifer draw by policy
- **Resilience**: How each policy handles price spikes and energy shortages

This enables direct A/B/C/D testing of water management strategies under identical conditions.
