# Metrics calculator for Water Simulation MVP
# Layer 3: Simulation Engine
#
# Computes yearly output metrics from simulation results:
# 1. Total water use (m3)
# 2. Water use per yield (m3/kg) - by crop and total
# 3. Water cost per unit (USD/m3)
# 4. Self-sufficiency percentage (groundwater / total water)

import datetime
import math
from dataclasses import dataclass, field


@dataclass
class ComputedYearlyMetrics:
    """Computed metrics for one farm for one year.

    Derived from YearlyFarmMetrics with additional calculated values.
    """
    year: int
    farm_id: str
    farm_name: str
    water_policy: str

    # Volume metrics
    total_water_m3: float
    groundwater_m3: float
    municipal_m3: float

    # Yield metrics
    total_yield_kg: float

    # Cost metrics
    total_water_cost_usd: float
    
    # Revenue metrics
    total_crop_revenue_usd: float

    # Computed ratios
    water_per_yield_m3_kg: float  # total_water / total_yield
    cost_per_m3_usd: float  # total_cost / total_water
    self_sufficiency_pct: float  # groundwater / total_water * 100

    # Per-crop metrics
    crop_water_per_yield: dict = field(default_factory=dict)  # {crop: m3/kg}

    # Resilience metrics (mvp-structure.md Section 4)
    aquifer_depletion_rate_m3_yr: float = 0.0
    aquifer_years_remaining: float = float('inf')
    days_without_municipal_water: int = 0

    # Aquifer drawdown feedback metrics (mvp-calculations.md Section 2)
    effective_pumping_head_m: float = 0.0  # Current effective head including drawdown
    drawdown_m: float = 0.0  # Additional head from depletion

    # Efficiency metrics
    water_storage_utilization_pct: float = 0.0
    irrigation_demand_gap_m3: float = 0.0
    irrigation_delivery_ratio: float = 1.0

    # Diversity
    crop_diversity_index: float = 0.0

    # Financial metrics (from infrastructure financing model)
    total_infrastructure_cost_usd: float = 0.0
    debt_service_usd: float = 0.0
    total_operating_expense_usd: float = 0.0
    net_income_usd: float = 0.0
    cash_reserves_usd: float = 0.0
    operating_margin_pct: float = 0.0
    debt_to_revenue_ratio: float = 0.0

    # Financial performance (simulation-level, same for all farms/years)
    npv_usd: float = 0.0
    irr_pct: float = 0.0  # as percentage
    payback_years: float = float('inf')
    roi_pct: float = 0.0
    cash_reserve_adequacy_months: float = 0.0

    # Energy metrics (community-level, same for all farms in a year)
    pv_generation_kwh: float = 0.0
    wind_generation_kwh: float = 0.0
    total_renewable_kwh: float = 0.0
    grid_import_kwh: float = 0.0
    grid_export_kwh: float = 0.0
    generator_kwh: float = 0.0
    generator_fuel_L: float = 0.0
    battery_throughput_kwh: float = 0.0
    curtailment_kwh: float = 0.0
    energy_self_sufficiency_pct: float = 0.0
    days_without_grid: int = 0
    blended_electricity_cost_usd_kwh: float = 0.0

    # Food processing metrics (from YearlyFarmMetrics)
    fresh_revenue_usd: float = 0.0
    processed_revenue_usd: float = 0.0
    processed_output_kg: float = 0.0
    post_harvest_loss_kg: float = 0.0

    # Labor metrics (from scenario infrastructure and area)
    total_labor_hours: float = 0.0
    field_labor_hours: float = 0.0
    processing_labor_hours: float = 0.0
    maintenance_labor_hours: float = 0.0
    admin_labor_hours: float = 0.0
    fte_count: float = 0.0
    total_labor_cost_usd: float = 0.0


@dataclass
class MonthlyFarmMetrics:
    """Monthly metrics for one farm for one month."""
    year: int
    month: int
    farm_id: str
    farm_name: str
    water_policy: str

    # Volume metrics
    total_water_m3: float
    groundwater_m3: float
    municipal_m3: float
    
    # Agricultural vs community water (for now, all is agricultural)
    agricultural_water_m3: float

    # Cost metrics
    total_water_cost_usd: float

    # Yield metrics (crops harvested this month)
    total_yield_kg: float

    # Revenue metrics (crops harvested this month)
    total_crop_revenue_usd: float

    # Computed ratios
    self_sufficiency_pct: float

    # Fields with defaults must come last
    community_water_m3: float = 0.0
    crop_yields_kg: dict = field(default_factory=dict)  # {crop: kg}
    crop_revenues_usd: dict = field(default_factory=dict)  # {crop: usd}
    energy_cost_usd: float = 0.0
    diesel_cost_usd: float = 0.0
    fertilizer_cost_usd: float = 0.0
    labor_cost_usd: float = 0.0
    total_operating_cost_usd: float = 0.0


@dataclass
class CommunityYearlyMetrics:
    """Aggregated metrics for entire community for one year."""
    year: int

    # Volume totals
    total_water_m3: float
    total_groundwater_m3: float
    total_municipal_m3: float

    # Yield totals
    total_yield_kg: float

    # Cost totals
    total_water_cost_usd: float

    # Computed averages
    avg_water_per_yield_m3_kg: float
    avg_cost_per_m3_usd: float
    community_self_sufficiency_pct: float

    # Per-farm breakdown
    farm_metrics: list = field(default_factory=list)


