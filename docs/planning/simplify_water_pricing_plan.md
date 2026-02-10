# Plan: Simplify Water Pricing System

## Context

The current water pricing system uses residential-style tiered pricing (progressive brackets where higher consumption pays higher per-unit rates). This is inappropriate for agricultural users, who typically pay flat rates. The system also lacks separate pricing for domestic water (households and community buildings), treating all water identically.

**Problem:**
- Tier pricing adds unnecessary complexity (11 files affected, 2 calculation functions, tier metadata tracking)
- Agricultural operations don't use tiered pricing in practice (especially in Sinai)
- Domestic water consumption exists but has no cost tracking

**Solution:**
Remove tier pricing entirely and implement simple flat-rate pricing with distinction between agricultural (irrigation) and domestic (household/building) water.

---

## Design Overview

### New Configuration Schema

```yaml
water_pricing:
  municipal_source: seawater_desalination  # or piped_groundwater

  agricultural:
    pricing_regime: unsubsidized  # or subsidized (independent from domestic)
    subsidized:
      price_usd_per_m3: 0.75
    unsubsidized:
      base_price_usd_m3: 1.20
      annual_escalation_pct: 3.0

  domestic:
    pricing_regime: subsidized  # or unsubsidized (independent from agricultural)
    subsidized:
      price_usd_per_m3: 0.45  # Lower rate for households
    unsubsidized:
      base_price_usd_m3: 0.75
      annual_escalation_pct: 3.0
```

**Key features:**
- Independent pricing regimes for agricultural vs domestic water
- Simple flat rates (no tier brackets, no use_tier parameter)
- Domestic water cost tracking (new capability)
- Preserves annual escalation for unsubsidized pricing

### Architecture Changes

**Remove:**
- All tier-related dataclasses: `TierBracket`, `TierPricingConfig`, `SubsidizedPricingConfig`, `UnsubsidizedPricingConfig`
- Tier calculation functions: `calculate_tiered_cost()`, `get_marginal_tier_price()`
- Tier metadata in state: `water_tier`, `tier_effective_rate`, `cumulative_monthly_water_m3` fields
- H2 fix code (marginal vs actual cost correction no longer needed)
- Monthly water consumption tracking (only needed for tiers)

**Add:**
- New dataclasses: `AgriculturalPricingConfig`, `DomesticPricingConfig`
- Domestic water cost calculation and tracking
- Simplified price lookup (direct flat rates or escalated base prices)

**Keep:**
- Household and building water demand tracking (already implemented)
- Groundwater vs municipal water allocation policies (unchanged)
- Annual escalation for unsubsidized pricing

---

## Implementation Steps

### Phase 1: Update Dataclasses (loader.py)

**File:** `src/settings/loader.py`

1. **Delete old dataclasses** (lines 162-229):
   - `TierBracket`
   - `TierPricingConfig`
   - `SubsidizedPricingConfig`
   - `UnsubsidizedPricingConfig`

2. **Add new dataclasses**:
```python
@dataclass
class AgriculturalPricingConfig:
    """Agricultural water pricing (for crop irrigation)."""
    pricing_regime: str  # subsidized or unsubsidized
    subsidized_price_usd_m3: float
    unsubsidized_base_price_usd_m3: float
    annual_escalation_pct: float

@dataclass
class DomesticPricingConfig:
    """Domestic water pricing (for households and community buildings)."""
    pricing_regime: str  # subsidized or unsubsidized
    subsidized_price_usd_m3: float
    unsubsidized_base_price_usd_m3: float
    annual_escalation_pct: float

@dataclass
class WaterPricingConfig:
    """Water pricing configuration."""
    municipal_source: str  # seawater_desalination or piped_groundwater
    agricultural: AgriculturalPricingConfig
    domestic: DomesticPricingConfig
```

3. **Update loader function** `_load_water_pricing()` (lines 613-641):
   - Remove `_load_tier_brackets()` and `_load_tier_pricing()` function calls
   - Parse new YAML structure with agricultural/domestic sections
   - Handle missing fields with defaults:
     - Agricultural: regime=unsubsidized, subsidized=$0.75, unsubsidized_base=$1.20, escalation=3.0%
     - Domestic: regime=subsidized, subsidized=$0.45, unsubsidized_base=$0.75, escalation=3.0%

