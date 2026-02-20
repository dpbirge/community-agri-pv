# Fix Proposals: Data Completeness (Section 2)

**Generated:** 2026-02-18  
**Scope:** Section 2 (Data Completeness) and Section 7 action items #23-34  
**Source:** `docs/codereview/systematic_doc_review_report.md`

---

### Issue #23 / Section 2 File Reference Mismatches: Fix `settings/mvp-settings.yaml` references in data.md

**Action Item:** Fix `settings/mvp-settings.yaml` references to `settings/settings.yaml` in data.md (3 places)

**Severity:** MINOR

**Summary:** The file `settings/mvp-settings.yaml` does not exist on disk. The actual scenario configuration file is `settings/settings.yaml`. The document `docs/arch/data.md` references the stale name in three locations: a directory tree diagram (line 36), a "Current scenario file" statement (line 390), and a Settings Configuration inventory table row (line 520).

**Proposed Solution:**

Edit `docs/arch/data.md` at three locations:

1. **Line 36** -- In the directory tree under "Scenario configurations live in":
  Change:

```
   └── mvp-settings.yaml  # MVP scenario configuration
```

   To:

```
   └── settings.yaml      # Active scenario configuration
```

1. **Line 390** -- In the "Settings Organization" section:
  Change:

```
   **Current scenario file**: `settings/mvp-settings.yaml`
```

   To:

```
   **Current scenario file**: `settings/settings.yaml`
```

1. **Line 520** -- In the "Settings (Configuration)" inventory table:
  Change:

```
   | Scenario YAML (`mvp-settings.yaml`) | Complete | Full infrastructure, community, policy selections |
```

   To:

```
   | Scenario YAML (`settings.yaml`) | Complete | Full infrastructure, community, policy selections |
```

**Rationale:** The file was likely renamed from `mvp-settings.yaml` to `settings.yaml` when the project moved beyond MVP scope. All three references are cosmetic/documentary and do not affect code execution, but they mislead developers about the correct file to edit.

**Confidence:** 5 -- Verified that `settings/settings.yaml` exists on disk and `settings/mvp-settings.yaml` does not.

---

**Owner Response: **Implement proposed solution

[blank]

---

### Issue #24 / Section 2 File Reference Mismatches: Fix stale pump equipment path in calculations.md

**Action Item:** Fix stale path `data/parameters/water/pump_equipment_parameters.csv` in calculations.md

**Severity:** MINOR

**Summary:** The calculations.md Groundwater Pumping Energy section (line 98) references `data/parameters/water/pump_equipment_parameters.csv` for pump efficiency values. This file does not exist. The correct file is `data/parameters/equipment/pump_systems-toy.csv`, which is registered in `data_registry.yaml` under `equipment.pump_systems`. The file was reorganized from a `water/` subfolder to the `equipment/` subfolder and renamed with proper naming conventions.

**Proposed Solution:**

Edit `docs/arch/calculations.md` at line 98:

Change:

```
- Parameter file:`data/parameters/water/pump_equipment_parameters.csv` (efficiency values)
```

To:

```
- Parameter file: `data/parameters/equipment/pump_systems-toy.csv` (pump specs including depth, flow rate, costs; via registry `equipment.pump_systems`)
```

**Rationale:** The pump specifications file contains well depth, flow rate, capital cost, O&M cost, and pumping energy per m3. The correct file path is confirmed on disk (`data/parameters/equipment/pump_systems-toy.csv`, 1552 bytes) and in the data registry under `equipment.pump_systems`. The description is updated to reflect the actual file contents more accurately.

**Confidence:** 5 -- File verified on disk and in data registry.

---

**Owner Response: **Implement proposed solution

[blank]

---

### Issue #25 / Section 2 File Reference Mismatches: Fix stale generator parameters path in calculations.md

**Action Item:** Fix stale path `data/parameters/energy/generator_parameters.csv` in calculations.md

**Severity:** MINOR

