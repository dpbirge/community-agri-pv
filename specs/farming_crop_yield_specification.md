# Farming and Crop Yield Specification

---

## Overview

The farming and crop yield subsystem simulates irrigated agriculture within a community agri-photovoltaic project in the Sinai Peninsula, Egypt. It models daily irrigation water demand per field, tracks crop growing seasons across multiple years, and computes harvest yields using the FAO Paper 33 water-yield response function.

The subsystem spans all three architectural layers:

- **Layer 1 (Pre-computed Data)**: Crop growth parameter CSVs, daily crop growth lookup tables, weather data, irrigation system specs.
- **Layer 2 (Configuration)**: Farm profile YAML defining farms, fields, crops, areas, conditions, and irrigation systems. Water policy YAML controlling irrigation mode and dispatch strategy.
- **Layer 3 (Simulation Engine)**: Source modules that normalize farm profiles, compute daily irrigation demand, and calculate harvest yields from water delivery history.

The key data flow is:

1. Farm profile defines fields with crops, areas, conditions, and irrigation systems.
2. `compute_irrigation_demand()` loads pre-computed crop daily growth CSVs, extracts daily ETc, and scales by field area and irrigation efficiency to produce m3/day demand per field.
3. The water balance orchestrator (`compute_daily_water_balance()`) feeds this demand to the water supply dispatch system, which delivers water subject to source constraints, treatment capacity, and monthly caps.
4. After simulation, the notebook iterates over harvest events and calls `compute_harvest_yield()` for each field-crop-planting-year combination, using the FAO Paper 33 formula to convert cumulative water delivery ratios into predicted yield.
5. Results are written to `simulation/daily_harvest_yields.csv`.

---

## Configuration (Layer 2)

### Farm Profile YAML

**File**: `settings/farm_profile_base.yaml`

Top-level structure:

```yaml
config_name: baseline_farm_collective

farms:
  - name: farm_1
    fields:
      - name: north_field
        area_ha: 1
        water_system: main_irrigation
        irrigation_system: drip
        condition: openfield
        plantings:
          - crop: kale
            plantings: [oct01]
          - crop: tomato
            plantings: [feb15]
```

**Farm-level keys**:

| Key    | Type   | Description              |
|--------|--------|--------------------------|
| `name` | string | Unique farm identifier   |
| `fields` | list | List of field definitions |

**Field-level keys**:

| Key                 | Type   | Description                                                                 |
|---------------------|--------|-----------------------------------------------------------------------------|
| `name`              | string | Unique field identifier across all farms                                    |
| `area_ha`           | float  | Cultivated area in hectares                                                 |
| `water_system`      | string | Name of water system this field draws from (e.g. `main_irrigation`)         |
| `irrigation_system` | string | Irrigation type: `drip`, `sprinkler`, or `furrow`                           |
| `condition`         | string | Microclimate condition: `openfield`, `underpv_low`, `underpv_medium`, `underpv_high` |
| `plantings`         | list   | List of crop entries, each with `crop` name and `plantings` date code list  |

**Planting entry structure**:

| Key         | Type         | Description                                                    |
|-------------|--------------|----------------------------------------------------------------|
| `crop`      | string       | Crop name matching data files (e.g. `tomato`, `kale`)          |
| `plantings` | list[string] | Planting date codes (e.g. `feb15`, `oct01`, `sep01`)           |

A single field can have multiple crop entries with multiple planting dates, enabling sequential cropping within a year. The overlap validator ensures no two growing seasons overlap on the same field.

**Available crops and planting codes** (from `planting_windows-research.csv`):

| Crop     | Planting Codes                   |
|----------|----------------------------------|
| cucumber | apr01, feb15, oct15, sep01       |
| kale     | dec01, feb01, mar15, oct01       |
| onion    | apr01, dec01, jan15              |
| potato   | jan15, nov15, sep15              |
| tomato   | apr01, aug01, feb15, nov01       |

**Planting code format**: Three-letter month abbreviation + two-digit day (e.g. `feb15` = February 15, `oct01` = October 1). Converted to MM-DD format internally via `planting_code_to_mmdd()`.

### Water Policy YAML (Irrigation-Relevant Section)

**File**: `settings/water_policy_base.yaml`

The `irrigation` section controls how crop water demand is determined:

```yaml
irrigation:
  mode: static          # static | dynamic
  static_policy: full_eto
```

| Key             | Values                                                        | Description                                                                                              |
|-----------------|---------------------------------------------------------------|----------------------------------------------------------------------------------------------------------|
| `mode`          | `static`, `dynamic`                                           | `static`: demand comes from a named pre-baked policy in growth CSVs. `dynamic`: demand uses `full_eto` as baseline; actual delivery determined by water supply system. |
| `static_policy` | `full_eto`, `optimal_deficit`, `deficit_80`, `deficit_60`, `rainfed` | Which irrigation policy column to read from crop growth CSVs when `mode=static`.                          |

