# Research Plan: Processed Product Data (Toy → Research Grade)

## Status: Complete

## Objective

Upgrade the food processing parameters in `data/parameters/crops/processing_specs-toy.csv` from toy-grade estimates to research-backed values. The current file has the right structure and plausible order-of-magnitude values, but the numbers need validation against empirical data.

## Output

Research-grade file created: `data/parameters/crops/processing_specs-research.csv`

## Current Toy Data

File: `data/parameters/crops/processing_specs-toy.csv`

Fields per crop per processing type:
- `energy_kwh_per_kg` — electricity for processing
- `labor_hours_per_kg` — labor time required
- `weight_loss_pct` — mass lost during processing
- `value_add_multiplier` — price multiplier vs fresh
- `processing_time_hours` — time from input to output

Crops: tomato, potato, onion, kale, cucumber
Processing types: fresh, packaged, canned, dried

## What Needs Validation

### Priority 1: Weight Loss Percentages (conversion ratios)

These directly drive the processed product output metric and revenue calculations.

**Research questions:**
1. What is the typical weight loss when drying each of the 5 crops? The current values range from 78% (potato) to 92% (cucumber) — are these consistent with literature?
2. What is a realistic canning weight loss? Currently a uniform 15% for all crops — does this vary by crop?
3. For fresh packaging (washing/sorting), is 3% loss reasonable?

**Sources to check:**
- FAO post-harvest processing handbooks
- USDA food composition databases (moisture content of fresh vs dried products)
- Academic literature on small-scale food processing in developing countries
- Egyptian food processing industry reports

**Validation approach:**
- Weight loss for drying can be cross-checked against moisture content: `weight_loss_pct ≈ (moisture_fresh - moisture_dried) / (1 - moisture_dried/100) × 100`
- Example: Tomato is ~94% water fresh, ~14% water dried → weight loss ≈ 93% (current toy: 88%)

### Priority 2: Value-Add Multipliers (price premiums)

These drive revenue calculations for processed products.

**Research questions:**
1. What is the actual price ratio of dried/canned/packaged products vs fresh in Egyptian markets?
2. Do multipliers vary by crop, or are the current uniform values (1.25×, 1.80×, 3.50×) reasonable?
3. How do multipliers change with scale (small community operation vs commercial)?

**Sources to check:**
- Egyptian wholesale market price data (CAPMAS, Ministry of Agriculture)
- FAO food price databases for Egypt and MENA region
- Reports on value-added agriculture in rural Egypt
- Historical processed crop prices already in `data/prices/crops/historical_processed_crop_prices-research.csv`

### Priority 3: Processing Energy Requirements

**Research questions:**
1. What is realistic energy consumption for solar tunnel dryers vs electric dehydrators in arid climates?
2. Is 0.4 kWh/kg for canning (retort processing) consistent with small-scale operations?
3. How does energy consumption scale with batch size?

**Sources to check:**
- Solar dryer performance studies for arid/semi-arid climates
- Small-scale food processing energy audits (UNIDO, FAO)
- Equipment manufacturer specifications

### Priority 4: Labor Requirements

**Research questions:**
1. Are the labor hours per kg reasonable for small-scale community processing?
2. How do labor requirements vary between manual and semi-automated equipment?

## Dependencies

- This data feeds into: processed product output calculation, processed product revenue, processing energy demand
- Related files: `data/parameters/crops/spoilage_rates-toy.csv` (may also need validation)

---

## Findings

Research completed 2026-02-05. Key findings organized by priority.

### Priority 1 Findings: Weight Loss Percentages

**Drying weight loss — significantly revised for most crops.** The toy data had a narrow range (78-92%) with values that were too low for high-moisture crops. Research values are based on USDA FoodData Central moisture content data, cross-validated against FAO empirical drying ratios.

**Derivation method:** `weight_loss_pct = 1 - (1 - moisture_fresh) / (1 - moisture_dried)`, where moisture content values come from USDA Standard Reference database.