def compute_yearly_metrics(yearly_farm_metrics):
    """Compute derived metrics from raw yearly farm metrics.

    Args:
        yearly_farm_metrics: YearlyFarmMetrics from simulation

    Returns:
        ComputedYearlyMetrics with calculated ratios
    """
    m = yearly_farm_metrics

    # Calculate ratios (with zero-division protection)
    if m.total_water_m3 > 0:
        cost_per_m3 = m.total_water_cost_usd / m.total_water_m3
        self_sufficiency = 100 * m.groundwater_m3 / m.total_water_m3
    else:
        cost_per_m3 = 0.0
        self_sufficiency = 0.0

    if m.total_yield_kg > 0:
        water_per_yield = m.total_water_m3 / m.total_yield_kg
    else:
        water_per_yield = 0.0

    # Calculate per-crop water efficiency
    crop_water_per_yield = {}
    for crop_name, water_m3 in m.crop_water_m3.items():
        yield_kg = m.crop_yield_kg.get(crop_name, 0)
        if yield_kg > 0:
            crop_water_per_yield[crop_name] = water_m3 / yield_kg
        else:
            crop_water_per_yield[crop_name] = 0.0

    return ComputedYearlyMetrics(
        year=m.year,
        farm_id=m.farm_id,
        farm_name=m.farm_name,
        water_policy=m.water_policy,
        total_water_m3=m.total_water_m3,
        groundwater_m3=m.groundwater_m3,
        municipal_m3=m.municipal_m3,
        total_yield_kg=m.total_yield_kg,
        total_water_cost_usd=m.total_water_cost_usd,
        total_crop_revenue_usd=m.total_crop_revenue_usd,
        water_per_yield_m3_kg=water_per_yield,
        cost_per_m3_usd=cost_per_m3,
        self_sufficiency_pct=self_sufficiency,
        crop_water_per_yield=crop_water_per_yield,
        # Food processing metrics
        fresh_revenue_usd=m.fresh_revenue_usd,
        processed_revenue_usd=m.processed_revenue_usd,
        processed_output_kg=m.processed_output_kg,
        post_harvest_loss_kg=m.post_harvest_loss_kg,
    )


def compute_monthly_metrics(simulation_state, data_loader=None, scenario=None):
    """Compute monthly metrics from daily water records and crop harvests.

    Args:
        simulation_state: SimulationState with daily_water_records and crops
        data_loader: Optional SimulationDataLoader for cost lookups (fertilizer, labor)
        scenario: Optional Scenario (reserved for future use)

    Returns:
        list of MonthlyFarmMetrics
    """
    monthly_metrics = []

    for farm in simulation_state.farms:
        farm_area_ha = farm.area_ha

        # Group daily records by year-month
        monthly_data = {}  # {(year, month): {water_m3, gw_m3, cost_usd, ...}}

        for record in farm.daily_water_records:
            key = (record.date.year, record.date.month)
            if key not in monthly_data:
                monthly_data[key] = {
                    "water_m3": 0.0,
                    "groundwater_m3": 0.0,
                    "municipal_m3": 0.0,
                    "cost_usd": 0.0,
                    "energy_cost_usd": 0.0,
                }
            monthly_data[key]["water_m3"] += record.groundwater_m3 + record.municipal_m3
            monthly_data[key]["groundwater_m3"] += record.groundwater_m3
            monthly_data[key]["municipal_m3"] += record.municipal_m3
            monthly_data[key]["cost_usd"] += record.cost_usd
            monthly_data[key]["energy_cost_usd"] += record.energy_cost_usd

        # Group crop harvests by year-month
        monthly_harvests = {}  # {(year, month): {yield_kg, revenue_usd, by_crop}}
        for crop in farm.crops:
            if crop.is_harvested:
                key = (crop.harvest_date.year, crop.harvest_date.month)
                if key not in monthly_harvests:
                    monthly_harvests[key] = {
                        "yield_kg": 0.0,
                        "revenue_usd": 0.0,
                        "crop_yields": {},
                        "crop_revenues": {},
                    }
                monthly_harvests[key]["yield_kg"] += crop.harvest_yield_kg
                monthly_harvests[key]["revenue_usd"] += crop.harvest_revenue_usd
                
                # Track by crop
                if crop.crop_name not in monthly_harvests[key]["crop_yields"]:
                    monthly_harvests[key]["crop_yields"][crop.crop_name] = 0.0
                    monthly_harvests[key]["crop_revenues"][crop.crop_name] = 0.0
                monthly_harvests[key]["crop_yields"][crop.crop_name] += crop.harvest_yield_kg
                monthly_harvests[key]["crop_revenues"][crop.crop_name] += crop.harvest_revenue_usd

        # Create monthly metrics for all months with data
        all_months = set(monthly_data.keys()) | set(monthly_harvests.keys())
        for year, month in sorted(all_months):
            water_data = monthly_data.get((year, month), {
                "water_m3": 0.0, "groundwater_m3": 0.0, "municipal_m3": 0.0,
                "cost_usd": 0.0, "energy_cost_usd": 0.0,
            })
            harvest_data = monthly_harvests.get((year, month), {
                "yield_kg": 0.0, "revenue_usd": 0.0, "crop_yields": {}, "crop_revenues": {}
            })

            total_water = water_data["water_m3"]
            groundwater = water_data["groundwater_m3"]
            self_suff = (100 * groundwater / total_water) if total_water > 0 else 0.0

            # Cost category breakdown
            energy_cost = water_data["energy_cost_usd"]
            diesel_cost = 0.0  # Not yet tracked

            if data_loader is not None:
                fertilizer_annual = data_loader.get_fertilizer_cost_usd_ha(
                    datetime.date(year, 1, 1)
                )
                fertilizer_monthly = fertilizer_annual * farm_area_ha / 12.0
                labor_monthly = data_loader.get_labor_cost_usd_ha_month() * farm_area_ha
            else:
                fertilizer_monthly = 0.0
                labor_monthly = 0.0

            # --- Energy cost separation (L3 clarity fix) ---
            # water_data["cost_usd"] comes from allocation.cost_usd which BUNDLES
            # the energy cost of water treatment (treatment kWh × electricity price)
            # into the overall water cost. For the operating cost breakdown we want
            # energy as a SEPARATE line item so it appears distinctly in cost charts
            # and tables.
            #
            # Strategy: subtract energy_cost from the bundled water cost to get the
            # "pure" water cost (municipal tariff + GW maintenance), then add energy
            # back as its own category. The net total is unchanged:
            #   total_operating = allocation.cost_usd + diesel + fertilizer + labor
            # because:  (cost_usd - energy) + energy = cost_usd
            water_cost_net = water_data["cost_usd"] - energy_cost
            total_operating = water_cost_net + energy_cost + diesel_cost + fertilizer_monthly + labor_monthly

            monthly_metrics.append(MonthlyFarmMetrics(
                year=year,
                month=month,
                farm_id=farm.farm_id,
                farm_name=farm.farm_name,
                water_policy=farm.water_policy_name,
                total_water_m3=total_water,
                groundwater_m3=groundwater,
                municipal_m3=water_data["municipal_m3"],
                agricultural_water_m3=total_water,  # All is agricultural for now
                community_water_m3=0.0,
                total_water_cost_usd=water_data["cost_usd"],
                total_yield_kg=harvest_data["yield_kg"],
                crop_yields_kg=harvest_data["crop_yields"],
                total_crop_revenue_usd=harvest_data["revenue_usd"],
                crop_revenues_usd=harvest_data["crop_revenues"],
                self_sufficiency_pct=self_suff,
                energy_cost_usd=energy_cost,
                diesel_cost_usd=diesel_cost,
                fertilizer_cost_usd=fertilizer_monthly,
                labor_cost_usd=labor_monthly,
                total_operating_cost_usd=total_operating,
            ))

    return monthly_metrics


