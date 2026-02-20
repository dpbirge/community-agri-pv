# Future Improvements

Features described in `overview.md` that are deferred from MVP. Each section
describes what the feature does, why it is deferred, and what architectural
changes would be needed to implement it.

## Collective Pooling Mechanism

### Description

A configurable percentage of individual farm profits flows to a collective reserve
fund each year. This reserve provides a buffer during down years caused by weather,
market, or equipment shocks. Distribution policies determine how funds are allocated
back to farmers during hardship. The pooling mechanism is a core element of the
community co-ownership model described in `overview.md` Section 3 (Economic model).

The existing `cost_allocation_method` parameter in `structure.md` (equal,
area_proportional, usage_proportional) handles shared infrastructure OPEX
allocation, but does not implement the profit-pooling and distribution mechanism.

### Why Deferred

Three design questions from `overview.md` remain open:

1. **Advance determination:** How are operating advances determined? Fixed amount
   per farm, based on planted area, or based on historical needs?
2. **Unrecovered advances:** What happens if a farmer's harvest revenue doesn't
   cover their advances? Is this absorbed by the collective or carried as debt?
3. **Cost allocation beyond OPEX:** How are collective costs allocated beyond the
   existing `cost_allocation_method` parameter (which covers only shared
   infrastructure OPEX)?

### Implementation Path

1. **`structure.md`**: Add a `collective_pooling` section to the scenario YAML
   schema with parameters: `pooling_pct` (fraction of net income contributed
   annually), `distribution_policy` (hardship criteria and payout rules), and
   `advance_method` (fixed, area_based, or historical).

2. **`policies.md`**: Either extend the economic policy domain with pooling-aware
   decision logic, or create a new community-level policy domain with its own
   context/decision dataclasses. The pooling mechanism operates at the community
   level (not per-farm), so it may be better modeled as a community-level
   mechanism rather than a farm-level policy.

3. **`calculations.md`**: Add formulas for annual pooling contributions
   (`farm_contribution = net_income * pooling_pct`), reserve fund balance
   tracking, and distribution calculations.

4. **`simulation_flow.md`**: Add a yearly boundary operation (Section 7.2) for
   pooling contributions after yearly metrics are computed. Add a monthly or
   event-triggered step for hardship distributions. The advance mechanism would
   need a monthly step in Section 7.1 for disbursement and a revenue-time step
   for recoupment.

5. **State management**: Add `PoolingState` dataclass tracking: `reserve_balance_usd`,
   `farm_contributions` (per farm, per year), `farm_distributions` (per farm, per
   year), and `outstanding_advances` (per farm).

## Load Shifting

### Description

Load shifting (also called demand-side management) involves scheduling flexible
energy loads to times when renewable generation is abundant or grid prices are low.
For example, running desalination treatment or food processing equipment during
peak solar hours rather than evening hours, or charging batteries during off-peak
grid pricing windows.

### Why Deferred

The simulation operates at a daily time step, which aggregates all demand and
generation within a single day. Load shifting requires sub-daily (hourly or
15-minute) time resolution to be meaningful -- shifting demand from one hour to
another within the same day is invisible at daily resolution. This is a
fundamental architectural constraint, not merely an unimplemented feature.

### Implementation Path

Adding load shifting would require substantial architectural changes:

1. **`overview.md` Section 2**: Change the time-step specification from daily to
   hourly (or add an optional sub-daily mode). This affects the entire simulation
   loop and all data contracts.

2. **Layer 1 pre-computation**: All precomputed data (weather, PV output, wind
   output, irrigation demand) would need hourly resolution instead of daily
   totals. The data files in `data/precomputed/` would grow by a factor of 24.

3. **`simulation_flow.md`**: The daily loop (Section 2) would need an inner hourly
   loop, or the entire loop would shift to hourly resolution. Energy dispatch
   (Section 5) would execute hourly instead of daily.

4. **`policies.md`**: Add a new load-shifting energy policy (or extend existing
   energy policies) with parameters for: shiftable vs. non-shiftable loads,
   preferred dispatch windows, and price-responsive scheduling thresholds.

5. **`structure.md`**: Add time-of-use pricing configuration (hourly grid tariff
   schedules) and shiftable load classification for each demand component.

6. **Performance**: Hourly resolution increases computation by 24x per simulation
   day. Monte Carlo runs would be significantly slower.

