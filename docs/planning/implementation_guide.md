# Implementation Guide

> Extracted from [overview.md](../arch/overview.md) Section 5. This document is the authoritative reference for build phasing, testing criteria, and data contracts across the three-layer architecture.

### Software architecture

This section provides guidance for iterative model development, designed to enable validation at each phase and reduce the risk of cascading errors during development (particularly important when using LLM coding assistants).

**Core principles:**

1. Build and validate physical systems before adding economic complexity
2. Start with minimal scale (1 farm) and expand incrementally
3. Use deterministic runs to validate logic before introducing stochasticity
4. Define clear data contracts between modules to isolate failures
5. Establish testing criteria at each phase before proceeding

**Phase 1: Layer 1 Libraries (Pre-compute)**

Build the upstream modules that generate pre-computed data libraries.

*Modules:*

- Weather generator (synthetic or historical time-series)
- PV power calculator (pvlib-based, outputs normalized kWh/day per kW)
- Wind power calculator (outputs normalized kWh/day per kW)
- Crop irrigation calculator (outputs m³/ha/day by crop × weather × planting date)
- Water treatment energy calculator (kWh/m³)
- Microclimate calculator (temperature/irradiance adjustments under PV)

*Data contract (Layer 1 → Layer 2/3):*

- Indexed libraries with consistent keys (weather_scenario_id, crop_type, planting_date, etc.)
- Normalized reference values that scale linearly with capacity/area
- Metadata describing available configurations and valid ranges

*Testing criteria:*

- [ ] Weather outputs pass statistical tests (temperature ranges, solar patterns, seasonality)
- [ ] PV outputs match pvlib reference cases within 1%
- [ ] Wind outputs match manufacturer power curves
- [ ] Crop irrigation totals fall within FAO reference ranges for crop type and climate
- [ ] All library keys are unique and consistently formatted

**Phase 2: Physical Systems (Single Farm, Deterministic)**

Build the simulation layer for physical flows only, with a single farm and no economic tracking.

*Modules:*

- Water system: extraction, treatment, irrigation scheduling
- Energy system: PV/wind dispatch, battery charge/discharge, grid/diesel backup
- Crop system: planting, growth tracking, harvest
- Labor system: hours tracking by profile

*Scope:*

- 1 farm, 1 weather scenario, 1 year
- Fixed policies (no decision logic yet)
- Track physical flows only (water m³, energy kWh, crop kg, labor hours)

*Data contract (between physical modules):*

- Daily state object containing: date, weather, available energy, water demand, crop status, labor demand
- Each module reads state, performs calculations, updates state
- Reconciliation step verifies all balances close

*Testing criteria:*

- [ ] Water balance closes: extraction + municipal = irrigation + losses (within 0.1%)
- [ ] Energy balance closes: generation + grid + diesel = demand + battery_delta + curtailment (within 0.1%)
- [ ] Crop yields match pre-computed expectations (given weather and irrigation)
- [ ] Labor hours fall within expected ranges for farm size and crop type
- [ ] No negative values for physical quantities
- [ ] Simulation completes 365 days without errors

**Phase 3: Physical Systems (3 Farms, Deterministic)**

Extend to multiple farms sharing infrastructure.

*New complexity:*

- 3 farms with different sizes and yield factors
- Shared energy and water infrastructure
- Aggregated vs individual tracking

*Testing criteria:*

- [ ] Community-level balances still close
- [ ] Individual farm outputs scale appropriately with farm size and yield factor
- [ ] Shared infrastructure properly allocates resources across farms
- [ ] Total labor = sum of individual farm labor

**Phase 4: Policies and Events (3 Farms, Deterministic)**

Add policy-based decision logic and discrete events.

*Modules:*

- Energy policy: priority ordering, load shifting
- Water policy: groundwater vs municipal switching
- Crop policy: irrigation timing flexibility
- Event system: equipment failures, maintenance schedules

*Testing criteria:*

- [ ] Energy policy correctly prioritizes sources (PV → battery → grid → diesel)
- [ ] Water policy switches sources at configured thresholds
- [ ] Irrigation timing shifts respond to energy availability
- [ ] Equipment failure events trigger appropriate downtime and repair costs
- [ ] Policies produce different outcomes than fixed baseline

**Phase 5: Post-Harvest System (3 Farms, Deterministic)**

Add storage, processing, and market timing.

*Modules:*

- Storage: inventory tracking, spoilage calculations
- Processing: capacity constraints, value-add, labor
- Market timing: sale decision logic

*Testing criteria:*

