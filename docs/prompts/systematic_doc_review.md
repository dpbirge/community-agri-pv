# Prompt: Systematic Documentation Review — Specs Consistency Check

## Objective

Conduct a comprehensive review of the 13 specification files in `specs/` against each other, the actual data files in `data/`, the data registry in `settings/data_registry.yaml`, and the reference settings YAML. The goal is to identify gaps, stale references, inconsistencies, or orphaned content that would prevent a competent developer from implementing the full simulation codebase from these specs alone.

**Important:** This review is documentation-focused. Do NOT read or reference any existing code in `src/`. Pretend the code does not exist. The question is: "Are these specs internally consistent and complete enough to build this system from scratch?"

## Key Review Concerns

- **Cross-reference integrity** — do all internal links and section references resolve correctly?
- **Policy name consistency** — do policy names in `reference_settings.yaml` match the canonical names in `policies.md` and `structure.md`?
- **Calculation file organization** — calculations are split across an index (`calculations.md`) and 4 domain files; is the split clean with no duplication or orphaned content?
- **Deferred features** — are all TBD/deferred items in the spec files tracked in `future_improvements.md`?

## Execution Plan

Launch 5 parallel review agents (Tasks), one per review dimension. Each agent produces a structured findings report. After all agents complete, synthesize findings into a single report at `docs/codereview/systematic_doc_review_report.md`.

---

## Agent 1: Cross-Reference Integrity Audit

**Scope:** Find every cross-reference between the 13 spec files (and to external files like data paths) and verify they are correct.

**Instructions:**

1. Read all 13 files in `specs/`:
   - `specs/overview.md`
   - `specs/structure.md`
   - `specs/calculations.md` (index)
   - `specs/calculations_water.md`
   - `specs/calculations_energy.md`
   - `specs/calculations_crop.md`
   - `specs/calculations_economic.md`
   - `specs/policies.md`
   - `specs/simulation_flow.md`
   - `specs/data.md`
   - `specs/metrics_and_reporting.md`
   - `specs/future_improvements.md`
   - `specs/reference_settings.yaml`

2. Extract every cross-reference (markdown links, file path mentions, section references):
   - **Internal links**: `[text](other_spec_file.md)` — verify the target file exists and the link text is accurate
   - **Section references**: "See Section X of Y.md" or "See Y.md Section X" — verify the section exists in the target file
   - **Data file paths**: `data/parameters/...`, `data/precomputed/...`, `data/prices/...` — verify the file exists on disk
   - **Settings references**: `settings/settings.yaml`, `settings/data_registry.yaml` — verify they exist

3. **Stale reference check** — search all 13 files for any references to:
   - `docs/arch/` — this path no longer exists; any reference is stale
   - Any file path that does not exist on disk
   - Section references (e.g., "Section X of Y.md") where the target section is missing or was moved

4. **Orphan check** — verify that every file in `specs/` is referenced by at least one other file. Flag any orphaned files.

**Output format:** Markdown table with columns: `Reference Text | Source File:Line | Target | Status (OK/BROKEN/STALE) | Issue Description`

---

## Agent 2: Policy Name and Parameter Consistency Audit

**Scope:** Verify that policy names, parameter names, and configuration options are consistent across `reference_settings.yaml`, `policies.md`, `structure.md`, and `simulation_flow.md`.

**Instructions:**

1. Read `specs/reference_settings.yaml` — extract every policy name used in farm configs and every parameter name.
2. Read `specs/policies.md` — extract the canonical list of policy names for all 6 domains (water, energy, crop, food processing, market, economic).
3. Read `specs/structure.md` — extract policy names from the policy definition tables.
4. Read `specs/simulation_flow.md` — extract any policy names referenced in the flow.

5. Cross-reference policy names:
   - For each policy name in `reference_settings.yaml`, verify it exists in `policies.md` as a canonical name.
   - For each canonical policy in `policies.md`, verify it appears in `structure.md` policy tables.
   - Flag any name mismatches between files.

