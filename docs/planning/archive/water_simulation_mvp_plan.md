# Water Policy Simulation MVP Implementation Plan

**STATUS: ✅ COMPLETE (February 2026)**

Water simulation MVP successfully implemented. All 6 phases complete. See `src/simulation/` for implementation.

---

## Overview

Implement minimal viable simulation to test water policies over a 10-year period (2015-2024) with 4 farms using different water allocation strategies.

**Target Output Metrics (Yearly):**
1. Total water use (m3)
2. Water use per yield (m3/kg) - by crop and total
3. Water cost per unit (USD/m3)
4. Self-sufficiency percentage (groundwater / total water)

**Control Parameters:**
- Crop planting policy: planting dates, percent of fields planted per crop
- Water infrastructure: well capacity, treatment capacity, storage capacity, irrigation system type
- Water policy: groundwater vs. municipal allocation strategy
- Water pricing regime: subsidized vs. unsubsidized municipal water

---

## Critical Water Source Distinction

The simulation models two fundamentally different water sources:

### 1. Community Groundwater (BWRO)
- **Source:** Brackish aquifer wells (community-owned)
- **Treatment:** Brackish Water Reverse Osmosis (BWRO) on-farm
- **Salinity:** 2,000-10,000 TDS (scenario: 6,500 TDS moderate)
- **Energy:** ~3.5-4.5 kWh/m3 for treatment
- **Cost components:**
  - Well pumping energy (depth-dependent)
  - BWRO treatment energy
  - Equipment maintenance (membranes, pumps)
- **Controlled by:** Community infrastructure capacity

### 2. Municipal Seawater Desalination (SWRO)
- **Source:** Red Sea via municipal desalination plant
- **Treatment:** Seawater Reverse Osmosis (SWRO) at municipal facility
- **Delivery:** Freshwater delivered via pipeline (no on-farm treatment)
- **Salinity:** Input ~35,000 TDS, output freshwater
- **Energy:** ~4-6 kWh/m3 (higher than BWRO due to salinity)
- **Cost:** Single price per m3 (includes all treatment/delivery)
- **Pricing options:**
  - **Subsidized:** Government-supported rates ($0.07-0.15/m3)
  - **Unsubsidized:** Full cost recovery ($0.50-1.00/m3)

### Cost Comparison Logic

Water policies compare:
```
GW cost/m3 = (pumping_kwh + treatment_kwh) × electricity_price + maintenance_per_m3
Municipal cost/m3 = price from pricing regime (subsidized or unsubsidized)
```

The `cheapest_source` policy dynamically selects based on this daily comparison.

---

## Implementation Phases

### Phase 1: Schema Updates (Scenario Configuration)

**Goal:** Enable per-farm crop configuration with planting schedules and water pricing options.

**Status:** YAML schema updated in `water_policy_only.yaml`

**Files to modify:**
- ✅ `settings/scenarios/water_policy_only.yaml` - Per-farm crops + water pricing config
- `settings/scripts/loader.py` - Update dataclasses to parse new schema

**New scenario structure:**
```yaml
# Water pricing configuration
water_pricing:
  municipal_source: seawater_desalination  # seawater_desalination or piped_nile
  pricing_regime: unsubsidized  # subsidized or unsubsidized
  subsidized:
    use_tier: 3  # Tier 1/2/3 from research data
  unsubsidized:
    base_price_usd_m3: 0.75  # SWRO full cost
    annual_escalation_pct: 3.0

# Per-farm crop configuration
farms:
  - id: farm_1
    name: "Conservative Farm"
    area_ha: 125
    crops:
      - name: tomato
        area_fraction: 0.30
        planting_date: "02-15"  # MM-DD format (year determined by simulation)
        percent_planted: 0.90
    policies:
      water: always_groundwater
```

**Planting date format:** `MM-DD` (e.g., "02-15" for Feb 15). Simulation constructs full date by combining with simulation year. Available windows: Feb 15, May 1, Aug 15, Nov 1.

**Deliverable:**
- ✅ YAML schema with per-farm crop allocation, planting dates, percent planted
- ✅ Water pricing config with subsidized/unsubsidized options
- Loader updates to parse new schema

---

### Phase 2: Data Loader Module

**Goal:** Load precomputed irrigation demand and yield data for simulation lookup.

**New file:** `src/data_loader.py`

