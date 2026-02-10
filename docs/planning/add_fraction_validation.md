# Add Fraction Sum Validation to ProcessingAllocation

**Generated:** February 6, 2026

## Plan: Add Fraction Sum Validation to ProcessingAllocation

### Problem Statement

The `ProcessingAllocation` dataclass at `/Users/dpbirge/GITHUB/community-agri-pv/src/policies/food_policies.py:37-54` holds four fraction fields (`fresh_fraction`, `packaged_fraction`, `canned_fraction`, `dried_fraction`) that represent the share of harvest directed to each processing pathway. The docstring on line 40 explicitly states "Fractions must sum to 1.0", but there is no runtime enforcement of this invariant.

Without validation, three failure modes can occur silently:

1. **Fractions sum to less than 1.0** -- some portion of the harvest disappears. For example, if a policy returns fractions summing to 0.90, then 10% of the harvested crop is never processed or sold. Revenue is understated, and the physical mass balance is broken.

2. **Fractions sum to more than 1.0** -- the simulation processes more crop than was actually harvested. For example, fractions summing to 1.05 would allocate 105% of the harvest, creating phantom crop volume. Revenue is overstated; physical mass conservation is violated.

3. **Individual fraction is negative** -- a negative fraction multiplied by `harvest_yield_kg` produces a negative `raw_kg`, which propagates negative weight loss, negative revenue, and corrupted accumulators on `CropState` and `FarmState`.

All three are especially dangerous because they propagate silently through `process_harvests()` in `simulation.py` (lines 393-438), where each fraction is multiplied by `crop.harvest_yield_kg` and the results accumulate into `FarmState.cumulative_crop_revenue_usd`, `cumulative_post_harvest_loss_kg`, etc. A subtle fraction error in one policy would corrupt every farm-year that uses that policy, and the bug would only be detectable by careful manual inspection of output CSVs.

### Current Behavior

Currently, `ProcessingAllocation` is a plain `@dataclass` with no `__post_init__` method:

```python
@dataclass
class ProcessingAllocation:
    fresh_fraction: float = 1.0
    packaged_fraction: float = 0.0
    canned_fraction: float = 0.0
    dried_fraction: float = 0.0
    policy_name: str = ""
```

The four built-in policies (`AllFresh`, `MaximizeStorage`, `Balanced`, `MarketResponsive`) all return hardcoded fractions that do sum to 1.0 -- verified by manual inspection:

| Policy | fresh | packaged | canned | dried | Sum |
|--------|-------|----------|--------|-------|-----|
| AllFresh | 1.0 | 0.0 | 0.0 | 0.0 | 1.0 |
| MaximizeStorage | 0.20 | 0.10 | 0.35 | 0.35 | 1.0 |
| Balanced | 0.50 | 0.20 | 0.15 | 0.15 | 1.0 |
| MarketResponsive (low) | 0.30 | 0.20 | 0.25 | 0.25 | 1.0 |
| MarketResponsive (high) | 0.65 | 0.15 | 0.10 | 0.10 | 1.0 |

There is also a fallback construction at `simulation.py:376`:
```python
allocation = ProcessingAllocation(fresh_fraction=1.0, policy_name="all_fresh")
```
This relies on the other three fractions defaulting to 0.0, so `1.0 + 0.0 + 0.0 + 0.0 = 1.0` -- valid.

**Where fractions originate:** Food policies are instantiated via `get_food_policy(name, **kwargs)` in `loader.py:517`. The `**kwargs` come from `community_policy_parameters` in the scenario YAML. Currently none of the four food policy constructors accept fraction-override parameters. However, the `**kwargs` pipeline exists, so a future scenario could pass custom fractions if a policy accepted them. This is the most likely avenue for user-introduced errors.

### Desired Behavior

When a `ProcessingAllocation` is constructed -- whether by a built-in policy's `allocate()` method, by the fallback in `simulation.py`, or by any future code -- the dataclass should immediately verify:

1. All four fraction fields are non-negative (each >= 0.0).
2. The four fractions sum to 1.0 within a floating-point tolerance.

If either condition is violated, a `ValueError` should be raised immediately with a clear message identifying the offending values and the policy name.

### Proposed Solution

**Step 1: Add `__post_init__` to `ProcessingAllocation`**