def aggregate_community_metrics(yearly_farm_metrics_list, year):
    """Aggregate farm metrics into community-level metrics for a year.

    Args:
        yearly_farm_metrics_list: List of YearlyFarmMetrics for the year
        year: Year for the metrics

    Returns:
        CommunityYearlyMetrics
    """
    # Filter to specified year
    year_metrics = [m for m in yearly_farm_metrics_list if m.year == year]

    if not year_metrics:
        return None

    # Sum totals across farms
    total_water = sum(m.total_water_m3 for m in year_metrics)
    total_gw = sum(m.groundwater_m3 for m in year_metrics)
    total_muni = sum(m.municipal_m3 for m in year_metrics)
    total_yield = sum(m.total_yield_kg for m in year_metrics)
    total_cost = sum(m.total_water_cost_usd for m in year_metrics)

    # Calculate averages
    if total_water > 0:
        avg_cost_per_m3 = total_cost / total_water
        self_sufficiency = 100 * total_gw / total_water
    else:
        avg_cost_per_m3 = 0.0
        self_sufficiency = 0.0

    if total_yield > 0:
        avg_water_per_yield = total_water / total_yield
    else:
        avg_water_per_yield = 0.0

    # Compute individual farm metrics
    farm_metrics = [compute_yearly_metrics(m) for m in year_metrics]

    return CommunityYearlyMetrics(
        year=year,
        total_water_m3=total_water,
        total_groundwater_m3=total_gw,
        total_municipal_m3=total_muni,
        total_yield_kg=total_yield,
        total_water_cost_usd=total_cost,
        avg_water_per_yield_m3_kg=avg_water_per_yield,
        avg_cost_per_m3_usd=avg_cost_per_m3,
        community_self_sufficiency_pct=self_sufficiency,
        farm_metrics=farm_metrics,
    )


