# Fix Proposals: Policy Extensibility (Section 4)

**Generated:** 2026-02-18
**Scope:** Section 4 (Policy Extensibility) and Section 7 action items #6, 19-21
**Source:** `docs/codereview/systematic_doc_review_report.md`

---

## Action Items

### Issue #6 / Section 4: Document YAML-to-Policy Parameter Wiring

**Action Item:** Document YAML-to-policy parameter wiring. Specify how configurable policy parameters are structured in YAML, extracted by loader, and injected into policy constructors.

**Severity:** CRITICAL

**Summary:** The architecture docs describe policies with configurable parameters (e.g., `conserve_groundwater.price_threshold_multiplier`, `adaptive.midpoint`, `quota_enforced.annual_quota_m3`) and the YAML file (`settings/settings.yaml`) already contains a `community_policy_parameters` section with per-policy parameter maps. However, no document specifies how the scenario loader extracts these parameters from YAML and passes them to policy constructors. A developer cannot implement the wiring from docs alone.

**Proposed Solution:**

Add a new section **"Policy Parameter Wiring"** to `structure.md` after the current Section 3 (Policies), as a new subsection 3.1. This is the correct location because `structure.md` owns the configuration schema, and `policies.md` already cross-references it for parameter definitions.

Text to add to `structure.md` after the policy characteristics subsection:

```markdown
### Policy parameter wiring

Policy parameters flow from the scenario YAML to policy instances through a three-step pipeline:

**Step 1: YAML structure**

All configurable policy parameters live under `community_policy_parameters` in the scenario YAML, keyed by policy name. Each policy name maps to a flat dictionary of parameter names and values:

```yaml
community_policy_parameters:
  conserve_groundwater:
    price_threshold_multiplier: 1.5
    max_gw_ratio: 0.30
  quota_enforced:
    annual_quota_m3: 20000
    monthly_variance_pct: 0.15
  hold_for_peak:
    price_threshold_multiplier: 1.2
  adaptive:
    midpoint: 1.0
    steepness: 5.0
    min_sell: 0.2
    max_sell: 1.0
  deficit_irrigation:
    deficit_fraction: 0.80
  min_water_quality:
    target_tds_ppm: 1500
  aggressive_growth:
    min_cash_months: 1
  conservative:
    min_cash_months: 6
  risk_averse:
    min_cash_months: 3
```

Policies that accept no configurable parameters (e.g., `max_groundwater`, `all_fresh`,
`fixed_schedule`, `balanced_finance`) do not need entries. Missing entries are valid and
mean "use all defaults."

**Step 2: Loader extraction**

The scenario loader (`load_scenario()`) reads `community_policy_parameters` into a
dictionary-of-dictionaries. When instantiating each farm's policy for a given domain,
the loader:

1. Reads the farm's selected policy name from `farms[i].policies.<domain>`
   (e.g., `farms[0].policies.water = "cheapest_source"`).
2. Looks up `community_policy_parameters[policy_name]` to get a parameter dict
   (or empty dict `{}` if no entry exists).
3. Passes that dict as keyword arguments to the factory function.

Pseudocode:

```
FOR each farm in scenario.farms:
    FOR each domain in [water, energy, crop, food, market, economic]:
        policy_name = farm.policies[domain]
        params = scenario.community_policy_parameters.get(policy_name, {})
        farm.policy_instances[domain] = get_{domain}_policy(policy_name, **params)
```

**Step 3: Factory function consumption**

Each domain's factory function accepts `**kwargs` and forwards them to the policy
constructor. The policy constructor uses keyword arguments with defaults:

```python
def get_water_policy(name, **kwargs):
    policies = {
        "max_groundwater": MaxGroundwater,
        "cheapest_source": CheapestSource,
        "conserve_groundwater": ConserveGroundwater,
        # ...
    }
    return policies[name](**kwargs)

class ConserveGroundwater(BaseWaterPolicy):
    def __init__(self, price_threshold_multiplier=1.5, max_gw_ratio=0.30):
        self.price_threshold_multiplier = price_threshold_multiplier
        self.max_gw_ratio = max_gw_ratio