File: `/Users/dpbirge/GITHUB/community-agri-pv/src/policies/food_policies.py`

Add a `__post_init__` method to the `ProcessingAllocation` dataclass. This method runs automatically after dataclass `__init__`, which means every construction site is covered without any changes to calling code.

```python
FRACTION_SUM_TOLERANCE = 0.001

@dataclass
class ProcessingAllocation:
    """Result of food processing policy decision.

    Fractions must sum to 1.0. Each represents the share of harvest
    directed to that processing pathway. Validated at construction time.

    Args:
        fresh_fraction: Fraction sold as fresh produce (0-1)
        packaged_fraction: Fraction sent to fresh packaging (0-1)
        canned_fraction: Fraction sent to canning (0-1)
        dried_fraction: Fraction sent to drying (0-1)
        policy_name: Name of the policy that produced this allocation
    """
    fresh_fraction: float = 1.0
    packaged_fraction: float = 0.0
    canned_fraction: float = 0.0
    dried_fraction: float = 0.0
    policy_name: str = ""

    def __post_init__(self):
        fractions = [self.fresh_fraction, self.packaged_fraction,
                     self.canned_fraction, self.dried_fraction]
        for name, value in zip(
            ["fresh", "packaged", "canned", "dried"], fractions
        ):
            if value < 0:
                raise ValueError(
                    f"ProcessingAllocation ({self.policy_name}): "
                    f"{name}_fraction is negative ({value})"
                )
        total = sum(fractions)
        if abs(total - 1.0) > FRACTION_SUM_TOLERANCE:
            raise ValueError(
                f"ProcessingAllocation ({self.policy_name}): "
                f"fractions sum to {total}, must be 1.0 "
                f"(tolerance {FRACTION_SUM_TOLERANCE}). "
                f"Values: fresh={self.fresh_fraction}, "
                f"packaged={self.packaged_fraction}, "
                f"canned={self.canned_fraction}, "
                f"dried={self.dried_fraction}"
            )
```

**Step 2: Define the tolerance constant**

Place `FRACTION_SUM_TOLERANCE = 0.001` as a module-level constant at the top of `food_policies.py`, after the imports. This value:

- Is consistent with the tolerance used in `validation.py:173` for equipment fractions (`0.01`), but tighter because processing allocation fractions are computed from simple hardcoded literals (0.20, 0.35, etc.) where floating point should not introduce more than ~1e-15 error. A tolerance of `0.001` provides comfortable margin.
- Matches the recommendation in `food_processing_fixes.md` Issue 6.
- Is loose enough to accommodate any future dynamic fraction calculations that might involve division.

**Step 3: No changes needed at any call site**

All six existing construction sites already produce valid fractions:

| Location | Fractions | Valid |
|----------|-----------|-------|
| `AllFresh.allocate()` (line 88) | 1.0/0.0/0.0/0.0 | Yes |
| `MaximizeStorage.allocate()` (line 107) | 0.20/0.10/0.35/0.35 | Yes |
| `Balanced.allocate()` (line 127) | 0.50/0.20/0.15/0.15 | Yes |
| `MarketResponsive.allocate()` low (line 162) | 0.30/0.20/0.25/0.25 | Yes |
| `MarketResponsive.allocate()` high (line 171) | 0.65/0.15/0.10/0.10 | Yes |
| `simulation.py:376` fallback | 1.0/0.0/0.0/0.0 | Yes |

No existing code will break.

**Step 4: Update the docstring**

Update the class docstring to note that validation is enforced at construction time, not merely documented as a contract. This is already reflected in the proposed code above ("Validated at construction time").

### Decision Points

**1. Validate at construction time vs. usage time?**

Recommendation: **Construction time** (via `__post_init__`).

Rationale: The error should surface as close to the source as possible. If a policy's `allocate()` method produces bad fractions, the `ValueError` will point directly at the policy call rather than at the downstream `process_harvests()` loop where the fractions are consumed. Construction-time validation also means that manual/test constructions like `ProcessingAllocation(fresh_fraction=0.5)` (which would silently sum to 0.5) are caught immediately.

The existing codebase already uses `__post_init__` for derived calculations in `CropState` (line 41 of `state.py`), so this pattern is established.

**2. Use `__post_init__` on the dataclass?**