An intermediate approach could model load shifting as a daily cost adjustment
factor (e.g., "X% of flexible load is shifted to solar hours, reducing grid
import cost by Y%") without actually simulating hourly dispatch. This would
capture the economic benefit approximately while preserving the daily time step.

## Crop Type Selection and Planting Optimization

### Description

Dynamic crop type selection and planting date optimization would allow the
simulation to choose which crops to plant and when, based on expected prices,
water availability, labor constraints, and climate forecasts. This contrasts with
the current approach where crop selection, area fractions, and planting dates are
static configuration parameters set in the scenario YAML.

### Why Deferred

Crop selection and planting dates are Layer 2 design decisions, not Layer 3
runtime policies. This is consistent with the architectural principle that Layer 3
cannot modify Layer 2 during execution (see `overview.md` Section 2). Making crop
selection a runtime policy would blur the boundary between design and simulation.

Additionally, meaningful crop optimization requires price forecasting models,
multi-objective optimization (balancing revenue, risk, water use, labor), and
possibly multi-year planning horizons -- all of which add substantial complexity.

### Implementation Path

If dynamic crop selection were desired, it could be implemented as a yearly
boundary operation (a "planting decision" step) rather than a daily policy:

1. **`simulation_flow.md`**: Add a new yearly boundary operation (Section 7.2)
   that runs before crop reinitialization. This step would evaluate candidate
   crop portfolios and select the best one based on configurable criteria.

2. **`policies.md`**: Add a new `CropSelectionPolicy` domain with:
   - Context: available crops, expected prices (from historical data or simple
     forecasts), water budget constraints, labor availability, current farm
     financial position.
   - Decision: crop names, area fractions, and planting dates for the coming year.
   - Policies could range from simple (rotate through a fixed set) to complex
     (optimize expected revenue subject to constraints).

3. **`structure.md`**: Add a `crop_selection_policy` field to farm configuration,
   and a `candidate_crops` list defining which crops are available for selection
   (with their parameters).

4. **Layer 2 / Layer 3 boundary**: The crop selection step would effectively be a
   "Layer 2.5" operation -- it modifies the farm's crop configuration between
   simulation years. This requires careful handling to maintain the layer
   separation principle. One approach: the crop selection policy outputs a new
   crop configuration that is validated against Layer 1 precomputed data (all
   candidate crops must have precomputed irrigation and yield data).

To test different crop strategies without this feature, create separate scenario
YAML files with different crop configurations and compare their outcomes.

## Working Capital Advances

### Description

Working capital advances are operating funds that flow to farmers throughout the
year to cover expenses (seeds, fertilizer, labor, maintenance) before harvest
revenue is received. The advances are recouped when goods are sold to market. This
mechanism is critical for farming communities where the gap between planting costs
and harvest revenue can span months.

The current model uses `starting_capital_usd` and daily cash tracking as a
simplified working capital mechanism -- each farm begins with a lump sum and cash
is updated daily as costs are incurred and revenue is received. This does not
model the advance/repayment cycle or the community's role in funding operations.

### Why Deferred

Three design questions from `overview.md` remain open (shared with the collective
pooling mechanism):

1. **Advance determination:** Fixed amount per farm, area-based, or based on
   historical operating costs?
2. **Unrecovered advances:** Absorbed by the collective fund, carried as
   individual farm debt, or written off after a period?
3. **Interaction with pooling:** Are advances drawn from the collective pool, from
   a separate working capital fund, or from external credit?

### Implementation Path

1. **`structure.md`**: Add working capital parameters to the scenario YAML:
   `advance_method` (fixed, area_based, historical), `advance_frequency`
   (monthly, quarterly), `max_advance_usd` (cap per farm per period), and
   `repayment_method` (automatic from revenue, scheduled, or manual).

2. **`policies.md`**: Extend the economic policy domain with advance-related
   decision logic. The economic policy context would gain new fields:
   `outstanding_advance_usd`, `advance_available_usd`. The decision output would
   include `request_advance` (bool) and `advance_amount_usd`.

3. **`calculations.md`**: Add formulas for advance sizing (e.g.,
   `monthly_advance = annual_opex_estimate / 12 * advance_fraction`), repayment
   deductions (`repayment = min(revenue * repayment_pct, outstanding_advance)`),
   and interest on outstanding advances if applicable.

4. **`simulation_flow.md`**: Add a monthly boundary step (Section 7.1) for advance
   disbursement. Modify Step 7 (Daily Accounting) to track advance balances and
   apply automatic repayment from revenue. Add a yearly boundary operation for
   advance reconciliation and write-off of unrecovered amounts.

5. **State management**: Extend `EconomicState` with: `outstanding_advance_usd`
   (per farm), `total_advances_received` (per farm, per year),
   `total_repayments` (per farm, per year), and `community_working_capital_fund`
   (if separate from the pooling reserve).

A minimal first implementation could add a single `monthly_advance_usd` parameter
to the economic policy context. Each farm receives a fixed monthly advance
deducted from the community fund. Revenue repayments are automatic at sale time.
This avoids the complex design questions while providing basic cash flow modeling.

## Insurance Policies

### Description

Crop insurance and equipment insurance as risk management alternatives to collective
pooling. Insurance provides external risk transfer rather than internal community
risk-sharing. Crop insurance would cover yield shortfalls from weather, pests, or
water stress. Equipment insurance would cover unexpected repair or replacement costs
for infrastructure components (wells, treatment units, PV, batteries, generators).

### Why Deferred

Six design questions remain unresolved, as noted in `policies.md` (Deferred Policy
Domains, Insurance policies):

1. **Payout triggers:** What event or threshold triggers insurance payouts?
2. **Deductibles:** What loss level must farms absorb before coverage begins?
3. **Participation:** Mandatory for all farms, or optional per-farm?
4. **Provider:** Government-subsidized programs vs. private insurance products?
5. **Interaction with pooling:** How does insurance interact with the collective
   pooling mechanism (duplicate coverage, complementary, or substitute)?
6. **Claims timing:** When are claims paid relative to the loss event?

No YAML schema, context/decision dataclass, or simulation loop integration exists
for insurance.

### Implementation Path

1. **`policies.md`**: Add a new insurance policy domain with its own context (claim
   triggers, coverage levels, deductible amounts) and decision (claim filed, payout
   amount) dataclasses.

2. **`structure.md`**: Add `insurance` section to scenario YAML with parameters:
   `crop_insurance_enabled` (bool), `equipment_insurance_enabled` (bool),
   `premium_usd_per_ha` or `premium_pct_of_revenue`, `deductible_pct`,
   `coverage_pct`, and `provider_type` (government, private).

3. **`simulation_flow.md`**: Add insurance premium deduction as a monthly cost in
   Step 7 (Daily Accounting). Add claim evaluation at harvest time (crop insurance)
   or at equipment failure events (equipment insurance).

4. **`calculations_economic.md`**: Add insurance premium and payout calculations.

## Community-Override Policy Scope

### Description

A community-level policy override mechanism that applies a single policy to all
farms in a given domain, overriding individual farm policy selections. When set,
all farms adopt the community policy. This simplifies configuration for shared
infrastructure decisions that require uniform behavior (e.g., all farms must use
the same water allocation strategy when sharing a single well system).

The YAML schema is fully designed in `structure.md` Section 3 (Policy scope and
hierarchy) under `community_policies`, with `null` meaning no override and a
non-null value forcing all farms to use that policy.

### Why Deferred

Per-farm policies are sufficient for current scenarios. The community-override
mechanism adds loader complexity (resolving override vs. per-farm settings) without
providing new analytical capability in MVP. The schema is documented and ready for
implementation when multi-farm scenarios require uniform policy enforcement.

### Implementation Path

1. **`src/settings/loader.py`**: When `community_policies.<domain>` is non-null,
   ignore `farms[i].policies.<domain>` for all farms and instantiate the community
   policy once, sharing the instance across all farms. Parameters are still read
   from `community_policy_parameters.<policy_name>`.

2. **`src/settings/validation.py`**: Validate that community-override policy names
   are valid for their domain.

3. **No simulation loop changes required**: The override is resolved at load time.
   The simulation loop always calls `farm.policy_instances[domain]` regardless of
   whether it was set by farm-level or community-level configuration.

## Harvest Scheduling Optimization

### Description

Dynamic harvest timing based on market conditions, storage capacity, labor
availability, and crop maturity windows. Currently, harvest is deterministic --
it occurs exactly `season_length_days` after planting with no early harvest or
delayed harvest mechanism (`simulation_flow.md` Section 4a.5).

An optimized harvest scheduler could delay harvest within a crop-specific
flexibility window to target higher market prices, coordinate labor across
multiple simultaneous harvests, or avoid harvesting when storage is full.

### Why Deferred

The current deterministic harvest model is adequate for MVP. Harvest flexibility
introduces complexity in crop state management (partial maturity tracking,
quality degradation during delay) and requires market price forecasting to make
meaningful timing decisions. The crop lifecycle state machine in
`simulation_flow.md` Section 4a would need a new HARVEST_WINDOW state between
LATE_SEASON and HARVEST_READY.

### Implementation Path

1. **`simulation_flow.md`**: Add a HARVEST_WINDOW state to the crop lifecycle
   (Section 4a.1) with a configurable `harvest_flexibility_days` parameter. During
   this window, harvest can be triggered by market conditions or forced at the end
   of the window.

2. **`policies.md`**: Extend the crop policy domain with a `decide_harvest(ctx)`
   method that evaluates whether to harvest today or wait, using market price
   context and storage availability.

3. **`calculations_crop.md`**: Add quality/yield degradation formulas for delayed
   harvest beyond optimal maturity.

## PV Microclimate Yield Protection

### Description

Modeling the fraction of crop yield protected from extreme heat by agri-PV shading.
In hot arid climates, PV panels reduce canopy temperature by 1.5-4.5 degrees C and
ET demand by 5-30%, which can produce net positive yield effects when heat stress
reduction outweighs light reduction. The calculation framework is fully specified
in `calculations_crop.md` Section 8 with formulas for shaded vs. unshaded yield
comparison.

### Why Deferred

Marked as TBD in `calculations_crop.md` Section 8. Requires crop-specific heat
stress thresholds and agri-PV microclimate data that do not yet exist in the data
infrastructure. The target data file `data/parameters/crops/microclimate_yield_effects-research.csv`
has not been created. Research plan for microclimate yield effects is pending.

### Implementation Path

1. **Data creation**: Create `data/parameters/crops/microclimate_yield_effects-research.csv`
   with per-crop, per-PV-density parameters: temperature reduction (degrees C), ET reduction
   (%), PAR reduction (%), net yield effect (%), and heat stress threshold (degrees C).
   Sources: Barron-Gafford et al. (2019), Marrou et al. (2013), Weselek et al. (2019).

2. **`simulation_flow.md`**: Apply `Yield_modifier` in Step 4 harvest yield
   calculation (Section 4.2) based on daily temperature and PV configuration.

3. **`calculations_crop.md`**: The formulas in Section 8 are ready for implementation
   once the data file is populated.

4. **Configuration**: Uses existing `energy_system.pv.density`, `energy_system.pv.height_m`,
   and `energy_system.pv.percent_over_crops` parameters from `structure.md`.

## Equipment Failure Events

### Description

Stochastic equipment failure events that reduce capacity or take components offline
for repair periods. Equipment failure data already exists in
`data/parameters/equipment/equipment_failure_rates-toy.csv` with MTBF (mean time
between failures), repair cost, and downtime parameters for all infrastructure
components. The Monte Carlo framework (`src/simulation/monte_carlo.py`) notes
equipment failure events as "not yet implemented" among its stochastic elements.

### Why Deferred

The simulation does not currently model discrete failure events. Equipment
degradation (PV degradation, battery capacity fade) is handled via smooth annual
factors in `simulation_flow.md` Section 7.2. Discrete stochastic failures add
complexity to the daily loop and require decisions about failure detection, repair
logistics, and backup capacity activation. The data infrastructure exists but the
simulation loop integration does not.

### Implementation Path

1. **`simulation_flow.md`**: Add a daily failure check step (before Step 1) that
   samples from an exponential failure distribution using each component's MTBF.
   When a failure occurs, reduce the component's effective capacity to zero for
   `downtime_days` and record the repair cost.

2. **State management**: Add `EquipmentState` tracking per-component status
   (operational, failed, under_repair), cumulative operating hours, and time
   since last failure.

3. **`calculations_economic.md`**: Add unplanned repair cost to daily accounting
   (Step 7). Repair costs come from `equipment_failure_rates-toy.csv`.

4. **Monte Carlo integration**: Enable equipment failure sampling in
   `monte_carlo.py` as an optional stochastic element alongside price and yield
   variation.

## Aquifer Drawdown Feedback

### Description

Dynamic pumping energy adjustment as the water table drops over years of
extraction. As cumulative groundwater extraction increases, the effective pumping
head increases, requiring more energy per cubic meter. This creates a positive
feedback loop: extraction leads to a deeper water table, which leads to higher energy cost
per cubic meter, which leads to higher operating expenses.

The linearized drawdown model is fully specified in `calculations_water.md`
Section 11, and the yearly boundary operation for updating effective pumping head
is specified in `simulation_flow.md` Section 7.2 (Aquifer state update). The
`calculations.md` overview notes this feature as "pending code implementation."

### Why Deferred

The formulas and simulation loop integration points are fully specified. The
feature is pending code implementation only. It requires connecting the yearly
aquifer state update (which recomputes `effective_head_m` and `pumping_kwh_per_m3`)
to the water policy context so that pumping energy costs increase over time.

### Implementation Path

1. **`src/simulation/simulation.py`**: At yearly boundaries, compute
   `fraction_depleted = cumulative_extraction / aquifer_exploitable_volume_m3`,
   then `drawdown_m = max_drawdown_m * fraction_depleted`, then
   `effective_head_m = well_depth_m + drawdown_m`. Recompute `pumping_kwh_per_m3`
   using the updated head.

2. **`src/simulation/state.py`**: Ensure `AquiferState` tracks
   `cumulative_extraction_m3`, `remaining_volume_m3`, `effective_head_m`, and
   `current_pumping_kwh_per_m3`.

3. **Water policy context**: Pass the updated `pumping_kwh_per_m3` to all water
   policies each day so that groundwater cost comparisons reflect the increasing
   pumping depth.

4. **Configuration**: Uses existing `aquifer_exploitable_volume_m3`,
   `aquifer_recharge_rate_m3_yr`, and `max_drawdown_m` parameters from
   `structure.md` (water system, groundwater wells section).