```

Unknown keyword arguments raise `TypeError` (standard Python behavior). This
provides validation without extra code.

**Naming convention:** YAML parameter keys must exactly match the constructor
keyword argument names documented in `policies.md` for each policy.

**Scope:** `community_policy_parameters` is community-wide. All farms selecting
the same policy name receive the same parameter values. Per-farm parameter
overrides are not supported in MVP. If needed in the future, a
`farm.policy_parameters` section could override specific values.
```
Additionally, add the following cross-reference note at the end of the "Configurable parameters" bullet in the `policies.md` "Common patterns" section (line 47):

```markdown
- **Configurable parameters**: Some policies accept tuning parameters (e.g.,
  threshold multipliers, reserve targets). Parameters are set at instantiation
  from the scenario YAML and remain fixed for the run. Defaults are noted in each
  policy description. See `structure.md` Section 3.1 (Policy parameter wiring)
  for the full YAML-to-constructor pipeline.
```

**Rationale:** The YAML already uses `community_policy_parameters` with flat per-policy dicts. This proposal formalizes that existing pattern and makes the three-step pipeline (YAML -> loader -> factory -> constructor) explicit. The `**kwargs` forwarding pattern is idiomatic Python, requires no registry metadata, and fails explicitly on typos via `TypeError`.

**Confidence:** 5 -- The YAML structure already exists in `settings/settings.yaml`, the policy constructors already accept parameters per `policies.md`, and the factory functions are already documented in the "Common patterns" table. This proposal connects the dots without inventing new patterns.

---

**Owner Response: **Implement proposed solution. Should we add a complete yaml schema to the structure file that shows the options (and default values when obvious) for a simulation config? Should we write a new arch file that solely discusses the settings/configuration schema?

[blank]

---

### Issue #19 / Section 4: Document Factory Function Registration Mechanism

**Action Item:** Document factory function registration mechanism. How to register new policies.

**Severity:** IMPORTANT

**Summary:** `policies.md` documents factory functions (`get_water_policy(name)`, `get_energy_policy(name)`, etc.) and lists them in a table, but never explains how a developer adds a new policy to the registry. The registration mechanism (mapping policy names to classes) is implicit. A developer adding a new policy needs to know exactly what steps to take.

**Proposed Solution:**

Add a new section **"How to Add a New Policy"** at the end of `policies.md`, before any appendix or after the last policy domain section (Economic Policies). This section serves as a developer guide and belongs in `policies.md` because that document owns the policy specifications.

Text to add to `policies.md`:

```markdown
## How to Add a New Policy

This section describes the steps to add a new policy to any domain. The registration
mechanism is a simple name-to-class dictionary inside each domain's factory function.

### Step 1: Define context and decision compatibility

Verify that the existing context and decision dataclasses for the domain cover your
policy's needs. All policies within a domain share the same context (input) and
decision (output) dataclass.

- If your policy needs a new context field, add it to the domain's context dataclass
  and update the simulation loop (in `simulation_flow.md`) to populate it. All
  existing policies in the domain must gracefully ignore the new field.
- If your policy returns a new output field, add it to the decision dataclass. Set a
  sensible default (e.g., `None`) so existing policies do not break.
- Prefer using existing fields over adding new ones. The `decision_reason` string is
  designed to carry policy-specific diagnostic information.

### Step 2: Implement the policy class

Create a new class that inherits from the domain's base class and implements the
required method:

| Domain | Base class | Method to implement |
|--------|-----------|-------------------|
| Water | `BaseWaterPolicy` | `allocate_water(ctx) -> WaterAllocation` |
| Energy | `BaseEnergyPolicy` | `allocate_energy(ctx) -> EnergyAllocation` |
| Crop | `BaseCropPolicy` | `decide(ctx) -> CropDecision` |
| Food | `BaseFoodPolicy` | `allocate(ctx) -> ProcessingAllocation` |
| Market | `BaseMarketPolicy` | `decide(ctx) -> MarketDecision` |
| Economic | `BaseEconomicPolicy` | `decide(ctx) -> EconomicDecision` |

The constructor accepts keyword arguments for any configurable parameters with defaults:

```python
class MyNewWaterPolicy(BaseWaterPolicy):
    def __init__(self, my_threshold=0.5):
        self.my_threshold = my_threshold

    def allocate_water(self, ctx):
        # Implementation using ctx fields and self.my_threshold
        ...
        return WaterAllocation(
            groundwater_m3=...,
            municipal_m3=...,
            energy_used_kwh=...,
            cost_usd=...,
            decision_reason="my_reason",
            constraint_hit=...,
            policy_name="my_new_policy",
        )
