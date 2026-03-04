# Session Prompt: Implement Treatment Smoothing Strategy

Implement the `maximize_treatment_efficiency` water dispatch strategy as specified
in `docs/planning/treatment_smoothing_strategy.md`. Read that file first — it
contains the full architecture, file-by-file changes, and testing plan.

Follow the implementation steps (1-11) in order. Key points:

- All changes are in `src/water.py` and `settings/water_policy_base.yaml`
- Add the `treatment_smoothing` config block to `water_policy_base.yaml` with
  `strategy` left as `minimize_cost` (the new section is dormant until strategy
  is switched)
- Add two new internal helpers: `_compute_treatment_target` and
  `_effective_treatment_target`
- Modify `_dispatch_day` step 3 with one branch, fallow handling, and prefill skip
- Modify `_run_simulation` to call pre-computation before the daily loop
- Modify `compute_water_supply` to parse the new config section
- Existing strategies must produce identical output — run regression check
- Run `python -m src.water` and the water balance notebook to validate