- [ ] Spoilage rates match configured parameters
- [ ] Processing throughput respects capacity limits
- [ ] Value-add multipliers correctly applied to processed goods
- [ ] Inventory balances: harvested = stored + processed + spoiled + sold
- [ ] Market timing rules trigger sales at configured thresholds

**Phase 6: Economic System (3 Farms, Deterministic)**

Add financial tracking, costs, revenues, and debt.

*Modules:*

- Cost tracking: capex (annualized), opex, labor costs
- Revenue tracking: crop sales by type and timing
- Cash flow: daily balances, working capital
- Debt service: principal, interest, payment schedules
- Pooling: contributions, distributions, reserve balance

*Data contract (physical → economic):*

- Physical modules output quantities (kWh, m³, kg, hours)
- Economic module applies prices and costs to quantities
- Clear separation: physical modules never reference prices

*Testing criteria:*

- [ ] Revenue = sum of (quantity sold × price) across all products
- [ ] Costs match configured opex rates × quantities
- [ ] Cash flow = revenue - costs - debt service ± pooling transfers
- [ ] Debt balance decreases correctly with payments
- [ ] NPV and ROI calculations match manual verification
- [ ] No farm goes below configured minimum cash reserve (or triggers appropriate response)

**Phase 7: Multi-Year Deterministic (3 Farms, 5 Years)**

Extend simulation length to test multi-year dynamics.

*New complexity:*

- Year-over-year accumulation (reserves, debt paydown)
- Seasonal patterns repeat correctly
- Long-term trends (if any) behave as expected

*Testing criteria:*

- [ ] Debt fully repaid by expected year (given payment schedule)
- [ ] Reserve fund grows in good years, depletes in bad years appropriately
- [ ] No drift in physical balances over multiple years
- [ ] Annual summaries aggregate correctly from daily data

**Phase 8: Stochastic Single Runs (3 Farms, 20 Years)**

Introduce stochastic elements one at a time.

*Sequence:*

1. Weather variability only (select from weather scenario library)
2. Add price variability
3. Add equipment failures

*Testing criteria:*

- [ ] Different weather scenarios produce different outcomes (not identical)
- [ ] Price variability affects cash flow variance as expected
- [ ] Equipment failures trigger repair events and costs
- [ ] Outcomes remain within plausible ranges (no extreme outliers from bugs)

**Phase 9: Monte Carlo (3 Farms, 20 Years, N Runs)**

Full Monte Carlo simulation capability.

*Testing criteria:*

- [ ] Distribution of outcomes is stable (more runs → converging statistics)
- [ ] Success rate (% completing without default) is plausible
- [ ] Worst-case and best-case outcomes are within reasonable bounds
- [ ] Results are reproducible with same random seed

**Phase 10: Scale to N Farms with Profiles**

Expand from 3 farms to full community (15–30 farms) using farm profiles.

*New complexity:*

- 2–5 farm profile types
- Farms assigned to profiles (e.g., 10 conservative, 10 moderate, 5 risk-tolerant)
- Distributional metrics across heterogeneous farms

*Testing criteria:*

- [ ] Profile assignments correctly determine farm parameters
- [ ] Community aggregates scale appropriately with number of farms
- [ ] Distributional metrics (Gini, worst-case farmer) compute correctly
- [ ] Performance remains acceptable (runtime scales linearly or better with farm count)

**Phase 11: Scenario Comparison and Reporting**

Build comparison and visualization tools.

*Modules:*

- Scenario runner: batch execution of multiple configurations
- Comparison dashboard: side-by-side metrics
- Visualization suite: time-series, distributions, Sankey diagrams

*Testing criteria:*

- [ ] Different scenarios produce meaningfully different outcomes
- [ ] Visualizations correctly represent underlying data
- [ ] Reports export cleanly (PDF, CSV, etc.)

**Data contract summary:**


| Interface            | From             | To              | Key data                                                          |
| -------------------- | ---------------- | --------------- | ----------------------------------------------------------------- |
| Library lookup       | Layer 1          | Layer 2         | Pre-computed reference values by scenario/config keys             |
| Design specification | Layer 2          | Layer 3         | Infrastructure sizes, farm profiles, policy selections            |
| Daily state          | Layer 3 modules  | Layer 3 modules | Date, weather, energy available, water demand, crop status, labor |
| Physical → Economic  | Physical modules | Economic module | Quantities only (kWh, m³, kg, hours) — no prices                  |
| Farm → Community     | Individual farms | Aggregator      | Farm-level metrics for community rollup                           |
| Simulation → Output  | Layer 3          | Reporting       | Daily logs, annual summaries, Monte Carlo distributions           |