def _compute_spec_metrics(farm_metrics_list, simulation_state, scenario=None):
    """Enhance ComputedYearlyMetrics with spec-defined resilience/efficiency metrics.

    Computes metrics from mvp-structure.md Section 4 that depend on daily
    records, aquifer state, water storage, and crop configuration.  Mutates
    farm_metrics_list in place.

    Args:
        farm_metrics_list: List of ComputedYearlyMetrics to enhance
        simulation_state: SimulationState with farms, aquifer, water_storage
        scenario: Optional Scenario (reserved for future crop config access)
    """
    if not farm_metrics_list:
        return

    # ------------------------------------------------------------------
    # 1. Aquifer depletion rate and years remaining (community-level)
    #    Also compute drawdown feedback metrics (effective head, drawdown_m)
    # ------------------------------------------------------------------
    aquifer_depletion_rate = 0.0
    aquifer_years_remaining = float('inf')
    effective_pumping_head = 0.0
    current_drawdown = 0.0

    if simulation_state.aquifer is not None:
        years_elapsed = (
            (simulation_state.current_date - simulation_state.start_date).days
            / 365.25
        )
        if years_elapsed > 0:
            annual_extraction = (
                simulation_state.aquifer.cumulative_extraction_m3 / years_elapsed
            )
            aquifer_depletion_rate = max(
                0.0,
                annual_extraction - simulation_state.aquifer.recharge_rate_m3_yr,
            )
            aquifer_years_remaining = simulation_state.aquifer.get_years_remaining(
                years_elapsed
            )

        # Compute drawdown feedback metrics if scenario provides well depth
        current_drawdown = simulation_state.aquifer.get_current_drawdown_m()
        if scenario is not None and hasattr(scenario, 'infrastructure'):
            base_depth = scenario.infrastructure.groundwater_wells.well_depth_m
            effective_pumping_head = simulation_state.aquifer.get_effective_head_m(
                base_depth
            )
        elif current_drawdown > 0:
            # No scenario available; report drawdown alone
            effective_pumping_head = current_drawdown

    # ------------------------------------------------------------------
    # 2. Water storage utilization per year (community-level)
    # ------------------------------------------------------------------
    storage_util_by_year = {}  # {year: {"total": float, "count": int}}
    if (
        simulation_state.water_storage is not None
        and simulation_state.water_storage.daily_levels
    ):
        for entry in simulation_state.water_storage.daily_levels:
            year = entry["date"].year
            if year not in storage_util_by_year:
                storage_util_by_year[year] = {"total": 0.0, "count": 0}
            storage_util_by_year[year]["total"] += entry["utilization_pct"]
            storage_util_by_year[year]["count"] += 1

    # ------------------------------------------------------------------
    # 3. Per-farm, per-year daily-record metrics
    #    - Days without municipal water
    #    - Irrigation demand gap and delivery ratio
    # ------------------------------------------------------------------
    # Build lookup: {farm_id: {year: [DailyWaterRecord, ...]}}
    farm_year_records = {}
    for farm in simulation_state.farms:
        farm_year_records[farm.farm_id] = {}
        for record in farm.daily_water_records:
            year = record.date.year
            if year not in farm_year_records[farm.farm_id]:
                farm_year_records[farm.farm_id][year] = []
            farm_year_records[farm.farm_id][year].append(record)

    # ------------------------------------------------------------------
    # 4. Crop diversity index (Shannon index) per year
    #    H = -sum(p_i * ln(p_i))  where p_i = crop_area / total_area
    # ------------------------------------------------------------------
    crop_areas_by_year = {}  # {year: {crop_name: total_area_ha}}
    for farm in simulation_state.farms:
        for crop in farm.crops:
            year = crop.planting_date.year
            if year not in crop_areas_by_year:
                crop_areas_by_year[year] = {}
            if crop.crop_name not in crop_areas_by_year[year]:
                crop_areas_by_year[year][crop.crop_name] = 0.0
            crop_areas_by_year[year][crop.crop_name] += crop.area_ha

    diversity_by_year = {}
    for year, areas in crop_areas_by_year.items():
        total_area = sum(areas.values())
        if total_area > 0 and len(areas) > 1:
            proportions = [a / total_area for a in areas.values()]
            diversity_by_year[year] = -sum(
                p * math.log(p) for p in proportions if p > 0
            )
        else:
            diversity_by_year[year] = 0.0  # single crop or no area

    # ------------------------------------------------------------------
    # 5. Energy metrics from community-level energy dispatch
    # ------------------------------------------------------------------
    energy_metrics_by_year = {}
    if (
        simulation_state.energy is not None
        and simulation_state.energy.daily_energy_records
    ):
        # Group daily energy records by year
        energy_by_year = {}
        for rec in simulation_state.energy.daily_energy_records:
            year = rec.date.year
            if year not in energy_by_year:
                energy_by_year[year] = []
            energy_by_year[year].append(rec)

        # Pre-compute per-year energy metrics (community-level, applied to all farms)
        for year, records in energy_by_year.items():
            pv_gen = sum(r.pv_generation_kwh for r in records)
            wind_gen = sum(r.wind_generation_kwh for r in records)
            total_renewable = pv_gen + wind_gen
            grid_import = sum(r.grid_import_kwh for r in records)
            grid_export = sum(r.grid_export_kwh for r in records)
            gen_kwh = sum(r.generator_kwh for r in records)
            gen_fuel = sum(r.generator_fuel_L for r in records)
            batt_throughput = sum(
                r.battery_charge_kwh + r.battery_discharge_kwh for r in records
            )
            curtailment = sum(r.curtailment_kwh for r in records)
            total_demand = sum(r.total_demand_kwh for r in records)

            # Energy self-sufficiency: renewable used / total demand
            renewable_used = total_renewable - curtailment - grid_export
            if total_demand > 0 and renewable_used > 0:
                self_suff = min(100.0, (renewable_used / total_demand) * 100)
            else:
                self_suff = 0.0

            # Days without grid import (demand > 0 but no grid used)
            days_no_grid = sum(
                1 for r in records
                if r.grid_import_kwh == 0 and r.total_demand_kwh > 0
            )

            energy_metrics_by_year[year] = {
                "pv_generation_kwh": pv_gen,
                "wind_generation_kwh": wind_gen,
                "total_renewable_kwh": total_renewable,
                "grid_import_kwh": grid_import,
                "grid_export_kwh": grid_export,
                "generator_kwh": gen_kwh,
                "generator_fuel_L": gen_fuel,
                "battery_throughput_kwh": batt_throughput,
                "curtailment_kwh": curtailment,
                "energy_self_sufficiency_pct": self_suff,
                "days_without_grid": days_no_grid,
            }

    # ------------------------------------------------------------------
    # 6. Apply computed values to each ComputedYearlyMetrics object
    # ------------------------------------------------------------------
    for fm in farm_metrics_list:
        # Community-level: aquifer (same value for every farm & year)
        fm.aquifer_depletion_rate_m3_yr = aquifer_depletion_rate
        fm.aquifer_years_remaining = aquifer_years_remaining
        fm.effective_pumping_head_m = effective_pumping_head
        fm.drawdown_m = current_drawdown

        # Community-level: crop diversity (per year)
        fm.crop_diversity_index = diversity_by_year.get(fm.year, 0.0)

        # Community-level: water storage utilization (per year)
        if fm.year in storage_util_by_year:
            s = storage_util_by_year[fm.year]
            fm.water_storage_utilization_pct = s["total"] / s["count"]

        # Per-farm, per-year: daily-record metrics
        records = farm_year_records.get(fm.farm_id, {}).get(fm.year, [])
        if records:
            # Days without municipal water (only count days with nonzero demand)
            fm.days_without_municipal_water = sum(
                1 for r in records
                if r.municipal_m3 == 0 and r.demand_m3 > 0
            )

            # Irrigation demand vs delivery
            total_demand = sum(r.demand_m3 for r in records)
            total_delivered = sum(
                r.groundwater_m3 + r.municipal_m3 for r in records
            )
            fm.irrigation_demand_gap_m3 = max(0.0, total_demand - total_delivered)
            fm.irrigation_delivery_ratio = (
                total_delivered / total_demand if total_demand > 0 else 1.0
            )

    # ------------------------------------------------------------------
    # 6. Financial metrics from infrastructure financing model
    # ------------------------------------------------------------------
    if simulation_state.economic is not None:
        econ = simulation_state.economic
        total_area = sum(f.area_ha for f in simulation_state.farms)

        for fm in farm_metrics_list:
            # Allocate community infrastructure costs proportionally by area
            farm = next(
                (f for f in simulation_state.farms if f.farm_id == fm.farm_id),
                None,
            )
            if farm and total_area > 0:
                area_fraction = farm.area_ha / total_area
            else:
                area_fraction = 1.0 / max(1, len(simulation_state.farms))

            fm.total_infrastructure_cost_usd = (
                econ.total_annual_infrastructure_cost_usd * area_fraction
            )
            fm.debt_service_usd = (
                econ.total_annual_debt_service_usd * area_fraction
            )

            # Total operating expense = water cost + infrastructure cost share
            fm.total_operating_expense_usd = (
                fm.total_water_cost_usd + fm.total_infrastructure_cost_usd
            )

            # Net income = crop revenue - operating expense
            fm.net_income_usd = (
                fm.total_crop_revenue_usd - fm.total_operating_expense_usd
            )

            # Operating margin (% of revenue)
            if fm.total_crop_revenue_usd > 0:
                fm.operating_margin_pct = (
                    fm.net_income_usd / fm.total_crop_revenue_usd
                ) * 100

            # Debt-to-revenue ratio
            if fm.total_crop_revenue_usd > 0:
                fm.debt_to_revenue_ratio = (
                    fm.debt_service_usd / fm.total_crop_revenue_usd
                )

            # Cash reserves (community-level, same for all farms)
            fm.cash_reserves_usd = econ.cash_reserves_usd

        # Community-level: energy metrics (per year, same for all farms)
        em = energy_metrics_by_year.get(fm.year)
        if em:
            fm.pv_generation_kwh = em["pv_generation_kwh"]
            fm.wind_generation_kwh = em["wind_generation_kwh"]
            fm.total_renewable_kwh = em["total_renewable_kwh"]
            fm.grid_import_kwh = em["grid_import_kwh"]
            fm.grid_export_kwh = em["grid_export_kwh"]
            fm.generator_kwh = em["generator_kwh"]
            fm.generator_fuel_L = em["generator_fuel_L"]
            fm.battery_throughput_kwh = em["battery_throughput_kwh"]
            fm.curtailment_kwh = em["curtailment_kwh"]
            fm.energy_self_sufficiency_pct = em["energy_self_sufficiency_pct"]
            fm.days_without_grid = em["days_without_grid"]

    # ------------------------------------------------------------------
    # 7. Labor metrics from scenario configuration
    #    Labor is relatively static (based on area and infrastructure,
    #    not daily operations). Field and maintenance labor are computed
    #    once from the scenario and distributed to farms by area fraction.
    #    Processing labor uses actual per-farm processed output.
    # ------------------------------------------------------------------
    if scenario is not None:
        from src.settings.calculations import (
            calculate_labor_requirements,
            LABOR_PROCESSING_HRS_PER_KG,
            LABOR_ADMIN_FRACTION,
            LABOR_FTE_HOURS,
            LABOR_HOURLY_RATE_USD,
        )

        # Compute base labor (field + maintenance) once from scenario
        base_labor = calculate_labor_requirements(scenario, processed_output_kg=0.0)
        total_area = sum(f.area_ha for f in simulation_state.farms)

        for fm in farm_metrics_list:
            # Determine farm's share of community labor
            farm = next(
                (f for f in simulation_state.farms if f.farm_id == fm.farm_id),
                None,
            )
            if farm and total_area > 0:
                area_fraction = farm.area_ha / total_area
            else:
                area_fraction = 1.0 / max(1, len(simulation_state.farms))

            # Field and maintenance labor distributed by area
            field_hrs = base_labor["field_labor_hrs"] * area_fraction
            maintenance_hrs = base_labor["maintenance_labor_hrs"] * area_fraction

            # Processing labor from actual processed output for this farm/year
            processing_hrs = fm.processed_output_kg * LABOR_PROCESSING_HRS_PER_KG

            # Admin: 5% of all other labor
            admin_hrs = (
                (field_hrs + processing_hrs + maintenance_hrs) * LABOR_ADMIN_FRACTION
            )

            total_hrs = field_hrs + processing_hrs + maintenance_hrs + admin_hrs

            fm.total_labor_hours = round(total_hrs, 1)
            fm.field_labor_hours = round(field_hrs, 1)
            fm.processing_labor_hours = round(processing_hrs, 1)
            fm.maintenance_labor_hours = round(maintenance_hrs, 1)
            fm.admin_labor_hours = round(admin_hrs, 1)
            fm.fte_count = round(total_hrs / LABOR_FTE_HOURS, 2)
            fm.total_labor_cost_usd = round(total_hrs * LABOR_HOURLY_RATE_USD, 2)