```

Follow the error handling conventions documented in the "Error handling" section above:
zero-demand early return, `ValueError` on NaN/negative inputs, division-by-zero guards.

### Step 3: Register in the factory function

Add the policy name and class to the dictionary inside the domain's
`get_<domain>_policy()` function:

```python
def get_water_policy(name, **kwargs):
    policies = {
        "max_groundwater": MaxGroundwater,
        "cheapest_source": CheapestSource,
        "conserve_groundwater": ConserveGroundwater,
        "min_water_quality": MinWaterQuality,
        "max_municipal": MaxMunicipal,
        "quota_enforced": QuotaEnforced,
        "my_new_policy": MyNewWaterPolicy,    # <-- add here
    }
    if name not in policies:
        raise ValueError(
            f"Unknown water policy '{name}'. "
            f"Available: {list(policies.keys())}"
        )
    return policies[name](**kwargs)
```

The dictionary key is the policy name string used in scenario YAML files.

### Step 4: Add configurable parameters to YAML (if any)

If the policy accepts constructor parameters, add default values under
`community_policy_parameters` in the scenario YAML:

```yaml
community_policy_parameters:
  my_new_policy:
    my_threshold: 0.5
```

See `structure.md` Section 3.1 (Policy parameter wiring) for the full
YAML-to-constructor pipeline.

### Step 5: Document the policy

Add a subsection to the appropriate domain section of this document (`policies.md`)
following the established format:

1. Policy name heading (e.g., `#### my_new_policy`)
2. Plain-language description of behavior
3. Parameters table (if configurable)
4. Pseudocode block
5. Decision reason values

### Step 6: Update scenario validation

Add the new policy name to the list of valid options for the domain in
`validation.py`. The validation function checks that every farm's policy
name appears in the domain's factory function registry.

### Summary checklist

- [ ] Context/decision dataclass covers policy needs (or extended)
- [ ] Policy class inherits from domain base class
- [ ] Constructor accepts keyword arguments with defaults
- [ ] Policy name added to factory function dictionary
- [ ] YAML `community_policy_parameters` entry added (if configurable)
- [ ] Policy documented in `policies.md`
- [ ] Validation updated with new policy name
```
**Rationale:** The registration mechanism is a simple dictionary lookup, which is the standard Pythonic pattern for factory functions. This proposal documents it explicitly and provides a step-by-step checklist. It avoids introducing metaclass registration, decorators, or plugin systems that would add complexity without benefit at this project scale.

**Confidence:** 5 -- The factory function pattern is already documented in `policies.md` (the "Common patterns" table shows all six factory functions). The dictionary-based registration is the most common Python factory pattern and aligns with the project's preference for functional programming and simplicity.

---

**Owner Response:**

[blank]

---

### Issue #20 / Section 4: Document Insurance Policies or Explicitly Defer

**Action Item:** Document insurance policies or explicitly defer. Mentioned prominently in overview.md but absent from policies.md.

**Severity:** IMPORTANT

**Summary:** `overview.md` Section 3 describes insurance in detail (crop insurance, equipment insurance, cost-vs-self-insurance comparisons) under "Insurance options." It lists six open design questions. `policies.md` contains no insurance policy, no insurance context/decision dataclass, and no pseudocode. This gap creates the impression that insurance is in scope when it is not implementable from the current docs.

**Proposed Solution:**

**Recommendation: Explicitly defer.** Insurance is not implementable because the six design questions in `overview.md` remain unanswered (payout triggers, deductibles, mandatory vs. optional, government vs. private products, interaction with pooling, claims timing). Writing speculative policy pseudocode without resolving these questions would produce an unreliable specification. Additionally, insurance is not referenced in `simulation_flow.md` (no daily or monthly execution step), `structure.md` (no YAML schema), or `calculations.md` (no premium/payout formulas).

**Edit 1: Add deferral note to `overview.md`** (Section 3, "Insurance options"):

Replace the current heading:

```markdown
#### Insurance options
```

with:

```markdown
#### Insurance options [DEFERRED -- not in MVP]
```

Add the following paragraph immediately after the existing "Considerations to be determined" list:

```markdown
**Implementation status:** Insurance is deferred from MVP. The design questions
listed above must be resolved before insurance can be specified as a policy domain.
When implemented, insurance will require: (1) a new policy domain in `policies.md`
with context/decision dataclasses, (2) a YAML configuration section in
`structure.md`, (3) premium and payout formulas in `calculations.md`, and (4)
integration into the simulation loop in `simulation_flow.md` (likely as a yearly
boundary operation). See `policies.md` "How to Add a New Policy" for the general
pattern.
```

**Edit 2: Add deferral note to ****`policies.md`** after the Economic Policies section, before the "How to Add a New Policy" section:

```markdown
## Deferred Policy Domains