6. Cross-reference parameters:
   - For each configurable parameter in `reference_settings.yaml`, verify it is documented in `structure.md` or the relevant spec file.
   - For each policy parameter listed in `policies.md` (constructor args, context fields), verify it has a corresponding YAML path in `reference_settings.yaml`.
   - Check that default values match across files.

7. Verify the YAML-to-policy wiring:
   - `structure.md` describes a "Policy Parameter Wiring" pipeline (YAML → Scenario → Policy). Verify this pipeline is consistent with what `reference_settings.yaml` actually contains.
   - Check that the 3 example farms in `reference_settings.yaml` use only valid policy names and parameter values.

**Output format:** Per-domain table: `Policy Name | reference_settings.yaml | policies.md | structure.md | simulation_flow.md | Status | Issue`

---

## Agent 3: Data Completeness and Registry Audit

**Scope:** Verify that every data file referenced in the specs actually exists on disk, and that every file on disk is accounted for in the docs and registry.

**Instructions:**

1. Read `settings/data_registry.yaml` and build a list of all registered file paths.
2. Run `find data/ -name "*.csv" | sort` to get every CSV on disk.
3. Read each spec file and extract every file path or filename reference:
   - `specs/overview.md`
   - `specs/structure.md`
   - `specs/calculations.md` (index)
   - `specs/calculations_water.md`
   - `specs/calculations_energy.md`
   - `specs/calculations_crop.md`
   - `specs/calculations_economic.md`
   - `specs/policies.md`
   - `specs/simulation_flow.md`
   - `specs/data.md`
   - `specs/metrics_and_reporting.md`
4. Cross-reference these three lists:
   - **Spec references -> disk**: Does every file path mentioned in the specs exist on disk? Flag mismatches.
   - **Registry -> disk**: Does every registry entry point to a file that exists? Flag missing files.
   - **Disk -> registry**: Are there CSV files on disk that are NOT in the registry? Determine if they should be registered.
   - **Disk -> specs**: Are there files on disk not mentioned in any spec? Flag orphaned files.
5. For each data file in the registry, read the first 15 lines (metadata header + column names) and verify:
   - The columns match what the specs say they should contain
   - The units match spec specifications
   - The file format follows the metadata standard (SOURCE, DATE, DESCRIPTION, UNITS, LOGIC, DEPENDENCIES)

**Output format:** Markdown table with columns: `File Reference | Source Spec | On Disk? | In Registry? | Column Match? | Issue Description`

---

## Agent 4: Calculation Split Consistency Audit

**Scope:** Verify that `calculations.md` (index) and the 4 domain calculation files form a complete, non-duplicated, correctly cross-referenced set.

**Instructions:**

1. Read `specs/calculations.md` (the index file).
2. Read all 4 domain calculation files:
   - `specs/calculations_water.md`
   - `specs/calculations_energy.md`
   - `specs/calculations_crop.md`
   - `specs/calculations_economic.md`
3. Verify index completeness:
   - Does the index file list ALL calculation sections from the 4 domain files?
   - Does every section in the domain files have a corresponding entry in the index?
   - Are there any calculation sections that appear in the index but not in any domain file (orphaned index entries)?

4. Check for content duplication:
   - Search for identical or near-identical formulas appearing in multiple domain files. Some cross-referencing is expected, but actual formula duplication risks divergence.
   - Check if any content that should be in a specific domain file ended up in the wrong one (e.g., water calculations in the energy file).

5. Check cross-references between domain files:
   - Where one domain file references a calculation in another (e.g., crop yield references water calculations), verify the reference points to the correct file and section.
   - Verify that shared concepts (e.g., `ET_actual / ET_crop` ratio used in both water and crop) are defined in one place and referenced from the other.

6. Check references FROM other specs TO calculations:
   - Read `specs/simulation_flow.md` — for every calculation reference, verify it points to the correct domain file.
   - Read `specs/policies.md` — same check.
   - Read `specs/structure.md` — same check.

7. Verify the index file's non-domain content:
   - The index file should contain: resilience/Monte Carlo calculations, sensitivity analysis, units/conversions, and references. Verify this content is present and not duplicated in the domain files.