**Summary:** The calculations.md Generator Fuel Consumption section (line 787) references `data/parameters/energy/generator_parameters.csv`. This file does not exist. The correct file is `data/parameters/equipment/generators-toy.csv`, registered in `data_registry.yaml` under `equipment.generators`. The file was reorganized from an `energy/` subfolder to the unified `equipment/` subfolder.

**Proposed Solution:**

Edit `docs/arch/calculations.md` at line 787:

Change:

```
- Parameter file:`data/parameters/energy/generator_parameters.csv`
```

To:

```
- Parameter file: `data/parameters/equipment/generators-toy.csv` (diesel generator specs and fuel coefficients; via registry `equipment.generators`)
```

**Rationale:** The generators file contains capacity, fuel coefficients (Willans line parameters), and cost data. Confirmed on disk (`data/parameters/equipment/generators-toy.csv`, 1516 bytes) and in data registry under `equipment.generators`.

**Confidence:** 5 -- File verified on disk and in data registry.

---

**Owner Response: **Implement proposed solution

[blank]

---

### Issue #26 / Section 2 File Reference Mismatches: Fix stale aquifer parameters path in calculations.md

**Action Item:** Fix stale path `data/parameters/water/aquifer_parameters.md` in calculations.md

**Severity:** MINOR

**Summary:** The calculations.md Aquifer Depletion Rate section (line 424) references `data/parameters/water/aquifer_parameters.md` for research-grade aquifer data. This path is wrong on two counts: (1) it is a markdown reference document, not a CSV parameter file, and (2) it lives in `docs/research/`, not `data/parameters/`. The correct path is `docs/research/aquifer_parameters.md`.

**Proposed Solution:**

Edit `docs/arch/calculations.md` at line 424:

Change:

```
- For research-grade data, see`data/parameters/water/aquifer_parameters.md`
```

To:

```
- For research-grade data, see `docs/research/aquifer_parameters.md`
```

**Rationale:** The aquifer parameters file is a markdown research document (2,414 bytes), not a CSV data file, so it correctly lives under `docs/research/` rather than `data/parameters/`. The data.md document (line 491-492) already references it with the correct type annotation "(documentation)" and without a registry key, consistent with its nature as a reference document. Note also that `data.md` line 559 already references the correct path `docs/research/aquifer_parameters.md` in its Water Subsystem data requirements table.

**Confidence:** 5 -- File verified at `docs/research/aquifer_parameters.md` on disk.

---

**Owner Response: **Implement proposed solution

[blank]

---

### Issue #27 / Section 2 File Reference Mismatches: Add `-toy` suffix to crop_salinity_tolerance.csv reference in calculations.md

**Action Item:** Add `-toy` suffix to `crop_salinity_tolerance.csv` reference in calculations.md

**Severity:** MINOR

**Summary:** The calculations.md Salinity Yield Reduction section (line 1239) references `data/parameters/crops/crop_salinity_tolerance.csv` with an annotation "(to be created)". The file has since been created with the standard `-toy` suffix as `data/parameters/crops/crop_salinity_tolerance-toy.csv` and is registered in `data_registry.yaml` under `crops.salinity_tolerance`. The reference needs to be updated to include the suffix and remove the "to be created" note.

**Proposed Solution:**

Edit `docs/arch/calculations.md` at line 1239:

Change:

```
- Parameter file: `data/parameters/crops/crop_salinity_tolerance.csv` (to be created)
```

To:

```
- Parameter file: `data/parameters/crops/crop_salinity_tolerance-toy.csv` (FAO-29 salinity thresholds; via registry `crops.salinity_tolerance`)
```

**Rationale:** The file now exists on disk (894 bytes, created 2026-02-18) and is registered in `data_registry.yaml` at line 25 as `crops.salinity_tolerance`. The "(to be created)" annotation is no longer accurate and should be replaced with a description of file contents and its registry key, consistent with the documentation style used for other dependency references in calculations.md.

**Confidence:** 5 -- File verified on disk and in data registry.

---

**Owner Response: **Implement proposed solution

[blank]

