# Water Simulation MVP Implementation Prompt

Use this prompt to continue implementation in a new Claude Code session.

---

## Prompt

Implement the Water Policy Simulation MVP for the Community Agri-PV project.

**Context:**
- Planning is complete. See `docs/planning/water_simulation_mvp_plan.md` for full implementation plan.
- All design questions resolved. See `docs/planning/water_simulation_followup_questions.md` for decisions.
- Scenario YAML updated with new schema. See `settings/scenarios/water_policy_only.yaml`.

**Goal:** Build a 10-year daily simulation (2015-2024) that tests 4 water allocation policies across 4 farms and outputs yearly metrics.

**Target output metrics:**
1. Total water use (m3)
2. Water use per yield (m3/kg) by crop and total
3. Water cost per unit (USD/m3)
4. Self-sufficiency percentage (groundwater / total water)

**Implementation phases (in order):**

1. **Phase 1: Update loader.py** - Add dataclasses for new YAML schema (water_pricing, per-farm crops with planting_date and percent_planted)

2. **Phase 2: Create src/data_loader.py** - Load precomputed irrigation demand and yield CSVs, provide lookup functions by (crop, planting_date, calendar_date)

3. **Phase 3: Create src/state.py** - Dataclasses for CropState, FarmState, SimulationState to track daily simulation state

4. **Phase 4: Create src/simulation.py** - Daily loop: calculate demand → execute water policy → update state → check harvests → snapshot yearly metrics

5. **Phase 5: Create src/metrics.py** - Calculate yearly metrics from accumulated data

6. **Phase 6: Create src/results.py** - Write CSVs (yearly_summary, yearly_community_summary, daily_farm_results) and generate plots (community-wide primary, per-farm secondary)

**Key design decisions:**
- Two water sources: Community groundwater (BWRO, on-farm treatment) vs Municipal seawater (SWRO, delivered freshwater)
- Pricing: Subsidized (tiered rates from research data) or Unsubsidized ($0.75/m3 + 3% annual escalation)
- Energy: Unlimited grid availability for MVP
- Infrastructure sharing: Proportional to farm area
- Yields: Single harvest at season end, attributed to harvest year
- Crop policies: Skipped for MVP (irrigation_multiplier = 1.0)

**Existing resources:**
- 4 water policies implemented in `settings/policies/water_policies.py`
- Precomputed irrigation data in `data/precomputed/irrigation_demand/`
- Precomputed yield data in `data/precomputed/crop_yields/`
- Electricity prices in `data/prices/electricity/historical_grid_electricity_prices-research.csv`
- Municipal water prices in `data/prices/water/historical_municipal_water_prices-research.csv`
- Water treatment energy in `data/precomputed/water_treatment/treatment_kwh_per_m3-toy.csv`

**Start with Phase 1** (update loader.py), then proceed sequentially through Phase 6. Create `src/__init__.py` and necessary directory structure.

---

## Files to read first

1. `docs/planning/water_simulation_mvp_plan.md` - Full implementation specifications
2. `docs/planning/water_simulation_followup_questions.md` - Design decisions summary
3. `settings/scenarios/water_policy_only.yaml` - Current scenario schema
4. `settings/scripts/loader.py` - Existing loader to update
5. `settings/policies/water_policies.py` - Existing water policies to integrate
