# Prompt: Fix Spec Audit Issues

Apply all 21 fixes from `docs/planning/spec_audit_fix_plan.md` to the spec files in `specs/`.

## Instructions

1. Read `docs/planning/spec_audit_fix_plan.md` completely before making any changes.
2. Apply fixes in order (Fix 1 through Fix 21) to the target files listed in each fix.
3. Target files: `specs/simulation_flow.md`, `specs/policies.md`, `specs/structure.md`. Do not modify `specs/metrics_and_reporting.md` (no changes needed).
4. For each fix, follow the "Replace ... With" instructions literally. Where the fix says "Add," insert the new content at the location specified.
5. After all fixes are applied, do a consistency pass: search each modified file for any remaining references to old names (e.g., `capacities[` that should now be `processing_throughput_kg_per_day[` or `storage_capacities_kg[`) and fix them.
6. Do NOT modify any code in `src/` or any files outside `specs/`.