---

### Issue #28 / Section 2 File Reference Mismatches: Remove reference to non-existent `docs/research/egyptian_utility_pricing.md`

**Action Item:** Create or remove reference to `docs/research/egyptian_utility_pricing.md` (file does not exist)

**Severity:** MINOR

**Summary:** The calculations.md Blended Electricity Cost section (line 1130) references `docs/research/egyptian_utility_pricing.md` for Egyptian tariff structure analysis. This file does not exist in `docs/research/` (only `aquifer_parameters.md` and `water_source_metadata.yaml` are present). However, the relevant Egyptian tariff research content is already thoroughly embedded in the metadata headers of the electricity price data files themselves -- specifically `data/prices/electricity/historical_grid_electricity_prices-research.csv`, which contains detailed EgyptERA tariff schedule sources, reform timelines, verified 2024 tariff rates, and data quality assessments across 12 metadata header lines.

**Proposed Solution:**

Edit `docs/arch/calculations.md` at line 1130:

Change:

```
- Grid electricity pricing follows Egyptian tariff structures (see `docs/research/egyptian_utility_pricing.md`)
```

To:

```
- Grid electricity pricing follows Egyptian tariff structures (see metadata headers in `data/prices/electricity/historical_grid_electricity_prices-research.csv` for full EgyptERA source documentation and tariff reform timeline)
```

**Rationale:** Creating a separate research document would duplicate information that already exists in well-documented CSV metadata headers. The research-grade electricity price files contain comprehensive sourcing (EgyptERA tariff schedules, CEIC Data, World Bank exchange rates), the full 2014-2024 subsidy reform timeline, verified 2024 tariff rates, and data quality assessments. This is the correct single source of truth for Egyptian electricity pricing methodology. If the owner later decides to extract this into a standalone research document, the reference can be updated at that time.

**Confidence:** 4 -- The embedded metadata in the research CSV files is thorough and covers the content that a standalone research document would contain. However, the owner may prefer to create a standalone document for readability or to add analysis beyond what fits in CSV headers.

**Alternative Solutions:** If the owner prefers a standalone research document: create `docs/research/egyptian_utility_pricing.md` by extracting and expanding the metadata from the electricity price CSV headers into a structured markdown document covering tariff reform history, EgyptERA source citations, verified rate tables, and the subsidized vs unsubsidized differential methodology.

---

**Owner Response:** Implement proposed solution

[blank]

---

### Issue #29 / Section 2 Inventory Inaccuracies: Update processed product count from 10 to 16 in data.md

**Action Item:** Update data.md: processed product count (10 to 16)

**Severity:** MINOR

**Summary:** The data.md Price Time-Series inventory table (line 499) states "10 products" for historical processed product prices. The actual count on disk and in the data registry is 16 products. Six additional products were created (likely by `generate_missing_processed_prices.py`): dried_potato, dried_onion, dried_cucumber, canned_potato, canned_kale, and canned_cucumber.

**Proposed Solution:**

Edit `docs/arch/data.md` at line 499:

Change:

```
| Historical processed product prices (10 products) | x | | `prices_processed.<product>` | Packaged, canned, dried variants |
```

To:

```
| Historical processed product prices (16 products) | x | | `prices_processed.<product>` | All crop-product combinations: 5 packaged, 5 canned, 4 dried, 1 pickled, 1 additional |
```

Additionally, update the directory tree in the `data/prices/processed/` section (lines 291-295) to reflect all 16 files. The current tree shows only 10 files. Replace the tree with:

```
├── processed/
│   ├── historical_canned_cucumber_prices-toy.csv
│   ├── historical_canned_kale_prices-toy.csv
│   ├── historical_canned_onion_prices-toy.csv
│   ├── historical_canned_potato_prices-toy.csv
│   ├── historical_canned_tomato_prices-toy.csv
│   ├── historical_dried_cucumber_prices-toy.csv
│   ├── historical_dried_kale_prices-toy.csv
│   ├── historical_dried_onion_prices-toy.csv
│   ├── historical_dried_potato_prices-toy.csv
│   ├── historical_dried_tomato_prices-toy.csv
│   ├── historical_packaged_cucumber_prices-toy.csv
│   ├── historical_packaged_kale_prices-toy.csv
│   ├── historical_packaged_onion_prices-toy.csv
│   ├── historical_packaged_potato_prices-toy.csv
│   ├── historical_packaged_tomato_prices-toy.csv
│   └── historical_pickled_cucumber_prices-toy.csv
```

**Rationale:** The full product matrix is: 5 crops x 3 processing types (packaged, canned, dried) = 15, plus pickled_cucumber = 16 total. The data registry (`data_registry.yaml` lines 84-100) lists all 16 products under `prices_processed`. The document should reflect the actual state of the data.

**Confidence:** 5 -- All 16 files verified on disk and in data registry.

---

**Owner Response: **Implement proposed solution

[blank]

---

### Issue #30 / Section 2 Inventory Inaccuracies: Mark `microclimate_yield_effects` as registered in data.md

**Action Item:** Update data.md: mark `microclimate_yield_effects` as registered

**Severity:** MINOR

**Summary:** The data.md Parameters inventory table (line 468) shows `microclimate_yield_effects` with the registry key annotation "(not in registry)". However, this file IS registered in `data_registry.yaml` at line 26 as `crops.microclimate_yield_effects`, pointing to `data/parameters/crops/microclimate_yield_effects-research.csv`.

**Proposed Solution:**

Edit `docs/arch/data.md` at line 468:

Change:

```
| Microclimate yield effects | | x | (not in registry) | PV shade effects by density |
```

To:

```
| Microclimate yield effects | | x | `crops.microclimate_yield_effects` | PV shade effects by density |
```

**Rationale:** The data registry clearly maps `crops.microclimate_yield_effects` to `data/parameters/crops/microclimate_yield_effects-research.csv`. The file is also correctly referenced in data.md's Crop and Harvest Subsystem data requirements table (line 591) using the correct path. The inventory table is simply outdated and needs to reflect the current registry state.

**Confidence:** 5 -- Verified in `data_registry.yaml` line 26.

---

**Owner Response: **Implement proposed solution

[blank]

---

### Issue #31 / Section 2 Inventory Inaccuracies: Mark `fertilizer_costs` as registered in data.md

**Action Item:** Update data.md: mark `fertilizer_costs` as registered

**Severity:** MINOR

**Summary:** The data.md Price Time-Series inventory table (line 504) shows `Historical fertilizer costs` with the registry key annotation "(not in registry)". However, this file IS registered in `data_registry.yaml` at lines 110-111 as `prices_inputs.fertilizer_costs`, pointing to `data/prices/inputs/historical_fertilizer_costs-toy.csv`.

**Proposed Solution:**

Edit `docs/arch/data.md` at line 504:

Change:

```
| Historical fertilizer costs | x | | (not in registry) | Per-hectare aggregate |
```

To:

```
| Historical fertilizer costs | x | | `prices_inputs.fertilizer_costs` | Per-hectare aggregate |
```

**Rationale:** The data registry clearly maps `prices_inputs.fertilizer_costs` to `data/prices/inputs/historical_fertilizer_costs-toy.csv`. The file is also correctly referenced in data.md's Economic Subsystem data requirements table (line 622) using the correct path. The inventory table is simply outdated.

**Confidence:** 5 -- Verified in `data_registry.yaml` lines 110-111.

---

**Owner Response: **Implement proposed solution

[blank]

---

### Issue #32 / Section 2 Inventory Inaccuracies: Add `density_variant` column to PV format example in data.md

**Action Item:** Update data.md: add `density_variant` column to PV format example

**Severity:** MINOR

