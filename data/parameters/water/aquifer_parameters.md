# Aquifer Parameters — Research Notes

## Overview

The simulation uses two aquifer parameters configured in the scenario YAML under `water_system.groundwater_wells`:

- **`aquifer_exploitable_volume_m3`** — Total volume of groundwater extractable by the community's wells before depletion
- **`aquifer_recharge_rate_m3_yr`** — Annual natural recharge from rainfall infiltration and lateral flow

These are intentionally simplified: a single volume scalar and a constant recharge rate, rather than a full hydrogeological model.

## Current Values (toy estimates)

| Parameter | Value | Basis |
|---|---|---|
| `aquifer_exploitable_volume_m3` | 500,000 m³ | Order-of-magnitude estimate for a small coastal alluvial aquifer |
| `aquifer_recharge_rate_m3_yr` | 5,000 m³/yr | Negligible — typical for arid climate with <50 mm/yr rainfall |

## Context: Sinai Peninsula Hydrogeology

**Aquifer types in the region:**
- Alluvial aquifers in wadi systems (unconfined, shallow, limited storage)
- Nubian Sandstone Aquifer System (deep, fossil water, essentially zero recharge)
- Coastal aquifers (risk of saltwater intrusion with over-extraction)

**Key considerations:**
- Sinai rainfall is extremely low (~20–50 mm/yr at the Red Sea coast)
- Most accessible groundwater is brackish (TDS 3,000–10,000 ppm), consistent with the BWRO treatment assumption
- Exploitable volume depends heavily on the specific aquifer geometry, which varies by location
- A community-scale assessment would typically involve a pumping test and geological survey

## Research Needed

To upgrade from toy to research-grade values:

1. **Literature search**: Egyptian geological surveys, RIGW (Research Institute for Groundwater) reports on Sinai aquifer characteristics
2. **Typical aquifer volumes**: Storage coefficients and saturated thickness for alluvial and sandstone aquifers in arid regions
3. **Recharge estimates**: Regional groundwater recharge studies for eastern Sinai / Gulf of Aqaba coast
4. **Sustainable yield**: Published sustainable extraction rates for community-scale wells in similar settings

## References

- RIGW/IWACO (1999). Hydrogeological Map of Egypt, 1:500,000 scale
- Issar, A.S. (2008). Progressive development of water resources in the Middle East for sustainable water supply
- Abou Heleika, M.M. & Niesner, E. (2009). Configuration of the limestone aquifers in the central part of Sinai, Egypt
