# Specifications

Core model specifications for the Community Agri-PV simulation. Single source of truth for configuration schema, calculation methodologies, policy logic, data formats, and simulation flow.

## Structure

| File | Description |
|------|-------------|
| `structure.md` | Configuration schema (YAML sections), state dataclasses, data file schemas, valid options |
| `calculations.md` | Cross-cutting calculation overview |
| `calculations_water.md` | Water treatment, conveyance, allocation, pumping, aquifer |
| `calculations_crop.md` | Irrigation demand, yield, salinity, microclimate effects |
| `calculations_energy.md` | Energy dispatch, PV/wind/battery/grid/diesel, treatment energy |
| `calculations_economic.md` | Financing, costs, revenue, tiered pricing |
| `policies.md` | Policy decision rules and pseudocode (water, energy, food, crop, economic, market) |
| `data.md` | Data catalog, file formats, metadata standards, column schemas |
| `simulation_flow.md` | Daily execution sequence, order of operations |
| `metrics_and_reporting.md` | Output metrics, yearly/community aggregations |
| `reference_settings.yaml` | Complete example scenario configuration |

## Cross-Reference Convention

Specs reference each other as: `→ spec_file.md § Section_Number`

## Subdirectories

- `_helper/` - Development guides (e.g., overview of model goals). Not part of the authoritative spec set.
- `_archive/` - Deprecated or superseded content.