Recommendation: **Yes**. This is the standard Python dataclass pattern for post-construction validation. It requires no changes to any existing call site and catches all construction paths including direct instantiation, policy returns, and fallback defaults.

**3. Tolerance value?**

Recommendation: **0.001**. This balances:
- The equipment fraction validation in `loader.py:351` uses `0.01` -- but that validates raw YAML input where users might type approximate values. For `ProcessingAllocation`, fractions are set programmatically, so a tighter tolerance is appropriate.
- The planning doc (`food_processing_fixes.md`) recommends `0.001`.
- All current fractions are exact decimal literals with zero floating-point error, so even `1e-9` would work today. Using `0.001` provides headroom for future dynamic calculations.

**4. Auto-normalize vs. raise error?**

Recommendation: **Raise error, do not auto-normalize**.

Auto-normalization (dividing each fraction by the sum) would mask bugs. Per the project's coding principles in `CLAUDE.md`: "AVOID try/accept statements or graceful fallbacks that inject dummy values or other defaults just to get code to work. We want code that fails explicitly when data or functions are not properly designed or formatted so errors and bugs can be caught and fixed." This applies directly -- a bad fraction sum is a bug, and the simulation should fail explicitly rather than silently correct it.

**5. Should individual fractions be validated for range [0, 1]?**

Recommendation: **Validate non-negative (>= 0), but do not cap at 1.0**. An individual fraction greater than 1.0 would automatically be caught by the sum-to-1.0 check (since all fractions are non-negative, one fraction > 1.0 forces the sum > 1.0). The critical check is non-negativity, which the sum check alone cannot catch (e.g., `fresh=-0.5, packaged=1.5, canned=0, dried=0` sums to 1.0 but is physically nonsensical).

### Implementation Sequence

1. Add `FRACTION_SUM_TOLERANCE = 0.001` module constant to `food_policies.py`.
2. Add `__post_init__` method to `ProcessingAllocation` with non-negativity check and sum check.
3. Update the class docstring to state validation is enforced.
4. Run the simulation (`python src/simulation/results.py settings/settings.yaml`) to confirm no existing code breaks.
5. Manually test with a bad allocation to confirm the error message is clear:
   ```python
   ProcessingAllocation(fresh_fraction=0.5, policy_name="test")
   # Should raise: fractions sum to 0.5, must be 1.0
   ```

### Questions / Remaining Unknowns

1. **Future configurable policies.** The `**kwargs` pipeline from YAML through `get_food_policy()` could theoretically be used to pass custom fraction overrides to a new policy class. Should there be a companion "validate-at-load-time" check in `loader.py` for food policy parameters, similar to the equipment fraction validation at `loader.py:349-352`? This is out of scope for this TODO item but worth noting as a follow-up.

2. **Testing infrastructure.** The `testing/` directory currently only contains a `README.md`. This validation is a good candidate for the first unit test: instantiate `ProcessingAllocation` with various invalid fraction combinations and assert that `ValueError` is raised. No test file exists yet to add this to.

3. **Tolerance alignment.** The equipment fraction validation in `validation.py:173` uses `0.01` tolerance while this plan recommends `0.001`. Should these be aligned to a single project-wide constant? Both are defensible at their current values given their different contexts (YAML user input vs. programmatic output), but a shared constant would enforce consistency.

### Critical Files for Implementation

- `/Users/dpbirge/GITHUB/community-agri-pv/src/policies/food_policies.py` - Primary file to modify: add `__post_init__` validation to `ProcessingAllocation` dataclass
- `/Users/dpbirge/GITHUB/community-agri-pv/src/simulation/simulation.py` - Consumer of `ProcessingAllocation` in `process_harvests()` (lines 374-438); no changes needed but must verify no breakage
- `/Users/dpbirge/GITHUB/community-agri-pv/src/settings/validation.py` - Reference for existing fraction validation pattern (lines 165-174, equipment fractions with 0.01 tolerance)
- `/Users/dpbirge/GITHUB/community-agri-pv/docs/planning/food_processing_fixes.md` - Source Issue 6 specification; update to mark as resolved after implementation
- `/Users/dpbirge/GITHUB/community-agri-pv/src/simulation/state.py` - Reference for existing `__post_init__` pattern in `CropState` (line 41)
