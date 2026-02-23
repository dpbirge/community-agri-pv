# Crop Growth and Yield Calculations

Extracted from the consolidated calculations specification. For other domain calculations see: [calculations_water.md](calculations_water.md), [calculations_energy.md](calculations_energy.md), [calculations_economic.md](calculations_economic.md). For the index, units, references, and resilience/Monte Carlo calculations see: [calculations.md](calculations.md).

## 1. Crop Yield Estimation

**Purpose:** Calculate expected crop yield based on water availability and other factors

**Formula (simplified water production function):**

```
Y_actual = Y_potential × (1 - K_y × (1 - ET_actual / ET_crop))
```

**Parameters:**

- Y_potential: Maximum yield under optimal conditions (kg/ha)
- K_y: Yield response factor (crop-specific sensitivity to water stress)
- ET_actual: Actual evapotranspiration achieved
- ET_crop: Crop water requirement

**K\_y values by crop (FAO-33, single-season):**

| Crop | K_y | Notes |
| --- | --- | --- |
| Tomato | 1.05 | FAO-33; sensitive to deficit during flowering |
| Potato | 1.10 | FAO-33; tuber formation is water-critical |
| Onion | 1.10 | FAO-33; shallow root system amplifies stress |
| Kale | 0.95 | Approximate; based on leafy green analogues (lettuce/spinach) |
| Cucumber | 0.90 | FAO-33; moderate tolerance to short deficits |

K_y > 1.0 means a given percentage of water deficit causes a *larger* percentage of yield loss (amplified response). These values are hardcoded in `simulation.py:process_harvests()` as `KY_VALUES`. The water ratio proxy `ET_actual / ET_crop` is computed as `cumulative_water_m3 / expected_total_water_m3`, clamped to [0, 1].

**Output:** Y_actual in kg/ha

**Dependencies:**

- Precomputed data:`data/precomputed/crop_yields/yield_kg_per_ha_<crop>-toy.csv`
- Configuration:`farms[].crops[].area_fraction`
- Configuration:`farms[].yield_factor` (farm management quality)

**Growth-stage-sensitive variant (Stewart multiplicative model):**

The single-season FAO-33 formula above applies a uniform K_y across the entire season. For more accurate long-range yield estimation, the Stewart multiplicative model accounts for differing water stress sensitivity across growth stages:

```
Y_actual / Y_potential = Π_i (1 - Ky_i × (1 - ETa_i / ETc_i))
```

Where i = each growth stage (initial, development, mid-season, late). This matters because water stress during flowering (high Ky) has a much larger yield impact than the same deficit during vegetative growth (low Ky). Stage-specific Ky values are available in FAO-33 Table 2 for the modeled crops.

## 2. Soil Salinity Yield Reduction (FAO-29) — DEFERRED

> **Status: Removed from MVP simulation loop. This section is retained as reference for future enhancement. The active yield formula (§ 1) does not include salinity_factor.**

**Purpose:** Account for progressive salt accumulation in the root zone when irrigating with imperfectly desalinated water. This is a critical long-range concern for any arid-climate system using brackish groundwater, even after BWRO treatment.

**Formula (FAO-29 threshold-slope model):**

```
Y_salinity / Y_potential = 1.0                                   when ECe ≤ ECe_threshold
Y_salinity / Y_potential = 1 - b × (ECe - ECe_threshold)         when ECe > ECe_threshold
Y_salinity / Y_potential = 0                                      when ECe ≥ ECe_zero_yield
```

**Crop salinity tolerance parameters (FAO-29):**

| Crop | ECe Threshold (dS/m) | Slope b (%/dS/m) | ECe at Zero Yield (dS/m) |
| --- | --- | --- | --- |
| Tomato | 2.5 | 9.9 | 12.6 |
| Potato | 1.7 | 12.0 | 10.0 |
| Onion | 1.2 | 16.0 | 7.5 |
| Kale | 1.8* | 9.7* | 12.1* |
| Cucumber | 2.5 | 13.0 | 10.2 |

*Kale uses cabbage (Brassica oleracea) as proxy -- same species. Values from FAO-29 Table 4 (cabbage: ECe=1.8, b=9.7).

**Root zone salinity accumulation model:**

```
ECe(season) = ECe(season-1) + EC_irrigation × concentration_factor - leaching_removal

concentration_factor = 1 / (1 - ET_fraction)
  where ET_fraction = fraction of applied water consumed by ET (typically 0.7-0.9 for drip)

leaching_removal = ECe(season-1) × leaching_fraction
  where leaching_fraction = excess water applied beyond ET requirement / total applied
```

BWRO permeate typically has EC of 0.1-0.5 dS/m (from TDS 50-300 ppm), but even this accumulates over seasons in arid climates with no rainfall leaching.

**Leaching requirement:**

```
LR = EC_irrigation / (5 × ECe_threshold - EC_irrigation)
```

The leaching requirement is the minimum fraction of extra water that must pass through the root zone to prevent salt buildup. For drip irrigation with BWRO permeate, LR is typically 0.05-0.15 (5-15% extra water).