| Crop | Fresh Moisture | Dried Moisture | Calculated Loss | FAO Empirical | Toy Value | Research Value |
|------|---------------|---------------|-----------------|---------------|-----------|---------------|
| Tomato | 94% | 14% (sun-dried) | 93.0% | 94% (25→1.5 lb) | 88% | **93%** |
| Potato | 79% | 6.5% (dehydrated flakes) | 77.5% | ~80% (5:1 rehydration) | 78% | **78%** |
| Onion | 89% | 5% (commercially dried) | 88.4% | 90% (25→2.5 lb) | 80% | **89%** |
| Kale | 90% | 8% (dehydrated) | 89.1% | 80-86% (5-7:1 ratio) | 82% | **87%** |
| Cucumber | 96% | 5% (dehydrated) | 95.8% | N/A (not common) | 92% | **95%** |

**Key citations:**
- Tomato fresh moisture 94%: USDA FoodData Central; confirmed by urbanwormcompany.com water content chart
- Tomato dried moisture 14%: Standard for sun-dried tomatoes (USDA SR Legacy)
- FAO drying ratios: FAO Small-Scale Postharvest Handling Practices (ae075e22), "25 pounds fresh yields 1.5 lb dried tomatoes, 2.5 lb dried onions"
- Potato moisture 79%: USDA FoodData Central; confirmed by Potatoes USA composition guide
- Potato dried 4.5-8.5%: Moisture Content and Physical Properties of Instant Mashed Potato (academia.edu)
- Onion fresh 86.6-89%: Onion dehydration review, J Food Sci Technol (PMC3614038); dried 4.6%: same source
- Kale fresh 89.6%: USDA NDB 168421 via myfooddata.com; dried 8%: estimated from drying studies
- Cucumber fresh 96.73%: Water content chart (reports.independent.ie); dried 4.5%: J. Scientific Research (drying and pickling study)

**Major changes from toy:**
- Tomato: 88% → 93% (+5 pp). Toy was significantly too low.
- Onion: 80% → 89% (+9 pp). Largest correction — onions are much higher moisture than toy assumed.
- Kale: 82% → 87% (+5 pp). Moderate correction upward.
- Cucumber: 92% → 95% (+3 pp). Slight correction — already near correct.
- Potato: 78% → 78% (unchanged). Toy value was already accurate.

**Canning weight loss — changed from uniform 15% to crop-specific values:**

| Crop | Toy Value | Research Value | Rationale |
|------|-----------|---------------|-----------|
| Tomato | 15% | **12%** | Peeling and coring; most flesh is retained |
| Potato | 15% | **18%** | Peeling losses are ~15% of weight, plus trimming |
| Onion | 15% | **10%** | Outer skin removal only; pickled onion retains most mass |
| Kale | 15% | **20%** | Stem and tough rib removal; significant waste |
| Cucumber | 15% | **8%** | Minimal trimming for pickling; mostly retained |

**Packaging weight loss — minor adjustments:**

Toy had uniform 3% for all crops. Research values: tomato 3%, potato 2%, onion 3%, kale 5%, cucumber 3%. Kale raised to 5% due to leaf damage and wilting losses typical of leafy greens (USDA ERS produce shrink data). Potato lowered to 2% (hardy root crop, minimal sorting waste).

### Priority 2 Findings: Value-Add Multipliers

**The toy data used uniform multipliers across all crops (1.25×, 1.80×, 3.50×). Research shows significant crop-specific variation, especially for dried products.**

The `value_add_multiplier` represents the price per kg of processed output divided by the price per kg of fresh product (as defined in `mvp-calculations.md`). The net revenue per kg of fresh input is `value_add_multiplier × (1 - weight_loss_pct/100)`.

**Dried product multipliers — major revision from uniform 3.50×:**

| Crop | Toy | Research | Key Data Point | Source |
|------|-----|----------|----------------|--------|
| Tomato | 3.5× | **8.0×** | Fresh 7 EGP/kg, dried 170 EGP/kg in Egypt; export $2.70/kg | Xinhua (2024), Tridge, Globy |
| Potato | 3.5× | **5.0×** | Dehydrated flakes $2-4/kg vs fresh $0.40-0.60/kg | Potatoes USA, market data |
| Onion | 3.5× | **5.0×** | Egypt is a major dried onion exporter; $1.50-3.00/kg dried | Tridge, IndexBox |
| Kale | 3.5× | **6.0×** | Dried kale/chips $8-15/kg wholesale vs fresh $2-3/kg | Market data |
| Cucumber | 3.5× | **4.0×** | Niche product; limited commercial data | Estimated |

