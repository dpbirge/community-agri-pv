# Fix Inflation / Price-Year Alignment

**Generated:** February 6, 2026

## Implementation Plan: Fix Inflation / Price-Year Alignment

### Problem Statement

The simulation mixes prices from different years without adjustment, producing distorted economic metrics. There are two distinct sub-problems:

**Sub-problem 1 -- Revenue/cost temporal mismatch.** The simulation period runs 2015-2020 (per `settings.yaml`). Crop revenues use nominal historical prices from 2015 onward (e.g., tomato farmgate at $0.32/kg in 2015). But infrastructure CAPEX/OPEX uses hardcoded 2024-basis reference costs in `REFERENCE_COSTS` inside `calculations.py` (e.g., PV at $1,200/kW, BWRO at $1,000/m3/day). When the simulation computes net income, NPV, IRR, and payback, it is subtracting 2024-dollar costs from 2015-dollar revenues. This systematically understates profitability and overstates payback period.

**Sub-problem 2 -- Historic prices include nominal drift that is not "real" variation.** The TODO note says: "We should use the variation but start at today's prices." This means the user wants to preserve the seasonal/market variation patterns from the historical price data (the month-to-month ups and downs) but re-anchor them to a current (2024) price level. That way the simulation captures realistic price volatility without the distortion of nominal inflation drift.

### Current Behavior

Here is exactly how prices flow through the system today:

1. **Crop prices** -- `SimulationDataLoader` loads either research CSV files (annual data with `usd_per_kg_farmgate/wholesale/retail` columns, e.g., `tomato_prices-research.csv`) or toy CSV files (monthly data with `usd_per_kg` column, e.g., `historical_tomato_prices-toy.csv`). The `get_crop_price()` function does a "most recent date <= target_date" lookup and returns the raw nominal USD value from the file. No adjustment is applied.

2. **Electricity prices** -- Loaded from research or toy CSVs indexed by date. The `get_electricity_price()` function finds the applicable tariff rate via date lookup and returns raw nominal `usd_per_kwh_avg_daily`. No adjustment.

3. **Diesel prices** -- Same pattern: raw nominal `usd_per_liter` from date-indexed CSV.

4. **Municipal water prices** -- Two regimes:
   - **Subsidized**: Looked up from CSV by year and tier (tier 1/2/3). Returns nominal USD value.
   - **Unsubsidized**: Uses `base_price_usd_m3` from `settings.yaml` with `annual_escalation_pct` applied: `price = base * (1 + escalation)^(year - start_year)`. This is the only place that applies any escalation, and it is scenario-driven (not data-driven).

5. **Infrastructure costs** -- `estimate_infrastructure_costs()` in `calculations.py` uses `REFERENCE_COSTS` dictionary (hardcoded, all in 2024 USD) to compute CAPEX and annual O&M. These costs are static across all simulation years.

6. **NPV/IRR** -- `compute_npv()` in `metrics.py` uses `economics.discount_rate` (0.06 per the settings) without specifying whether it is real or nominal. It discounts annual net income (2015-dollar revenue minus 2024-dollar costs).

7. **Toy price generation** -- `generate_price_data.py` adds a small 10% linear upward trend over 10 years (`np.linspace(0, 0.10, n)`) to simulate inflation, but this is baked into the data, not adjustable.

**Net result:** Year 1 (2015) revenue uses $0.32/kg tomato farmgate price while infrastructure cost uses $1,200/kW PV cost from 2024. The NPV calculation treats these as comparable dollars, which they are not.

### Desired Behavior

Per the TODO: "use the variation but start at today's prices." The target state is:

1. All prices (crop, electricity, diesel, water, labor, fertilizer) and all costs (CAPEX, OPEX) are expressed in a common reference year (2024 USD).
2. Historical price time-series retain their real variation (seasonality, shocks, year-to-year relative changes) but are re-anchored so the most recent year's value matches the 2024 level.
3. Infrastructure costs remain at their current 2024-basis values (no change needed on the cost side).
4. The discount rate is documented as a real rate.
5. Economic metrics (NPV, IRR, payback, operating margin) are internally consistent.
6. The approach is simple, documented, and does not require external CPI data for the initial fix (since CPI-based adjustment introduces complexity around cross-currency PPP that is not yet resolved).

### Proposed Solution

The solution uses a "re-anchoring" approach: for each price series, compute a ratio factor that shifts the historical series so that its most recent value equals the known 2024 reference price, while preserving the relative variation pattern.

#### Step 1: Add `price_basis_year` to scenario configuration

**File:** `/Users/dpbirge/GITHUB/community-agri-pv/settings/settings.yaml`

Add under the `economics:` section:

```yaml
economics:
  currency: USD
  discount_rate: 0.06
  discount_rate_type: real  # NEW: explicit documentation
  price_basis_year: 2024     # NEW: all prices adjusted to this year
```

**File:** `/Users/dpbirge/GITHUB/community-agri-pv/src/settings/loader.py`

Add `price_basis_year` (int, default 2024) and `discount_rate_type` (str, default "real") to the `EconomicsConfig` dataclass. Load them in `_load_economics()`, falling back to defaults if absent for backward compatibility.

#### Step 2: Create the price re-anchoring function

**File:** `/Users/dpbirge/GITHUB/community-agri-pv/src/simulation/data_loader.py`

Add a new module-level function:

```python
def reanchor_price_series(df, price_column, reference_year=2024):
    """Re-anchor a price time-series so the reference_year value = actual value,
    while preserving relative variation from the original series.

    Method: Compute ratio = actual_reference_year_value / original_reference_year_value.
    Multiply all values by this ratio. If reference_year data is missing, use the
    last available year.

    This preserves seasonality and year-to-year variation patterns while shifting
    the absolute level to match the reference year's known price.

    For research files with annual data: the ratio is direct.
    For toy files with monthly data: use the annual mean of the reference year.

    Args:
        df: DataFrame indexed by date with price column(s)
        price_column: Column name or list of column names to adjust
        reference_year: Year whose value should be preserved as-is

    Returns:
        DataFrame with adjusted prices (same structure)
    """
```

The key insight: for the **research** crop price files (annual data), the 2024 value IS the real 2024 price, so the ratio is 1.0 for 2024 and all earlier years get scaled up by (2024_price / their_nominal_price_in_that_year). But this is NOT what we want -- that would lose the variation. Instead:

**The correct approach for research files** (annual granularity): These already represent the real price level for each year. The distortion comes from comparing them against 2024-basis costs. The fix: use the 2024 price as the constant price for all simulation years, since the model claims to operate in "real terms." For annual research data, the simplest fix is to just use the 2024 row's value for all years.

**The correct approach for toy files** (monthly granularity): These have seasonal variation that IS the signal we want to preserve. The approach:
1. Compute the mean price in the reference year (2024).
2. Compute the mean price across the entire series.
3. Scale factor = reference_year_mean / series_mean.
4. Multiply all prices by this scale factor.

This centers the entire series around the 2024 average while preserving every month-to-month fluctuation.

**However**, re-reading the TODO more carefully -- "use the variation but start at today's prices" -- the user likely wants:
- For **toy data** (monthly, 2015-2024): shift the pattern so that the 2024 months remain as-is, and earlier years are proportionally adjusted upward (removing the nominal drift). This is achieved by dividing each price by its year's annual mean and multiplying by the 2024 annual mean.
- For **research data** (annual, 2015-2024): use a single constant value (the 2024 price) since there is no intra-year variation to preserve.

This needs a **decision point** from the user (see below).

#### Step 3: Apply re-anchoring in SimulationDataLoader.__init__()

**File:** `/Users/dpbirge/GITHUB/community-agri-pv/src/simulation/data_loader.py`

After loading each price DataFrame, apply the re-anchoring function if `price_basis_year` is provided. This means `SimulationDataLoader.__init__()` gains a new parameter:

```python
def __init__(self, registry_path=..., use_research_prices=True,
             electricity_pricing_regime="subsidized", project_root=None,
             price_multipliers=None, price_basis_year=None):  # NEW
```

When `price_basis_year` is not None, after loading each price series, call `reanchor_price_series()` on:
- `self.crop_prices[crop]` for each crop (columns: `usd_per_kg` or `usd_per_kg_farmgate`, `usd_per_kg_wholesale`, `usd_per_kg_retail`)
- `self.electricity_prices` (column: `usd_per_kwh_avg_daily`, `usd_per_kwh_offpeak`, `usd_per_kwh_peak`)
- `self.diesel_prices` (column: `usd_per_liter`)
- `self.municipal_prices` (columns: `usd_per_m3_tier1`, `usd_per_m3_tier2`, `usd_per_m3_tier3` or `usd_per_m3`)
- `self.fertilizer_costs` (column: `usd_per_ha`)

#### Step 4: Pass price_basis_year from scenario to data_loader

**File:** `/Users/dpbirge/GITHUB/community-agri-pv/src/simulation/simulation.py`

In `run_simulation()`, when constructing `SimulationDataLoader`:

```python
price_basis_year = getattr(scenario.economics, 'price_basis_year', None)
data_loader = SimulationDataLoader(
    electricity_pricing_regime=electricity_pricing_regime,
    price_basis_year=price_basis_year,
)
```

#### Step 5: Verify REFERENCE_COSTS are 2024-basis (no change needed)

**File:** `/Users/dpbirge/GITHUB/community-agri-pv/src/settings/calculations.py`