When `mode=dynamic`, the irrigation demand module always requests `full_eto` demand. The water supply dispatch system then delivers what it can, and any shortfall propagates to yield reduction via the FAO response function.

### Scenario YAML

**File**: `scenarios/scenario_base.yaml`

References the farm profile and water policy files:

```yaml
farm_profiles: settings/farm_profile_base.yaml
water_policy:  settings/water_policy_base.yaml
data_registry: settings/data_registry_base.yaml
```

### Data Registry YAML

**File**: `settings/data_registry_base.yaml`

Maps logical data names to file paths (relative to repo root). Farming-relevant entries:

```yaml
crops:
  growth_params:           data/crops/crop_params/crop_growth_params-research.csv
  yield_response_factors:  data/crops/crop_params/yield_response_factors-research.csv
  daily_growth_dir:        data/crops/crop_daily_growth

water_supply:
  irrigation_systems:      data/water/irrigation_systems-toy.csv
```

Note: `planting_windows-research.csv` is not registered in the data registry. It is resolved by `_load_season_lengths()` in `src/farm_profile.py` via path inference from the `growth_params` CSV location (same parent directory).

---

## Data Inputs (Layer 1)

### Crop Growth Parameters

**File**: `data/crops/crop_params/crop_growth_params-research.csv`

Source: FAO Paper 33, FAO Paper 66, Monteith/Sinclair RUE literature, FAO Paper 29 (salt tolerance).

| Column                           | Type    | Unit                   | Description                                              |
|----------------------------------|---------|------------------------|----------------------------------------------------------|
| `crop`                           | string  | --                     | Crop name                                                |
| `potential_yield_kg_per_ha`      | float   | kg fresh weight/ha     | Maximum attainable fresh yield under optimal conditions   |
| `harvest_index`                  | float   | dimensionless (0-1)    | Fraction of above-ground dry biomass that is marketable   |
| `rue_g_per_mj`                   | float   | g DM / MJ PAR          | Radiation use efficiency                                  |
| `dry_matter_fraction`            | float   | dimensionless (0-1)    | Fraction of fresh weight that is dry matter               |
| `t_base_c`                       | float   | degrees Celsius        | Base temperature (growth ceases below)                    |
| `t_opt_low_c`                    | float   | degrees Celsius        | Lower bound of optimal temperature range                  |
| `t_opt_high_c`                   | float   | degrees Celsius        | Upper bound of optimal temperature range                  |
| `t_max_c`                        | float   | degrees Celsius        | Maximum temperature (growth ceases above)                 |
| `tds_no_penalty_ppm`            | float   | ppm                    | TDS below which yield is unaffected                       |
| `tds_lethal_ppm`                | float   | ppm                    | TDS above which crop dies                                 |
| `tds_yield_decline_pct_per_100ppm` | float | % per 100 ppm         | Linear yield decline rate in TDS stress zone              |
| `salt_tolerance`                 | string  | --                     | FAO tolerance rating: S=sensitive, MS=moderately sensitive |

Current crop values:

| Crop     | Potential Yield (kg/ha) | Harvest Index | RUE (g/MJ) | t_base | t_opt_low | t_opt_high | t_max | TDS No Penalty (ppm) |
|----------|------------------------|---------------|-------------|--------|-----------|------------|-------|----------------------|
| tomato   | 60,000                 | 0.60          | 1.60        | 10     | 20        | 28         | 35    | 1,070                |
| potato   | 35,000                 | 0.75          | 1.55        | 5      | 17        | 24         | 30    | 730                  |
| onion    | 40,000                 | 0.80          | 1.20        | 7      | 18        | 27         | 35    | 510                  |
| kale     | 25,000                 | 0.85          | 1.40        | 5      | 15        | 22         | 30    | 770                  |
| cucumber | 40,000                 | 0.65          | 1.50        | 12     | 22        | 30         | 38    | 1,070                |

### Yield Response Factors

**File**: `data/crops/crop_params/yield_response_factors-research.csv`

Source: FAO Paper 33 (Doorenbos & Kassam, 1979).

| Column              | Type   | Unit            | Description                                                |
|---------------------|--------|-----------------|------------------------------------------------------------|
| `crop`              | string | --              | Crop name                                                  |
| `ky_whole_season`   | float  | dimensionless   | Yield sensitivity to water deficit (whole-season Ky)        |
| `wue_curvature`     | float  | dimensionless   | Controls concavity of water-yield curve (beta parameter)    |
| `source`            | string | --              | Citation                                                    |
| `notes`             | string | --              | Additional context                                          |

Current values:

| Crop     | Ky   | WUE Curvature | Notes                                     |
|----------|------|---------------|-------------------------------------------|
| tomato   | 1.05 | 3.5           | Most sensitive during flowering            |
| potato   | 1.10 | 3.5           | Most sensitive during stolonization        |
| onion    | 1.10 | 3.5           | Most sensitive during bulb formation       |
| kale     | 0.95 | 3.5           | Cabbage proxy; may be 5-10% less sensitive |
| cucumber | 1.00 | 3.5           | Literature consensus (not in FAO 33)       |

Interpretation: Ky > 1.0 means yield drops more than proportionally to water deficit (sensitive). Ky < 1.0 means yield drops less than proportionally (tolerant).

### Planting Windows

**File**: `data/crops/crop_params/planting_windows-research.csv`

Source: Egyptian Ministry of Agriculture, FAO Crop Calendar Platform.

| Column                          | Type   | Unit | Description                                     |
|---------------------------------|--------|------|-------------------------------------------------|
| `crop`                          | string | --   | Crop name                                       |
| `planting_date_mmdd`            | string | --   | Planting date in MM-DD format                   |
| `season_label`                  | string | --   | Season name (e.g. `winter-spring`, `fall`, `nili`) |
| `window_type`                   | string | --   | `primary` or `secondary`                         |
| `expected_season_length_days`   | int    | days | Days from planting to final harvest              |
| `notes`                         | string | --   | Additional context                               |

Season lengths by crop and planting date:

| Crop     | Planting  | Season Length | Season Label   |
|----------|-----------|--------------|----------------|
| tomato   | 02-15     | 135 days     | winter-spring  |
| tomato   | 04-01     | 135 days     | spring         |
| tomato   | 08-01     | 120 days     | nili           |
| tomato   | 11-01     | 135 days     | fall-winter    |
| potato   | 09-15     | 120 days     | fall           |
| potato   | 11-15     | 120 days     | winter         |
| potato   | 01-15     | 110 days     | winter-spring  |
| onion    | 12-01     | 150 days     | fall-winter    |
| onion    | 01-15     | 150 days     | winter         |
| onion    | 04-01     | 130 days     | spring         |
| kale     | 10-01     | 85 days      | fall           |
| kale     | 12-01     | 85 days      | winter         |
| kale     | 02-01     | 85 days      | winter-spring  |
| kale     | 03-15     | 75 days      | spring         |
| cucumber | 02-15     | 95 days      | winter-spring  |
| cucumber | 04-01     | 85 days      | spring         |
| cucumber | 09-01     | 95 days      | fall           |
| cucumber | 10-15     | 95 days      | fall-winter    |

### Crop Coefficients (Kc by Growth Stage)

**File**: `data/crops/crop_params/crop_coefficients-research.csv`

Source: FAO Irrigation and Drainage Paper No. 56.

| Column               | Type   | Unit            | Description                                             |
|----------------------|--------|-----------------|---------------------------------------------------------|
| `crop`               | string | --              | Crop name                                               |
| `stage`              | string | --              | Growth stage: `initial`, `development`, `mid`, `late`   |
| `days_in_stage`      | int    | days            | Duration of this growth stage                           |
| `kc_value`           | float  | dimensionless   | Crop coefficient (ETc = Kc * ETo)                       |
| `root_depth_m`       | float  | meters          | Effective root depth during stage                       |
| `critical_depletion` | float  | dimensionless   | Fraction of available water depletable before stress    |

Four rows per crop (one per stage). During the `development` stage, Kc transitions linearly from initial to mid-season values. During `late` stage, Kc transitions from mid to end values.

### Microclimate Yield Effects

**File**: `data/crops/crop_params/microclimate_yield_effects-research.csv`

Source: Barron-Gafford et al. (2019), Marrou et al. (2013), Weselek et al. (2021).

| Column                    | Type   | Unit         | Description                                         |
|---------------------------|--------|--------------|-----------------------------------------------------|
| `crop`                    | string | --           | Crop name                                           |
| `pv_density`              | string | --           | Panel density: `low`, `medium`, `high`              |
| `temperature_reduction_C` | float  | degrees C    | Average daytime air temperature reduction            |
| `et_reduction_pct`        | float  | percentage   | Evapotranspiration reduction percentage              |
| `par_reduction_pct`       | float  | percentage   | PAR reduction percentage                             |
| `net_yield_effect_pct`    | float  | percentage   | Net yield change (positive = increase)               |
| `heat_stress_threshold_C` | float  | degrees C    | Temperature above which heat stress occurs           |

Note: This file is **not directly used by the simulation engine**. The ET reduction and temperature adjustments for agri-PV conditions are instead captured through condition-specific weather files and the PV microclimate factors file (see below). This file serves as a reference for the net yield effects observed in literature.

### PV Microclimate Factors

**File**: `data/weather/pv_microclimate_factors-research.csv`

Source: Meta-analysis of 320 experiments from 111 agri-PV sites.