The following policy domains are described in `overview.md` but are not yet
specified with sufficient detail for implementation. They are explicitly excluded
from MVP.

### Insurance policies

`overview.md` Section 3 describes crop insurance and equipment insurance as risk
management alternatives to collective pooling. Six design questions remain
unresolved (payout triggers, deductibles, mandatory vs. optional participation,
government vs. private products, interaction with pooling mechanism, and claims
timing). Insurance will be specified as a new policy domain when these questions
are answered. No YAML schema, context/decision dataclass, or simulation loop
integration exists for insurance.
```

**Rationale:** Deferral is the correct approach because (a) the design questions are substantive and domain-specific -- answering them requires research into Egyptian agricultural insurance programs, not just engineering judgment; (b) writing speculative pseudocode would create a false impression of implementability; (c) the explicit deferral note prevents a developer from searching for missing insurance code.

**Confidence:** 5 -- The `overview.md` text itself acknowledges the questions are unresolved ("should be addressed in future research before implementation"). The deferral note simply makes this status explicit and cross-references the future implementation path.

---

**Owner Response: **Implement proposed solution

[blank]

---

### Issue #21 / Section 4: Clarify Community-Override Policy Scope

**Action Item:** Clarify community-override policy scope. Either specify the YAML schema and interaction mechanism or remove "community override supported" claims from policy domains.

**Severity:** IMPORTANT

**Summary:** `policies.md` states that community-override policies are "supported" in multiple domains (Water, Food Processing, Market, Energy, Crop, Economic all claim "Community-override policies are supported"). `structure.md` Section 3 describes a three-level policy hierarchy (farm-level, community-override, household). However, no document specifies: (a) the YAML schema for expressing a community override, (b) how the loader resolves override vs. farm-level policy, or (c) how the simulation loop applies overrides. `simulation_flow.md` Section 10.6 already flags this as "[NEEDS OWNER INPUT]" and proposes a schema, but it is not adopted into the normative specification.

**Proposed Solution:**

**Recommendation: Adopt the proposed schema from ****`simulation_flow.md`**** Section 10.6 as the normative specification, but mark it as deferred from MVP.** The schema is already designed and sensible. The current `settings/settings.yaml` does not contain a `community_policies` section, confirming it is not implemented. The farm-level policy mechanism is fully functional for MVP.

**Edit 1: Add ****`community_policies`**** schema to ****`structure.md`** in Section 3 (Policies), under "Policy scope and hierarchy," after the existing three-level description:

```markdown
**Community-override YAML schema [DEFERRED -- not in MVP]:**

When a community-level override is set for a domain, all farms use that policy
regardless of their individual `farms[i].policies.<domain>` setting. The override
is expressed in the scenario YAML under `community_policies`:

```yaml
community_policies:
    water_policy: cheapest_source    # overrides all farm water policies
    energy_policy: null              # no override, farms use individual
    food_policy: null
    market_policy: null
    crop_policy: null
    economic_policy: null
```

A `null` value (or missing key) means no override -- farms use their individual
policy selections. A non-null value must be a valid policy name for that domain.

**Loader behavior:** When `community_policies.<domain>` is non-null, the loader
ignores `farms[i].policies.<domain>` for all farms and instantiates the community
policy once, sharing the instance across all farms. Parameters for the community
policy are still read from `community_policy_parameters.<policy_name>`.

