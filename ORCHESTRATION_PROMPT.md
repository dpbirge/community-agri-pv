# Parallel Data Generation Orchestration Prompt

**Copy and paste this prompt to launch parallel data generation agents.**

---

I need you to orchestrate parallel data generation for the Community Agri-PV simulation model. This is a multi-agent task where each agent generates different datasets independently.

## Context

- **Project**: Community farm simulation model for Sinai Peninsula, Egypt
- **Location**: Red Sea coast, hot arid climate
- **Scope**: Toy datasets for initial model development
- **Complete specifications**: See `docs/planning/data-generation-orchestration.md`

## Instructions

1. **Read the orchestration plan**: `docs/planning/data-generation-orchestration.md`
2. **Launch agents in parallel** for all Wave 1 tasks (Tasks 1-7, 10-11)
3. **Each agent should**:
   - Work independently on their assigned task
   - Follow metadata standards and quality checks
   - Report completion status with statistics
4. **After Wave 1 completes**, launch Wave 2 tasks (Tasks 8-9) which depend on weather data

## Wave 1 Tasks (Launch in Parallel)

Launch these agents simultaneously:

1. **Task 1: Weather Data** → `data/precomputed/weather/`
2. **Task 2: Crop Parameters** → `data/parameters/crops/`
3. **Task 3: Equipment Specs** → `data/parameters/equipment/`
4. **Task 4: Price Time-Series** → `data/prices/`
5. **Task 5: Labor Parameters** → `data/parameters/labor/`
6. **Task 6: Community Parameters** → `data/parameters/community/`
7. **Task 7: Cost Parameters** → `data/parameters/costs/`
8. **Task 10: Water Treatment** → `data/precomputed/water_treatment/`
9. **Task 11: Microclimate** → `data/precomputed/microclimate/`

## Wave 2 Tasks (Launch After Weather Data Ready)

10. **Task 8: PV and Wind Power** → Depends on Task 1
11. **Task 9: Irrigation and Yields** → Depends on Tasks 1 and 2

## Agent Instructions Template

For each agent, use this format:

```
Generate toy dataset for [TASK NAME] according to specifications in docs/planning/data-generation-orchestration.md, Task [N].

Requirements:
- Follow metadata header standards
- All values in specified units
- No missing data
- Validate against quality checks
- Report completion with statistics

Output folder: [FOLDER PATH]
Deliverables: [FILE LIST]
```

## Success Criteria

All datasets complete and validated. Ready to build Layer 3 simulation code.

---

**Start by reading the orchestration document, then launch all Wave 1 agents in parallel.**
