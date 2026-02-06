# Documentation

Documentation for the Community Agri-PV simulation model.

## Structure

- **`architecture/`** - Core model specifications (start here)
  - `community-model-plan.md` - Complete domain model specifications
  - `mvp-structure.md` - Configuration schema and policy structure
  - `mvp-calculations.md` - Calculation methodologies and formulas
  - `data-organization.md` - Data structure and format specifications

- **`codereview/`** - Code review reports
  - Calculations vs code verification reports
  - `archive/` - Historical code review documents

- **`planning/`** - Implementation plans and research plans
  - `code-review-fix-plan-claude-2026-02-05.md` - Current fix plan
  - `archive/` - Completed planning documents (water simulation, Layer 2 fixes, etc.)

- **`prompts/`** - AI assistant prompts for development workflows
  - `RESEARCH_PROMPT.md` - Research data collection instructions (active)
  - `_archive/` - Completed workflow prompts

- **`research/`** - Research findings
  - `egyptian_utility_pricing.md` - Egyptian electricity pricing research
  - `egyptian_water_pricing.md` - Egyptian water pricing research

- **`validation/`** - Validation reports
  - `_archive/` - Historical validation reports

## Key Documents

Start with `architecture/community-model-plan.md` for the complete model architecture and specifications.

## Current Status

- **Layer 1 (Pre-computation)**: Complete - 50 toy datasets, 14 research datasets
- **Layer 2 (Configuration)**: Complete - Scenario loader, all 6 policy types implemented, validation, calculations
- **Layer 3 (Simulation)**: Water simulation MVP complete with energy, crop, food processing, and economic tracking