**Simulation loop behavior:** No changes to the simulation loop are required.
The override is resolved at load time by the scenario loader, so the simulation
loop always calls `farm.policy_instances[domain]` regardless of whether it was
set by farm-level or community-level configuration.

This feature is deferred from MVP. Per-farm policies are sufficient for
current scenarios.
```
**Edit 2: Qualify "community override supported" claims in `policies.md`.**

In each domain header that currently says "Community-override policies are supported," append the deferral note. For example, in the Food Processing Policies scope paragraph:

Replace:
```
Community-override policies are supported—if set, all farms adopt that policy.
```
With:
```
Community-override policies are supported in the schema design but deferred
from MVP—if set, all farms would adopt that policy. See `structure.md`
Section 3 for the proposed YAML schema.
```
Apply the same change to all domain scope paragraphs that reference community overrides:
- Water Policies (line 96 area)
- Food Processing Policies (line 347 area)
- Market Policies (line 462 area)
- Energy Policies (line 586 area)
- Crop Policies (line 692 area)
- Economic Policies (line 791 area)

**Edit 3: Resolve `simulation_flow.md` Section 10.6** by marking it as `[RESOLVED]`:

```markdown
### [RESOLVED] ~~10.6 Community-Override Policy vs. Farm-Level Policy YAML Schema~~

Resolved: The community-override schema is documented in `structure.md` Section 3
(Policy scope and hierarchy) and marked as deferred from MVP. Per-farm policies are
used for all current scenarios. The schema from the original proposal is adopted
as the normative design for future implementation.
```

**Rationale:** This approach preserves the design intent (community overrides are a planned feature) while clearly communicating that it is not yet implemented. The schema in `simulation_flow.md` 10.6 is already well-designed and requires no modification. Making the override resolution happen at load time (not in the simulation loop) is architecturally clean and consistent with how the loader already handles farm-level policies.

**Confidence:** 5 -- The proposed schema already exists in `simulation_flow.md` 10.6 and is well-designed. The `settings/settings.yaml` confirms no `community_policies` section exists, so this is correctly identified as unimplemented. The load-time resolution approach is consistent with the existing architecture.

---

**Owner Response: **Implement proposed solution. To confirm, when a policy is set at the community scale, it applies to all farms equally (the farms just take on that policy). This lets the user simplify policy setting and doens't have to copy-paste the same policy to each farm (which will lead to user errrors).

[blank]

---

## Gap Table Resolutions

The following table from Section 4 of the review report lists features described in `overview.md` but absent from `policies.md`. Each row is resolved below with a recommendation to specify, defer, or remove.

| Feature | overview.md Section | policies.md Status | Recommendation |
| --- | --- | --- | --- |
| Insurance policies | Section 3 (detailed) | Absent entirely | **Defer** (see Issue #20 above) |
| Collective pooling mechanism | Line 193 | Not specified as policy | **Defer** with note |
| Community-override policies | All domains claim support | No schema, logic, or pseudocode | **Defer** with schema (see Issue #21 above) |
| Load management / load shifting | Energy policies | Not implemented | **Remove** from overview.md |
| Crop type selection / planting optimization | Crop policies | Not governed by any policy | **Remove** from overview.md |
| Working capital advance rules | Economic policies | Not specified | **Defer** with note |
| Gradual spoilage model (rate %/day) | Food processing | Replaced by binary shelf-life model | **Reconcile** overview.md to match policies.md |

### Gap: Collective Pooling Mechanism

**Action Item:** Resolve the status of collective pooling as a policy or mechanism.

**Severity:** IMPORTANT

**Summary:** `overview.md` Section 3 (Economic model) describes a "Collective pooling mechanism" where a configurable percentage of profits flows to a collective reserve fund, with distribution policies for hardship. This is not represented as a policy in `policies.md`, not configured in `structure.md` (no YAML parameters for pooling percentage or distribution rules), and not integrated into `simulation_flow.md` (no daily or yearly step for pooling contributions or distributions).

**Proposed Solution:**

**Defer with explicit note.** The pooling mechanism requires design decisions that are flagged as open questions in `overview.md` itself ("How are operating advances determined?", "What happens if revenue doesn't cover advances?", "How are infrastructure costs allocated?"). The `cost_allocation_method` parameter in `structure.md` (equal, area_proportional, usage_proportional) addresses one aspect of collective cost sharing but does not constitute a full pooling mechanism.

Add the following to the "Deferred Policy Domains" section proposed in Issue #20 (in `policies.md`):

```markdown
### Collective pooling mechanism

