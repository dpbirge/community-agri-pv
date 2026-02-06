# Community Farm Modeling Specifications

## 1. Overview

### Primary goal

This model serves as an ‘what-if’ educational tool for farming communities, helping them understand the strengths and weaknesses of various infrastructural configurations, farming layouts, scheduling options, and agri-PV investments. The goal is to facilitate exploration of trade-offs rather than prescribe specific solutions.

The model simulates the operation of a collective farming community in an water limited, irrigation reliant region with a focus on testing co-ownership models for financing, operating, and distributing risks of water, energy, and farm systems. The model is also concerned with community resilience against both economic and environmental shocks and seeks to understand the best community designs, operational principles, and economic agreements for long-term stability.

The model generates standard reporting figures for an agri-PV farm system including unit costs, crop and processed food outputs, and energy and water system balances. Outputs include daily cash flow data and annual summary time-series showing net cash flows, profits, losses, inputs, and outputs.

### Community scale and context

**Community parameters (to be specified per scenario):**

| Parameter | Default/Range | Notes |
| --- | --- | --- |
| Total community area | 25 km² (5 × 5 km) | Includes all land uses |
| Farmland area | 500 hectares (20%) | Irrigated cropland |
| Number of farms | 15–30 | Individual family farms |
| Community population | *TBD* | For energy demand sizing |
| Non-farm land uses | *TBD* | Housing, buildings, solar arrays, turbines, storage, processing, buffer zones, wells, etc. |

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

#### Layer 3: Simulation Layer

Layer 3 is where time advances and decisions are made. It takes the pre-computed physical data and design specifications from Layers 1 and 2 and simulates daily operations over the full scenario period.

Each simulation day follows a consistent sequence. First, retrieve conditions: environmental data and resource availability from pre-computed libraries. Second, execute policies: operational decisions including energy allocation, irrigation timing, water source selection, harvest and sale timing. Third, track flows: physical quantities (water pumped, energy consumed, crops harvested) recorded in material balances. Fourth, record economics: costs incurred, revenues earned, cash positions updated.

Layer 3 handles all dynamic, state-dependent logic: inventory management (crops in storage, battery state of charge), event processing (equipment failures, maintenance schedules), and financial accounting (debt service, pooling contributions). The layer maintains strict separation between physical and economic calculations-physical modules output only quantities (kWh, cubic meters, kg), and a separate economic module applies prices to those quantities.

At the end of each time-step, Layer 3 performs reconciliation checks to ensure all material and energy balances close. Any discrepancy indicates a modeling error rather than a valid simulation outcome.

#### Layer Interactions and Data Flow

The three layers interact through well-defined interfaces with minimal coupling.

Layer 1 to Layer 2: Layer 1 produces indexed libraries that Layer 2 queries but never modifies. The interface is read-only: Layer 2 provides keys (weather scenario ID, crop type, planting date) and receives reference values. Layer 1 has no knowledge of specific scenarios-it simply provides a complete library of physical relationships.

Layer 2 to Layer 3: Layer 2 consumes Layer 1 libraries and produces a scenario package for Layer 3. This package contains everything Layer 3 needs: scaled physical curves, farm definitions, policy configurations, and initial state. Once assembled, Layer 2 role is complete.

Layer 3 execution: Layer 3 executes the scenario package in isolation. It cannot request new pre-computations from Layer 1 or modify the design specification from Layer 2. This constraint ensures simulation results are fully determined by the scenario package, supporting reproducibility and comparison across runs.

For Monte Carlo analysis, Layer 3 executes multiple runs with different stochastic draws (weather scenarios, price paths, failure events) while holding the design specification constant. This reveals how a single infrastructure and policy configuration performs across a range of conditions.

#### What Each Layer Does Not Do

Boundaries are as important as responsibilities. Layer 1 does not make operational decisions, track state over time, or incorporate economics. It computes physical relationships only. Layer 2 does not simulate. It validates, configures, and assembles, but time never advances in Layer 2. Layer 3 does not re-compute physical relationships. If PV output for a given weather day was pre-computed as X kWh/kW, Layer 3 uses that value-it does not run pvlib or crop models during simulation.

