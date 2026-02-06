# Settings: Layer 2 Configuration

Simulation configuration for the Community Agri-PV model.

## Structure

```
settings/
├── data_registry.yaml       # Single source of truth for data file paths
└── mvp-settings.yaml        # MVP scenario configuration
```

## Data Registry

All data file paths are defined in `data_registry.yaml`. Scenarios reference this shared registry.

```bash
# Validate data registry (all files exist)
python src/settings/validation.py --registry

# Validate a specific scenario
python src/settings/validation.py settings/mvp-settings.yaml
```

## Loading Scenarios

```python
from src.settings.loader import load_scenario

scenario = load_scenario("settings/mvp-settings.yaml")
# scenario.farms, scenario.infrastructure, scenario.water_pricing, etc.
```

## Policies

All six policy types are implemented in `src/policies/`:

| Domain | Policies | File |
|--------|----------|------|
| **Water** | `always_groundwater`, `always_municipal`, `cheapest_source`, `conserve_groundwater`, `quota_enforced` | `water_policies.py` |
| **Energy** | `pv_first_battery_grid_diesel`, `grid_first`, `cheapest_energy` | `energy_policies.py` |
| **Food** | `all_fresh`, `maximize_storage`, `balanced`, `market_responsive` | `food_policies.py` |
| **Crop** | `fixed_schedule`, `deficit_irrigation`, `weather_adaptive` | `crop_policies.py` |
| **Economic** | `balanced`, `aggressive_growth`, `conservative`, `risk_averse` | `economic_policies.py` |
| **Market** | `sell_immediately`, `hold_for_peak`, `process_when_low`, `adaptive_marketing` | `market_policies.py` |

## Policy Usage

```python
from src.policies import get_water_policy, WaterPolicyContext

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

1. Copy `mvp-settings.yaml` as template
2. Modify farms, policies, and parameters
3. Validate: `python src/settings/validation.py settings/your-scenario.yaml`
4. Run: `python src/simulation/results.py settings/your-scenario.yaml`
