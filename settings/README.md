# Settings: Layer 2 Configuration

This folder contains simulation configuration for the Community Agri-PV model.

## Architecture

```
settings/
├── data_registry.yaml   # Single source of truth for data file paths
├── scenarios/           # Scenario configurations (policies, farms)
│   └── toy_4farm.yaml
├── policies/            # Policy implementations
│   ├── water_policies.py     # 4 functional water policies
│   ├── energy_policies.py    # Stub
│   ├── crop_policies.py      # Stub
│   ├── economic_policies.py  # Stub
│   └── market_policies.py    # Stub
├── validation.py        # Registry and scenario validation
└── README.md
```

## Data Registry

All data file paths are defined in `data_registry.yaml`. Scenarios do not contain file paths - they reference the shared registry.

**To switch datasets** (e.g., toy → research):
```bash
# Edit data_registry.yaml, change "-toy.csv" to "-research.csv"
# Then validate:
python settings/validation.py --registry
```

**Registry structure:**
```yaml
weather:
  daily: data/precomputed/weather/daily_weather_scenario_001-toy.csv

crops:
  coefficients: data/parameters/crops/crop_coefficients-toy.csv
  ...

irrigation:
  tomato: data/precomputed/irrigation_demand/irrigation_m3_per_ha_tomato-toy.csv
  ...
```

**Load registry in code:**
```python
from settings.validation import load_registry

registry = load_registry()
weather_file = registry["weather"]["daily"]
tomato_irrigation = registry["irrigation"]["tomato"]
```

## Scenarios

Scenarios define:
- Simulation time range
- Infrastructure configuration (capacities)
- Farm structure and policy assignments
- Economic parameters

Scenarios do **not** define data file paths - those come from the registry.

### toy_4farm.yaml

4 equal-sized farms (125 ha each) with distinct water policies:

| Farm | Water Policy | Economic Policy |
|------|-------------|-----------------|
| Farm 1 | always_groundwater | conservative |
| Farm 2 | always_municipal | moderate |
| Farm 3 | cheapest_source | aggressive |
| Farm 4 | conserve_groundwater | balanced |

## Water Policies

Four functional policies for comparative testing:

```python
from settings.policies.water_policies import (
    WaterPolicyContext,
    AlwaysGroundwater,
    AlwaysMunicipal,
    CheapestSource,
    ConserveGroundwater,
)

ctx = WaterPolicyContext(
    demand_m3=1000,
    available_energy_kwh=5000,
    treatment_kwh_per_m3=2.2,
    gw_maintenance_per_m3=0.25,
    municipal_price_per_m3=0.65,
    energy_price_per_kwh=0.07,
)

policy = CheapestSource()
result = policy.allocate_water(ctx)
# result.groundwater_m3, result.municipal_m3, result.cost_usd
```

## Validation

```bash
# Validate data registry (all files exist)
python settings/validation.py --registry

# Validate a specific scenario
python settings/validation.py settings/scenarios/toy_4farm.yaml

# Validate everything
python settings/validation.py --all
```

## Adding New Scenarios

1. Copy `toy_4farm.yaml` as template
2. Modify farm counts, sizes, and policy assignments
3. Run `python settings/validation.py settings/scenarios/your_scenario.yaml`

Scenarios share the same data registry. To use different data, edit the registry (affects all scenarios).
