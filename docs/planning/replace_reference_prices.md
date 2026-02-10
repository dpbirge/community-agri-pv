# Replace Hardcoded REFERENCE_PRICES in MarketResponsive

**Generated:** February 6, 2026

## Complete Investigation Summary

### Where REFERENCE_PRICES Lives

The `REFERENCE_PRICES` dict is in `/Users/dpbirge/GITHUB/community-agri-pv/src/policies/food_policies.py`, lines 149-155, inside the `MarketResponsive` class (a food processing policy, not a market policy as the TODO item's title might suggest). The hardcoded values are:

```python
REFERENCE_PRICES = {
    "tomato": 0.30,
    "potato": 0.25,
    "onion": 0.20,
    "kale": 0.40,
    "cucumber": 0.35,
}
```

### How REFERENCE_PRICES Is Used

In `MarketResponsive.allocate()` (line 157-177), the policy compares `ctx.fresh_price_per_kg` against `ref * 0.80` where `ref` comes from `REFERENCE_PRICES`. If the current price is below 80% of the reference, the policy shifts harvest allocation toward processing (30% fresh / 70% processed) instead of the normal allocation (65% fresh / 35% processed).

### The Mismatch with CSV Data

The CSV price files contain **wholesale** prices (columns: `date`, `usd_per_kg`, `season`, `market_condition`). The historical averages from the toy data are approximately:
- **Tomato**: ~$0.91/kg wholesale (hardcoded reference: $0.30 -- off by 3x)
- **Potato**: ~$0.60/kg wholesale (hardcoded reference: $0.25 -- off by 2.4x)
- **Onion**: ~$0.52/kg wholesale (hardcoded reference: $0.20 -- off by 2.6x)
- **Kale**: ~$2.53/kg wholesale (hardcoded reference: $0.40 -- off by 6.3x)
- **Cucumber**: ~$1.08/kg wholesale (hardcoded reference: $0.35 -- off by 3.1x)

The hardcoded values are labeled as "farmgate prices" but the toy CSV only has wholesale. Since the simulation uses `get_crop_price_usd_kg(crop, date, price_type="farmgate")` -- and the toy data falls back to the single `usd_per_kg` column (wholesale) -- the `MarketResponsive` policy currently compares wholesale prices against what are supposed to be farmgate references. The threshold `ref * 0.80` means prices like $0.24/kg for tomato, which is far below any value in the CSV data. In practice, the "low price" branch probably never fires with current data.

### How Policies Currently Receive Config from YAML

The established pattern (visible in `ConserveGroundwater`, `QuotaEnforced`, `HoldForPeak`, `ProcessWhenLow`, and `AggressiveGrowth`) is:
1. Policy classes accept parameters via `__init__(**kwargs)` with defaults
2. `community_policy_parameters` section in scenario YAML defines parameter overrides keyed by policy name
3. `_load_farm()` in `loader.py` looks up `policy_parameters.get(policy_name, {})` and passes as `**kwargs` to the factory function
4. Factory functions (`get_food_policy`, `get_water_policy`, etc.) forward `**kwargs` to the class constructor

Currently, `MarketResponsive.__init__()` takes no parameters. The fix needs to add a `reference_prices` kwarg.

### How process_harvests() Calls Food Policies

In `simulation.py`, `process_harvests()` (lines 318-440) builds a `FoodProcessingContext` with `fresh_price_per_kg=price_per_kg` (the current day's farmgate/wholesale price) and calls `farm_config.food_policy.allocate(ctx)`. The policy already has access to the current price through context; it just needs a better reference baseline.

### The `data_loader` and Price Access

`SimulationDataLoader` (in `data_loader.py`) loads all crop price CSVs at init and stores them in `self.crop_prices` (dict by crop name). The method `get_crop_price_usd_kg(crop, date, price_type)` retrieves prices. The loader also has access to the full DataFrames, which could be used to compute rolling averages.

---

## Detailed Implementation Plan

### Problem Statement

The `MarketResponsive` food processing policy uses a hardcoded `REFERENCE_PRICES` dictionary with fixed USD/kg values that serve as price thresholds for deciding whether to sell fresh or shift harvest into processing. These values are problematic for three reasons:

1. **Incorrect scale**: The hardcoded values ($0.20-0.40/kg) are dramatically lower than the actual prices in the CSV data ($0.52-2.53/kg average), meaning the "low price" threshold is never reached and the policy's processing branch is effectively dead code.

2. **Static over time**: In multi-year simulations with price trends, inflation, or currency shifts, fixed reference prices become increasingly stale.

3. **Not configurable**: Users cannot tune these thresholds per scenario. Other policies in the system (e.g., `ConserveGroundwater`, `QuotaEnforced`, `HoldForPeak`) all accept constructor parameters from scenario YAML, but `MarketResponsive` does not.

### Current Behavior

The `MarketResponsive.allocate()` method:
1. Looks up `REFERENCE_PRICES[crop_name]` with fallback to 0.30
2. Computes threshold = `ref * 0.80`
3. If `ctx.fresh_price_per_kg < threshold`: allocates 30% fresh / 20% packaged / 25% canned / 25% dried
4. Else: allocates 65% fresh / 15% packaged / 10% canned / 10% dried

Because the reference prices are far below market prices, condition (3) essentially never triggers, and the policy always produces the "normal/high price" allocation -- functionally identical to a policy that always does 65/15/10/10.

### Desired Behavior

The `MarketResponsive` policy should:
- Accept reference prices as a configurable parameter via `__init__()`, matching the existing policy convention
- When no explicit reference prices are provided, derive them from the historical crop price CSV data (compute the overall mean for each crop)
- Allow the price floor multiplier (currently hardcoded at 0.80) to also be configurable
- Support scenario-level overrides via `community_policy_parameters` in YAML

### Proposed Solution

This is a three-step implementation: (A) make `MarketResponsive` accept constructor parameters, (B) add a helper function to compute reference prices from CSV data, and (C) wire the data into the policy at instantiation time.

#### Step A: Add constructor parameters to MarketResponsive

**File**: `/Users/dpbirge/GITHUB/community-agri-pv/src/policies/food_policies.py`

1. Add `__init__` method to `MarketResponsive`:
   ```python
   def __init__(self, reference_prices=None, price_floor_multiplier=0.80):
       self.reference_prices = reference_prices or {}
       self.price_floor_multiplier = price_floor_multiplier
   ```

2. Modify `allocate()` to use instance attributes:
   ```python
   def allocate(self, ctx):
       ref = self.reference_prices.get(ctx.crop_name, 0.0)
       if ref <= 0:
           # No reference available -- default to normal/high allocation
           ...
       if ctx.fresh_price_per_kg < ref * self.price_floor_multiplier:
           ...
   ```

3. Add `get_parameters()`:
   ```python
   def get_parameters(self):
       return {
           "reference_prices": self.reference_prices,
           "price_floor_multiplier": self.price_floor_multiplier,
       }
   ```

4. Remove the class-level `REFERENCE_PRICES` constant entirely. Do not leave dead code alongside the new implementation.

#### Step B: Add a function to compute reference prices from loaded price data

**File**: `/Users/dpbirge/GITHUB/community-agri-pv/src/simulation/data_loader.py`

Add a method to `SimulationDataLoader`:

```python
def compute_reference_crop_prices(self, price_type="farmgate"):
    """Compute mean historical price per crop from loaded price data.

    Returns:
        dict: {crop_name: mean_usd_per_kg} for all loaded crops
    """
    reference = {}
    for crop_name, prices_df in self.crop_prices.items():
        col = f"usd_per_kg_{price_type}"
        if col not in prices_df.columns:
            col = "usd_per_kg"
        reference[crop_name] = float(prices_df[col].mean())
    return reference
```

This approach uses the full-history mean, which is straightforward and deterministic. It runs once at initialization, not per day.

#### Step C: Wire computed prices into policy instantiation

**File**: `/Users/dpbirge/GITHUB/community-agri-pv/src/simulation/simulation.py`

In `run_simulation()`, after `data_loader` is created but before the main loop starts, compute reference prices and inject them into any farm that uses `market_responsive` food policy:

```python
# Compute reference prices for MarketResponsive food policy
reference_prices = data_loader.compute_reference_crop_prices()

for farm_config in scenario.farms:
    if hasattr(farm_config.food_policy, 'reference_prices'):
        if not farm_config.food_policy.reference_prices:
            farm_config.food_policy.reference_prices = reference_prices
```

This preserves explicit overrides from YAML (Step D below) while providing CSV-derived defaults.

#### Step D: Add YAML configuration support

**File**: `/Users/dpbirge/GITHUB/community-agri-pv/settings/settings.yaml`

Add to `community_policy_parameters`:

```yaml
community_policy_parameters:
  market_responsive:
    price_floor_multiplier: 0.80
    # Optional explicit overrides (if omitted, computed from CSV):
    # reference_prices:
    #   tomato: 0.90
    #   potato: 0.60
    #   onion: 0.52
    #   kale: 2.50
    #   cucumber: 1.08
```

**File**: `/Users/dpbirge/GITHUB/community-agri-pv/src/settings/loader.py`

No changes needed -- the existing `_load_farm()` function already passes `policy_parameters.get(food_policy_name, {})` as `**kwargs` to `get_food_policy()`, so any dict key matching an `__init__` parameter name is automatically forwarded.

#### Step E: Update documentation

**File**: `/Users/dpbirge/GITHUB/community-agri-pv/docs/architecture/policies.md`

Update Section 4.6 (MarketResponsive) to document:
- `reference_prices` parameter (dict or empty for CSV-derived)
- `price_floor_multiplier` parameter (default 0.80)
- How CSV-derived reference prices are computed (full-history mean)
- That explicit YAML overrides take precedence

**File**: `/Users/dpbirge/GITHUB/community-agri-pv/TODO.md`

Remove the line: "Replace hardcoded REFERENCE_PRICES in MarketResponsive with CSV-derived or configurable thresholds"

### Decision Points

1. **Derive from historical averages vs explicit config?**
   **Recommendation**: Both. Compute from CSV as the default, allow explicit override via YAML. This matches the existing pattern where policies have constructor defaults but accept scenario-level overrides.

2. **Rolling window vs fixed full-history mean?**
   **Recommendation**: Start with full-history mean (the entire loaded CSV). A rolling window adds complexity (window size parameter, handling of simulation dates beyond price data range) and is better suited for a future enhancement when the simulation supports dynamic mid-run recalculation. The full-history mean is stable, reproducible, and sufficient for the current use case where the reference price is a baseline, not a forecast.

3. **Per-crop thresholds vs single threshold?**
   **Recommendation**: Per-crop, which is the current design. The 0.80 multiplier is per-crop already (applied to each crop's reference). Making `price_floor_multiplier` a single float (not per-crop) is sufficient since the multiplier represents a policy preference (how much below normal triggers processing), not a crop-specific physical property.

4. **Where to compute reference prices -- policy class, data_loader, or simulation init?**
   **Recommendation**: `data_loader` computes them (it owns the price data), `simulation.py` injects them into policies that need them. The policy class itself should not load data (maintaining Layer 2/3 separation -- policies are design-time, data loading is runtime).

5. **What if a crop appears in simulation but not in price CSV?**
   **Recommendation**: The `get()` call with a default of `0.0` means the policy skips the low-price branch for unknown crops (defaulting to normal/high allocation). This is safe -- processing an unknown crop without a reference baseline could waste harvest.

### Remaining Questions

1. **Should the AdaptiveMarketing policy in market_policies.py also get configurable thresholds?** -- It uses hardcoded multipliers (1.10, 0.85, 0.50, 0.60) against `ctx.avg_price_per_kg`. These are relative multipliers rather than absolute prices, so they are less affected by the scale mismatch. But they should be reviewed for consistency.

2. **Research vs toy price data** -- The `load_crop_prices()` function has a `use_research` flag (defaults to `True`), but research crop price files may not exist for all crops. The reference price computation should handle missing files gracefully.

3. **When research-grade price CSVs are added, should reference prices be recomputed?** -- Yes, the computation from CSV handles this automatically since `SimulationDataLoader.__init__()` loads whatever CSV the registry points to.

### Critical Files for Implementation

- `/Users/dpbirge/GITHUB/community-agri-pv/src/policies/food_policies.py` - Primary target: add `__init__` parameters to `MarketResponsive`, remove hardcoded `REFERENCE_PRICES` constant
- `/Users/dpbirge/GITHUB/community-agri-pv/src/simulation/data_loader.py` - Add `compute_reference_crop_prices()` method to `SimulationDataLoader` for deriving baselines from CSV
- `/Users/dpbirge/GITHUB/community-agri-pv/src/simulation/simulation.py` - Inject computed reference prices into food policies during `run_simulation()` initialization
- `/Users/dpbirge/GITHUB/community-agri-pv/docs/architecture/policies.md` - Update MarketResponsive documentation in Section 4.6 with new parameters and behavior
- `/Users/dpbirge/GITHUB/community-agri-pv/settings/settings.yaml` - Add `market_responsive` entry to `community_policy_parameters` as example/default configuration