def compute_all_metrics(simulation_state, data_loader=None, scenario=None):
    """Compute all metrics from simulation results.

    Args:
        simulation_state: SimulationState with yearly_metrics
        data_loader: Optional SimulationDataLoader for cost lookups
        scenario: Optional Scenario (reserved for future use)

    Returns:
        dict: {
            'farm_metrics': [ComputedYearlyMetrics],
            'community_metrics': [CommunityYearlyMetrics],
            'monthly_metrics': [MonthlyFarmMetrics],
            'years': [int]
        }
    """
    # Get all years in the simulation
    years = sorted(set(m.year for m in simulation_state.yearly_metrics))

    # Compute per-farm metrics
    farm_metrics = [
        compute_yearly_metrics(m) for m in simulation_state.yearly_metrics
    ]

    # Enhance farm metrics with spec-defined resilience/efficiency metrics
    # (aquifer, storage utilization, demand gap, diversity index, etc.)
    _compute_spec_metrics(farm_metrics, simulation_state, scenario=scenario)

    # Compute community metrics per year
    community_metrics = []
    for year in years:
        cm = aggregate_community_metrics(simulation_state.yearly_metrics, year)
        if cm:
            community_metrics.append(cm)

    # Compute monthly metrics (with cost categories if data_loader provided)
    monthly_metrics = compute_monthly_metrics(
        simulation_state, data_loader=data_loader, scenario=scenario
    )

    result = {
        "farm_metrics": farm_metrics,
        "community_metrics": community_metrics,
        "monthly_metrics": monthly_metrics,
        "years": years,
        "financial_performance": None,
    }

    # Compute financial performance if economic state and scenario are available
    if simulation_state.economic is not None and scenario is not None:
        result["financial_performance"] = compute_financial_performance(
            result, simulation_state, scenario
        )

    return result