`overview.md` Section 3 describes a collective reserve fund where a configurable
percentage of farm profits is pooled annually, with distribution rules for
hardship periods. Three design questions remain open: (1) how operating advances
are determined, (2) how unrecovered advances are handled, and (3) how collective
costs are allocated beyond the existing `cost_allocation_method` parameter.
Pooling will be specified as either an extension to the economic policy domain
or as a standalone community-level mechanism when these questions are answered.
No YAML schema, policy logic, or simulation loop integration currently exists.
```

Also add to `overview.md` Section 3 (Collective pooling mechanism), after the "Questions to be determined" list:

```markdown
**Implementation status:** Collective pooling is deferred from MVP. The
`cost_allocation_method` parameter in `structure.md` handles shared
infrastructure cost allocation but does not implement the profit-pooling
and distribution mechanism described above.
```

**Confidence:** 4 -- The open questions in `overview.md` clearly indicate this feature is not ready for specification. The deferral is appropriate, but the owner may want to partially implement pooling (e.g., just the contribution percentage) without the full distribution logic.

**Alternative Solutions:** If partial implementation is desired, specify a minimal pooling mechanism: a single `pooling_pct` parameter in the economic policy that deducts a fraction of monthly net income to a community reserve. Distribution would be manual (not policy-governed) for MVP.

---

**Owner Response: L**et's actually move all community pooling text from all files and move to a new md file called future_improvements.md in the same directory. A short description of how what is needed to implement pooling should be added. This is more than a todo list, it is aware of the structure of the model and helps guide adding new specifications to implement the.

[blank]

---

### Gap: Load Management / Load Shifting

**Action Item:** Resolve the status of load management / load shifting in energy policies.

**Severity:** MINOR

**Summary:** `overview.md` Section 3 (Policy framework, Energy policies) lists "Load management and load shifting" as an energy policy category. `policies.md` does not implement any load-shifting policy. The three implemented energy policies (microgrid, renewable_first, all_grid) control source priority and grid interaction, not demand-side load shifting. The daily simulation loop in `simulation_flow.md` does not support intra-day time steps required for meaningful load shifting.

**Proposed Solution:**

**Remove from ****`overview.md`****.** Load shifting requires sub-daily (hourly or 15-minute) time resolution to be meaningful. The simulation operates at a daily time step, which makes load shifting impossible to model -- shifting demand from one hour to another within the same day is invisible at daily resolution. This is not a deferral (implying future implementation) but a scope exclusion (the model architecture does not support it).

Edit `overview.md` Section 3 (Policy framework, Energy policies):

Replace:
```markdown
- Load management and load shifting
- Priority ordering: diesel backup vs grid backup vs battery
```

With:
```markdown
- Priority ordering: diesel backup vs grid backup vs battery
```

Add a note explaining the removal:

```markdown
> **Scope note:** Load management and load shifting are excluded from the model.
> These strategies require sub-daily (hourly) time resolution to be meaningful.
> The simulation operates at a daily time step, which aggregates all demand and
> generation within a day. Energy dispatch priority ordering achieves the relevant
> economic optimization at daily resolution.
```

**Confidence:** 5 -- The daily time step is a fundamental architectural constraint documented in `overview.md` Section 2 and used throughout `simulation_flow.md`. Load shifting is architecturally incompatible with the current model, not merely unimplemented.

---

**Owner Response: **Implement proposed solution. Add a small section in the newly created future_improvements.md file that outlines what would need to be added to the model to handle load shifting. 
[blank]

---

### Gap: Crop Type Selection / Planting Optimization

**Action Item:** Resolve the status of crop type selection and planting optimization in crop policies.

**Severity:** MINOR

**Summary:** `overview.md` Section 3 (Policy framework, Crop policies) lists "Crop type selection and mixing strategies" and "Planting date optimization for climate and market variables." The implemented crop policies in `policies.md` (fixed_schedule, deficit_irrigation, weather_adaptive) only adjust irrigation demand -- they do not govern what crops are planted or when. Crop selection and planting dates are static configuration in `structure.md` (set per-farm in the scenario YAML), not dynamic policy decisions.

**Proposed Solution:**

**Remove from ****`overview.md`** and clarify the distinction between configuration and policy. Crop selection and planting dates are Layer 2 design decisions, not Layer 3 runtime policies. This is consistent with the architectural principle that Layer 3 cannot modify Layer 2 during execution.

Edit `overview.md` Section 3 (Policy framework, Crop policies):

Replace:
```markdown
- Crop type selection and mixing strategies
- Planting date optimization for climate and market variables
- Harvest scheduling to smooth labor requirements
- Irrigation timing flexibility based on energy availability
```

With:
```markdown
- Irrigation adjustment strategies (deficit irrigation, weather-adaptive demand)
- Harvest scheduling to smooth labor requirements [DEFERRED]
```

Add a note:

```markdown
> **Scope note:** Crop type selection, planting dates, and area fractions are
> static configuration parameters set in the scenario YAML (see `structure.md`
> Farm configurations). They are Layer 2 design decisions, not Layer 3 runtime
> policies. To test different crop mixes or planting strategies, create separate
> scenario files. Crop policies in the simulation govern only irrigation demand
> adjustment during the growing season.
```

**Confidence:** 5 -- The architectural separation between Layer 2 (design/configuration) and Layer 3 (simulation/runtime) is a core principle documented in `overview.md` Section 2. Making crop selection a runtime policy would violate this separation.

---

**Owner Response: **Implement proposed solution. Again, add a note to the future_improvements.md file to discuss how this could be implemented, if the users wanted to.

[blank]

---

### Gap: Working Capital Advance Rules

**Action Item:** Resolve the status of working capital advance rules in economic policies.

**Severity:** IMPORTANT

**Summary:** `overview.md` Section 3 (Policy framework, Economic policies) lists "Working capital advance rules." `overview.md` Section 3 (Economic model, Working capital and cash flow) describes operating advances to farmers with three open design questions (how advances are determined, what happens if revenue doesn't cover advances, how costs are allocated). No corresponding policy, YAML parameter, or simulation logic exists in `policies.md`, `structure.md`, or `simulation_flow.md`.

**Proposed Solution:**

**Defer with explicit note.** Working capital advances interact with the collective pooling mechanism and require the same open design questions to be resolved. The current economic model initializes each farm with `starting_capital_usd` and tracks `current_capital_usd` through the simulation. This is a simplified version of working capital that does not model advances or repayment.

Add to the "Deferred Policy Domains" section in `policies.md` (appended after the collective pooling entry):

```markdown
### Working capital advance rules