| Column                          | Type   | Unit            | Description                                           |
|---------------------------------|--------|-----------------|-------------------------------------------------------|
| `density_variant`               | string | --              | `low`, `medium`, `high`                               |
| `ground_coverage_pct`           | int    | percentage      | Ground area covered by panel projection               |
| `temp_adjustment_c`             | float  | degrees C       | Temperature shift (negative = cooling)                |
| `irradiance_multiplier`         | float  | fraction (0-1)  | Fraction of full-sun PAR reaching crop level          |
| `wind_speed_multiplier`         | float  | fraction (0-1)  | Fraction of ambient wind speed at crop level          |
| `evapotranspiration_multiplier` | float  | fraction (0-1)  | Fraction of reference ET                              |

Current values:

| Density | GCR  | Temp Adj  | Irradiance | Wind  | ET    |
|---------|------|-----------|------------|-------|-------|
| low     | 30%  | -0.80 C   | 0.65       | 0.95  | 0.85  |
| medium  | 50%  | -1.50 C   | 0.50       | 0.85  | 0.80  |
| high    | 80%  | -2.50 C   | 0.35       | 0.60  | 0.55  |

These factors are applied to openfield weather data by the `generate_underpv_weather.py` script to produce condition-specific weather files.

### Daily Crop Growth Lookup Tables

**Directory**: `data/crops/crop_daily_growth/{crop}/`

**Naming convention**: `{crop}_{planting_code}_{condition}-research.csv`
  - Example: `tomato_feb15_openfield-research.csv`
  - Example: `cucumber_sep01_underpv_low-research.csv`

One file per (crop, planting date, condition) combination. Each file contains all irrigation policies crossed with all weather years. Total of 80 files (5 crops x 4 planting dates avg x 4 conditions).

**Generated by**: `data/_scripts/generate_crop_lookup.py`

| Column                    | Type   | Unit                  | Description                                                      |
|---------------------------|--------|-----------------------|------------------------------------------------------------------|
| `irrigation_policy`       | string | --                    | Policy name: `full_eto`, `optimal_deficit`, `deficit_80`, `deficit_60`, `rainfed` |
| `weather_scenario_id`     | string | --                    | Weather scenario identifier (e.g. `001`)                         |
| `weather_year`            | int    | --                    | Year of weather data used                                        |
| `day_of_season`           | int    | --                    | Day within the growing season (1-based)                          |
| `date`                    | string | YYYY-MM-DD            | Calendar date                                                    |
| `growth_stage`            | string | --                    | Current stage: `initial`, `development`, `mid`, `late`           |
| `kc`                      | float  | dimensionless         | Crop coefficient on this day                                     |
| `fpar`                    | float  | fraction (0-1)        | Fractional PAR interception                                      |
| `eto_mm`                  | float  | mm/day                | Reference evapotranspiration (Hargreaves)                        |
| `etc_mm`                  | float  | mm/day                | Crop evapotranspiration                                          |
| `water_applied_mm`        | float  | mm/day                | Actual water applied (irrigation + precipitation)                |
| `water_stress_coeff`      | float  | fraction (0-1)        | Ks = min(1, water_applied / ETc)                                 |
| `temp_stress_coeff`       | float  | fraction (0-1)        | Kt from piecewise-linear cardinal temperature model              |
| `biomass_kg_ha`           | float  | kg DM/ha/day          | Daily above-ground dry biomass increment                         |
| `cumulative_biomass_kg_ha`| float  | kg DM/ha              | Running total of above-ground dry biomass                        |
| `yield_fresh_kg_ha`       | float  | kg fresh weight/ha    | Harvest yield (non-zero only on final day of season)             |

**Irrigation policies and their water application fractions**:

| Policy            | Fraction of ETc | Notes                                     |
|-------------------|-----------------|-------------------------------------------|
| `full_eto`        | 1.00 (100%)     | Full crop water requirement               |
| `optimal_deficit` | Crop-specific   | Crop-optimized deficit fraction            |
| `deficit_80`      | 0.80 (80%)      | Fixed 80% of ETc                          |
| `deficit_60`      | 0.60 (60%)      | Fixed 60% of ETc                          |
| `rainfed`         | 0.00 (0%)       | Precipitation only                        |

Optimal deficit fractions by crop (hardcoded in `generate_crop_lookup.py`):

| Crop     | Optimal Fraction |
|----------|-----------------|
| tomato   | 0.80            |
| potato   | 0.85            |
| onion    | 0.80            |
| kale     | 0.75            |
| cucumber | 0.80            |

### Weather Data

**Directory**: `data/weather/`

