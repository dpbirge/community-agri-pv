# Prompt: Review Architecture Docs for Data Gaps and Hardcoded Values

## Objective

Audit all six docs/arch/ files against the actual data/ folder and src/ codebase to produce two deliverables:

1. **Missing Data Report** — data files or datasets referenced or implied by the architecture docs that do not exist in the data/ folder
2. **Hardcoded Values Report** — numeric constants, lookup tables, or configuration values embedded in Python source files that should be externalized to CSV data files pointed to by the data registry

## Scope

### Architecture docs to review (read every line)
- docs/arch/overview.md (708 lines) — domain specs, system boundaries
- docs/arch/data.md (782 lines) — data folder spec, dataset inventory, planned files table
- docs/arch/calculations.md (2545 lines) — formulas, coefficients, conversion factors
- docs/arch/policies.md (886 lines) — policy decision rules, thresholds, lookup references
- docs/arch/simulation_flow.md (1000 lines) — daily loop steps, data inputs per step
- docs/arch/structure.md (504 lines) — config schema, valid enum values, defaults

### Data folder to cross-reference
- settings/data_registry.yaml — the single source of truth for data file paths
- data/parameters/ — static parameter CSVs
- data/precomputed/ — Layer 1 output CSVs
- data/prices/ — historical price time-series CSVs

### Source code to scan for hardcoded values
- src/simulation/ — simulation engine (simulation.py, data_loader.py, state.py, metrics.py)
- src/policies/ — all 6 policy files
- src/settings/ — loader.py, calculations.py, validation.py
- settings/settings.yaml — scenario configuration

## Instructions

### Part 1: Missing Data

For each arch doc, extract every reference to a data file, dataset, parameter table, or lookup that the doc says should exist. Cross-reference against the actual data/ folder contents. Report:

| Doc | Section | Expected Dataset | Purpose | Status |
|-----|---------|-----------------|---------|--------|
| ... | ... | ... | ... | EXISTS / MISSING / PARTIAL |

Pay special attention to:
- The "Planned (Not Yet Created)" table in data.md — verify it's current
- Formulas in calculations.md that reference data files not yet created (e.g., crop_salinity_tolerance.csv for FAO-29)
- Policy decision rules in policies.md that mention parameters or thresholds with no corresponding data file
- Simulation steps in simulation_flow.md that load data not present in the registry
- Any data described narratively ("the community uses X") that implies a parameter file should exist

### Part 2: Hardcoded Values

Scan all Python source files in src/ and the settings YAML files for:

1. **Magic numbers** — numeric literals used in calculations that represent physical constants, engineering parameters, or policy thresholds (e.g., pump_efficiency=0.60, friction_factor=0.02, markup=1.165)
2. **Inline lookup tables** — dictionaries or if/elif chains that map categories to values (these should be CSVs)
3. **Default parameters** — function defaults that embed domain knowledge rather than referencing data files
4. **Conversion factors** — unit conversions that could change by context (e.g., exchange rates, density values)
5. **Threshold values** — decision boundaries in policies (e.g., minimum battery SOC, maximum drawdown)

For each finding, report:

| File:Line | Value | What It Represents | Recommendation |
|-----------|-------|--------------------|----------------|
| ... | ... | ... | Move to [existing/new] CSV: [path] |

### Exclusions — do NOT flag these as hardcoded:
- Universal physical constants (gravity=9.81, water density=1000 kg/m³)
- Pure mathematical constants (pi, e)
- Code-structural values (loop indices, array sizes, format strings)
- Values that are already loaded from data files or the registry
- Test/debug values clearly marked as such

## Output Format

Write the results to docs/codereview/ as a single markdown file with two sections:
1. Missing Data Report (table)
2. Hardcoded Values Report (table)

Include a summary count at the top: X missing datasets, Y hardcoded values found.

For each hardcoded value, classify priority:
- **HIGH** — value is used in production calculations and affects simulation output
- **MEDIUM** — value is a reasonable default but should be configurable
- **LOW** — value is stable/universal and externalizing adds complexity without benefit