This separation keeps the model computationally tractable while supporting the complexity needed for meaningful scenario analysis.

### Domain Overview

The model represents an integrated agricultural community with interdependent physical and economic systems. The physical domain includes water infrastructure (extraction, treatment, irrigation), energy infrastructure (solar, wind, storage, grid connection, backup generation), and agricultural operations (crop cultivation, post-harvest storage and processing). The economic domain covers individual farmer finances, collective pooling and reserves, debt service, and optional insurance mechanisms.

Each system is specified in detail in Section 3: Subsystem Specifications, which defines the parameters, constraints, and behaviors for water, energy, labor, crops, post-harvest operations, and economic arrangements.

### Stochastic Parameters

The Monte Carlo framework varies parameters across runs to test system robustness. Stochastic elements are organized by their causal relationships.

**Primary drivers** are root-level random variables sampled at the start of each run. Weather scenarios (temperature, irradiance, wind speed, precipitation patterns) serve as the primary driver, selected from the pre-computed Layer 1 library.

**Derived variability** flows deterministically from weather. Crop yields, irrigation demand, PV output, and wind output all vary across runs because they depend on weather-but given a weather scenario, their values are fixed by Layer 1 pre-computation.

**Independent factors** vary separately from weather: market prices for crops and processed goods, grid energy prices, municipal water prices, and equipment failure events. These are sampled independently according to configured volatility patterns or failure probabilities.

**Correlations** between factors can be modeled where data supports them (e.g., regional drought coinciding with higher water prices or crop price spikes). The model can implement these correlations or assume independence as a simplifying assumption, depending on available data and scenario goals.

#### Crop and Processed Product Prices

Price dynamics for agricultural commodities represent a critical source of uncertainty and a major driver of farm decision-making. The model treats prices as stochastic inputs calibrated to historical data, capturing both the volatility farmers face and the decision trade-offs between crop selection, sale timing, and processing.

**Raw crop prices** exhibit characteristic patterns that the model should capture: seasonal variation (prices typically lowest at harvest when supply peaks, higher in off-season), year-to-year volatility driven by regional and global supply conditions, and longer-term trends reflecting demand shifts or input cost changes. Historical price series from FAO, USDA, or regional agricultural ministries provide the basis for calibrating mean levels, seasonal patterns, and volatility parameters. For each crop type in the model, price parameters include a baseline annual mean, a seasonal adjustment curve, and a volatility measure (standard deviation or coefficient of variation).

**Processed product prices** (dried goods, canned products, packaged items) follow related but distinct dynamics. Processing creates a price spread-the difference between the raw crop price and the processed product price-that compensates for processing costs, weight loss, labor, and storage. This spread is not constant: it varies with raw crop prices, seasonal demand for processed goods, and market conditions. The model captures this by defining processed product prices as a function of raw prices plus a stochastic spread component, rather than as a fixed multiplier.

