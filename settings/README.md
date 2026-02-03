# Settings: Layer 2 Configuration

Simulation configuration for the Community Agri-PV model.

## Structure

```
settings/
├── data_registry.yaml       # Single source of truth for data file paths
├── scenarios/               # Scenario configurations (policies, farms)
│   ├── water_policy_only.yaml      # Multi-farm water policy comparison
│   └── development_full_copy.yaml  # Full scenario template
├── policies/                # Policy implementations
│   ├── water_policies.py    # 4 functional water policies
│   ├── energy_policies.py   # Stub
│   ├── crop_policies.py     # Stub
│   ├── economic_policies.py # Stub
│   └── market_policies.py   # Stub
└── scripts/                 # Configuration utilities
    ├── loader.py            # Scenario loader (YAML -> dataclasses)
    ├── validation.py        # Registry and scenario validation
    └── calculations.py      # Calculation layer for scenario computations
```

## Data Registry

All data file paths are defined in `data_registry.yaml`. Scenarios reference this shared registry.

```bash
# Validate data registry (all files exist)
python settings/scripts/validation.py --registry

# Validate a specific scenario
python settings/scripts/validation.py settings/scenarios/water_policy_only.yaml
```

## Loading Scenarios

```python
from settings.scripts.loader import load_scenario

scenario = load_scenario("settings/scenarios/water_policy_only.yaml")
# scenario.farms, scenario.infrastructure, scenario.water_pricing, etc.
```

## Water Policies

Four functional policies for comparative testing:

| Policy | Strategy |
|--------|----------|
| `always_groundwater` | 100% groundwater, municipal fallback if energy insufficient |
| `always_municipal` | 100% municipal, no treatment energy needed |
| `cheapest_source` | Dynamic selection based on daily cost comparison |
| `conserve_groundwater` | Prefer municipal, use GW when price > threshold |

```python
from settings.policies import get_water_policy, WaterPolicyContext

ctx = WaterPolicyContext(
    demand_m3=1000,
    available_energy_kwh=5000,
    treatment_kwh_per_m3=2.2,
    gw_maintenance_per_m3=0.25,
    municipal_price_per_m3=0.65,
    energy_price_per_kwh=0.07,
)

policy = get_water_policy("cheapest_source")
result = policy.allocate_water(ctx)
# result.groundwater_m3, result.municipal_m3, result.cost_usd
```

## Adding Scenarios

1. Copy `water_policy_only.yaml` as template
2. Modify farms, policies, and parameters
3. Validate: `python settings/scripts/validation.py settings/scenarios/your_scenario.yaml`
4. Run: `python src/results.py settings/scenarios/your_scenario.yaml`