def summarize_farm(farm_metrics_list):
    """Generate summary statistics for a farm across all years.

    Args:
        farm_metrics_list: List of ComputedYearlyMetrics for one farm

    Returns:
        dict with summary statistics
    """
    if not farm_metrics_list:
        return {}

    n = len(farm_metrics_list)
    total_water = sum(m.total_water_m3 for m in farm_metrics_list)
    total_yield = sum(m.total_yield_kg for m in farm_metrics_list)
    total_cost = sum(m.total_water_cost_usd for m in farm_metrics_list)
    total_gw = sum(m.groundwater_m3 for m in farm_metrics_list)

    return {
        "farm_id": farm_metrics_list[0].farm_id,
        "farm_name": farm_metrics_list[0].farm_name,
        "water_policy": farm_metrics_list[0].water_policy,
        "years": n,
        "total_water_m3": total_water,
        "total_yield_kg": total_yield,
        "total_cost_usd": total_cost,
        "total_groundwater_m3": total_gw,
        "avg_water_per_year_m3": total_water / n if n > 0 else 0,
        "avg_yield_per_year_kg": total_yield / n if n > 0 else 0,
        "avg_cost_per_year_usd": total_cost / n if n > 0 else 0,
        "overall_water_per_yield_m3_kg": total_water / total_yield if total_yield > 0 else 0,
        "overall_cost_per_m3_usd": total_cost / total_water if total_water > 0 else 0,
        "overall_self_sufficiency_pct": 100 * total_gw / total_water if total_water > 0 else 0,
    }


def compare_policies(all_metrics):
    """Generate policy comparison summary.

    Args:
        all_metrics: Output from compute_all_metrics()

    Returns:
        dict with policy comparison data
    """
    # Group farm metrics by farm
    by_farm = {}
    for m in all_metrics["farm_metrics"]:
        if m.farm_id not in by_farm:
            by_farm[m.farm_id] = []
        by_farm[m.farm_id].append(m)

    # Generate summaries
    summaries = [summarize_farm(metrics) for metrics in by_farm.values()]

    # Sort by total cost (lowest first)
    summaries.sort(key=lambda s: s["total_cost_usd"])

    return {
        "farm_summaries": summaries,
        "total_years": len(all_metrics["years"]),
        "start_year": min(all_metrics["years"]),
        "end_year": max(all_metrics["years"]),
    }


def compute_counterfactual_water_cost(simulation_state, data_loader, scenario):
    """Compute counterfactual cost if ALL water came from municipal source.

    For each farm and each daily water record, computes what the cost would
    have been if the entire demand_m3 was purchased from the municipal source
    at the prevailing municipal price for that year.

    Args:
        simulation_state: SimulationState with farms and daily_water_records
        data_loader: SimulationDataLoader for subsidized price lookup
        scenario: Loaded Scenario with water_pricing config

    Returns:
        dict: {
            "yearly_costs": {year: {farm_id: counterfactual_cost_usd}},
            "yearly_prices_per_m3": {year: price_per_m3}
        }
    """
    water_pricing = scenario.water_pricing
    start_year = scenario.metadata.start_date.year

    # Pre-compute municipal price for each year
    years = sorted(set(m.year for m in simulation_state.yearly_metrics))
    yearly_prices = {}
    for year in years:
        if water_pricing.pricing_regime == "unsubsidized":
            base_price = water_pricing.unsubsidized.base_price_usd_m3
            escalation = water_pricing.unsubsidized.annual_escalation_pct / 100
            yearly_prices[year] = base_price * ((1 + escalation) ** (year - start_year))
        else:
            # Subsidized: look up from data_loader
            yearly_prices[year] = data_loader.get_municipal_price_usd_m3(
                year, tier=water_pricing.subsidized.use_tier
            )

    # Compute counterfactual costs from daily records
    yearly_costs = {year: {} for year in years}

    for farm in simulation_state.farms:
        farm_yearly_costs = {year: 0.0 for year in years}
        for record in farm.daily_water_records:
            year = record.date.year
            if year in yearly_prices:
                farm_yearly_costs[year] += record.demand_m3 * yearly_prices[year]
        for year in years:
            yearly_costs[year][farm.farm_id] = farm_yearly_costs[year]

    return {
        "yearly_costs": yearly_costs,
        "yearly_prices_per_m3": yearly_prices,
    }


