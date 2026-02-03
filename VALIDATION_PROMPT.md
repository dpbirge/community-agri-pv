# Data Generation Validation Task

## Objective
Verify that all 11 data generation tasks from the Community Agri-PV simulation were completed correctly. For each task, confirm data quality, format compliance, and identify any gaps requiring additional research.

## Reference Document
Read `docs/planning/data-generation-orchestration.md` for full specifications of each task.

## Validation Checklist

For each task below:
1. Confirm the output file(s) exist
2. Verify CSV metadata headers are present (SOURCE, DATE, DESCRIPTION, UNITS, LOGIC, DEPENDENCIES, ASSUMPTIONS)
3. Check data ranges match specifications
4. Flag any missing columns, unrealistic values, or format issues
5. Note any additional research needed to improve data quality

### Tasks to Validate

| Task | Output Location | Key Checks | Agent Status |
|------|-----------------|------------|--------------|
| 1. Weather Data | `data/precomputed/weather/` | 15 years, summer 38-46°C, winter 18-26°C, solar 3-8 kWh/m²/day | ✅ Complete |
| 2. Crop Parameters | `data/parameters/crops/` | 4 files, FAO-56 Kc +7%, 5 crops | ✅ Complete |
| 3. Equipment Specs | `data/parameters/equipment/` | 6 files, PV/wind/battery/water/processing/failure | ✅ Complete |
| 4. Price Time-Series | `data/prices/` | Crops, electricity, water, diesel; EGP→USD conversion | ✅ Complete |
| 5. Labor Parameters | `data/parameters/labor/` | Requirements and wages | ✅ Complete |
| 6. Community Parameters | `data/parameters/community/` | 20 farms, land allocation | ✅ Complete |
| 7. Cost Parameters | `data/parameters/costs/` | Capital and operating costs | ✅ Complete |
| 8. PV/Wind Power | `data/precomputed/power/` | Normalized kWh/kW, uses weather data | ✅ Complete |
| 9. Irrigation/Yields | `data/precomputed/irrigation_demand/` + `crop_yields/` | 5 crops × planting dates | ✅ Complete |
| 10. Water Treatment | `data/precomputed/water_treatment/` | Energy curves by salinity | ✅ Complete |
| 11. Microclimate | `data/precomputed/microclimate/` | PV shade adjustments | ✅ Complete |

## Output Format

For each task, report:
```
## Task N: [Name]
- **Status**: Complete / Incomplete / Partial
- **Files Found**: [list]
- **Format Compliance**: Pass / Fail (details)
- **Data Quality**: Pass / Fail (specific issues)
- **Research Gaps**: [any additional data sources or refinements needed]
```

## Final Summary

After validating all tasks, provide:
1. Overall completion status
2. Critical issues requiring immediate attention
3. Recommended research priorities to improve data realism
4. Any dependencies between tasks that may have issues

Start by reading the orchestration document, then systematically validate each task.