The `REFERENCE_COSTS` dictionary and `capital_costs-research.csv` are already 2024-basis. Add a comment documenting this:

```python
# Reference costs in 2024 USD. When price_basis_year is set in the scenario,
# all revenue-side prices are also adjusted to 2024 USD, ensuring consistency.
REFERENCE_COSTS = { ... }
```

#### Step 6: Document the approach in calculations.md

**File:** `/Users/dpbirge/GITHUB/community-agri-pv/docs/architecture/calculations.md`

Update the "Inflation and Real vs Nominal Values" section (around line 1916) to document:
- The model now operates in constant 2024 USD terms.
- Price re-anchoring method (preserve variation, anchor to reference year).
- The discount rate is a real rate (net of inflation).
- Infrastructure costs are already 2024-basis.

#### Step 7: Update water pricing escalation logic

**File:** `/Users/dpbirge/GITHUB/community-agri-pv/src/simulation/simulation.py` (function `build_water_policy_context`)

The unsubsidized water pricing already applies escalation from the scenario start year:
```python
municipal_price = base_price * ((1 + escalation) ** years_from_start)
```

When operating in constant-dollar (real) terms with `price_basis_year` set, this escalation should be interpreted as a **real** escalation rate (above inflation). If the intent is constant real prices, set `annual_escalation_pct: 0` in the scenario. If the intent is to model real water scarcity premium growth, keep it. Document this in the settings YAML comments.

#### Step 8: Add validation

**File:** `/Users/dpbirge/GITHUB/community-agri-pv/src/settings/validation.py`

Add a validation check: if `price_basis_year` is set, verify that all price CSV files contain data for that year. Warn if the reference year is outside the data range.

### Specific Implementation for Each Price Category

| Price Category | Data File(s) | Columns to Adjust | Re-anchor Method |
|---|---|---|---|
| Crop prices (research) | `data/prices/crops/{crop}_prices-research.csv` | `usd_per_kg_farmgate`, `usd_per_kg_wholesale`, `usd_per_kg_retail` | Use 2024 row value as constant (annual data, no variation to preserve) |
| Crop prices (toy) | `data/prices/crops/historical_{crop}_prices-toy.csv` | `usd_per_kg` | Divide by year-mean, multiply by 2024-year-mean (preserves monthly pattern) |
| Electricity (research) | `data/prices/electricity/historical_grid_electricity_prices-research.csv` | `usd_per_kwh_avg_daily`, `usd_per_kwh_offpeak`, `usd_per_kwh_peak` | Use 2024 row value as constant (step-change tariff data) |
| Electricity (toy) | `data/prices/electricity/historical_grid_electricity_prices-toy.csv` | Same columns | Divide by year-mean, multiply by 2024-year-mean |
| Diesel (research) | `data/prices/diesel/historical_diesel_prices-research.csv` | `usd_per_liter` | Use 2024 row value as constant |
| Diesel (toy) | `data/prices/diesel/historical_diesel_prices-toy.csv` | `usd_per_liter` | Divide by year-mean, multiply by 2024-year-mean |
| Water (research) | `data/prices/water/historical_municipal_water_prices-research.csv` | `usd_per_m3_tier1/2/3` | Use 2024 row value as constant |
| Water (toy) | `data/prices/water/historical_municipal_water_prices-toy.csv` | `usd_per_m3` | Divide by year-mean, multiply by 2024-year-mean |
| Fertilizer (toy) | `data/prices/inputs/historical_fertilizer_costs-toy.csv` | `usd_per_ha` | Divide by year-mean, multiply by 2024-year-mean |
| Processed goods (toy) | `data/prices/processed/historical_*_prices-toy.csv` | `usd_per_kg` | Divide by year-mean, multiply by 2024-year-mean |

### Decision Points (Require User Input)

**Decision 1: Re-anchoring strategy for research (annual) data.**

Two options:
- **Option A (Simple):** Use a single constant price (the 2024 value) for all simulation years. Since research data is annual with no intra-year variation, there is nothing to "preserve." This is the cleanest real-terms approach.
- **Option B (Preserve inter-year variation):** Scale all years proportionally so 2024 stays fixed but earlier years retain their relative distance from 2024. Example: if 2020 tomato was 36% higher than 2024 in nominal terms ($0.75 vs $0.55 wholesale), the adjusted 2020 price would be $0.55 x (0.75/0.55) = $0.75 -- wait, that keeps it unchanged. The issue is that research prices in USD already reflect real market conditions (currency effects, supply/demand), not just inflation. **Recommendation: Option A** for simplicity in the MVP. The real year-to-year USD variation in Egyptian crop prices is dominated by EGP devaluation effects, not actual market variation.

**Decision 2: Simulation period.**