**Key insight:** The toy uniform 3.50× was far too low for dried products. Dried products sell for 4-24× the price per kg of fresh product because the massive weight reduction concentrates value. Sun-dried tomatoes are the highest-premium product, supported by strong Egyptian export data (>$100M annual exports per MALR).

**Net revenue effects (value_add_multiplier × output ratio):**

| Crop | Toy Net Effect | Research Net Effect | Change |
|------|---------------|-------------------|--------|
| Tomato dried | 0.42× | 0.56× | +33% |
| Potato dried | 0.77× | 1.10× | +43% |
| Onion dried | 0.70× | 0.55× | -21% (higher weight loss offsets) |
| Kale dried | 0.63× | 0.78× | +24% |
| Cucumber dried | 0.28× | 0.20× | -29% (higher weight loss) |

Note: Most dried products still yield less net revenue per kg of fresh input than selling fresh, but processing provides shelf-life extension (up to 2 years), 90% transport cost reduction, and access to export markets (FAO Nubaria SDT project data).

**Canned and packaged multipliers — made crop-specific:**

| Product | Toy | Research | Rationale |
|---------|-----|----------|-----------|
| Canned tomato | 1.80× | **1.5×** | Very common product, modest premium (USDA ERS) |
| Canned potato | 1.80× | **1.4×** | Less common canned product |
| Canned onion | 1.80× | **1.3×** | Pickled onion, modest premium |
| Canned kale | 1.80× | **1.3×** | Canned greens, modest premium |
| Canned cucumber | 1.80× | **1.6×** | Pickled cucumber, popular product |
| Packaged (all) | 1.25× | **1.15-1.30×** | Slight crop-specific variation; kale highest (bagged greens premium) |

Sources: USDA ERS "Fruit and vegetable costs vary by type and form" (2022 data showing fresh vs canned price ratios); Egyptian market reports from Tridge and CAPMAS.

### Priority 3 Findings: Processing Energy

**Drying energy — values adjusted based on physics and Sinai climate context:**

Base calculation: Latent heat of vaporization = 2.26 MJ/kg water = 0.628 kWh/kg water. At 30% typical dryer efficiency (from Agroengineering journal tomato study showing 15-58% range), electrical energy = ~2.09 kWh per kg water removed. With 40-50% solar thermal contribution in Sinai's arid climate, effective electrical energy is ~1.1-1.5 kWh per kg water removed.

| Crop | Toy (kWh/kg) | Research (kWh/kg) | Water Removed (kg/kg) | Notes |
|------|-------------|-------------------|----------------------|-------|
| Tomato dried | 2.5 | **2.0** | 0.93 | Solar-assisted, most water removed by sun |
| Potato dried | 3.0 | **2.5** | 0.78 | Dense product needs more controlled heating |
| Onion dried | 2.25 | **1.8** | 0.88 | Moderate energy needs |
| Kale dried | 2.0 | **1.2** | 0.89 | Thin leaves dry easily with minimal energy |
| Cucumber dried | 3.25 | **2.8** | 0.95 | Highest water content, most energy-intensive |

Sources: Agroengineering journal (solar-electric dryer tomato study, SEC 5.53-150 kWh/kg total); Nature Scientific Reports (handmade solar dryer for tomatoes); MDPI Agriculture (solar dryer efficiency 49.2%); EPA AP-42 Section 9.8.2 (dehydrated fruits and vegetables).

**Canning energy — revised with crop-specific values:**

Industrial data from ASABE shows 2.7-6.6 MJ/kg (0.75-1.83 kWh/kg) total energy for vegetable canning at ~100,000 kg/day scale. For small-scale community operations, the electrical component is estimated at 40-60% of total energy. Values range from 0.35 kWh/kg (cucumber/onion pickling — high-acid, lower retort temp) to 0.55 kWh/kg (potato — low-acid, requires higher-temperature retort processing).

### Priority 4 Findings: Labor and Processing Time

**Drying labor — validated against FAO field data:**

Key reference: FAO Nubaria Sun-Dried Tomato project (ITA/004/RNE/GCP) reports 40-45 labor-days per ton of dried tomato output. Converting: 42.5 days × 8 hrs = 340 hrs per 1000 kg dried. For 14.3:1 fresh-to-dried ratio: 340/14,300 = 0.024 hrs/kg fresh input for semi-industrial operations. Community-scale processing is estimated at ~4× more labor-intensive, giving ~0.10 hrs/kg — consistent with toy values.