**Output format:** Checklist of all calculation sections with: `Section Title | Domain File | In Index? | Cross-refs OK? | Status | Notes`

---

## Agent 5: Implementation Sufficiency — "Build From Scratch" Test

**Scope:** Assess whether the 13 spec files together provide everything needed to implement a full simulation codebase from scratch. Identify information gaps that would force a developer to make assumptions.

**Instructions:**

1. Read all 13 files in `specs/`, plus `settings/data_registry.yaml` and a sample of key data files (first 15 lines each).
2. Walk through a hypothetical implementation, identifying what a developer would need to know at each step:

   **a. Layer 1 (Pre-computation):**
   - Can a developer build the weather data generator from the specs?
   - Can they build the PV power calculator? (Is pvlib usage documented?)
   - Can they build the wind power calculator? (Are power curves specified?)
   - Can they build the irrigation demand calculator? (Is FAO Penman-Monteith fully specified?)
   - Can they build the crop yield calculator?
   - Can they build the household/community building demand generators?

   **b. Layer 2 (Design/Configuration):**
   - Is the YAML schema fully specified in `structure.md` + `reference_settings.yaml`? Could a developer write a YAML loader from the specs?
   - Is the data registry format documented in `data.md`?
   - Is scenario validation fully specified?
   - Is the `calculate_system_constraints()` function fully specified?
   - Is infrastructure cost calculation fully specified in `calculations_economic.md`?

   **c. Layer 3 (Simulation):**
   - Is the SimulationState data structure fully specified? (All fields, types, initial values?)
   - Is the daily loop in `simulation_flow.md` unambiguous enough to implement step-by-step?
   - Are all state transitions documented?
   - Is the crop state machine (planting -> growth stages -> harvest -> replanting) fully specified?
   - Is the StorageTranche/FIFO system fully specified?
   - Is the energy dispatch algorithm fully specified in `calculations_energy.md` for all 3 policy variants?

   **d. Data contracts between layers:**
   - Are the interfaces between Layer 1 -> Layer 2 -> Layer 3 fully defined?
   - Can a developer connect data files to the simulation without reading existing code?
   - Are registry key naming conventions documented in `data.md`?

   **e. Output and reporting:**
   - Is the output format (CSV, JSON, plots) fully specified in `metrics_and_reporting.md`?
   - Can a developer build all 6 plots and 2 tables from `metrics_and_reporting.md`?
   - Is the Monte Carlo framework fully specified in `calculations.md`?
   - Is the sensitivity analysis framework fully specified in `calculations.md`?

   **f. Deferred features:**
   - Read `specs/future_improvements.md` — verify that every feature marked as deferred/TBD in the other specs has a corresponding entry here.
   - Are the "why deferred" rationales sufficient?
   - Are there features mentioned as deferred in simulation_flow.md or policies.md that are NOT listed in future_improvements.md?

   **g. Missing pieces (things not documented anywhere):**
   - List every question a developer would need to ask that isn't answered in the specs.
   - Categorize as: (1) design decision needed, (2) data missing, (3) formula missing, (4) ambiguous specification.

**Output format:** Section-by-section assessment with a "confidence score" (1-5) for each area, where 5 = "fully implementable from specs alone" and 1 = "major gaps, would require significant assumptions or external research."

---

## Post-Agent Synthesis

After all 5 agents complete, compile their findings into a single report:

1. **Executive summary**: Overall documentation quality score and top-10 critical findings.
2. **Cross-reference integrity**: Agent 1 results — stale refs, broken links, moved sections.
3. **Policy consistency**: Agent 2 results — name mismatches, parameter gaps, wiring issues.
4. **Data completeness**: Agent 3 results — files missing, mismatched, or unregistered.
5. **Calculation split quality**: Agent 4 results — split cleanliness, duplication, orphaned content.
6. **Implementation readiness**: Agent 5 results — confidence scores and missing pieces.
7. **Prioritized action items**: Ranked list of all issues by severity (CRITICAL -> IMPORTANT -> MINOR).

Write the final report to `docs/codereview/systematic_doc_review_report.md`.