`overview.md` Section 3 describes operating advances flowing to farmers throughout
the year, recouped when goods are sold. The advance determination method (fixed
amount, area-based, or historical), unrecovered advance handling, and interaction
with collective pooling are all open design questions. Working capital advances
will be specified as part of the economic policy domain when these questions are
answered. The current model uses `starting_capital_usd` and daily cash tracking
as a simplified working capital mechanism.
```

Also edit `overview.md` Section 3 (Policy framework, Economic policies):

Replace:
```markdown
- Working capital advance rules
```

With:
```markdown
- Working capital advance rules [DEFERRED -- see open questions in Economic model section]
```

**Confidence:** 4 -- The deferral is clearly appropriate given the open questions. However, the owner may want to implement a simple advance mechanism (e.g., monthly fixed advance per farm) without resolving all design questions.

**Alternative Solutions:** If a minimal mechanism is desired, add a `monthly_advance_usd` parameter to the economic policy context. Each farm receives a fixed monthly advance deducted from the community fund. Revenue repayments are automatic at sale time. This avoids the complex design questions while providing basic cash flow modeling.

---

**Owner Response:** Implement proposed solution. Add section in future_improvements.md explaining how it might be added.

[blank]

---

### Gap: Gradual Spoilage Model (rate %/day) vs Binary Shelf-Life Model

**Action Item:** Reconcile the gradual spoilage model in `overview.md` with the binary shelf-life model in `policies.md`.

**Severity:** IMPORTANT

**Summary:** `overview.md` Section 3 (Post-harvest system, Spoilage parameters) specifies a gradual spoilage model with a `spoilage_rate` in `%/day` that is a "function of storage conditions and product type." `policies.md` and `simulation_flow.md` implement a binary shelf-life model where product is either 100% sellable (before `shelf_life_days`) or 100% forced-sold (at expiry). The data file `storage_spoilage_rates-toy.csv` contains `shelf_life_days` per crop/product type, consistent with the binary model. The gradual model is not implemented anywhere.

**Proposed Solution:**

**Reconcile ****`overview.md`**** to match ****`policies.md`****.** The binary shelf-life model is already fully specified (policies.md FIFO/umbrella rule, simulation_flow.md Section 4.8, data file schema) and implemented. The gradual model would require: (a) a daily weight reduction step in the simulation loop, (b) a quality-degradation factor affecting sale price, (c) a threshold below which product is unsellable, and (d) interaction with the FIFO tranche system. This is substantial additional complexity for uncertain benefit in an educational model.

Edit `overview.md` Section 3 (Post-harvest system, Spoilage parameters table):

Replace the current spoilage parameters table:

```markdown
**Spoilage parameters (by product type):**