Four weather files, one per condition:
- `daily_weather_openfield-research.csv` -- Base weather from NASA POWER API (MERRA-2 reanalysis)
- `daily_weather_underpv_low-research.csv` -- Adjusted for low-density agri-PV (30% GCR)
- `daily_weather_underpv_medium-research.csv` -- Adjusted for medium-density agri-PV (50% GCR)
- `daily_weather_underpv_high-research.csv` -- Adjusted for high-density agri-PV (80% GCR)

| Column                     | Type   | Unit       | Description                                |
|----------------------------|--------|------------|--------------------------------------------|
| `date`                     | string | YYYY-MM-DD | Calendar date                              |
| `temp_max_c`               | float  | Celsius    | Daily maximum 2-meter air temperature      |
| `temp_min_c`               | float  | Celsius    | Daily minimum 2-meter air temperature      |
| `solar_irradiance_kwh_m2`  | float  | kWh/m2/day | Surface solar irradiance                   |
| `wind_speed_ms`            | float  | m/s        | 10-meter wind speed                        |
| `precip_mm`                | float  | mm/day     | Bias-corrected precipitation               |
| `weather_scenario_id`      | string | --         | Scenario identifier (e.g. `001`)           |

Date range: 2010-01-01 through 2024-12-31 (15 years). Location: 28N, 34E (Sinai Peninsula, Red Sea coast).

Under-PV weather files are derived from openfield data by applying PV microclimate factors: temperature shifted by `temp_adjustment_c`, irradiance multiplied by `irradiance_multiplier`, wind speed multiplied by `wind_speed_multiplier`. Precipitation is passed through unchanged.

### Irrigation Systems

**File**: `data/water/irrigation_systems-toy.csv`

| Column                         | Type   | Unit           | Description                                     |
|--------------------------------|--------|----------------|-------------------------------------------------|
| `irrigation_type`              | string | --             | Full name: `drip_irrigation`, `sprinkler_irrigation`, `furrow_irrigation` |
| `efficiency`                   | float  | fraction (0-1) | Water delivery efficiency                        |
| `capital_cost_per_ha`          | float  | USD/ha         | Installation cost                                |
| `om_cost_per_ha_per_year`      | float  | USD/ha/year    | Annual operating and maintenance cost            |
| `application_energy_kwh_per_m3`| float  | kWh/m3         | Energy to apply water to field                   |

Current values:

| Type      | Efficiency | Capital (USD/ha) | O&M (USD/ha/yr) | Energy (kWh/m3) |
|-----------|-----------|-------------------|------------------|-----------------|
| drip      | 0.90      | 3,500             | 180              | 0.06            |
| sprinkler | 0.75      | 2,200             | 120              | 0.12            |
| furrow    | 0.60      | 800               | 50               | 0.02            |

The efficiency lookup supports both full names (e.g. `drip_irrigation`) and short names (e.g. `drip`) for compatibility with farm profile conventions.

---

## Computation Logic (Layer 3)

### Farm Profile Normalization and Validation

**Module**: `src/farm_profile.py`

**Functions**:

```python
def planting_code_to_mmdd(code)
    # Converts 'oct01' -> '10-01', 'feb15' -> '02-15'

def normalize_plantings(field)
    # Expands field['plantings'] to flat list of {crop, planting} dicts
    # Input:  [{crop: 'kale', plantings: ['oct01', 'dec01']}, ...]
    # Output: [{crop: 'kale', planting: 'oct01'}, {crop: 'kale', planting: 'dec01'}, ...]

def validate_no_overlap(farm_config, registry, root_dir)
    # Raises ValueError if any field has overlapping growing seasons
    # Uses planting_windows-research.csv for season lengths
    # Computes (start_date, end_date) intervals and checks all pairs on each field
```

The overlap validation uses a reference year (2020) and computes season intervals using `expected_season_length_days` from the planting windows file. Two intervals overlap if `start_a < end_b and start_b < end_a`.

**Internal helper**:

```python
def _load_season_lengths(registry, root_dir)
    # Returns dict mapping (crop, mmdd) -> expected_season_length_days
    # Path: resolved from registry['crops']['growth_params'] parent / 'planting_windows-research.csv'
```

### Irrigation Demand Calculation

**Module**: `src/irrigation_demand.py`

**Public function signature**:

```python
def compute_irrigation_demand(
    farm_profiles_path,
    registry_path,
    *,
    water_system_name='main_irrigation',
    irrigation_policy='full_eto',
    water_policy_path=None,
    root_dir=None,
)
```

**Computation steps**:

1. **Resolve irrigation policy**: If `water_policy_path` is provided, reads the water policy YAML. For `static` mode, uses the `static_policy` value. For `dynamic` mode, uses `full_eto`.

2. **Validate farm profile**: Calls `validate_no_overlap()` to check for season conflicts.

3. **Load data**: Irrigation efficiency lookup from `irrigation_systems-toy.csv`, crop TDS thresholds from `crop_growth_params-research.csv`, crop daily growth CSVs from `data/crops/crop_daily_growth/`.