**Combined yield model:**

```
Y_actual = Y_potential × water_stress_factor × salinity_factor × yield_factor

water_stress_factor = (1 - K_y × (1 - ET_actual / ET_crop))
salinity_factor = max(0, 1 - b × max(0, ECe - ECe_threshold) / 100)
```

**Dependencies:**

- Parameter file: `data/parameters/crops/crop_salinity_tolerance-toy.csv` (FAO-29 salinity thresholds; via registry `crops.salinity_tolerance`)
- Configuration: BWRO permeate quality (derived from `water_system.water_treatment.tds_ppm` and recovery rate)
- Simulation output: cumulative irrigation records per crop

**Notes:**

- For MVP: Can be omitted if simulation is ≤3 years. For simulations >5 years with brackish water sources, salinity accumulation is a first-order yield effect
- Onion and potato are most salt-sensitive among the modeled crops — these will show yield decline first
- Periodic leaching events (applying extra water beyond ET) are the standard management practice and should be factored into water demand calculations

**Sources:**

- FAO Irrigation and Drainage Paper No. 33 (Doorenbos & Kassam, 1979)
- FAO Irrigation and Drainage Paper No. 29 Rev.1 (Ayers & Westcot, 1985) — Water quality for agriculture
- Regional yield data for Sinai Peninsula and similar arid climates
- Maas & Hoffman (1977) — Crop salt tolerance: current assessment (original threshold-slope data)

## 3. Crop Growth Stages

**Purpose:** Track crop development and adjust water requirements

**Stages:** Initial → Development → Mid-season → Late season

**Duration:** Crop and climate-specific (from parameter files)

**K\_c by Stage (example for tomato):**

- Initial: 0.6
- Development: 0.6 → 1.15 (linear increase)
- Mid-season: 1.15
- Late season: 1.15 → 0.7 (linear decrease)

**Dependencies:**

- Parameter file:`data/parameters/crops/crop_coefficients-toy.csv`
- Configuration:`farms[].crops[].planting_dates`

**Sources:**

- FAO-56 crop coefficient tables
- Regional crop calendars for Egypt

## 4. Post-Harvest Handling Losses

**Purpose:** Calculate physical losses from bruising, handling damage, and rejected product between harvest and the processing intake point. This is distinct from processing weight loss (water removal, trimming), which is covered in the Processed Product Output section below.

**Formula (applied before the food processing split):**

```
handling_loss_kg = raw_yield_kg × handling_loss_rate
harvest_available_kg = raw_yield_kg - handling_loss_kg
```

`harvest_available_kg` is the quantity that enters the food processing pipeline (simulation_flow.md § 3, Step 4). The food policy split, capacity clipping, and processing weight loss all operate on `harvest_available_kg`, not `raw_yield_kg`.

**Handling loss rate:**

- Default: 0.05 (5%) -- configurable via `post_harvest_handling_loss_rate` in `settings.yaml`
- The 5% default reflects reduced losses from on-site processing. FAO estimates 10-15% for typical developing-economy supply chains where produce must be transported to distant markets or processing facilities. The community's co-located processing facility eliminates most transport-related spoilage and damage.
- Crop-specific handling loss rates may be defined in `data/parameters/crops/crop_coefficients-toy.csv` for future refinement.

**Parameters:**

- `handling_loss_rate`: From `settings.yaml` `post_harvest_handling_loss_rate` (default 0.05). Applies uniformly to all crops at the harvest point, before any processing pathway decision.

**Output:** handling_loss_kg in kg per harvest event; tracked as a standalone metric for reporting

**Notes:**

- This handling loss is physically separate from the processing weight loss (see Processed Product Output below). The two losses are applied sequentially: handling loss first (harvest to processing intake), then processing weight loss (during drying, canning, etc.).
- The `(1 - loss_rate)` term has been removed from the fresh revenue formula (see [calculations_economic.md](calculations_economic.md) Crop Revenue Calculation) because the handling loss is now applied upstream. Revenue is computed on `output_kg` which already reflects both the handling loss and the processing weight loss (0% for fresh).

**Sources:**

- FAO post-harvest loss assessment methodology (FAO-PHL)
- FAO Irrigation and Drainage Paper No. 33 (Doorenbos & Kassam, 1979)
- Typical fresh produce losses in developing economies: 10-15% (Hodges et al., 2011)
- Reduced to 5% for on-site processing based on elimination of transport and wholesale market handling

## 5. Processed Product Output

**Purpose:** Calculate output quantity of processed products from raw harvest input

**Formula:**

```
Processed_output_kg = raw_input_kg × (1 - weight_loss_pct / 100)
```

**Per-crop, per-processing-type weight loss (from \****`data/parameters/crops/processing_specs-toy.csv`**\*\*):**

| Crop | Fresh | Packaged | Canned | Dried |
| --- | --- | --- | --- | --- |
| Tomato | 0% | 3% | 15% | 88% |
| Potato | 0% | 3% | 15% | 78% |
| Onion | 0% | 3% | 15% | 80% |
| Kale | 0% | 3% | 15% | 82% |
| Cucumber | 0% | 3% | 15% | 92% |