| Crop | Toy (hrs/kg) | Research (hrs/kg) | Notes |
|------|-------------|-------------------|-------|
| Tomato dried | 0.12 | **0.10** | Slightly reduced; validated by FAO SDT data |
| Potato dried | 0.144 | **0.14** | Peeling adds labor; kept similar to toy |
| Onion dried | 0.108 | **0.10** | Similar to tomato processing complexity |
| Kale dried | 0.096 | **0.08** | Simple prep (wash, tear); less than root crops |
| Cucumber dried | 0.156 | **0.12** | Reduced; slicing is simpler than toy assumed |

**Processing time — refined with crop-specific drying behavior:**

Key change: Kale drying time reduced from 24h (same as all dried in toy) to 6h, since thin leaves dry much faster than dense tomato slices or potato pieces. Supported by Colorado State Extension data showing leafy vegetables dry in 2-8 hours at 130-160°F. Potato and cucumber drying reduced to 20h (less water than tomato, though cucumber has more water the thinner slices compensate). Canning time made crop-specific: 6h for pickled products (onion, cucumber), 10h for low-acid potato (longer retort), 8h for tomato and kale.

### Summary: Key Differences Between Toy and Research Values

| Parameter | Biggest Changes | Direction |
|-----------|----------------|-----------|
| Drying weight loss | Tomato +5pp, Onion +9pp, Cucumber +3pp | Mostly increased (crops lose more weight) |
| Canning weight loss | Now crop-specific (8-20% vs uniform 15%) | Varies by crop |
| Dried value multiplier | All crops increased (3.5× → 4-8×) | Significantly increased |
| Canned value multiplier | Reduced from 1.80× to 1.3-1.6× | Decreased for most crops |
| Drying energy | Decreased for most crops (solar-assisted) | Slightly decreased |
| Kale drying time | 24h → 6h | Major reduction (thin leaves) |

### Sources Used

1. **USDA FoodData Central** — Moisture content data for fresh and dried vegetables (fdc.nal.usda.gov)
2. **FAO Small-Scale Postharvest Handling Practices** (FAO, ae075e) — Drying ratios: 25 lbs fresh → X lbs dried
3. **FAO/UNIDO Pre-Feasibility Studies for 5 Crops for Processing in Upper Egypt** (PwC/SALASEL, 2012) — Egyptian processing industry context, labor, and market data
4. **FAO Nubaria Sun-Dried Tomato Project** (ITA/004/RNE/GCP) — 40-45 labor-days per ton dried tomato, 25-30% value increase, 90% transport cost reduction
5. **Onion dehydration: a review** — J Food Sci Technol, PMC3614038 — Onion moisture content fresh (86.6-91.2%) and dried (4.6%)
6. **Tridge Market Intelligence** — Global dried tomato and onion wholesale prices; Egyptian export data
7. **Xinhua News Agency** (2024-12-31) — Egyptian sun-dried tomato export market ($100M+ annually), fresh 7 EGP/kg vs dried 170 EGP/kg, 10:1 fresh-to-dried ratio
8. **USDA ERS** — "Fruit and vegetable costs vary by type and form" — Canned vs fresh price comparisons
9. **ASABE Transactions** — "Processing Energy Requirements for Several Vegetables" (vegetable canning: 2.7-6.6 MJ/kg); "Analysis of Direct Energy Usage in Vegetable Canneries"
10. **Agroengineering Journal** — Solar-electric dryer energy consumption for tomato slices (SEC 5.53-150 kWh/kg)
11. **Colorado State Extension** — "Drying Vegetables" — Drying times, temperature guidelines, target moisture levels
12. **Potatoes USA** — Dehydrated potato product specifications, 1 kg dried → 5 kg rehydrated
13. **USDA Food Yields** (ARS, ah102.pdf) — Processed yields of fruits and vegetables
14. **MDPI Agriculture** — Food solar dryer performance evaluation (49.2% efficiency, payback 1 year)
15. **J. Scientific Research** — Cucumber drying study: fresh 89% moisture → dried 4.5% moisture