4. **Collect fields**: Filters all fields across all farms that are linked to the specified `water_system_name`.

5. **Per-field demand** (via `_compute_field_demand()`):
   - For each planting on the field, loads the crop daily growth CSV matching `(crop, planting, condition, irrigation_policy)`.
   - Extracts the `etc_mm` column (daily crop evapotranspiration).
   - Concatenates all plantings for the field.
   - Computes delivery demand:

     ```
     demand_m3 = etc_mm * area_ha * 10 / irrigation_efficiency
     ```

     Where the factor of 10 converts mm over 1 hectare to cubic meters (1 mm * 1 ha = 10 m3).

   - Output columns per field: `{name}_etc_mm_per_ha`, `{name}_demand_m3`, `{name}_crop`.

6. **Assemble full date range**: Creates a complete daily date axis spanning Jan 1 of the earliest year to Dec 31 of the latest year found in the data. Left-joins all field demand DataFrames onto this axis. Fallow days (no active crop) get 0.0 demand and `'none'` for the crop column.

7. **Aggregate**:
   - `total_demand_m3`: Sum of all field `_demand_m3` columns.
   - `crop_tds_requirement_ppm`: Minimum `tds_no_penalty_ppm` across all active crops on each day. On days with no active crop, this is NaN.

8. **Rename `date` to `day`** in the output DataFrame.

**Output columns**:

| Column                        | Type   | Unit   | Description                                           |
|-------------------------------|--------|--------|-------------------------------------------------------|
| `day`                         | datetime | --   | Calendar date                                         |
| `{field}_etc_mm_per_ha`       | float  | mm/day | Raw ETc for the active crop on this field              |
| `{field}_demand_m3`           | float  | m3/day | Water delivery demand after area and efficiency scaling |
| `{field}_crop`                | string | --     | Crop name active on this field (`'none'` if fallow)    |
| `total_demand_m3`             | float  | m3/day | Sum of all field demands                               |
| `crop_tds_requirement_ppm`    | float  | ppm    | Minimum TDS threshold across active crops (NaN if none)|

**Supporting function**:

```python
def get_field_irrigation_specs(
    farm_profiles_path, registry_path,
    *,
    water_system_name='main_irrigation',
    root_dir=None,
)
```

Returns a dict mapping `field_name` to `{irrigation_system, application_energy_kwh_per_m3}`. Used by the water balance orchestrator to compute per-field application energy.

### Crop Yield Calculation

**Module**: `src/crop_yield.py`

**Public function signature**:

```python
def compute_harvest_yield(
    crop,
    planting,
    condition,
    weather_year,
    delivered_m3_series,
    demand_m3_series,
    *,
    registry_path,
    root_dir=None,
)
```

**FAO Paper 33 Water-Yield Response Formula**:

```
f     = ETa_season / ETc_season       (clamped to [0, 1])
alpha = max(1.0, 1 + wue_curvature * (1.15 - ky_whole_season))
yield_kg_ha = potential_yield_kg_per_ha * f^(1/alpha) * avg_Kt
```

Where:
- `f` is the ratio of cumulative actual water delivered to cumulative potential demand over the growing season.
- `alpha` controls the concavity of the response curve. Higher alpha produces a more concave curve, meaning mild deficits have less yield impact.
- `avg_Kt` is the mean daily temperature stress coefficient over the season.

**Computation steps**:

1. **Load yield parameters**: From `yield_response_factors-research.csv` (ky, wue_curvature) and `crop_growth_params-research.csv` (potential_yield_kg_per_ha).

2. **Load temperature stress series**: From the crop daily growth CSV for this (crop, planting, condition, weather_year) combination, filtered to `irrigation_policy='full_eto'`. Extracts the `temp_stress_coeff` column.

3. **Align delivered and demand series**: Inner-joins on the date index. Both series are expected to be `pd.Series` indexed by date.

4. **Compute daily ETa**: `ETa = min(delivered, demand)` per day. This means over-delivery beyond demand does not count as additional crop water use.

5. **Compute seasonal ratio**: `f = sum(ETa) / sum(ETc)`, clamped to [0, 1].

6. **Compute average temperature stress**: Mean of `temp_stress_coeff` series aligned to the season dates.

7. **Compute alpha**: `alpha = max(1.0, 1.0 + wue_curvature * (1.15 - ky))`.

8. **Compute yield**: `yield_kg_ha = potential_yield * f^(1/alpha) * avg_Kt`.

9. **Return**: Float value in kg/ha (fresh weight).

**Alpha values for current crops** (with wue_curvature=3.5 for all):