4. **Delete helper functions**:
   - `_load_tier_brackets()` (lines 563-581)
   - `_load_tier_pricing()` (lines 584-610)

### Phase 2: Remove Tier Calculation Functions (data_loader.py)

**File:** `src/simulation/data_loader.py`

1. **Delete functions**:
   - `calculate_tiered_cost()` (lines 658-746)
   - `get_marginal_tier_price()` (lines 749-778)

2. **Keep but simplify**:
   - `load_municipal_water_prices()` - Keep for CSV compatibility
   - `get_municipal_price()` - Remove `tier` parameter, return single column value
   - `SimulationDataLoader.get_municipal_price_usd_m3()` - Remove `tier` parameter

### Phase 3: Simplify Simulation Loop (simulation.py)

**File:** `src/simulation/simulation.py`

1. **Remove imports** (lines 15-16):
   - Delete `calculate_tiered_cost`, `get_marginal_tier_price` imports

2. **Update `build_water_policy_context()`** (lines 150-175):

Replace tier pricing logic with:
```python
# Get agricultural water price based on pricing regime
water_pricing = scenario.water_pricing
ag_pricing = water_pricing.agricultural

if ag_pricing.pricing_regime == "subsidized":
    municipal_price = ag_pricing.subsidized_price_usd_m3
else:
    # Unsubsidized: use base price with annual escalation
    base_price = ag_pricing.unsubsidized_base_price_usd_m3
    escalation = ag_pricing.annual_escalation_pct / 100
    years_from_start = year - scenario.metadata.start_date.year
    municipal_price = base_price * ((1 + escalation) ** years_from_start)
```

Remove `cumulative_monthly_water_m3` parameter from function signature.

3. **Delete H2 fix code block** (lines 936-960):
   - Remove entire tier cost calculation and replacement logic

4. **Add domestic water cost calculation** (new function)

5. **Integrate domestic water cost into daily loop** (after line 895)

6. **Update `update_farm_state()` call** (line 962):
   - Remove `tier_info` parameter

### Phase 4: Clean Up State Management (state.py)

**File:** `src/simulation/state.py`

1. **Update `DailyWaterRecord`**: Remove tier metadata fields
2. **Update `MonthlyConsumptionTracker`**: Remove `water_m3` field
3. **Update `FarmState`**: Delete `get_monthly_water_m3()` method
4. **Update `update_farm_state()` function**: Remove `tier_info` parameter

### Phase 5: Update Metrics (metrics.py)

**File:** `src/simulation/metrics.py`

- Remove `tier` parameter from `get_municipal_price_usd_m3()` calls (lines 889, 961)

### Phase 6: Migrate Configuration (settings.yaml)

**File:** `settings/settings.yaml`

Replace water_pricing section with new schema (agricultural + domestic sections)

### Phase 7: Update Documentation

- **docs/arch/structure.md**: Update pricing spec (lines 157-162)
- **docs/arch/calculations.md**: Remove tier section, add simple formulas
- **src/README.md**: Remove tier pricing references

---

## Critical Files

| File | Changes |
|------|---------|
| `src/settings/loader.py` | Replace 4 dataclasses, update parser |
| `src/simulation/data_loader.py` | Delete 2 functions (~150 lines) |
| `src/simulation/simulation.py` | Simplify price lookup, remove H2 fix, add domestic cost |
| `src/simulation/state.py` | Remove tier metadata fields |
| `settings/settings.yaml` | New pricing schema |
| `docs/arch/structure.md` | Update pricing spec |

---

## Verification

1. Load settings.yaml with new pricing schema
2. Test subsidized/unsubsidized pricing for agricultural and domestic
3. Run simulation and verify domestic water costs tracked
4. Check outputs have no tier metadata columns

**Expected:** Agricultural costs per farm, domestic costs at community level, no tier fields in daily records.