**Functions:**
```python
def load_irrigation_demand(crop_name: str, data_registry: dict) -> pd.DataFrame
    """Load irrigation CSV for a crop, return DataFrame indexed by (planting_date, calendar_date)."""

def get_daily_irrigation(df: pd.DataFrame, planting_date: str, calendar_date: str) -> float
    """Look up irrigation_m3_per_ha_per_day for specific date combination."""

def load_yield_data(crop_name: str, data_registry: dict) -> pd.DataFrame
    """Load yield CSV for a crop."""

def get_season_yield(df: pd.DataFrame, planting_date: str) -> dict
    """Return {yield_kg_per_ha, harvest_date, weather_stress_factor} for planting date."""

def load_municipal_water_prices(data_registry: dict) -> pd.DataFrame
    """Load annual water prices, return DataFrame indexed by year."""
```

**Data flow:**
- Input: Precomputed CSVs from `/data/precomputed/irrigation_demand/` and `/data/precomputed/crop_yields/`
- Output: Lookup-ready DataFrames for simulation queries

**Deliverable:** Working data loader with tests.

---

### Phase 3: State Management

**Goal:** Track simulation state across daily time steps.

**New file:** `src/state.py`

**Dataclasses:**
```python
@dataclass
class CropState:
    crop_name: str
    planting_date: str
    area_ha: float
    cumulative_water_m3: float = 0.0
    harvest_yield_kg: float = 0.0
    is_harvested: bool = False

@dataclass
class FarmState:
    farm_id: str
    crops: list[CropState]
    cumulative_groundwater_m3: float = 0.0
    cumulative_municipal_m3: float = 0.0
    cumulative_water_cost_usd: float = 0.0

@dataclass
class SimulationState:
    current_date: date
    farms: list[FarmState]
    year_metrics: dict  # Accumulated yearly totals for reporting
```

**State update pattern:**
- Immutable updates (create new state each day)
- Year boundaries trigger metrics snapshot and reset

**Deliverable:** State dataclasses with initialization from scenario.

---

### Phase 4: Daily Simulation Loop

**Goal:** Execute daily water allocation for each farm.

**New file:** `src/simulation.py`

**Main loop structure:**
```python
def run_simulation(scenario: Scenario, data_registry: dict) -> SimulationResults:
    """
    Run daily simulation from start_date to end_date.

    For each day:
      1. Calculate irrigation demand per farm (sum of active crops)
      2. Execute water policy for each farm
      3. Update farm state with water volumes and costs
      4. Check for harvest events (update yields)
      5. At year boundary: snapshot metrics
    """
```

**Daily water demand calculation:**
```python
def calculate_farm_demand(farm: FarmState, date: date, irrigation_data: dict) -> float:
    """Sum irrigation_m3_per_ha * area_ha for all active (unharvested) crops."""
```

**Policy execution:**
```python
def execute_water_policy(farm: Farm, demand_m3: float, context: WaterPolicyContext) -> WaterAllocation:
    """Call farm's water policy with context, return allocation."""
```

**Deliverable:** Working simulation loop that produces daily state updates.

---

### Phase 5: Metrics Calculator

**Goal:** Compute yearly output metrics from simulation results.

**New file:** `src/metrics.py`

**Functions:**
```python
def calculate_yearly_metrics(year_data: dict) -> YearlyMetrics:
    """
    Compute metrics from accumulated yearly data.

    Returns:
        total_water_m3: groundwater + municipal
        water_per_yield_by_crop: {crop: m3/kg}
        water_per_yield_total: total_water / total_yield
        water_cost_per_m3: total_cost / total_water
        self_sufficiency_pct: groundwater / total_water * 100
    """

@dataclass
class YearlyMetrics:
    year: int
    farm_id: str
    total_water_m3: float
    groundwater_m3: float
    municipal_m3: float
    total_yield_kg: float
    total_water_cost_usd: float
    water_per_yield_m3_per_kg: float
    water_cost_per_m3_usd: float
    self_sufficiency_pct: float
    crop_metrics: dict  # Per-crop water/yield ratios
```

**Deliverable:** Metrics dataclass and calculator.

---

### Phase 6: Results Output

**Goal:** Write simulation results to CSV and generate graphs.

**New file:** `src/results.py`

**Output files:**
```
/results/water_policy_only_YYYYMMDD_HHMMSS/
  yearly_summary.csv              # Yearly metrics per farm (40 rows: 10 years × 4 farms)
  yearly_community_summary.csv    # Yearly community-wide aggregates (10 rows)
  daily_farm_results.csv          # Daily per-farm water flows (stored for analysis)
  simulation_config.json          # Snapshot of scenario parameters

  plots/
    community_water_use.png       # PRIMARY: Community total water use over time
    community_crop_yields.png     # PRIMARY: Community total yields by crop
    community_water_cost.png      # PRIMARY: Community water cost over time
    community_self_sufficiency.png # PRIMARY: GW vs municipal ratio over time

    farm_water_use.png            # SECONDARY: Per-farm water use comparison
    farm_yields.png               # SECONDARY: Per-farm yield comparison
    farm_costs.png                # SECONDARY: Per-farm cost comparison
```

