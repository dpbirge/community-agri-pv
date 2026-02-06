# Architecture

Core model specifications for the Community Agri-PV simulation model.

## Files

- **`overview.md`** - Complete domain model specifications, including physical systems, community structure, economics, and simulation methodology. This is the primary reference for understanding the model's scope and design philosophy.

- **`structure.md`** - Configuration schema and policy structure definitions. Defines all valid system configurations, policy types, and their parameters. Single source of truth for what can be configured in a simulation scenario.

- **`calculations.md`** - Calculation methodologies and formulas. Documents how physical quantities (irrigation demand, yields, energy, costs) are computed. Complements structure.md with the "how" to its "what".

- **`policies.md`** - Policy decision rules, pseudocode, and integration details. Documents how each policy domain makes allocation and timing decisions.

- **`data.md`** - Data structure, file formats, metadata standards, and quality suffixes (toy/research/real). Reference for understanding and creating datasets.

## Reading Order

For new developers:
1. Start with `overview.md` to understand the overall model
2. Read `structure.md` to see what can be configured
3. Reference `calculations.md` when implementing calculations
4. Reference `policies.md` for policy decision rules
5. Use `data.md` when working with datasets
