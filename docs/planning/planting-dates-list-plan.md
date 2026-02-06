# Plan: List-based planting dates with overlap validation

## Context

The YAML crop config currently requires repeating the entire crop entry for each planting window. This is verbose and error-prone. The user wants a cleaner format where each crop has a list of planting dates, plus validation that the selected windows don't overlap on the same land.

Additionally, the exploration found a bug: `simulation.py:107` overwrites `crop_demands[crop.crop_name]` instead of accumulating, so when two plantings of the same crop are active simultaneously, only the last one's demand is recorded.

## Changes

### 1. `settings/settings.yaml` — new format

```yaml
crops:
  - name: tomato
    area_fraction: 0.20
    planting_dates: ["02-15", "04-01"]
    percent_planted: 0.90
```

Back to 5 crop entries (one per crop) with `planting_dates` (list) replacing `planting_date` (string).

### 2. `src/settings/loader.py` — parse list, expand to internal configs

- Keep `FarmCropConfig` as-is (single `planting_date: str`) — this is the internal per-planting representation used downstream
- In `_load_farm_crops()`: read `planting_dates` (list) from YAML, create one `FarmCropConfig` per date
- Clean switch to new format (no backwards compat needed per project conventions)

### 3. `src/simulation/state.py` — overlap validation

- In `initialize_farm_state()`: after creating all CropState objects, group by `crop_name` and check for overlapping `[planting_date, harvest_date]` ranges
- Raise `ValueError` if any two plantings of the same crop overlap (since they use the same land)

### 4. `src/simulation/simulation.py` — fix accumulation bug

- Line 107: change `crop_demands[crop.crop_name] = crop_demand` to accumulate with `+=` (using `get()` default of 0.0)

## Files to modify

| File | Change |
|------|--------|
| `settings/settings.yaml` | `planting_date` → `planting_dates` list |
| `src/settings/loader.py` | Parse list in `_load_farm_crops()` |
| `src/simulation/state.py` | Add overlap check in `initialize_farm_state()` |
| `src/simulation/simulation.py` | Fix `crop_demands` accumulation bug (line 107) |

## Verification

1. Run the simulation: `python src/simulation/results.py settings/settings.yaml`
2. Test overlap detection by temporarily adding overlapping dates to settings.yaml (e.g., tomato "02-15" and "03-01") and confirming it raises an error
3. Verify the simulation completes with the valid 2-window config