def compute_blended_water_cost_per_m3(simulation_state):
    """Compute blended (effective) water cost per m3 for each farm each year.

    Blended cost = total_water_cost_usd / total_water_m3, representing the
    actual average cost per m3 of the groundwater+municipal mix the farm used.

    Args:
        simulation_state: SimulationState with yearly_metrics

    Returns:
        dict: {year: {farm_id: blended_cost_per_m3}}
    """
    result = {}
    for m in simulation_state.yearly_metrics:
        if m.year not in result:
            result[m.year] = {}
        if m.total_water_m3 > 0:
            result[m.year][m.farm_id] = m.total_water_cost_usd / m.total_water_m3
        else:
            result[m.year][m.farm_id] = 0.0
    return result


def compute_market_water_price_per_m3(scenario, years, data_loader=None):
    """Compute the municipal water price per m3 for each year.

    Uses the same pricing logic as the simulation: unsubsidized escalation
    formula or subsidized tier lookup from data_loader.

    Args:
        scenario: Loaded Scenario with water_pricing config
        years: List of years to compute prices for
        data_loader: SimulationDataLoader (required for subsidized pricing)

    Returns:
        dict: {year: price_per_m3}
    """
    water_pricing = scenario.water_pricing
    start_year = scenario.metadata.start_date.year
    result = {}
    for year in years:
        if water_pricing.pricing_regime == "unsubsidized":
            base_price = water_pricing.unsubsidized.base_price_usd_m3
            escalation = water_pricing.unsubsidized.annual_escalation_pct / 100
            result[year] = base_price * ((1 + escalation) ** (year - start_year))
        else:
            if data_loader is None:
                raise ValueError(
                    "data_loader is required for subsidized pricing regime"
                )
            result[year] = data_loader.get_municipal_price_usd_m3(
                year, tier=water_pricing.subsidized.use_tier
            )
    return result


def compute_revenue_concentration(yearly_farm_metrics_list):
    """Compute revenue concentration for each year.

    Revenue concentration = max(crop_revenue) / sum(crop_revenue) × 100.
    Lower values indicate more diversified revenue streams.

    Args:
        yearly_farm_metrics_list: List of YearlyFarmMetrics from simulation_state.yearly_metrics

    Returns:
        list of dicts: [{year, farm_id, concentration_pct, dominant_crop}]
    """
    results = []
    for m in yearly_farm_metrics_list:
        crop_revenues = m.crop_revenue_usd
        if not crop_revenues:
            results.append({
                "year": m.year,
                "farm_id": m.farm_id,
                "concentration_pct": 0.0,
                "dominant_crop": "none",
            })
            continue

        total_revenue = sum(crop_revenues.values())
        if total_revenue <= 0:
            results.append({
                "year": m.year,
                "farm_id": m.farm_id,
                "concentration_pct": 0.0,
                "dominant_crop": "none",
            })
            continue

        dominant_crop = max(crop_revenues, key=crop_revenues.get)
        max_revenue = crop_revenues[dominant_crop]
        concentration_pct = (max_revenue / total_revenue) * 100

        results.append({
            "year": m.year,
            "farm_id": m.farm_id,
            "concentration_pct": concentration_pct,
            "dominant_crop": dominant_crop,
        })

    return results


def compute_cost_volatility(monthly_metrics):
    """Compute coefficient of variation of monthly total operating costs.

    CV = std / mean. Lower = more stable costs.

    Args:
        monthly_metrics: List of MonthlyFarmMetrics with total_operating_cost_usd

    Returns:
        float: CV value, or 0.0 if insufficient data
    """
    costs = [m.total_operating_cost_usd for m in monthly_metrics]
    if len(costs) < 2:
        return 0.0
    mean_cost = sum(costs) / len(costs)
    if mean_cost <= 0:
        return 0.0
    variance = sum((c - mean_cost) ** 2 for c in costs) / (len(costs) - 1)
    std_cost = variance ** 0.5
    return std_cost / mean_cost


def compute_net_income(monthly_metrics):
    """Compute net income metrics from monthly data.

    For each month: net_income = total_crop_revenue - total_operating_cost
    Operating margin = net_income / revenue × 100 (guarded against zero revenue)

    Args:
        monthly_metrics: list of MonthlyFarmMetrics

    Returns:
        list of dicts: [{year, month, farm_id, revenue_usd, cost_usd,
                         net_income_usd, operating_margin_pct}]
    """
    results = []
    for m in monthly_metrics:
        revenue = m.total_crop_revenue_usd
        cost = m.total_operating_cost_usd
        net_income = revenue - cost
        if revenue > 0:
            operating_margin = (net_income / revenue) * 100
        else:
            operating_margin = 0.0

        results.append({
            "year": m.year,
            "month": m.month,
            "farm_id": m.farm_id,
            "revenue_usd": revenue,
            "cost_usd": cost,
            "net_income_usd": net_income,
            "operating_margin_pct": operating_margin,
        })
    return results


# ---------------------------------------------------------------------------
# Financial Performance Metrics
# ---------------------------------------------------------------------------


def compute_npv(annual_net_incomes, discount_rate, initial_capex=0.0):
    """Compute Net Present Value of cash flows.

    NPV = -Initial_CAPEX + Σ(Net_income(t) / (1+r)^t) for t=1..N

    Args:
        annual_net_incomes: list of yearly net income values [year1, year2, ...]
        discount_rate: real annual discount rate (e.g., 0.06 for 6%)
        initial_capex: total initial capital expenditure (positive value)

    Returns:
        float: NPV in USD
    """
    npv = -initial_capex
    for t, income in enumerate(annual_net_incomes, start=1):
        npv += income / ((1 + discount_rate) ** t)
    return npv