**Value-add multiplier** (processed price = fresh price × multiplier):

- Packaged: 1.25×
- Canned: 1.80×
- Dried: 3.50×

**Allocation logic:**

The food processing policy determines what fraction of each crop goes to each processing pathway. See `policies.md` Food Processing Policies for full allocation rules for all four policies (`all_fresh`, `maximize_storage`, `balanced_mix`, `market_responsive`), including the forced-sale umbrella rule.

**Policy-specific allocation fractions:**

See `policies.md` Food Processing Policies for the authoritative fraction tables for all policies (`all_fresh`, `maximize_storage`, `balanced_mix`, `market_responsive`), including the `market_responsive` price-trigger logic. Fractions are not duplicated here to avoid divergence.

**Dependencies:**

- Parameter file:`data/parameters/crops/processing_specs-toy.csv` (weight loss, value multipliers)
- Configuration:`food_processing_system.[type].equipment` (energy and cost calculations only; processing throughput is unlimited)
- Food processing policy selection (allocation fractions)
- Crop yield output from simulation

**Notes:**

- Current data is toy-grade; research plan for processed product data is pending (see `future_improvements.md`)
- Processing throughput is unlimited; storage capacity is the binding constraint on inventory

## 6. Crop Diversity Index

**Purpose:** Quantify the diversity of crops grown as a measure of revenue resilience

**Formula (Shannon Diversity Index):**

```
H = -Σ (p_i × ln(p_i))  for all crops where p_i > 0
```

**Where:**

- `p_i`: Proportion from crop i (see basis note below)
- `p_i = yield_crop_i / total_yield` (or revenue-weighted variant; see note)

**Complementary metric — crop count:**

```
Crop_count = count of crops with area_fraction > 0
```

**Output:** Shannon index H (dimensionless, higher = more diverse); crop count (integer)

**Interpretation:**

- H = 0: Monoculture (one crop only)
- H = ln(n): Maximum diversity (all n crops equally represented)
- For 5 crops: H_max = ln(5) ≈ 1.61

**Notes:**

- This is a*(resilience)* metric
- Can be computed on yield basis or revenue basis; revenue-weighted is more meaningful for economic resilience

> **MVP implementation note:** The current implementation in `metrics.py:_compute_spec_metrics()` computes the Shannon index using **area-based proportions** (`p_i = crop_area_ha / total_area_ha`), aggregated across all farms for each year. This is simpler and more stable than yield-based or revenue-based weighting, since area is known at planting time regardless of harvest outcomes. Yield-weighted and revenue-weighted variants are planned as future enhancements for economic resilience analysis.

## 7. PV Microclimate Yield Protection

> **Status: TBD** — Requires crop-specific heat stress thresholds and agri-PV microclimate data. Research plan for microclimate yield effects is pending (see `future_improvements.md`). Target data file: `data/parameters/crops/microclimate_yield_effects-research.csv`.

**Purpose:** Estimate the fraction of crop yield protected from extreme heat by agri-PV shading

**Formula (once data is available):**

```
On days where T_max > heat_stress_threshold_C:
  Yield_modifier = 1 + (net_yield_effect_pct / 100)

On days where T_max ≤ heat_stress_threshold_C:
  Yield_modifier = 1 - (par_reduction_pct / 100) × light_sensitivity_factor

Yield_protection_pct = (Y_shaded - Y_unshaded) / Y_unshaded × 100
```

**Where:**

- `Y_shaded`: Yield under agri-PV panels (reduced ET demand, lower leaf temperature)
- `Y_unshaded`: Yield in open field (full solar exposure, higher heat stress)
- `net_yield_effect_pct`: Net yield change from shading, per crop and PV density (from data file)
- `par_reduction_pct`: Reduction in photosynthetically active radiation (from data file)
- `heat_stress_threshold_C`: Per-crop temperature threshold (from data file)

**Parameters needed (per crop × PV density):**

- Temperature reduction under panels (°C): typically 1.5–4.5°C depending on density
- ET reduction (%): typically 5–30% depending on density
- PAR reduction (%): 15–50% depending on density
- Net yield effect (%): can be positive (shade benefit > light loss) in hot climates
- Heat stress threshold (°C): crop-specific, typically 30–35°C

**Dependencies:**

- Configuration:`energy_system.pv.density`,`energy_system.pv.height_m`
- Precomputed data: daily maximum temperatures from weather data
- Parameter file:`data/parameters/crops/microclimate_yield_effects-research.csv` (to be created)

**Sources:**

- Dupraz et al. (2011) — Land Equivalent Ratio under agri-PV
- Barron-Gafford et al. (2019) — Agrivoltaics provide mutual benefits across the food-energy-water nexus in a hot arid climate
- Marrou et al. (2013) — Productivity and radiation use efficiency of lettuces grown under agrivoltaic systems
- Weselek et al. (2019) — Review of agri-PV effects on crop production
