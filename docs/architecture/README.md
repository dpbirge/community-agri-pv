# Architecture

Core model specifications for the Community Agri-PV simulation model.

## Files

- **`community-model-plan.md`** - Complete domain model specifications, including physical systems, community structure, economics, and simulation methodology. This is the primary reference for understanding the model's scope and design philosophy.

- **`mvp-structure.md`** - Configuration schema and policy structure definitions. Defines all valid system configurations, policy types, and their parameters. Single source of truth for what can be configured in a simulation scenario.

- **`mvp-calculations.md`** - Calculation methodologies and formulas. Documents how physical quantities (irrigation demand, yields, energy, costs) are computed. Complements mvp-structure.md with the "how" to its "what".

- **`data-organization.md`** - Data structure, file formats, metadata standards, and quality suffixes (toy/research/real). Reference for understanding and creating datasets.

## Reading Order

For new developers:
1. Start with `community-model-plan.md` to understand the overall model
2. Read `mvp-structure.md` to see what can be configured
3. Reference `mvp-calculations.md` when implementing calculations
4. Use `data-organization.md` when working with datasets
