# Community Farm Modeling Outline

CRITICAL NOTE: To coding and review agents. This file is meant as a **guide** to help develop clear and complete specification files. It is acceptable for the specifications to not match this file perfectly, or for certain functionality outlined in this file to be missing in the detailed specification files. It is critical that the specifications are coherent unto themselves. This file is not part of the technical specifications however, but a high-level overview of architectural decisions and general goals for the model. Differences should be raised as just that, differences, but not necessarily as errors or critical issues that must be addressed.

## 1. Overview

### Primary goal

This model serves as an ‘what-if’ educational tool for farming communities, helping them understand the strengths and weaknesses of various infrastructural configurations, farming layouts, scheduling options, and agri-PV investments. The goal is to facilitate exploration of trade-offs rather than prescribe specific solutions.

The model simulates the operation of a collective farming community in an water limited, irrigation reliant region with a focus on testing co-ownership models for financing, operating, and distributing risks of water, energy, and farm systems. The model is also concerned with community resilience against both economic and environmental shocks and seeks to understand the best community designs, operational principles, and economic agreements for long-term stability.

The model generates standard reporting figures for an agri-PV farm system including unit costs, crop and processed food outputs, and energy and water system balances. Outputs include daily cash flow data and annual summary time-series showing net cash flows, profits, losses, inputs, and outputs.

### Community scale and context

**Community parameters (to be specified per scenario):**


| Parameter            | Default/Range      | Notes                                                                                      |
| -------------------- | ------------------ | ------------------------------------------------------------------------------------------ |
| Total community area | 25 km² (5 × 5 km)  | Includes all land uses                                                                     |
| Farmland area        | 500 hectares (20%) | Irrigated cropland                                                                         |
| Number of farms      | 15–30              | Individual family farms                                                                    |
| Community population | *TBD*              | For energy demand sizing                                                                   |
| Non-farm land uses   | *TBD*              | Housing, buildings, solar arrays, turbines, storage, processing, buffer zones, wells, etc. |


**Climate, energy, and water context:**

The baseline climate is a hot, arid region with negligible rainfall requiring year-round irrigation. The model is weather and soil-agnostic, it will run on whatever data is provided.

The community operates as a community-owned-microgrid with the following baseline energy situation:

- Grid connection available (reliability and pricing varies by scenario)
- Baseline grid electricity prices set per scenario (may include time-of-use variations)
- Diesel fuel available for backup generation (price set per scenario)
- Grid export potential may be enabled or disabled per scenario (affects curtailment decisions)
- Community-owned generation (PV, wind) and storage (battery) reduce grid dependence and stabilize costs

Both groundwater and municipal water sources are assumed available without supply constraints (within the model), though water quality and efficiency remain important for cost and energy tracking (e.g. increasing brackish water requires more energy for desalination). Water sources include:

- Brackish groundwater requiring onsite desalination treatment (future versions of model should add optimization of farming operations under supply constraint)
- Purchased municipal water from a government operated treatment plant (in this case desalinated ocean water

The ratio of groundwater to municipal water is a policy decision (see Policy Framework).

## 2. Model Architecture

### Computational Architecture

The model operates at a daily time-step over simulation periods of 5-30 years, allowing observation of how the system responds to various changes and shocks. To achieve both computational efficiency and clear separation of concerns, the model is organized into three distinct layers, each with well-defined responsibilities and strict boundaries.

#### Layer 1: Pre-computation Layer

Layer 1 handles all computationally expensive physical calculations that depend only on environmental conditions and infrastructure specifications-not on operational decisions. This layer runs before any simulation begins and produces indexed libraries of reference data.

The key insight behind Layer 1 is that many physical relationships are deterministic given their inputs: solar panel output depends on weather and panel specifications; crop water demand depends on weather, crop type, and growth stage; treatment energy depends on water chemistry. None of these depend on how the farm is operated day-to-day. By pre-computing these relationships across all relevant combinations of weather scenarios, crop types, planting dates, and infrastructure configurations, the simulation layer can retrieve values through simple lookups rather than repeated calculation.

Layer 1 produces normalized reference values (e.g., kWh per installed kW, cubic meters per hectare) that scale linearly with capacity or area. This normalization allows the Design Layer to specify any infrastructure size without requiring new pre-computation.

Critically, Layer 1 is never re-run by subsequent layers. If a simulation requests a configuration that does not exist in the pre-computed libraries (for example, a crop type that was not included), the system raises a validation error. This constraint ensures that all simulation runs draw from identical physical baselines, making results comparable and debugging tractable.

#### Layer 2: Design Layer

Layer 2 translates scenario specifications into concrete simulation parameters. It serves as the bridge between human-readable design decisions (500 kW of solar panels, 30 percent groundwater allocation) and the data structures the simulation layer consumes.

The Design Layer performs three functions. First, infrastructure specification: it defines the capacity of wells, treatment plants, solar arrays, batteries, and processing facilities. Second, community structure: it establishes the number of farms, their profiles, starting conditions, and economic arrangements. Third, policy selection: it chooses which rule sets govern operational decisions during simulation.

When a design is finalized, Layer 2 validates that all required pre-computed data exists in the Layer 1 libraries. It then assembles the complete input package for simulation: scaled versions of the reference curves (multiplying normalized PV output by installed capacity, for example), farm assignments, policy rule sets, and initial conditions.

Layer 2 is purely configurational-it performs no simulation. Its output is a complete, validated scenario specification that Layer 3 can execute without further reference to Layer 1 or external data.

A key aspect of the design layer is that it can be informed and constrained by the available datasets produced in Layer 1. So Layer 1 sets up the open-space for Layer 2.

#### Layer 3: Simulation Layer

Layer 3 is where time advances and decisions are made. It takes the pre-computed physical data and design specifications from Layers 1 and 2 and simulates daily operations over the full scenario period.

Each simulation day follows a consistent sequence. First, retrieve conditions: environmental data and resource availability from pre-computed libraries. Second, execute policies: operational decisions including energy allocation, irrigation timing, water source selection, harvest and sale timing. Third, track flows: physical quantities (water pumped, energy consumed, crops harvested) recorded in material balances. Fourth, record economics: costs incurred, revenues earned, cash positions updated.

Layer 3 handles all dynamic, state-dependent logic: inventory management (crops in storage, battery state of charge), event processing (equipment failures [DEFERRED], maintenance schedules [DEFERRED]), and financial accounting (debt service, pooling contributions). The layer maintains strict separation between physical and economic calculations-physical modules output only quantities (kWh, cubic meters, kg), and a separate economic module applies prices to those quantities.

At the end of each time-step, Layer 3 performs reconciliation checks to ensure all material and energy balances close. Any discrepancy indicates a modeling error rather than a valid simulation outcome.

#### Layer Interactions and Data Flow

The three layers interact through well-defined interfaces with minimal coupling.

Layer 1 to Layer 2: Layer 1 produces indexed libraries that Layer 2 queries but never modifies. The interface is read-only: Layer 2 provides keys (weather scenario ID, crop type, planting date) and receives reference values. Layer 1 has no knowledge of specific scenarios-it simply provides a complete library of physical relationships.

Layer 2 to Layer 3: Layer 2 consumes Layer 1 libraries and produces a scenario package for Layer 3. This package contains everything Layer 3 needs: scaled physical curves, farm definitions, policy configurations, and initial state. Once assembled, Layer 2 role is complete.

Layer 3 execution: Layer 3 executes the scenario package in isolation. It cannot request new pre-computations from Layer 1 or modify the design specification from Layer 2. This constraint ensures simulation results are fully determined by the scenario package, supporting reproducibility and comparison across runs.

For Monte Carlo analysis [DEFERRED — not in MVP], Layer 3 executes multiple runs with different stochastic draws (weather scenarios, price paths, failure events) while holding the design specification constant. This reveals how a single infrastructure and policy configuration performs across a range of conditions.

#### What Each Layer Does Not Do

Boundaries are as important as responsibilities. Layer 1 does not make operational decisions, track state over time, or incorporate economics. It computes physical relationships only. Layer 2 does not simulate. It validates, configures, and assembles, but time never advances in Layer 2. Layer 3 does not re-compute physical relationships. If PV output for a given weather day was pre-computed as X kWh/kW, Layer 3 uses that value-it does not run pvlib or crop models during simulation.

This separation keeps the model computationally tractable while supporting the complexity needed for meaningful scenario analysis.

### Domain Overview

The model represents an integrated agricultural community with interdependent physical and economic systems. The physical domain includes water infrastructure (extraction, treatment, irrigation), energy infrastructure (solar, wind, storage, grid connection, backup generation), and agricultural operations (crop cultivation, post-harvest storage and processing). The economic domain covers individual farmer finances, collective pooling and reserves, debt service, and optional insurance mechanisms.

Each system is specified in detail in Section 3: Subsystem Specifications, which defines the parameters, constraints, and behaviors for water, energy, labor, crops, post-harvest operations, and economic arrangements.

### Stochastic Parameters [DEFERRED — not in MVP]

**Implementation status:** The Monte Carlo framework and stochastic parameter sampling are deferred from MVP. The MVP simulation runs deterministically using a single weather scenario and historical price time-series loaded from CSV files. The framework described below defines the target design for stochastic simulation. When implemented, this will require: (1) a Monte Carlo wrapper around the daily loop in `simulation_flow.md`, (2) parameter sampling and injection logic, (3) stochastic price generation or scenario selection, and (4) equipment failure event modeling. See `monte_carlo.py` for the existing framework scaffold.

The Monte Carlo framework varies parameters across runs to test system robustness. Stochastic elements are organized by their causal relationships.

**Primary drivers** are root-level random variables sampled at the start of each run. Weather scenarios (temperature, irradiance, wind speed, precipitation patterns) serve as the primary driver, selected from the pre-computed Layer 1 library.

**Derived variability** flows deterministically from weather. Crop yields, irrigation demand, PV output, and wind output all vary across runs because they depend on weather-but given a weather scenario, their values are fixed by Layer 1 pre-computation.

**Independent factors** vary separately from weather: market prices for crops and processed goods, grid energy prices, municipal water prices, and equipment failure events [DEFERRED — not in MVP; no discrete failure/downtime model exists]. These are sampled independently according to configured volatility patterns or failure probabilities.

**Correlations** between factors can be modeled where data supports them (e.g., regional drought coinciding with higher water prices or crop price spikes). The model can implement these correlations or assume independence as a simplifying assumption, depending on available data and scenario goals.

#### Crop and Processed Product Prices

Price dynamics for agricultural commodities represent a critical source of uncertainty and a major driver of farm decision-making.

> **MVP note:** The MVP uses historical price time-series loaded from CSV files (`data/prices/`) rather than stochastic price generation. These historical series already embed the seasonal variation, year-to-year volatility, and trend patterns described below — the simulation replays actual price history rather than sampling from a statistical model. This approach effectively captures realistic price dynamics for deterministic runs. The stochastic framework described below would add the ability to generate synthetic price paths for Monte Carlo analysis, but the historical replay achieves the same educational objectives for single-run scenarios. The gap is that the MVP cannot generate price scenarios beyond the historical record or test tail-risk events not present in the data.

**Raw crop prices** exhibit characteristic patterns: seasonal variation (prices typically lowest at harvest when supply peaks, higher in off-season), year-to-year volatility driven by regional and global supply conditions, and longer-term trends reflecting demand shifts or input cost changes. Historical price series from FAO, USDA, or regional agricultural ministries provide the basis for calibrating mean levels, seasonal patterns, and volatility parameters. For each crop type in the model, price parameters include a baseline annual mean, a seasonal adjustment curve, and a volatility measure (standard deviation or coefficient of variation).

**Processed product prices** (dried goods, canned products, packaged items) follow related but distinct dynamics. Processing creates a price spread — the difference between the raw crop price and the processed product price — that compensates for processing costs, weight loss, labor, and storage. This spread is not constant: it varies with raw crop prices, seasonal demand for processed goods, and market conditions. The model captures this by defining processed product prices as a function of raw prices plus a stochastic spread component, rather than as a fixed multiplier.

**The planting decision** depends heavily on expected price levels and volatility at harvest time. Farmers choosing crops months before harvest must form expectations about future prices. The model supports different expectation-formation rules: naive expectations (last year's price), moving averages, or simple forecasts. Risk-averse farmers may favor crops with lower price volatility even if expected prices are lower, while risk-tolerant farmers may plant high-volatility crops seeking upside. The interaction between crop choice and price uncertainty is a key educational output of the model.

**The sell-or-process decision** hinges on the price spread between raw and processed goods relative to processing costs. When raw prices are high, immediate sale may be optimal; when raw prices are depressed, processing can capture value that would otherwise be lost. However, processing requires time, labor, energy, and storage — all of which have costs and capacity constraints. The model allows farmers to make this decision based on current prices and price forecasts, with different farmers potentially following different rules based on their risk tolerance and cash flow needs.

**Sale timing for storable goods** introduces additional price exposure. Farmers holding processed products can wait for better prices, but face storage costs and spoilage risk. The model tracks inventory positions and allows sale timing rules that respond to price thresholds, storage duration, or cash flow requirements. This creates a trade-off between holding for potential price appreciation and the carrying costs of delayed sale.

**Price correlation structure** matters for community-level risk. If all farmers plant the same crop, they face correlated price risk — a price crash affects everyone simultaneously. Crop diversification across the community can reduce this correlation, but only if different crops have imperfectly correlated prices. The model can test how community-level crop mixing strategies affect collective risk exposure compared to individual optimization.

## 3. Subsystem Specifications

### Physical Systems

#### Labor model

The community farm is primarily human labor-based with hand-driven machinery only (no tractors).

**Labor availability:**

Labor supply is assumed unlimited—additional workers can always be hired as needed. Labor is not modeled as a constraint to optimize around, but labor costs and employment generation are key output metrics.

**Labor sources:**

- Community members (primary workforce, paid wages)
- External hired labor (available for peak periods, potentially higher cost)

**Labor profiles (3–5 categories):**


| Profile                       | Activities                                                | Notes                          |
| ----------------------------- | --------------------------------------------------------- | ------------------------------ |
| Field work                    | Planting, weeding, harvesting, irrigation management      | Seasonal, weather-dependent    |
| Transport and logistics       | Moving crops from field to storage/processing, deliveries | Linked to harvest timing       |
| Food processing and packaging | Drying, canning, packaging operations                     | Post-harvest, can be scheduled |
| Infrastructure maintenance    | PV cleaning, pump maintenance, building upkeep            | Year-round, relatively stable  |
| Administrative and sales      | Financial management, market sales, coordination          | Year-round, relatively stable  |


**Labor parameters:**


| Parameter              | Unit                    | Notes                                     |
| ---------------------- | ----------------------- | ----------------------------------------- |
| Labor hours per action | hours/event or hours/kg | By activity type                          |
| Community labor wage   | $/hour                  | Wage paid to community members            |
| External labor wage    | $/hour                  | Wage paid to hired external workers       |
| External labor ratio   | %                       | Proportion of labor from external sources |


**Employment outputs:**

Job creation and employment are tracked as key community benefit metrics:

- Total employment generated (person-years per year)
- Employment by profile (distribution of work types)
- Peak employment periods (monthly labor demand)
- Community vs external employment ratio

**Labor smoothing:**

Crop scheduling decisions (planting dates, crop mixing) can be designed to smooth labor demand across the season and spread out harvesting periods, reducing peak labor requirements.

### Economic & Financial Systems

#### Economic model

The economic architecture balances individual farmer autonomy with collective risk management.

**Individual farmer accounts:**

Each farm is modeled independently with its own yields, revenues, and expenses. Farms may differ in starting capital, farm size, and crop yield factors (soil quality). Solar access, irrigation infrastructure, and fertilizer inputs are identical across farms.

**Collective pooling mechanism:**

A configurable percentage of individual profits flows to a collective reserve fund each year. This reserve provides a buffer during down years caused by weather, market, or equipment shocks. Distribution policies determine how funds are allocated back to farmers during hardship.

**Implementation status:** Collective pooling is deferred from MVP. The  
`cost_allocation_method` parameter in `structure.md` handles shared  
infrastructure cost allocation but does not implement the profit-pooling  
and distribution mechanism described above. See `future_improvements.md`  
for implementation guidance.

**Working capital and cash flow:**

Cash flows are modeled at the daily time-step to capture the seasonal nature of farming economics. Farmers work collectively to operate shared infrastructure (including communal storage, processing facilities, and financial administration). Money flows to farmers throughout the year to cover operating expenses and is recouped when goods are sold to market.

*Questions to be determined in future research:*

- How are operating advances determined? Fixed amount per farm, based on planted area, or based on historical needs?
- What happens if a farmer's harvest revenue doesn't cover their advances? Is this absorbed by the collective or carried as debt?
- How are collective infrastructure costs allocated across farms (equal share, proportional to farm size, proportional to usage)?

**Collective debt service:**

The community holds collective debt for shared infrastructure purchases (PV systems, water treatment, processing equipment). A single debt structure applies to the entire community (see Debt Financing Options).

**Discount rate and inflation:**

Financial calculations follow standard modeling conventions:

- Real discount rate: configurable parameter (default 5–7% typical for agricultural projects)
- All prices modeled in real terms (constant currency) unless otherwise specified
- Inflation can be applied as a sensitivity parameter for nominal scenario testing
- NPV calculations use the specified real discount rate
- ROI and payback calculations assume constant real prices unless inflation scenarios are enabled

#### Debt financing options

*Content to be added*

#### Farmer heterogeneity

The community consists of 5–30 individual farms, each modeled with distinct characteristics.

**Variable parameters (differ by farm):**


| Parameter        | Range/Type           | Notes                                                             |
| ---------------- | -------------------- | ----------------------------------------------------------------- |
| Farm size        | hectares             | Land area allocated to each farm                                  |
| Yield factor     | 0.8–1.2 (multiplier) | Accounts for soil quality variations; applied to base crop yields |
| Starting capital | $                    | Initial cash reserves at simulation start                         |
| Risk tolerance   | policy selection     | Determines which economic policy the farmer operates under        |


**Risk tolerance and policy selection:**

Risk tolerance is translated into the specific policies each farmer agrees to operate under:

- Conservative farmers may opt for higher pooling percentages and earlier sale timing
- Risk-tolerant farmers may prefer lower pooling and hold crops for better prices
- The policy framework allows testing how different farmer compositions affect community outcomes

**Constant parameters (identical across farms):**

- Solar and irrigation infrastructure access
- Fertilizer inputs and costs
- Access to shared processing and storage facilities
- Collective debt obligations (shared proportionally)

#### Insurance options [DEFERRED -- not in MVP]

As an alternative or complement to self-insurance through collective pooling, the model can test formal insurance products.

**Insurance types:**

- Crop insurance policies with configurable premiums and coverage levels
- Equipment insurance for shared infrastructure (PV, water treatment, processing)

**Key comparison:**

The model can compare insurance costs vs self-insurance reserve requirements to help communities decide which risk management approach works best for their situation.

**Considerations to be determined:**

The following insurance design questions should be addressed in future research before implementation:

- What triggers a payout? (Yield below X% of expected? Revenue below threshold? Weather event?)
- What are appropriate deductible levels and coverage caps?
- Is insurance mandatory for all farmers or optional on a per-farmer basis?
- Should the model distinguish between government-subsidized crop insurance programs and private insurance products?
- How do insurance payouts interact with the collective pooling mechanism?
- What is the claims process and timing of payouts (immediate vs end of season)?

**Implementation status:** Insurance is deferred from MVP. The design questions  
listed above must be resolved before insurance can be specified as a policy domain.  
When implemented, insurance will require: (1) a new policy domain in `policies.md`  
with context/decision dataclasses, (2) a YAML configuration section in  
`structure.md`, (3) premium and payout formulas in `calculations.md`, and (4)  
integration into the simulation loop in `simulation_flow.md` (likely as a yearly  
boundary operation). See `policies.md` "How to Add a New Policy" for the general  
pattern.

### Operations

#### Post-harvest system

The model tracks post-harvest economics with full parameterization of storage, processing, and sales.

**Storage parameters:**


| Parameter             | Unit                 | Notes                                               |
| --------------------- | -------------------- | --------------------------------------------------- |
| Storage capacity      | kg or m³             | By storage type (ambient, climate-controlled)       |
| Storage cost          | $/kg/day or $/m³/day | Operating cost including energy for climate control |
| Storage energy demand | kWh/m³/day           | For climate-controlled storage                      |


**Spoilage parameters (by product type):**


| Parameter  | Unit | Notes                                                                                                                                                                                                     |
| ---------- | ---- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Shelf life | days | Maximum storage duration per crop and product type before forced sale. Binary model: product is fully sellable until expiry, then must be sold immediately. Data source: `storage_spoilage_rates-toy.csv` |


> **Design decision:** The simulation uses a binary shelf-life model (product  
> is either sellable or expired) rather than a gradual spoilage model  
> (continuous weight loss %/day). The binary model is simpler, well-suited to  
> the FIFO tranche tracking system (see `policies.md` umbrella rule), and  
> appropriate for an educational tool where the key insight is shelf-life  
> duration differences between fresh and processed products. A gradual model  
> could be added as a future refinement if needed.

**Processing parameters:**


| Parameter            | Unit     | Notes                                                                        |
| -------------------- | -------- | ---------------------------------------------------------------------------- |
| Processing capacity  | kg/day   | Maximum throughput per processing type                                       |
| Processing labor     | hours/kg | Labor requirement by processing type                                         |
| Processing cost      | $/kg     | Non-labor operating costs (packaging, energy, materials)                     |
| Processing energy    | kWh/kg   | Energy demand for processing operations                                      |
| Value-add multiplier | ratio    | Price multiplier for processed vs fresh product (e.g., 1.5× for dried goods) |
| Processing loss      | %        | Weight loss during processing (e.g., drying reduces mass)                    |


**Market timing:**

Farmers can choose when to sell based on individual decision rules. This is particularly relevant for non-perishable goods (dried products, canned goods) that can be held for better market conditions.


| Parameter              | Unit     | Notes                                                           |
| ---------------------- | -------- | --------------------------------------------------------------- |
| Farmer sale rule       | policy   | Individual rule set for when to sell (see Farmer Heterogeneity) |
| Market price forecast  | $/kg     | Farmer's expectation of future prices (simple or sophisticated) |
| Holding cost threshold | $/kg/day | Maximum acceptable storage cost before forced sale              |


#### Policy framework

This model is designed for educational purposes to help farming communities understand the strengths and weaknesses of different system configurations, agreements, and business models.

Policies are rule sets that govern operational decisions. The framework supports testing the following policy categories:

**Water policies:**

- Groundwater vs municipal water ratio (baseline allocation)
- Trigger conditions for switching water sources:
  - Groundwater treatment cost exceeds municipal price by X%
  - Energy availability for treatment falls below threshold
  - Municipal price spike triggers shift to groundwater
- ~~Seasonal allocation strategies~~ — Removed for MVP. Water source allocation does not vary by season. Seasonal differences in crop water *demand* are captured by the irrigation model, but supply-side policies are season-agnostic.

**Energy policies:**

- Priority ordering: diesel backup vs grid backup vs battery
- Baseline assumes microgrid with grid connection
- Curtailment vs battery storage vs grid export decisions

> **Scope note:** Load management and load shifting are excluded from the model.  
> These strategies require sub-daily (hourly) time resolution to be meaningful.  
> The simulation operates at a daily time step, which aggregates all demand and  
> generation within a day. Energy dispatch priority ordering achieves the relevant  
> economic optimization at daily resolution. See `future_improvements.md` for what  
> would be needed to add load shifting.

**Crop policies:**

- Irrigation adjustment strategies (deficit irrigation, weather-adaptive demand)
- Harvest scheduling to smooth labor requirements [DEFERRED]

> **Scope note:** Crop type selection, planting dates, and area fractions are  
> static configuration parameters set in the scenario YAML (see `structure.md`  
> Farm configurations). They are Layer 2 design decisions, not Layer 3 runtime  
> policies. To test different crop mixes or planting strategies, create separate  
> scenario files. Crop policies in the simulation govern only irrigation demand  
> adjustment during the growing season. See `future_improvements.md` for how  
> dynamic crop selection could be implemented.

**Economic policies:**

- Pooling percentages and distribution rules
- Debt structure selection (fixed monthly payments per financing profile; no accelerated repayment in MVP)
- Insurance vs self-insurance strategies
- Working capital advance rules [DEFERRED -- see open questions in Economic model section]

**Market policies:**

- Individual farmer rules for sale timing
- Collective vs individual marketing strategies
- Price threshold triggers for selling stored goods

**Policy interactions:**

Policy choices can interact in important ways. For example:

- Aggressive market timing + low pooling = high individual risk exposure
- High energy self-sufficiency + groundwater preference = lower operating costs but higher capex
- Crop diversification + staggered planting = smoother labor and cash flow but potentially lower peak yields

The model focuses on the most important policy levers to avoid over-complication, but can test policy combinations to reveal these interaction effects.

## 4. Outputs & Validation

### Model outputs and data viz

**Output granularity:**

Daily data is stored for all flows; monthly and annual summaries are generated for reporting. Farmer-level and community-level aggregations are provided separately.

**Primary output metrics:**

- Food outputs (kg by crop type, processed goods by category)
- Daily and annual cash flows (individual farmer and community aggregate)
- Payback period for infrastructure investments
- Return on investment (ROI)
- Net present value (NPV) of community operations
- Monte Carlo success rate (% of simulations completing 20 years without default)

**Energy robustness metrics:**

- Self-sufficiency ratio (% energy from owned assets vs grid/diesel)
- Curtailment events (excess generation that cannot be used or stored)
- Days of stored energy reserves
- Grid and diesel dependency ratio
- Cost volatility reduction vs baseline scenario (no owned infrastructure)

**Labor metrics:**

- Labor hours by profile (field work, transport, processing, maintenance, admin)
- Peak labor demand periods (monthly breakdown)
- Labor cost as percentage of revenue
- Total employment generated (person-years per year)
- External vs community labor ratio

**Risk and resilience metrics:**

- Probability of crop failure by scenario
- Minimum cash reserves required for solvency
- Debt coverage ratio over time
- Water and energy cost stability index
- Default probability across Monte Carlo runs

**Distributional metrics (farmer-level):**

- Distribution of farmer outcomes (revenue, profit) across the community
- Worst-case farmer scenario (minimum profit/loss)
- Gini coefficient or similar inequality measure for farmer incomes
- Pooling fund contribution vs withdrawal by farmer

**Visualization types:**

- Time-series plots: cash flow, energy balance, water usage, crop inventory (daily/monthly/annual)
- Probability distributions: Monte Carlo outcome histograms for key metrics
- Scenario comparison dashboards: side-by-side policy/infrastructure comparisons
- Sankey diagrams: annual energy and water flow visualization
- Farmer-level heatmaps: performance variation across farms

### How do we validate results?

**Input validation:**

Input data is validated by individual upstream modules (PV power via pvlib, wind power, crop yields via crop simulators). These modules use established, open-source libraries with their own validation histories.

**Financial calculations:**

All financial calculations follow standard best practices (NPV, IRR, payback period, debt service coverage ratios).

**Sensitivity analysis:**

Key parameters are varied systematically to confirm the model responds appropriately:

- Capex/opex variations (±20%) should produce proportional changes in payback and ROI
- Weather severity should correlate with crop yield and irrigation cost outcomes
- Price volatility should affect cash flow variance in expected directions

**Comparison against published benchmarks:**

Output results are checked against:

- Published agri-PV yield studies for comparable climates
- FAO and regional agricultural extension data for crop yields and water usage
- Industry benchmarks for PV system costs and performance ratios
- Historical price ranges for relevant crops and energy markets

**Code quality:**

- Unit tests for individual functions and modules
- Integration tests for system interactions (e.g., energy shortage triggers correct backup sequence)
- Code review assistance from multiple AI models (Opus, ChatGPT, Gemini, Grok) to identify logic errors

## 5. Implementation Guide

See [implementation_guide.md](../planning/implementation_guide.md) for the phased build plan and testing criteria. For data file formats, naming conventions, and the complete data catalog, see `data.md`.

## 6. References

[[1]](1): U.S. Department of Agriculture, Farm Service Agency, "Farm Loan Programs," accessed January 2026, [https://www.fsa.usda.gov/resources/farm-loan-programs](https://www.fsa.usda.gov/resources/farm-loan-programs).

[[2]](2): U.S. Department of Agriculture, Farm Service Agency, "Beginning Farmers and Ranchers Loans," accessed January 2026, [https://www.fsa.usda.gov/resources/beginning-farmers-and-ranchers-loans](https://www.fsa.usda.gov/resources/beginning-farmers-and-ranchers-loans).

[[3]](3): Farm Credit Administration, "Fiscal Year 2025 Proposed Budget and Performance Plan," accessed January 2026, [https://www.fca.gov/template-fca/about/BudgetFY2025.pdf](https://www.fca.gov/template-fca/about/BudgetFY2025.pdf).