def compute_irr(annual_net_incomes, initial_capex, max_iterations=100, tolerance=1e-6):
    """Compute Internal Rate of Return using bisection method.

    Find rate r where: 0 = -CAPEX + Σ(Net_income(t) / (1+r)^t)

    Args:
        annual_net_incomes: list of yearly net income values
        initial_capex: total initial capital expenditure (positive value)
        max_iterations: maximum iterations for bisection
        tolerance: convergence threshold

    Returns:
        float: IRR as decimal (e.g., 0.12 for 12%), or None if not converged
    """
    # If no CAPEX, IRR is undefined (infinite return on zero investment)
    if initial_capex <= 0:
        return None

    # Bisection between -50% and 500%
    low, high = -0.50, 5.0
    for _ in range(max_iterations):
        mid = (low + high) / 2
        npv = compute_npv(annual_net_incomes, mid, initial_capex)
        if abs(npv) < tolerance:
            return mid
        if npv > 0:
            low = mid
        else:
            high = mid

    # Return best guess even if not fully converged
    return (low + high) / 2


def compute_payback_period(annual_net_incomes, initial_capex):
    """Compute simple payback period in years.

    Payback = min(t) such that Σ(Net_income(y), y=1..t) >= CAPEX

    Args:
        annual_net_incomes: list of yearly net income values
        initial_capex: total initial capital expenditure

    Returns:
        float: years to payback (fractional), or float('inf') if never
    """
    if initial_capex <= 0:
        return 0.0

    cumulative = 0.0
    for t, income in enumerate(annual_net_incomes):
        prev_cumulative = cumulative
        cumulative += income
        if cumulative >= initial_capex:
            # Interpolate within the year
            if income > 0:
                fraction = (initial_capex - prev_cumulative) / income
                return t + fraction
            return float(t + 1)

    return float('inf')  # Never pays back within simulation period


def compute_roi(avg_annual_net_income, total_capex):
    """Simple ROI = avg annual net income / total CAPEX * 100.

    Args:
        avg_annual_net_income: average annual net income (USD)
        total_capex: total capital expenditure (USD)

    Returns:
        float: ROI as percentage, or 0.0 if no CAPEX
    """
    if total_capex <= 0:
        return 0.0
    return (avg_annual_net_income / total_capex) * 100


def compute_cash_reserve_adequacy(cash_reserves, avg_monthly_opex):
    """Months of expenses coverable by reserves.

    Args:
        cash_reserves: current cash reserves (USD)
        avg_monthly_opex: average monthly operating expenditure (USD)

    Returns:
        float: months of runway
    """
    if avg_monthly_opex <= 0:
        return float('inf')
    return cash_reserves / avg_monthly_opex


def compute_financial_performance(all_metrics, simulation_state, scenario):
    """Compute all financial performance metrics.

    Combines NPV, IRR, payback period, ROI, and cash reserve adequacy
    into a single summary dict.  Should be called AFTER the simulation
    completes, using data from compute_all_metrics().

    Args:
        all_metrics: output from compute_all_metrics()
        simulation_state: SimulationState with economic state
        scenario: Scenario with economics config

    Returns:
        dict with all financial performance metrics
    """
    farm_metrics = all_metrics["farm_metrics"]
    years = all_metrics["years"]

    # Extract annual net incomes across all farms
    # Net income per year = total crop revenue - total operating expense
    annual_net_incomes = []
    annual_revenues = []
    annual_opex = []
    for year in years:
        year_metrics = [m for m in farm_metrics if m.year == year]
        year_revenue = sum(m.total_crop_revenue_usd for m in year_metrics)
        year_opex = sum(m.total_operating_expense_usd for m in year_metrics)
        annual_net_incomes.append(year_revenue - year_opex)
        annual_revenues.append(year_revenue)
        annual_opex.append(year_opex)

    # Get total CAPEX from economic state (sum of capital_usd across subsystems)
    total_capex = 0.0
    if simulation_state.economic:
        infra = simulation_state.economic.annual_infrastructure_costs
        for subsystem, data in infra.items():
            total_capex += data.get("capital_usd", 0.0)

    # Discount rate from scenario
    discount_rate = scenario.economics.discount_rate

    # Compute all metrics
    npv = compute_npv(annual_net_incomes, discount_rate, total_capex)
    irr = compute_irr(annual_net_incomes, total_capex)
    payback = compute_payback_period(annual_net_incomes, total_capex)
    avg_income = sum(annual_net_incomes) / len(annual_net_incomes) if annual_net_incomes else 0.0
    roi = compute_roi(avg_income, total_capex)

    # Cash reserve adequacy
    cash = simulation_state.economic.cash_reserves_usd if simulation_state.economic else 0.0
    avg_monthly_opex = sum(annual_opex) / len(annual_opex) / 12 if annual_opex else 0.0
    adequacy = compute_cash_reserve_adequacy(cash, avg_monthly_opex)

    # Total debt service
    total_debt_service = 0.0
    if simulation_state.economic:
        total_debt_service = simulation_state.economic.cumulative_debt_service_usd

    # Debt to revenue
    total_revenue = sum(annual_revenues)
    annual_debt = total_debt_service / len(years) if years else 0.0
    annual_revenue = total_revenue / len(years) if years else 0.0
    debt_to_revenue = annual_debt / annual_revenue if annual_revenue > 0 else 0.0

    return {
        "npv_usd": npv,
        "irr_pct": irr * 100 if irr is not None else None,
        "payback_years": payback,
        "roi_pct": roi,
        "avg_annual_net_income_usd": avg_income,
        "total_capex_usd": total_capex,
        "cash_reserves_usd": cash,
        "cash_reserve_adequacy_months": adequacy,
        "debt_to_revenue_ratio": debt_to_revenue,
        "total_revenue_usd": total_revenue,
        "total_opex_usd": sum(annual_opex),
        "discount_rate": discount_rate,
        "annual_net_incomes": annual_net_incomes,
    }