With prices anchored to 2024, does it still make sense to simulate 2015-2020? The weather data drives physical outputs (yields, irrigation demand) and is tied to real dates. Options:
- **Option A:** Keep 2015-2020 simulation period, but all monetary values are in 2024 USD. Weather variation from 2015-2020 drives physical quantities; economics are at 2024 price levels.
- **Option B:** Shift the simulation to a future period (e.g., 2024-2030) with projected weather. This is a larger scope change and not needed for the inflation fix.
- **Recommendation: Option A.** The physical simulation uses historical weather patterns as a proxy; the economic layer just needs self-consistent prices.

**Decision 3: What to do with the unsubsidized water escalation.**

Currently `annual_escalation_pct: 3.0` in settings. If all prices are in constant 2024 USD:
- This 3% escalation becomes a **real** price increase (above inflation). Is this intended? Water scarcity could justify 1-2% real escalation.
- Or should it be set to 0% for pure constant-dollar analysis?
- **Recommendation:** Rename/document the parameter as `real_annual_escalation_pct` and keep it at a lower value (e.g., 1-2%) or 0%.

**Decision 4: Should toy data generation be updated?**

`generate_price_data.py` bakes in a 10% linear trend. Should the generator be updated to produce flat (no-trend) toy data, relying on the re-anchoring function for any level-shifting?
- **Recommendation:** Yes, remove the trend from toy generation. The re-anchoring handles level-shifting at load time.

### Questions / Remaining Unknowns

1. **Labor costs**: `LABOR_HOURLY_RATE_USD = 3.50` in `calculations.py` is a hardcoded constant. What year is this based on? Should it also be tagged with a basis year and adjusted?

2. **Processed goods prices**: The toy processed price files (dried tomato, canned onion, etc.) are generated from fresh prices times multipliers. If fresh prices are re-anchored, should processed prices also be re-anchored independently, or should they be regenerated from the adjusted fresh prices?

3. **EGP-denominated columns**: Many research CSVs include `egp_per_kg_original` and `usd_egp_exchange_rate`. The re-anchoring only adjusts USD columns. Should EGP columns be left as historical references (documentation only) or dropped to avoid confusion?

4. **Sensitivity analysis / Monte Carlo**: The existing `price_multipliers` parameter in `SimulationDataLoader` applies multiplicative factors to prices. Does re-anchoring interact correctly with this? (It should -- re-anchoring happens at load time, multipliers apply on top at query time.)

5. **Future: forward-looking scenarios (2025-2040).** The re-anchoring approach handles historical data well. For forward projections, a different mechanism (real escalation rates per category) will be needed. The current fix should be designed not to preclude this.

### Implementation Sequence

| Order | Task | Files | Effort |
|---|---|---|---|
| 1 | Add `price_basis_year` and `discount_rate_type` to `EconomicsConfig` | `loader.py`, `settings.yaml` | Small |
| 2 | Write `reanchor_price_series()` function | `data_loader.py` | Medium |
| 3 | Apply re-anchoring in `SimulationDataLoader.__init__()` | `data_loader.py` | Medium |
| 4 | Pass `price_basis_year` from scenario to data loader | `simulation.py` | Small |
| 5 | Add comments documenting REFERENCE_COSTS basis year | `calculations.py` | Small |
| 6 | Update calculations.md inflation section | `calculations.md` | Small |
| 7 | Document escalation parameter semantics | `settings.yaml` | Small |
| 8 | Add validation for price_basis_year coverage | `validation.py` | Small |
| 9 | Test: run simulation with and without re-anchoring, compare NPV | Manual | Medium |
| 10 | (Optional) Remove trend from toy data generation | `generate_price_data.py` | Small |

### Critical Files for Implementation

- `/Users/dpbirge/GITHUB/community-agri-pv/src/simulation/data_loader.py` - Core file: add `reanchor_price_series()` function and integrate it into `SimulationDataLoader.__init__()`. This is where all price loading and caching happens.
- `/Users/dpbirge/GITHUB/community-agri-pv/src/settings/loader.py` - Add `price_basis_year` and `discount_rate_type` fields to `EconomicsConfig` dataclass (line 297) and `_load_economics()` parsing logic.
- `/Users/dpbirge/GITHUB/community-agri-pv/src/simulation/simulation.py` - Pass `price_basis_year` from scenario to `SimulationDataLoader` in `run_simulation()` (around line 747).
- `/Users/dpbirge/GITHUB/community-agri-pv/settings/settings.yaml` - Add `price_basis_year: 2024` and `discount_rate_type: real` under the `economics:` section.
- `/Users/dpbirge/GITHUB/community-agri-pv/docs/architecture/calculations.md` - Update the "Inflation and Real vs Nominal Values" section (line 1916) to document the re-anchoring approach and real-terms framework.