| Parameter | Unit | Notes |
| --- | --- | --- |
| Spoilage rate | %/day | Function of storage conditions and product type |
| Shelf life (fresh) | days | Maximum storage before total loss |
| Shelf life (dried) | days | Extended shelf life for processed goods |
| Shelf life (canned) | days | Extended shelf life for preserved goods |
```

With:

```markdown
**Spoilage parameters (by product type):**

| Parameter | Unit | Notes |
| --- | --- | --- |
| Shelf life | days | Maximum storage duration per crop and product type before forced sale. Binary model: product is fully sellable until expiry, then must be sold immediately. Data source: `storage_spoilage_rates-toy.csv` |

> **Design decision:** The simulation uses a binary shelf-life model (product
> is either sellable or expired) rather than a gradual spoilage model
> (continuous weight loss %/day). The binary model is simpler, well-suited to
> the FIFO tranche tracking system (see `policies.md` umbrella rule), and
> appropriate for an educational tool where the key insight is shelf-life
> duration differences between fresh and processed products. A gradual model
> could be added as a future refinement if needed.
```

**Confidence:** 5 -- The binary model is fully implemented across three documents and the data file. The gradual model exists only in `overview.md` as a conceptual description. Aligning `overview.md` with the implemented specification is the correct resolution.

---

**Owner Response: **Implement proposed solution. The only food that spoils is fresh food and that food will be sold off fairly quickly. A single binary spoilage rate is fine to use for now. Canned and other processing mechanisms packages the food in a way that spoilage cannot be detected anyways.

[blank]

---

## Summary of All Changes by File

| File | Change Type | Description |
| --- | --- | --- |
| `structure.md` | **Add** Section 3.1 | Policy parameter wiring (YAML -> loader -> factory -> constructor) |
| `structure.md` | **Add** to Section 3 | Community-override YAML schema (deferred) |
| `policies.md` | **Edit** Common patterns | Cross-reference to `structure.md` Section 3.1 for parameter wiring |
| `policies.md` | **Add** new section | "How to Add a New Policy" developer guide |
| `policies.md` | **Add** new section | "Deferred Policy Domains" (insurance, pooling, working capital) |
| `policies.md` | **Edit** domain scopes | Qualify "community override supported" with deferral note (6 domains) |
| `overview.md` | **Edit** Insurance options | Add `[DEFERRED]` tag and implementation status note |
| `overview.md` | **Edit** Economic model | Add implementation status note for collective pooling |
| `overview.md` | **Edit** Energy policies | Remove load management/shifting; add scope note |
| `overview.md` | **Edit** Crop policies | Remove crop selection/planting optimization; add scope note |
| `overview.md` | **Edit** Economic policies | Tag working capital advances as `[DEFERRED]` |
| `overview.md` | **Edit** Spoilage parameters | Replace gradual model with binary shelf-life model description |
| `simulation_flow.md` | **Edit** Section 10.6 | Mark as `[RESOLVED]` with reference to `structure.md` |