| Crop     | Ky   | Alpha = max(1, 1 + 3.5 * (1.15 - Ky)) | Interpretation           |
|----------|------|------------------------------------------|--------------------------|
| tomato   | 1.05 | 1.35                                     | Mild concavity           |
| potato   | 1.10 | 1.175                                    | Near-linear response     |
| onion    | 1.10 | 1.175                                    | Near-linear response     |
| kale     | 0.95 | 1.70                                     | Strong concavity (tolerant) |
| cucumber | 1.00 | 1.525                                    | Moderate concavity       |

### Data Generation (Pre-computation)

**Script**: `data/_scripts/generate_crop_lookup.py`

Generates all crop daily growth lookup CSVs. The yield formula in this script is identical to `compute_harvest_yield()` in `src/crop_yield.py`, ensuring cross-validation:

```python
alpha = 1.0 + wue_beta * (1.15 - ky)
alpha = max(alpha, 1.0)
ky_factor = f ** (1.0 / alpha)
yield_fresh = potential_yield * ky_factor * avg_kt
```

Key models within the generation script:

- **ETo**: Hargreaves equation (FAO-56 Eq. 52): `ETo = 0.0023 * (T_mean + 17.8) * (T_max - T_min)^0.5 * Ra`
- **ETc**: `Kc * ETo_ref * (1 - ET_reduction)`. Under PV conditions, `ETo_ref` is computed from openfield temperatures (via `temp_adj_c > 0` branch) to avoid double-counting the temperature-driven ETo reduction already captured in the condition-specific weather files.
- **fPAR**: Canopy interception ramps from 0.10 (seedling) through growth stages to a crop-specific maximum (0.60-0.85), then declines to 80% of max during late stage.
- **Water stress**: `Ks = min(1.0, water_applied / ETc)`
- **Temperature stress**: Piecewise linear from cardinal temperatures: 0 below t_base, linear ramp to 1 at t_opt_low, 1.0 through t_opt_high, linear decline to 0 at t_max.
- **Daily biomass**: `RUE * PAR_MJ * fPAR * Ks * Kt * 10.0` (the factor of 10 converts g/m2 to kg/ha).
- **Water application cap**: `water_applied = min(irrigation + precip, ETc * 1.1)` -- prevents unrealistic over-watering.

Max fPAR values by crop (hardcoded):

| Crop     | Max fPAR |
|----------|----------|
| tomato   | 0.85     |
| potato   | 0.80     |
| onion    | 0.60     |
| kale     | 0.75     |
| cucumber | 0.75     |

### Orchestration and Harvest Yield Assembly

The harvest yield computation is **not** performed by a dedicated function in `src/`. It is implemented directly in the simulation notebook (`notebooks/simulation.ipynb`). The flow is:

1. Run `compute_daily_water_balance()` to get the full water balance DataFrame including per-field delivered and demanded volumes.

2. Load the farm profile and season lookup.

3. For each (farm, field, crop, planting_code, year) combination:
   a. Compute planting date and harvest date using the season length lookup.
   b. Skip if harvest date exceeds simulation end or planting date precedes simulation start.
   c. Extract the `{field_name}_delivered_m3` and `{field_name}_demand_m3` columns for the season date range from the water balance DataFrame.
   d. Call `compute_harvest_yield()` with these series.
   e. Record the result with metadata (harvest_date, field, crop, planting, condition, yield_kg_per_ha, area_ha, harvest_kg).

4. Build a daily harvest yields DataFrame:
   - Create a complete daily date axis spanning the simulation period.
   - Pivot harvest records into per-field-crop columns: `{field}_{crop}_harvest_kg`.
   - Each harvest event is a single-day entry (on the harvest_date) with the total harvest_kg for that field.
   - `total_harvest_kg`: Sum across all field-crop columns.

5. Save to `simulation/daily_harvest_yields.csv`.

---

## Output Format

### Daily Harvest Yields CSV

**File**: `simulation/daily_harvest_yields.csv`

One row per calendar day across the simulation period. Most rows are zeros; non-zero values appear only on harvest dates.

| Column                           | Type     | Unit | Description                                      |
|----------------------------------|----------|------|--------------------------------------------------|
| `day`                            | datetime | --   | Calendar date                                    |
| `{field}_{crop}_harvest_kg`      | float    | kg   | Total harvest for this field-crop on this date   |
| `total_harvest_kg`               | float    | kg   | Sum of all field-crop harvest columns            |

Column naming convention: `{field_name}_{crop}_harvest_kg`. Example columns from the baseline configuration:

- `east_field_cucumber_harvest_kg`
- `north_field_kale_harvest_kg`
- `north_field_tomato_harvest_kg`
- `south_field_onion_harvest_kg`
- `south_field_potato_harvest_kg`
- `west_field_kale_harvest_kg`
- `west_field_tomato_harvest_kg`

Harvest values represent `yield_kg_per_ha * area_ha` for the field, giving total kilograms of fresh product. This is a single point value placed on the harvest date (the day after the last day of the growing season).

### Harvest Summary (Intermediate, Not Saved)