**The planting decision** depends heavily on expected price levels and volatility at harvest time. Farmers choosing crops months before harvest must form expectations about future prices. The model supports different expectation-formation rules: naive expectations (last year's price), moving averages, or simple forecasts. Risk-averse farmers may favor crops with lower price volatility even if expected prices are lower, while risk-tolerant farmers may plant high-volatility crops seeking upside. The interaction between crop choice and price uncertainty is a key educational output of the model.

**The sell-or-process decision** hinges on the price spread between raw and processed goods relative to processing costs. When raw prices are high, immediate sale may be optimal; when raw prices are depressed, processing can capture value that would otherwise be lost. However, processing requires time, labor, energy, and storage-all of which have costs and capacity constraints. The model allows farmers to make this decision based on current prices and price forecasts, with different farmers potentially following different rules based on their risk tolerance and cash flow needs.

**Sale timing for storable goods** introduces additional price exposure. Farmers holding processed products can wait for better prices, but face storage costs and spoilage risk. The model tracks inventory positions and allows sale timing rules that respond to price thresholds, storage duration, or cash flow requirements. This creates a trade-off between holding for potential price appreciation and the carrying costs of delayed sale.

**Price correlation structure** matters for community-level risk. If all farmers plant the same crop, they face correlated price risk-a price crash affects everyone simultaneously. Crop diversification across the community can reduce this correlation, but only if different crops have imperfectly correlated prices. The model can test how community-level crop mixing strategies affect collective risk exposure compared to individual optimization.

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

| Profile | Activities | Notes |
| --- | --- | --- |
| Field work | Planting, weeding, harvesting, irrigation management | Seasonal, weather-dependent |
| Transport and logistics | Moving crops from field to storage/processing, deliveries | Linked to harvest timing |
| Food processing and packaging | Drying, canning, packaging operations | Post-harvest, can be scheduled |
| Infrastructure maintenance | PV cleaning, pump maintenance, building upkeep | Year-round, relatively stable |
| Administrative and sales | Financial management, market sales, coordination | Year-round, relatively stable |

**Labor parameters:**

| Parameter | Unit | Notes |
| --- | --- | --- |
| Labor hours per action | hours/event or hours/kg | By activity type |
| Community labor wage | $/hour | Wage paid to community members |
| External labor wage | $/hour | Wage paid to hired external workers |
| External labor ratio | % | Proportion of labor from external sources |

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

| Parameter | Range/Type | Notes |
| --- | --- | --- |
| Farm size | hectares | Land area allocated to each farm |
| Yield factor | 0.8–1.2 (multiplier) | Accounts for soil quality variations; applied to base crop yields |
| Starting capital | $ | Initial cash reserves at simulation start |
| Risk tolerance | policy selection | Determines which economic policy the farmer operates under |

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

#### Insurance options

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

### Operations

#### Post-harvest system

The model tracks post-harvest economics with full parameterization of storage, processing, and sales.

**Storage parameters:**

| Parameter | Unit | Notes |
| --- | --- | --- |
| Storage capacity | kg or m³ | By storage type (ambient, climate-controlled) |
| Storage cost | $/kg/day or $/m³/day | Operating cost including energy for climate control |
| Storage energy demand | kWh/m³/day | For climate-controlled storage |

**Spoilage parameters (by product type):**

| Parameter | Unit | Notes |
| --- | --- | --- |
| Spoilage rate | %/day | Function of storage conditions and product type |
| Shelf life (fresh) | days | Maximum storage before total loss |
| Shelf life (dried) | days | Extended shelf life for processed goods |
| Shelf life (canned) | days | Extended shelf life for preserved goods |

**Processing parameters:**

| Parameter | Unit | Notes |
| --- | --- | --- |
| Processing capacity | kg/day | Maximum throughput per processing type |
| Processing labor | hours/kg | Labor requirement by processing type |
| Processing cost | $/kg | Non-labor operating costs (packaging, energy, materials) |
| Processing energy | kWh/kg | Energy demand for processing operations |
| Value-add multiplier | ratio | Price multiplier for processed vs fresh product (e.g., 1.5× for dried goods) |
| Processing loss | % | Weight loss during processing (e.g., drying reduces mass) |

**Market timing:**

Farmers can choose when to sell based on individual decision rules. This is particularly relevant for non-perishable goods (dried products, canned goods) that can be held for better market conditions.

| Parameter | Unit | Notes |
| --- | --- | --- |
| Farmer sale rule | policy | Individual rule set for when to sell (see Farmer Heterogeneity) |
| Market price forecast | $/kg | Farmer's expectation of future prices (simple or sophisticated) |
| Holding cost threshold | $/kg/day | Maximum acceptable storage cost before forced sale |

#### Policy framework

This model is designed for educational purposes to help farming communities understand the strengths and weaknesses of different system configurations, agreements, and business models.

Policies are rule sets that govern operational decisions. The framework supports testing the following policy categories:

**Water policies:**

- Groundwater vs municipal water ratio (baseline allocation)
- Trigger conditions for switching water sources:
    - Groundwater treatment cost exceeds municipal price by X%
    - Energy availability for treatment falls below threshold
    - Municipal price spike triggers shift to groundwater
- Seasonal allocation strategies (e.g., more groundwater in high-solar months when treatment energy is cheap)

**Energy policies:**

- Load management and load shifting
- Priority ordering: diesel backup vs grid backup vs battery
- Baseline assumes microgrid with grid connection
- Curtailment vs battery storage vs grid export decisions

**Crop policies:**

- Crop type selection and mixing strategies
- Planting date optimization for climate and market variables
- Harvest scheduling to smooth labor requirements
- Irrigation timing flexibility based on energy availability

**Economic policies:**

- Pooling percentages and distribution rules
- Debt structure selection
- Insurance vs self-insurance strategies
- Working capital advance rules

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

- [ ]  Weather outputs pass statistical tests (temperature ranges, solar patterns, seasonality)
- [ ]  PV outputs match pvlib reference cases within 1%
- [ ]  Wind outputs match manufacturer power curves
- [ ]  Crop irrigation totals fall within FAO reference ranges for crop type and climate
- [ ]  All library keys are unique and consistently formatted

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

- [ ]  Water balance closes: extraction + municipal = irrigation + losses (within 0.1%)
- [ ]  Energy balance closes: generation + grid + diesel = demand + battery_delta + curtailment (within 0.1%)
- [ ]  Crop yields match pre-computed expectations (given weather and irrigation)
- [ ]  Labor hours fall within expected ranges for farm size and crop type
- [ ]  No negative values for physical quantities
- [ ]  Simulation completes 365 days without errors

**Phase 3: Physical Systems (3 Farms, Deterministic)**

Extend to multiple farms sharing infrastructure.

*New complexity:*

- 3 farms with different sizes and yield factors
- Shared energy and water infrastructure
- Aggregated vs individual tracking

*Testing criteria:*

- [ ]  Community-level balances still close
- [ ]  Individual farm outputs scale appropriately with farm size and yield factor
- [ ]  Shared infrastructure properly allocates resources across farms
- [ ]  Total labor = sum of individual farm labor

**Phase 4: Policies and Events (3 Farms, Deterministic)**

Add policy-based decision logic and discrete events.

*Modules:*

- Energy policy: priority ordering, load shifting
- Water policy: groundwater vs municipal switching
- Crop policy: irrigation timing flexibility
- Event system: equipment failures, maintenance schedules

*Testing criteria:*

- [ ]  Energy policy correctly prioritizes sources (PV → battery → grid → diesel)
- [ ]  Water policy switches sources at configured thresholds
- [ ]  Irrigation timing shifts respond to energy availability
- [ ]  Equipment failure events trigger appropriate downtime and repair costs
- [ ]  Policies produce different outcomes than fixed baseline

**Phase 5: Post-Harvest System (3 Farms, Deterministic)**

Add storage, processing, and market timing.

*Modules:*

- Storage: inventory tracking, spoilage calculations
- Processing: capacity constraints, value-add, labor
- Market timing: sale decision logic

*Testing criteria:*

- [ ]  Spoilage rates match configured parameters
- [ ]  Processing throughput respects capacity limits
- [ ]  Value-add multipliers correctly applied to processed goods
- [ ]  Inventory balances: harvested = stored + processed + spoiled + sold
- [ ]  Market timing rules trigger sales at configured thresholds

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

- [ ]  Revenue = sum of (quantity sold × price) across all products
- [ ]  Costs match configured opex rates × quantities
- [ ]  Cash flow = revenue - costs - debt service ± pooling transfers
- [ ]  Debt balance decreases correctly with payments
- [ ]  NPV and ROI calculations match manual verification
- [ ]  No farm goes below configured minimum cash reserve (or triggers appropriate response)

**Phase 7: Multi-Year Deterministic (3 Farms, 5 Years)**

Extend simulation length to test multi-year dynamics.

*New complexity:*

- Year-over-year accumulation (reserves, debt paydown)
- Seasonal patterns repeat correctly
- Long-term trends (if any) behave as expected

*Testing criteria:*

- [ ]  Debt fully repaid by expected year (given payment schedule)
- [ ]  Reserve fund grows in good years, depletes in bad years appropriately
- [ ]  No drift in physical balances over multiple years
- [ ]  Annual summaries aggregate correctly from daily data

**Phase 8: Stochastic Single Runs (3 Farms, 20 Years)**

Introduce stochastic elements one at a time.

*Sequence:*

1. Weather variability only (select from weather scenario library)
2. Add price variability
3. Add equipment failures

*Testing criteria:*

- [ ]  Different weather scenarios produce different outcomes (not identical)
- [ ]  Price variability affects cash flow variance as expected
- [ ]  Equipment failures trigger repair events and costs
- [ ]  Outcomes remain within plausible ranges (no extreme outliers from bugs)

**Phase 9: Monte Carlo (3 Farms, 20 Years, N Runs)**

Full Monte Carlo simulation capability.

*Testing criteria:*

- [ ]  Distribution of outcomes is stable (more runs → converging statistics)
- [ ]  Success rate (% completing without default) is plausible
- [ ]  Worst-case and best-case outcomes are within reasonable bounds
- [ ]  Results are reproducible with same random seed

**Phase 10: Scale to N Farms with Profiles**

Expand from 3 farms to full community (15–30 farms) using farm profiles.

*New complexity:*

- 2–5 farm profile types
- Farms assigned to profiles (e.g., 10 conservative, 10 moderate, 5 risk-tolerant)
- Distributional metrics across heterogeneous farms

*Testing criteria:*

- [ ]  Profile assignments correctly determine farm parameters
- [ ]  Community aggregates scale appropriately with number of farms
- [ ]  Distributional metrics (Gini, worst-case farmer) compute correctly
- [ ]  Performance remains acceptable (runtime scales linearly or better with farm count)

**Phase 11: Scenario Comparison and Reporting**

Build comparison and visualization tools.

*Modules:*

- Scenario runner: batch execution of multiple configurations
- Comparison dashboard: side-by-side metrics
- Visualization suite: time-series, distributions, Sankey diagrams

*Testing criteria:*

- [ ]  Different scenarios produce meaningfully different outcomes
- [ ]  Visualizations correctly represent underlying data
- [ ]  Reports export cleanly (PDF, CSV, etc.)

**Data contract summary:**

| Interface | From | To | Key data |
| --- | --- | --- | --- |
| Library lookup | Layer 1 | Layer 2 | Pre-computed reference values by scenario/config keys |
| Design specification | Layer 2 | Layer 3 | Infrastructure sizes, farm profiles, policy selections |
| Daily state | Layer 3 modules | Layer 3 modules | Date, weather, energy available, water demand, crop status, labor |
| Physical → Economic | Physical modules | Economic module | Quantities only (kWh, m³, kg, hours) — no prices |
| Farm → Community | Individual farms | Aggregator | Farm-level metrics for community rollup |
| Simulation → Output | Layer 3 | Reporting | Daily logs, annual summaries, Monte Carlo distributions |

## 6. References

[[1]](1): U.S. Department of Agriculture, Farm Service Agency, "Farm Loan Programs," accessed January 2026, https://www.fsa.usda.gov/resources/farm-loan-programs.

[[2]](2): U.S. Department of Agriculture, Farm Service Agency, "Beginning Farmers and Ranchers Loans," accessed January 2026, https://www.fsa.usda.gov/resources/beginning-farmers-and-ranchers-loans.

[[3]](3): Farm Credit Administration, "Fiscal Year 2025 Proposed Budget and Performance Plan," accessed January 2026, https://www.fca.gov/template-fca/about/BudgetFY2025.pdf.