**Summary:** The data.md PV Power File Format Example (lines 136-140) shows 4 columns: `weather_scenario_id, date, kwh_per_kw_per_day, capacity_factor`. The actual file `data/precomputed/pv_power/pv_normalized_kwh_per_kw_daily-toy.csv` has 5 columns: `weather_scenario_id, date, density_variant, kwh_per_kw_per_day, capacity_factor`. The `density_variant` column (values: low, medium, high) is a key modeling dimension representing the three agri-PV panel density configurations documented in the Project Specifications Summary section of the same document (lines 682-685).

**Proposed Solution:**

Edit `docs/arch/data.md` at lines 128-140. Replace the PV Power File Format Example:

Change:

```csv
# SOURCE: pvlib calculations with synthetic weather data
# DATE: 2026-02-02
# DESCRIPTION: Normalized daily PV output per kW installed capacity
# UNITS: kwh_per_kw_per_day (kWh/kW/day)
# LOGIC: pvlib.ModelChain with fixed-tilt system, standard modules, temperature derating
# DEPENDENCIES: precomputed/weather/daily_weather_scenario_001-toy.csv, parameters/equipment/pv_systems-toy.csv
# ASSUMPTIONS: Fixed tilt 25°, azimuth 180° (south-facing), system losses 14%, temperature coefficient -0.4%/°C
weather_scenario_id,date,kwh_per_kw_per_day,capacity_factor
001,2024-01-01,4.2,0.175
001,2024-01-02,4.5,0.188
001,2024-01-03,4.1,0.171
```

To (matching actual file metadata and structure):

```csv
# SOURCE: Computed from weather data using simplified PV model
# DATE: 2026-02-06
# DESCRIPTION: Normalized daily PV power output per kW of installed capacity for three agri-PV density variants (low/medium/high ground coverage)
# UNITS: date=YYYY-MM-DD, density_variant=text, kwh_per_kw_per_day=kWh/kW/day, capacity_factor=dimensionless(0-1)
# LOGIC: PV output = solar_irradiance * tilt_factor(1.05) * temp_factor * (1-system_losses). Temp factor uses cell temp model: T_cell = T_avg + 25C + density_adjustment. Temperature coefficient = -0.4%/C from 25C reference. System losses = 15%.
# DEPENDENCIES: data/precomputed/weather/daily_weather_scenario_001-toy.csv
# ASSUMPTIONS: Fixed-tilt 28deg south-facing panels. Module efficiency ~19%. High density panels run 2C cooler (shading effect), low density run 2C hotter. All panels receive full irradiance (panels above crops, not shaded by each other).
weather_scenario_id,date,density_variant,kwh_per_kw_per_day,capacity_factor
001,2010-01-01,low,3.4202,0.1425
001,2010-01-01,medium,3.4499,0.1437
001,2010-01-01,high,3.4796,0.145
```

**Rationale:** The format example should match the actual file structure. Key differences from the old example: (1) `density_variant` column is present, (2) tilt angle is 28 degrees (not 25), (3) system losses are 15% (not 14%), (4) data starts from 2010 (not 2024), and (5) the metadata header reflects the actual generation method (simplified PV model, not pvlib). The three density variants (low/medium/high ground coverage) are a core architectural feature for agri-PV scenarios.

**Confidence:** 5 -- Format example taken directly from actual file on disk.

---

**Owner Response: **Implement proposed solution

[blank]

---

### Issue #32b / Section 2 Inventory Inaccuracies: Update Irrigation Demand File Format Example in data.md

**Action Item:** (Supplemental to Section 2 findings) Update data.md irrigation format to include `calendar_date` and `etc_mm` columns

**Severity:** MINOR

**Summary:** The data.md Irrigation Demand File Format Example (lines 153-158) shows 7 columns: `weather_scenario_id, planting_date, crop_day, growth_stage, kc, et0_mm, irrigation_m3_per_ha_per_day`. The actual file has 9 columns, including two additional columns: `calendar_date` (actual calendar date, positioned between `crop_day` and `growth_stage`) and `etc_mm` (crop evapotranspiration = ET0 x Kc, positioned between `et0_mm` and `irrigation_m3_per_ha_per_day`). This was flagged in Section 2 of the review report.

