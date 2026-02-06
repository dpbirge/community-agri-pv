# Documentation

Documentation for the Community Agri-PV simulation model.

## Structure

- **`architecture/`** - Core model specifications (start here)
  - `overview.md` - Complete domain model specifications
  - `structure.md` - Configuration schema and policy structure
  - `calculations.md` - Calculation methodologies and formulas
  - `policies.md` - Policy decision rules and pseudocode
  - `data.md` - Data structure and format specifications

- **`codereview/`** - Code review reports
  - `calculations-vs-code-review-2026-02-05.md` - Active issue tracker (2 remaining items + deferred)
  - `archive/` - Historical code review documents

- **`planning/`** - Implementation plans and research plans
  - `archive/` - Completed planning documents (water simulation, Layer 2 fixes, code review fix plan, etc.)

- **`prompts/`** - AI assistant prompts for development workflows
  - `RESEARCH_PROMPT.md` - Research data collection instructions (active)
  - `_archive/` - Completed workflow prompts

- **`research/`** - Research findings
  - `egyptian_utility_pricing.md` - Egyptian electricity pricing research
  - `egyptian_water_pricing.md` - Egyptian water pricing research

- **`validation/`** - Validation reports
  - `_archive/` - Historical validation reports

## Key Documents

Start with `architecture/overview.md` for the complete model architecture and specifications.

## Current Status

- **Layer 1 (Pre-computation)**: Complete - 50 toy datasets, 14 research datasets
- **Layer 2 (Configuration)**: Complete - Scenario loader, all 6 policy types implemented, validation, calculations
- **Layer 3 (Simulation)**: Water simulation MVP complete with energy, crop, food processing, and economic tracking