**Table format (yearly_summary.csv):**
```
year,farm_id,farm_name,water_policy,total_water_m3,groundwater_m3,municipal_m3,total_yield_kg,water_cost_usd,water_per_yield_m3_kg,cost_per_m3_usd,self_sufficiency_pct
2015,farm_1,Conservative Farm,always_groundwater,125000,120000,5000,850000,15000,0.147,0.12,96.0
2015,farm_2,Municipal Water Farm,always_municipal,125000,0,125000,850000,25000,0.147,0.20,0.0
...
```

**Table format (yearly_community_summary.csv):**
```
year,total_water_m3,total_groundwater_m3,total_municipal_m3,total_yield_kg,total_water_cost_usd,avg_water_per_yield_m3_kg,avg_cost_per_m3_usd,community_self_sufficiency_pct
2015,500000,350000,150000,3400000,75000,0.147,0.15,70.0
...
```

**Primary plots (community-wide):**
- Daily/monthly water use stacked by source (groundwater vs municipal)
- Cumulative yields by crop over simulation period
- Water cost trends with pricing regime annotation
- Self-sufficiency percentage over time

**Secondary plots (per-farm comparison):**
- Side-by-side farm comparison for each metric
- Useful for evaluating policy effectiveness

**Deliverable:** CSV writers and matplotlib graph generators for both community and farm-level views.

---

### Phase 7 (Deferred): Water Flow Engine

**Goal:** Track physical water flow through infrastructure.

**Note:** Defer to post-MVP. For MVP, treat water infrastructure as instantaneous:
- Wells have unlimited capacity (within scenario limits)
- Treatment is instantaneous
- Storage is not modeled (no evaporation, no carryover)

**Future implementation considerations:**
- Storage dynamics: fill/draw patterns, evaporation losses
- Capacity constraints: max daily well extraction, treatment throughput
- Infrastructure failures: pump maintenance, membrane replacement

**This phase is intentionally last** because:
1. Policy comparison is valid without storage dynamics
2. Adds significant complexity (storage state, constraint handling)
3. Can be added incrementally after core loop works

---

## File Structure After Implementation

```
/src/
  __init__.py
  data_loader.py      # Phase 2
  state.py            # Phase 3
  simulation.py       # Phase 4
  metrics.py          # Phase 5
  results.py          # Phase 6
  water_flow.py       # Phase 7 (deferred)

/settings/
  scenarios/
    water_policy_only.yaml  # Updated Phase 1
  scripts/
    loader.py              # Updated Phase 1
```

---

## Dependencies

**Required libraries (already in project):**
- pandas (data loading, manipulation)
- numpy (calculations)
- pyyaml (scenario loading)

**New dependencies:**
- matplotlib (daily graphs)
- dataclasses (Python 3.7+ stdlib)

---

## Testing Strategy

**Unit tests:**
- `test_data_loader.py` - Verify irrigation/yield lookups return correct values
- `test_state.py` - Verify state initialization and updates
- `test_metrics.py` - Verify metric calculations with known inputs

**Integration test:**
- Run 1-year simulation with known inputs, verify outputs match manual calculation

---

## Implementation Order

| Order | Phase | Estimated Complexity | Dependencies |
|-------|-------|---------------------|--------------|
| 1 | Phase 1: Schema Updates | Low | None |
| 2 | Phase 2: Data Loader | Low | Phase 1 |
| 3 | Phase 3: State Management | Low | Phase 1 |
| 4 | Phase 4: Simulation Loop | Medium | Phases 2, 3 |
| 5 | Phase 5: Metrics Calculator | Low | Phase 4 |
| 6 | Phase 6: Results Output | Medium | Phase 5 |
| 7 | Phase 7: Water Flow Engine | High | Deferred |

---

## Success Criteria

MVP is complete when:
1. `python src/simulation.py settings/scenarios/water_policy_only.yaml` runs without errors
2. Produces `yearly_summary.csv` with 10 years × 4 farms = 40 rows
3. Each row contains all 4 target metrics
4. Produces `daily_system_states.png` showing daily water allocation patterns
5. Results show meaningful differences between water policies

---

## Open Questions

✅ All questions resolved. See [water_simulation_followup_questions.md](water_simulation_followup_questions.md) for decision summary.

**Key decisions:**
- Yield timing: Single harvest at season end, attributed to harvest year
- Energy: Unlimited grid availability for MVP
- Infrastructure sharing: Proportional to farm area
- Crop policies: Skipped (irrigation_multiplier = 1.0)
- Results: Community-wide primary plots, per-farm secondary plots