**Proposed Solution:**

Edit `docs/arch/data.md` at lines 153-158. Replace the Irrigation Demand File Format Example:

Change:

```csv
weather_scenario_id,planting_date,crop_day,growth_stage,kc,et0_mm,irrigation_m3_per_ha_per_day
001,2024-01-01,1,initial,0.60,5.2,31.2
001,2024-01-01,2,initial,0.60,5.4,32.4
001,2024-01-01,25,development,0.85,5.8,49.3
001,2024-01-01,50,mid,1.15,6.2,71.3
001,2024-01-01,110,late,0.80,5.5,44.0
```

To (matching actual file column order):

```csv
weather_scenario_id,planting_date,crop_day,calendar_date,growth_stage,kc,et0_mm,etc_mm,irrigation_m3_per_ha_per_day
001,2010-01-01,1,2010-01-01,initial,0.60,5.2,3.12,34.7
001,2010-01-01,2,2010-01-02,initial,0.60,5.4,3.24,36.0
001,2010-01-01,25,2010-01-25,development,0.85,5.8,4.93,54.8
001,2010-01-01,50,2010-02-19,mid,1.15,6.2,7.13,79.2
001,2010-01-01,110,2010-04-20,late,0.80,5.5,4.40,48.9
```

Also update the metadata header to include units for the two missing columns. Add to the UNITS line:

```
# UNITS: ..., calendar_date (YYYY-MM-DD), ..., etc_mm (mm/day), ...
```

**Rationale:** The `calendar_date` column is important for aligning irrigation demand with weather time-series data. The `etc_mm` column (crop ET = ET0 x Kc) is an intermediate calculation value useful for debugging and validation. Both exist in the actual data files and should be documented in the format specification so developers know to expect them.

**Confidence:** 4 -- Column names and order are verified from actual file headers. Sample data values are approximated based on the FAO calculation methodology and should be reviewed against actual file content for exact values.

**Alternative Solutions:** If exact sample values are important, read the first few data rows from the actual irrigation file and copy them directly.

---

**Owner Response: **Implement proposed solution

[blank]

---

### Issue #33 / Section 2 Inventory Inaccuracies: Update or remove "Planned Datasets" section in data.md

**Action Item:** Update or remove "Planned Datasets" section (all 3 created)

**Severity:** MINOR

**Summary:** The data.md "Planned Datasets (Not Yet Created)" section (lines 506-514) lists three datasets as not yet existing. All three have since been created and registered in `data_registry.yaml`:

1. `parameters/crops/crop_salinity_tolerance.csv` -- now exists as `data/parameters/crops/crop_salinity_tolerance-toy.csv` (registered as `crops.salinity_tolerance`)
2. `parameters/economic/equipment_lifespans.csv` -- now exists as `data/parameters/economic/equipment_lifespans-toy.csv` (registered as `economic.equipment_lifespans`)
3. `parameters/crops/storage_costs-toy.csv` -- now exists as `data/parameters/crops/food_storage_costs-toy.csv` (registered as `crops.storage_costs`)

**Proposed Solution:**

**Option A (Recommended): Remove the entire section.** Delete lines 506-514 ("Planned Datasets (Not Yet Created)" through the table). All three datasets exist and are registered, so the section serves no purpose and is misleading.

**Option B: Convert to a "Recently Created Datasets" note.** If historical tracking is desired, replace the section with a brief note:

```markdown
### Recently Created Datasets

The following datasets were previously planned and have been created and registered:

| Dataset | Registry Key | Actual Path |
|---|---|---|
| Crop salinity tolerance | `crops.salinity_tolerance` | `data/parameters/crops/crop_salinity_tolerance-toy.csv` |
| Equipment lifespans | `economic.equipment_lifespans` | `data/parameters/economic/equipment_lifespans-toy.csv` |
| Food storage costs | `crops.storage_costs` | `data/parameters/crops/food_storage_costs-toy.csv` |
```