The notebook also builds a `harvests` DataFrame with one row per harvest event:

| Column            | Type     | Unit      | Description                                    |
|-------------------|----------|-----------|------------------------------------------------|
| `harvest_date`    | datetime | --        | Date the harvest occurs                        |
| `field`           | string   | --        | Field name                                     |
| `crop`            | string   | --        | Crop name                                      |
| `planting`        | string   | --        | Planting code (e.g. `feb15`)                   |
| `condition`       | string   | --        | Growing condition                              |
| `yield_kg_per_ha` | float    | kg/ha     | Predicted yield per hectare                    |
| `area_ha`         | float    | ha        | Field area                                     |
| `harvest_kg`      | float    | kg        | Total harvest (yield_kg_per_ha * area_ha)      |

This DataFrame is not saved to disk but is used to generate the daily CSV and printed summaries.

---

## Gaps and Design Notes

### Resolved Items

**1. Harvest yield logic** — `compute_community_harvest()` and `save_harvest_yields()` now exist in `src/crop_yield.py`, following the same public API pattern as other modules. The simulation notebook imports and calls these directly.

**2. Tests** — `tests/test_crop_yield.py`, `tests/test_farm_profile.py`, and `tests/test_irrigation_demand.py` provide pytest coverage for the farming subsystem.

**3. Planting windows in data registry** — `planting_windows-research.csv` is now registered under `crops.planting_windows` in `settings/data_registry_base.yaml`.

**4. Column name consistency** — All crop data files now use `crop` as the crop identifier column. Previously, some files (yield response factors, microclimate yield effects, food processing specs, handling loss rates, storage spoilage rates, processing labor) used `crop_name`. Standardized to `crop` across all CSV files.

**5. Weather year range** — The simulation runs all weather years present in the crop daily growth CSVs (2010-2024). No `start_date`/`end_date` fields in scenario config.

**6. Cross-year planting season handling** — `validate_no_overlap()` in `src/farm_profile.py` projects all plantings into two consecutive reference years (2020 and 2021), checking all cross-year pairs. A November planting extending into March is correctly tested against early-year plantings on the same field. Same-planting-code pairs across years are excluded (same annual event, not an overlap).

### Design Decisions (Not Gaps)

**Proportional water allocation** — In `src/water_balance.py`, per-field delivered volume is computed as a proportional share of total irrigation delivery:

```python
delivery_ratio = irrigation_delivered / irrigation_demand
field_delivered = field_demand * delivery_ratio
```

All fields receive the same proportional reduction during deficit days. This is the intended behavior for the simulation's scope. Crop-sensitivity-based prioritization (routing more water to high-Ky crops during shortfalls) would require a field-level dispatch optimizer, which is beyond the current model's purpose.

**Biomass columns are diagnostic only** — The crop daily growth CSVs contain `biomass_kg_ha` and `cumulative_biomass_kg_ha` columns tracking daily dry matter accumulation via the RUE model. These are not used to compute yield. The actual yield calculation uses the FAO water-yield response formula (`potential_yield * f^(1/alpha) * avg_Kt`), which is decoupled from cumulative biomass to avoid the dry-matter-fraction amplification problem (crops with >95% water content produce unrealistic fresh yields from any reasonable dry biomass). The biomass columns are retained for educational and diagnostic purposes.

**Temperature stress coefficient loaded from `full_eto` policy** — `compute_harvest_yield()` loads `temp_stress_coeff` from the crop daily growth CSV filtered to `irrigation_policy='full_eto'`. This works correctly in both static and dynamic mode because `temp_stress_coeff` depends only on weather (temperature), not on water application. Water stress affects `Ks` (water stress coefficient), not `Kt` (temperature stress coefficient). The filter choice is arbitrary — any policy would return the same `Kt` values for a given weather year.

### Future Enhancement: Salt Stress in Yield

The crop growth parameters file includes salt tolerance data (`tds_no_penalty_ppm`, `tds_lethal_ppm`, `tds_yield_decline_pct_per_100ppm`) and the irrigation demand module computes `crop_tds_requirement_ppm`. However, `compute_harvest_yield()` does not apply a TDS-based yield penalty. This is acceptable because the water supply dispatch system uses TDS blending logic to keep delivered water within crop tolerance thresholds — salt stress should not occur under normal operation.

If salt stress modeling were needed (e.g., for scenarios where blending capacity is insufficient), the implementation path would be: add an optional `delivered_tds_series` parameter to `compute_harvest_yield()` that applies a Maas-Hoffman linear penalty using the existing crop salt tolerance parameters. The daily `Ks_salt` would interpolate between `tds_no_penalty_ppm` (1.0) and `tds_lethal_ppm` (0.0), and the season-average would multiply into the yield formula alongside `avg_Kt`. The data infrastructure is already in place; only the yield function would need modification.