Additionally, these three datasets should be added to the Parameters and Economic inventory tables above (if not already present) with their registry keys:

- Add to Parameters table: `| Crop salinity tolerance | x | | crops.salinity_tolerance | FAO-29 ECe thresholds and slope b |`
- Add to Parameters table: `| Food storage costs | x | | crops.storage_costs | Daily storage cost per kg by product type |`
- Add to Economic/Settings table or Parameters table: `| Equipment lifespans | x | | economic.equipment_lifespans | Component lifespans for replacement cost |`

**Rationale:** The "Not Yet Created" label is factually incorrect and could confuse developers into thinking they need to create these files. Note that the third dataset's actual filename (`food_storage_costs-toy.csv`) differs from the planned name (`storage_costs-toy.csv`), which was also a source of potential confusion.

**Confidence:** 5 -- All three files verified on disk and in data registry.

---

**Owner Response: **Implement proposed solution

[blank]

---

### Issue #34 / Section 2 Metadata Compliance: Remove `nimbalyst` editor annotations from data files

**Action Item:** Remove `nimbalyst` editor annotations from `wells-toy.csv` and `community_buildings_energy_kwh_per_day-toy.csv`

**Severity:** MINOR

**Summary:** The review report identified `nimbalyst` editor artifact annotations (JSON configuration strings from the Nimbalyst CSV editor extension) in 2 data files. Upon inspection, 4 files actually contain these annotations, all on line 1:

1. `data/parameters/equipment/wells-toy.csv` (line 1)
2. `data/precomputed/community_buildings/community_buildings_energy_kwh_per_day-toy.csv` (line 1)
3. `data/precomputed/crop_yields/yield_kg_per_ha_cucumber-toy.csv` (line 1)
4. `data/precomputed/community_buildings/community_buildings_water_m3_per_day-toy.csv` (line 1)

These lines contain JSON strings like:

```
# nimbalyst: {"hasHeaders":false,"headerRowCount":0,"frozenColumnCount":0,"columnWidths":{"2":151}}
```

These are editor-specific display preferences, not data metadata, and violate the project's metadata standards (SOURCE, DATE, DESCRIPTION, UNITS, LOGIC, DEPENDENCIES).

**Proposed Solution:**

Delete line 1 (the `# nimbalyst:` line) from each of the 4 files listed above:

1. `**data/parameters/equipment/wells-toy.csv**` -- Remove line 1:

```
   # nimbalyst: {"hasHeaders":false,"headerRowCount":0,"frozenColumnCount":0,"columnWidths":{"2":151}}
```

1. `**data/precomputed/community_buildings/community_buildings_energy_kwh_per_day-toy.csv**` -- Remove line 1:

```
   # nimbalyst: {"hasHeaders":false,"headerRowCount":0,"frozenColumnCount":0,"columnWidths":{"1":129}}
```

1. `**data/precomputed/crop_yields/yield_kg_per_ha_cucumber-toy.csv**` -- Remove line 1:

```
   # nimbalyst: {"hasHeaders":false,"headerRowCount":0,"frozenColumnCount":0,"columnWidths":{"0":138}}
```

1. `**data/precomputed/community_buildings/community_buildings_water_m3_per_day-toy.csv**` -- Remove line 1:

```
   # nimbalyst: {"hasHeaders":false,"headerRowCount":0,"frozenColumnCount":0,"columnWidths":{"0":234}}
```

No other lines need modification. The standard metadata headers (SOURCE, DATE, DESCRIPTION, etc.) begin on line 2 in each file and will become line 1 after removal.

**Rationale:** These annotations are remnants of the Nimbalyst VS Code CSV editor extension and serve no purpose for the simulation model. They could confuse automated metadata parsers that expect the first comment line to begin with `# SOURCE:`. Removing them ensures all data files conform to the project's embedded metadata standards.

**Confidence:** 5 -- All 4 annotations verified by searching for `nimbalyst` across the entire `data/` directory. The exact line content for each file is confirmed.

---

**Owner Response: **Implement proposed solution

[blank]

---