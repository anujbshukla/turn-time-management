from __future__ import annotations

"""Generate realistic, correlated warehouse history + 45-day planning data.

The generator deliberately models relationships instead of independent random fields:
carrier reliability -> arrival delay; product mix + pallets + resources + congestion ->
service duration; resource shortages and dock queues -> SLA performance.

Run after Alembic upgrade to revision c7f2a6d9b210.
"""

import argparse
import json
import math
import os
import random
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from statistics import mean
from typing import Any, Iterable

try:
    import psycopg
except ModuleNotFoundError:  # Allows --dry-run validation outside the backend venv.
    psycopg = None  # type: ignore[assignment]

DEFAULT_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://turntime:localpassword@localhost:5432/turn_time",
)
DEFAULT_SEED = 20260814
DEFAULT_HISTORY_DAYS = 365
DEFAULT_HISTORICAL_APPOINTMENTS = 150_000
DEFAULT_FUTURE_DAYS = 45

FACILITIES = [
    ("FAC001", "Atlanta Distribution Center", "America/New_York", 55, 14, 8, 1.03, 1.02),
    ("FAC002", "Dallas Distribution Center", "America/Chicago", 62, 16, 9, 1.01, 1.00),
    ("FAC003", "Chicago Distribution Center", "America/Chicago", 58, 15, 8, 0.98, 0.99),
    ("FAC004", "New Jersey Distribution Center", "America/New_York", 60, 15, 9, 0.99, 0.98),
    ("FAC005", "Los Angeles Distribution Center", "America/Los_Angeles", 68, 17, 10, 0.97, 0.98),
    ("FAC006", "Miami Distribution Center", "America/New_York", 44, 12, 7, 1.02, 1.03),
    ("FAC007", "Seattle Distribution Center", "America/Los_Angeles", 42, 11, 7, 1.04, 1.03),
    ("FAC008", "Phoenix Distribution Center", "America/Phoenix", 47, 12, 8, 1.05, 1.04),
    ("FAC009", "Denver Distribution Center", "America/Denver", 45, 12, 7, 1.03, 1.02),
    ("FAC010", "Houston Distribution Center", "America/Chicago", 57, 14, 8, 1.00, 1.00),
]

CARRIER_NAMES = [
    "NorthStar Logistics", "BlueLine Transport", "Rapid Freight", "Summit Carriers",
    "Atlas Transportation", "Pioneer Logistics", "Redwood Freight", "Metro Haulage",
    "Prime Distribution", "Eagle Transport", "Horizon Freight", "United Cargo",
    "Coastal Logistics", "National Express", "Silver Road Transport", "Continental Freight",
    "Velocity Logistics", "Evergreen Carriers", "Interstate Transport", "Gateway Freight",
    "Apex Linehaul", "Keystone Freight", "Liberty Logistics", "TransCentral", "Arrow Transport",
    "Great Lakes Freight", "Sunbelt Carriers", "Pacific Haul", "Heartland Express", "Delta Logistics",
    "Meridian Freight", "CrossRoad Transport", "IronHorse Logistics", "Canyon Freight", "StarRoute",
    "OakLine Carriers", "Capital Transport", "Harbor Freightways", "Frontier Logistics", "Union Freight",
    "Peak Transport", "Blue Ridge Logistics", "Prairie Cargo", "Atlantic Carriers", "WestGate Freight",
    "Southern Linehaul", "Northeast Express", "MileStone Logistics", "Skyway Freight", "RoadLink Transport",
]

CUSTOMER_PREFIXES = [
    "FreshMart", "Value Foods", "Metro Grocery", "Home Essentials", "Premier Wholesale",
    "Urban Markets", "Regional Pharmacy", "Quick Commerce", "Industrial Supply", "Consumer Goods",
    "Harvest Foods", "Prime Retail", "Family Grocers", "HealthFirst", "MarketSquare",
    "Daily Essentials", "National Foods", "CarePoint", "TradeSource", "City Retail",
]

CATEGORIES = {
    "Frozen Foods": ("Frozen", "Standard", 1.25, 0.95),
    "Dairy": ("Chilled", "Standard", 1.15, 0.90),
    "Produce": ("Chilled", "Fragile", 1.35, 1.05),
    "Beverages": ("Ambient", "Standard", 0.88, 1.05),
    "Packaged Foods": ("Ambient", "Standard", 0.82, 0.82),
    "Household": ("Ambient", "Standard", 0.78, 0.80),
    "Personal Care": ("Ambient", "High Value", 1.08, 0.76),
    "Electronics": ("Ambient", "High Value", 1.45, 0.72),
    "Industrial Supplies": ("Ambient", "Oversized", 1.55, 1.30),
    "Pet Products": ("Ambient", "Standard", 0.92, 0.90),
}

DISTANCE_BANDS = [("Local", 0.34), ("Regional", 0.38), ("Long Haul", 0.20), ("Cross Country", 0.08)]
LOAD_TYPES = [("Palletized", 0.74), ("Floor Loaded", 0.12), ("Mixed", 0.10), ("Slip Sheet", 0.04)]


@dataclass(frozen=True)
class FacilityProfile:
    facility_id: str
    name: str
    timezone: str
    base_volume: int
    loaders: int
    forklifts: int
    dock_eff: float
    labor_eff: float
    congestion_sensitivity: float


@dataclass(frozen=True)
class CarrierProfile:
    carrier_id: str
    name: str
    on_time_rate: float
    mean_delay: float
    delay_sd: float
    long_haul_penalty: float


@dataclass(frozen=True)
class CustomerProfile:
    customer_id: str
    name: str
    industry: str
    priority_tier: str
    sla: int
    complexity: float
    typical_pallets: int
    typical_skus: int
    inbound_share: float


@dataclass(frozen=True)
class ProductProfile:
    product_id: str
    name: str
    sku: str
    category: str
    temp_zone: str
    handling_type: str
    unit_weight: float
    unit_volume: float
    units_per_case: int
    cases_per_pallet: int
    minutes_per_pallet: float
    complexity: float
    forklift_intensity: float
    staging_intensity: float


def weighted_choice(rng: random.Random, values: list[tuple[Any, float]]) -> Any:
    target = rng.random() * sum(weight for _, weight in values)
    running = 0.0
    for value, weight in values:
        running += weight
        if target <= running:
            return value
    return values[-1][0]


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def normal_int(rng: random.Random, center: float, sd: float, low: int, high: int) -> int:
    return int(round(clamp(rng.gauss(center, sd), low, high)))


def build_profiles(rng: random.Random) -> tuple[list[FacilityProfile], list[CarrierProfile], list[CustomerProfile], list[ProductProfile]]:
    facilities = [
        FacilityProfile(fid, name, tz, volume, loaders, forklifts, dock_eff, labor_eff, rng.uniform(0.90, 1.12))
        for fid, name, tz, volume, loaders, forklifts, dock_eff, labor_eff in FACILITIES
    ]

    carriers: list[CarrierProfile] = []
    for index, name in enumerate(CARRIER_NAMES, 1):
        quality = rng.betavariate(8.0, 2.2)
        on_time = clamp(0.68 + 0.30 * quality, 0.68, 0.975)
        mean_delay = 5 + (1 - quality) * 34
        carriers.append(CarrierProfile(f"CAR{index:03d}", name, on_time, mean_delay, 8 + (1 - quality) * 18, rng.uniform(5, 20)))

    industries = ["Grocery", "Retail", "Pharmaceutical", "Consumer Goods", "Industrial", "Electronics"]
    customers: list[CustomerProfile] = []
    for index in range(1, 101):
        industry = weighted_choice(rng, [("Grocery", .32), ("Retail", .24), ("Pharmaceutical", .10), ("Consumer Goods", .18), ("Industrial", .10), ("Electronics", .06)])
        tier = weighted_choice(rng, [("Strategic", .15), ("Preferred", .30), ("Standard", .55)])
        sla = 90 if tier == "Strategic" and rng.random() < .35 else (120 if rng.random() < .82 else 150)
        typical = normal_int(rng, 24 if industry in {"Grocery", "Retail"} else 18, 8, 5, 52)
        skus = normal_int(rng, 7 if industry in {"Retail", "Consumer Goods"} else 5, 3, 1, 18)
        prefix = CUSTOMER_PREFIXES[(index - 1) % len(CUSTOMER_PREFIXES)]
        customers.append(CustomerProfile(
            f"CUS{index:03d}", f"{prefix} {index:03d}", industry, tier, sla,
            rng.uniform(.88, 1.22), typical, skus, rng.uniform(.40, .72)
        ))

    products: list[ProductProfile] = []
    category_names = list(CATEGORIES)
    for index in range(1, 501):
        category = category_names[(index - 1) % len(category_names)] if rng.random() < .65 else rng.choice(category_names)
        temp_zone, handling_type, base_minutes, forklift_base = CATEGORIES[category]
        weight = round(rng.uniform(0.4, 45.0), 2)
        units_per_case = rng.choice([4, 6, 8, 10, 12, 16, 20, 24])
        cases_per_pallet = rng.randint(20, 72)
        volume = round(rng.uniform(0.03, 2.4), 4)
        complexity = clamp(rng.gauss(1.0, .12) * (1.16 if handling_type in {"Fragile", "High Value", "Oversized"} else 1), .72, 1.55)
        products.append(ProductProfile(
            f"PRD{index:04d}", f"{category} Item {index:04d}", f"SKU-{index:05d}", category,
            temp_zone, handling_type, weight, volume, units_per_case, cases_per_pallet,
            clamp(rng.gauss(base_minutes, .16), .48, 2.3), complexity,
            clamp(rng.gauss(forklift_base, .13), .45, 1.55), rng.uniform(.65, 1.35),
        ))
    return facilities, carriers, customers, products


def weekday_factor(day: date) -> float:
    return [1.08, 1.12, 1.10, 1.06, 1.02, .58, .45][day.weekday()]


def seasonal_factor(day: date) -> float:
    # Smooth annual seasonality plus modest month-end/quarter-end pressure.
    annual = 1.0 + .09 * math.sin((day.timetuple().tm_yday / 365.0) * 2 * math.pi - .7)
    month_end = 1.08 if day.day >= 27 else 1.0
    quarter_end = 1.08 if day.month in {3, 6, 9, 12} and day.day >= 24 else 1.0
    return annual * month_end * quarter_end


def build_volume_plan(
    rng: random.Random,
    facilities: list[FacilityProfile],
    start: date,
    end: date,
    target_total: int | None,
) -> dict[tuple[str, date], int]:
    raw: dict[tuple[str, date], float] = {}
    day = start
    while day <= end:
        for facility in facilities:
            variation = clamp(rng.gauss(1.0, .09), .76, 1.27)
            raw[(facility.facility_id, day)] = facility.base_volume * weekday_factor(day) * seasonal_factor(day) * variation
        day += timedelta(days=1)

    scale = (target_total / sum(raw.values())) if target_total else 1.0
    plan = {key: max(4, int(round(value * scale))) for key, value in raw.items()}
    if target_total:
        difference = target_total - sum(plan.values())
        keys = list(plan)
        rng.shuffle(keys)
        step = 1 if difference > 0 else -1
        for i in range(abs(difference)):
            key = keys[i % len(keys)]
            if step > 0 or plan[key] > 4:
                plan[key] += step
    return plan


def scheduled_hour(rng: random.Random, appointment_type: str) -> float:
    # Multi-modal schedule: early inbound and afternoon outbound peaks.
    bucket = weighted_choice(rng, [("early", .20), ("morning", .36), ("midday", .22), ("afternoon", .18), ("night", .04)])
    centers = {"early": 5.8, "morning": 8.8, "midday": 12.2, "afternoon": 15.3, "night": 20.0}
    center = centers[bucket] + (-.35 if appointment_type == "Inbound" else .35)
    return clamp(rng.gauss(center, 1.15), 3.5, 22.5)


def to_datetime(day: date, hour: float) -> datetime:
    whole = int(hour)
    minute = int((hour - whole) * 60)
    return datetime.combine(day, time(whole, minute))


def distribute_pallets(rng: random.Random, pallets: int, sku_count: int) -> list[int]:
    sku_count = max(1, min(sku_count, pallets))
    values = [1] * sku_count
    for _ in range(pallets - sku_count):
        values[rng.randrange(sku_count)] += 1
    rng.shuffle(values)
    return values


def reset_database(cur: psycopg.Cursor[Any]) -> None:
    cur.execute("""
        TRUNCATE TABLE
            optimization_mission_appointments,
            optimization_missions,
            product_handling_history,
            appointment_resource_allocations,
            recommendation_actions,
            appointment_recommendations,
            appointment_predictions,
            appointment_events,
            appointment_products,
            equipment_status_events,
            labor_shifts,
            equipment,
            product_operational_profiles,
            customer_operational_profiles,
            carrier_operational_profiles,
            facility_operational_profiles,
            appointments,
            products,
            customers,
            docks,
            carriers,
            facilities
        RESTART IDENTITY CASCADE;
    """)


def insert_reference_data(cur: psycopg.Cursor[Any], facilities, carriers, customers, products, rng: random.Random) -> dict[str, list[str]]:
    cur.executemany("INSERT INTO facilities (facility_id, facility_name, timezone, active) VALUES (%s,%s,%s,TRUE)", [(f.facility_id, f.name, f.timezone) for f in facilities])
    cur.executemany("INSERT INTO facility_operational_profiles (facility_id, weekday_base_volume, weekend_volume_factor, dock_efficiency_factor, labor_efficiency_factor, congestion_sensitivity, base_loader_capacity, base_forklift_capacity, peak_start_hour, peak_end_hour) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,7,17)", [(f.facility_id, f.base_volume, .54, f.dock_eff, f.labor_eff, f.congestion_sensitivity, f.loaders, f.forklifts) for f in facilities])

    cur.executemany("INSERT INTO carriers (carrier_id, carrier_name, active) VALUES (%s,%s,TRUE)", [(c.carrier_id, c.name) for c in carriers])
    cur.executemany("INSERT INTO carrier_operational_profiles (carrier_id, baseline_on_time_rate, mean_delay_minutes, delay_stddev_minutes, long_haul_penalty_minutes) VALUES (%s,%s,%s,%s,%s)", [(c.carrier_id, c.on_time_rate, c.mean_delay, c.delay_sd, c.long_haul_penalty) for c in carriers])

    cur.executemany("INSERT INTO customers (customer_id, customer_name, industry, priority_tier, default_sla_minutes, annual_revenue, active) VALUES (%s,%s,%s,%s,%s,%s,TRUE)", [(c.customer_id, c.name, c.industry, c.priority_tier, c.sla, round(2_000_000 + rng.random()*98_000_000, 2)) for c in customers])
    cur.executemany("INSERT INTO customer_operational_profiles (customer_id, handling_complexity_factor, typical_pallets, typical_skus, inbound_share, priority_bias) VALUES (%s,%s,%s,%s,%s,%s)", [(c.customer_id, c.complexity, c.typical_pallets, c.typical_skus, c.inbound_share, 1.12 if c.priority_tier == "Strategic" else 1.03 if c.priority_tier == "Preferred" else 1.0) for c in customers])

    cur.executemany("""INSERT INTO products (product_id, product_name, sku, category, unit_of_measure, unit_weight_lb, length_in, width_in, height_in, unit_volume_cuft, units_per_case, cases_per_pallet, temperature_zone, handling_type, active)
                       VALUES (%s,%s,%s,%s,'Each',%s,12,10,8,%s,%s,%s,%s,%s,TRUE)""",
                    [(p.product_id, p.name, p.sku, p.category, p.unit_weight, p.unit_volume, p.units_per_case, p.cases_per_pallet, p.temp_zone, p.handling_type) for p in products])
    cur.executemany("INSERT INTO product_operational_profiles (product_id, base_minutes_per_pallet, handling_complexity_factor, forklift_intensity, staging_intensity, damage_risk_factor) VALUES (%s,%s,%s,%s,%s,%s)", [(p.product_id, p.minutes_per_pallet, p.complexity, p.forklift_intensity, p.staging_intensity, 1.20 if p.handling_type in {"Fragile", "High Value"} else 1.0) for p in products])

    docks_by_facility: dict[str, list[str]] = {}
    dock_rows = []
    for facility in facilities:
        dock_ids = []
        for n in range(1, 13):
            dock_id = f"{facility.facility_id}-D{n:02d}"
            dock_ids.append(dock_id)
            zone = "Frozen" if n in {1,2} else "Chilled" if n in {3,4,5} else "Ambient"
            dock_rows.append((dock_id, facility.facility_id, f"Dock {n:02d}", "Shipping/Receiving", zone))
        docks_by_facility[facility.facility_id] = dock_ids
    cur.executemany("INSERT INTO docks (dock_id, facility_id, dock_name, dock_type, temperature_zone, active) VALUES (%s,%s,%s,%s,%s,TRUE)", dock_rows)

    equipment_rows = []
    for facility in facilities:
        for n in range(1, facility.forklifts + 1):
            equipment_rows.append((f"{facility.facility_id}-FL{n:02d}", facility.facility_id, "Forklift", f"Forklift {n:02d}", "Available", 11.50, 5000))
        for n in range(1, max(2, facility.forklifts // 3) + 1):
            equipment_rows.append((f"{facility.facility_id}-RT{n:02d}", facility.facility_id, "Reach Truck", f"Reach Truck {n:02d}", "Available", 13.50, 4000))
    cur.executemany("INSERT INTO equipment (equipment_id, facility_id, equipment_type, equipment_name, status, hourly_operating_cost, capacity, active) VALUES (%s,%s,%s,%s,%s,%s,%s,TRUE)", equipment_rows)
    return docks_by_facility


def insert_labor_shifts(cur: psycopg.Cursor[Any], facilities: list[FacilityProfile], start: date, end: date, rng: random.Random) -> None:
    rows = []
    day = start
    while day <= end:
        for facility in facilities:
            for shift_name, factor in [("Day", 1.0), ("Evening", .62), ("Night", .28)]:
                weekend = .78 if day.weekday() >= 5 else 1.0
                planned_loaders = max(3, round(facility.loaders * factor * weekend))
                callout = rng.binomialvariate(planned_loaders, .035) if hasattr(rng, "binomialvariate") else sum(rng.random() < .035 for _ in range(planned_loaders))
                available = max(2, planned_loaders - callout)
                rows.append((facility.facility_id, day, shift_name, "Loader", planned_loaders, available, 0, 27.50))
                staging = max(2, round(planned_loaders * .28))
                rows.append((facility.facility_id, day, shift_name, "Staging", staging, max(1, staging - (1 if rng.random() < .04 else 0)), 0, 25.00))
                forklift_ops = max(2, round(facility.forklifts * factor * weekend))
                rows.append((facility.facility_id, day, shift_name, "Forklift Operator", forklift_ops, forklift_ops, forklift_ops, 29.50))
        if len(rows) >= 5000:
            cur.executemany("INSERT INTO labor_shifts (facility_id, shift_date, shift_name, role, planned_headcount, available_headcount, forklift_certified_count, hourly_rate) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)", rows)
            rows.clear()
        day += timedelta(days=1)
    if rows:
        cur.executemany("INSERT INTO labor_shifts (facility_id, shift_date, shift_name, role, planned_headcount, available_headcount, forklift_certified_count, hourly_rate) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)", rows)


def appointment_record(
    rng: random.Random,
    seq: int,
    day: date,
    daily_volume: int,
    facility: FacilityProfile,
    carrier: CarrierProfile,
    customer: CustomerProfile,
    products: list[ProductProfile],
    dock_ids: list[str],
    anchor: date,
    current_hour: int,
) -> tuple[tuple[Any, ...], list[tuple[Any, ...]], tuple[Any, ...], list[tuple[Any, ...]], tuple[Any, ...] | None]:
    appointment_type = "Inbound" if rng.random() < customer.inbound_share else "Outbound"
    load_type = weighted_choice(rng, LOAD_TYPES)
    scheduled = to_datetime(day, scheduled_hour(rng, appointment_type))
    distance = weighted_choice(rng, DISTANCE_BANDS)
    peak = 7 <= scheduled.hour <= 10 or 15 <= scheduled.hour <= 18
    traffic = int(clamp(round(rng.gauss(2.0 if peak else .7, .9)), 0, 4))
    weather = weighted_choice(rng, [(0,.66),(1,.20),(2,.09),(3,.04),(4,.01)])
    surge = daily_volume > facility.base_volume * 1.17 or (rng.random() < .025)

    carrier_distance_penalty = {"Local": -4, "Regional": 0, "Long Haul": carrier.long_haul_penalty * .55, "Cross Country": carrier.long_haul_penalty}[distance]
    lateness_pressure = (traffic * 4.2) + (weather * 4.5) + carrier_distance_penalty
    if rng.random() < carrier.on_time_rate:
        actual_delay = normal_int(rng, -4 + lateness_pressure * .18, 8, -45, 35)
    else:
        actual_delay = normal_int(rng, carrier.mean_delay + lateness_pressure, carrier.delay_sd, -10, 240)

    estimated_delay = normal_int(rng, actual_delay if day <= anchor else carrier.mean_delay + lateness_pressure, 10 if day <= anchor else 14, -35, 220)
    eta = scheduled + timedelta(minutes=estimated_delay)

    pallets = normal_int(rng, customer.typical_pallets * (1.08 if load_type == "Floor Loaded" else 1.0), max(4, customer.typical_pallets*.28), 4, 60)
    sku_count = normal_int(rng, customer.typical_skus + pallets/12, 2.4, 1, min(18, pallets))
    industry_categories = {
        "Grocery": {"Frozen Foods", "Dairy", "Produce", "Beverages", "Packaged Foods", "Pet Products"},
        "Retail": set(CATEGORIES),
        "Pharmaceutical": {"Personal Care", "Packaged Foods", "Household"},
        "Consumer Goods": {"Beverages", "Packaged Foods", "Household", "Personal Care", "Pet Products"},
        "Industrial": {"Industrial Supplies", "Household"},
        "Electronics": {"Electronics", "Household"},
    }
    preferred_categories = industry_categories.get(customer.industry, set(CATEGORIES))
    category_pool = [p for p in products if p.category in preferred_categories]
    dominant_zone = weighted_choice(rng, [("Ambient", .66), ("Chilled", .22), ("Frozen", .12)])
    zone_pool = [p for p in category_pool if p.temp_zone == dominant_zone]
    if len(zone_pool) < sku_count:
        zone_pool = category_pool
    selected = rng.sample(zone_pool, k=min(sku_count, len(zone_pool)))
    pallet_distribution = distribute_pallets(rng, pallets, len(selected))
    product_lines: list[tuple[Any, ...]] = []
    total_weight = 0.0
    total_cube = 0.0
    weighted_minutes = 0.0
    forklift_need = 0.0
    staging_need = 0.0
    for product, line_pallets in zip(selected, pallet_distribution):
        cases = line_pallets * product.cases_per_pallet
        quantity = cases * product.units_per_case
        line_weight = quantity * product.unit_weight
        line_cube = quantity * product.unit_volume
        total_weight += line_weight
        total_cube += line_cube
        weighted_minutes += line_pallets * product.minutes_per_pallet * product.complexity
        forklift_need += line_pallets * product.forklift_intensity
        staging_need += line_pallets * product.staging_intensity
        product_lines.append((f"DEMO{seq:07d}", product.product_id, quantity, cases, line_pallets, round(line_weight,2), round(line_cube,4)))

    temp_zones = [p.temp_zone for p in selected]
    preferred_numbers = range(1,3) if "Frozen" in temp_zones else range(3,6) if "Chilled" in temp_zones else range(6,13)
    preferred_docks = [dock_ids[n-1] for n in preferred_numbers]
    dock_id = rng.choice(preferred_docks)

    congestion_ratio = daily_volume / max(1, facility.base_volume)
    hourly_pressure = (1.20 if peak else .82) * congestion_ratio
    dock_congestion = clamp((hourly_pressure - .45) * 72 * facility.congestion_sensitivity + rng.gauss(0,7), 8, 98)
    labor_util = clamp(hourly_pressure * 66 + rng.gauss(0,8), 18, 99)
    forklift_util = clamp(hourly_pressure * 61 + (forklift_need/pallets)*14 + rng.gauss(0,8), 15, 99)
    queue_depth = max(0, round((dock_congestion - 48) / 10 + rng.gauss(0,1.2)))

    planned_loaders = 1 + int(pallets >= 18) + int(pallets >= 38) + int(load_type == "Floor Loaded" and pallets >= 25)
    planned_forklifts = 1 + int(forklift_need / max(1,pallets) > 1.10 and pallets >= 20) + int(pallets >= 48)
    planned_staging = 1 if staging_need/pallets > .95 or pallets >= 32 else 0
    shortage_chance = clamp((labor_util - 78) / 90, 0, .28)
    actual_loaders = max(1, planned_loaders - (1 if rng.random() < shortage_chance else 0))
    actual_forklifts = max(1, planned_forklifts - (1 if rng.random() < clamp((forklift_util-82)/100,0,.20) else 0))
    actual_staging = max(0, planned_staging - (1 if planned_staging and rng.random() < shortage_chance*.55 else 0))

    wait_minutes = max(0, round(queue_depth * rng.uniform(5.0, 9.0) + max(actual_delay,0)*.05 + rng.gauss(2,4)))
    loader_gain = 1 + .62*(actual_loaders-1)
    forklift_gain = 1 + .28*(actual_forklifts-1)
    handling_minutes = (weighted_minutes * 1.78 * customer.complexity) / (facility.labor_eff * loader_gain * forklift_gain)
    sku_overhead = sku_count * rng.uniform(1.0, 1.8)
    floor_penalty = pallets * .65 if load_type == "Floor Loaded" else pallets * .14 if load_type == "Mixed" else 0
    congestion_penalty = max(0, dock_congestion - 65) * .32
    external_penalty = weather*2.2 + (6 if surge else 0)
    shortage_penalty = max(0, planned_loaders-actual_loaders)*13 + max(0,planned_forklifts-actual_forklifts)*9
    loading_duration = max(18, round(14 + handling_minutes + sku_overhead + floor_penalty + congestion_penalty + external_penalty + shortage_penalty + rng.gauss(0,7)))
    closeout = normal_int(rng, 10 if appointment_type == "Outbound" else 7, 3, 3, 20)
    turn_time = wait_minutes + loading_duration + closeout

    priority = 3 if customer.priority_tier == "Strategic" and rng.random() < .38 else 2 if customer.priority_tier in {"Strategic","Preferred"} and rng.random() < .52 else 1
    sla = customer.sla
    detention_rate = 175 if customer.priority_tier == "Strategic" else 125 if customer.priority_tier == "Preferred" else 95

    historical = day < anchor
    today = day == anchor
    cancelled = historical and rng.random() < .022
    actual_arrival = scheduled + timedelta(minutes=actual_delay) if historical or (today and scheduled.hour < current_hour - 1) else None
    loading_start = actual_arrival + timedelta(minutes=wait_minutes) if actual_arrival else None
    loading_end = loading_start + timedelta(minutes=loading_duration) if loading_start else None
    departed = loading_end + timedelta(minutes=closeout) if loading_end else None

    if cancelled:
        status = "Cancelled"
        actual_arrival = loading_start = loading_end = departed = None
        actual_turn = actual_loading = arrival_delay_value = sla_missed = None
    elif historical:
        status = "Completed"
        actual_turn, actual_loading, arrival_delay_value = turn_time, loading_duration, actual_delay
        sla_missed = actual_turn > sla
    elif today:
        if scheduled.hour <= current_hour - 4:
            status = "Completed"; actual_turn, actual_loading, arrival_delay_value, sla_missed = turn_time, loading_duration, actual_delay, turn_time > sla
        elif scheduled.hour <= current_hour - 2:
            status = "In Progress"; actual_turn = actual_loading = sla_missed = None; arrival_delay_value = actual_delay
            loading_end = departed = None
        elif scheduled.hour <= current_hour:
            status = rng.choice(["Arrived","Waiting","Dock Assigned"]); actual_turn = actual_loading = sla_missed = None; arrival_delay_value = actual_delay
            loading_start = loading_end = departed = None
        else:
            status = "Scheduled"; actual_turn = actual_loading = arrival_delay_value = sla_missed = None; actual_arrival = loading_start = loading_end = departed = None
    else:
        status = "Scheduled"; actual_turn = actual_loading = arrival_delay_value = sla_missed = None; actual_arrival = loading_start = loading_end = departed = None

    appt_id = f"DEMO{seq:07d}"
    appointment = (
        appt_id, scheduled, customer.customer_id, customer.name, facility.facility_id, carrier.carrier_id,
        scheduled, eta, actual_arrival, scheduled, loading_start, scheduled + timedelta(minutes=sla), loading_end,
        dock_id, status, appointment_type, load_type, f"TRL-{seq%99999:05d}", pallets, sku_count,
        round(total_weight,2), round(total_cube,2), priority, sla, detention_rate,
        loading_start, loading_end, departed, arrival_delay_value, actual_loading, actual_turn, sla_missed,
        distance, traffic, weather, surge,
    )

    # Rebuild line ids now that appt_id is known (same value as used above, kept explicit).
    resource = (appt_id, planned_loaders, actual_loaders if historical or (today and status != "Scheduled") else None,
                planned_forklifts, actual_forklifts if historical or (today and status != "Scheduled") else None,
                planned_staging, actual_staging if historical or (today and status != "Scheduled") else None,
                queue_depth, round(dock_congestion,2), round(labor_util,2), round(forklift_util,2), "Synthetic V2")

    events: list[tuple[Any, ...]] = []
    if actual_arrival:
        events.append((appt_id, "ARRIVED", actual_arrival, "Carrier checked in", "Yard Operations"))
    if loading_start:
        events.append((appt_id, "LOADING_STARTED", loading_start, f"Service started with {actual_loaders} loader(s) and {actual_forklifts} forklift(s)", "Dock Supervisor"))
    if departed:
        events.append((appt_id, "DEPARTED", departed, "Appointment completed and trailer departed", "Dock Supervisor"))

    # Temporary baseline prediction until ML-v2 is trained. The training/scoring job will supersede it.
    expected_service = max(20, round(loading_duration + rng.gauss(0,8)))
    pred_turn = max(20, expected_service + max(estimated_delay,0)*.10 + max(0,dock_congestion-70)*.20)
    margin = pred_turn - sla
    miss_prob = clamp(.10 + margin/110 + max(estimated_delay,0)/240 + max(0,dock_congestion-75)/150, .03, .97)
    prediction = (appt_id, eta, estimated_delay, expected_service, round(miss_prob,4), round(1-miss_prob*.72,4), int(round(miss_prob*100)), miss_prob >= .55, "synthetic-baseline-v2")
    return appointment, product_lines, resource, events, prediction


def copy_rows(cur: psycopg.Cursor[Any], statement: str, rows: Iterable[tuple[Any, ...]]) -> None:
    with cur.copy(statement) as copy:
        for row in rows:
            copy.write_row(row)


def seed_operational_data(conn: psycopg.Connection[Any], rng: random.Random, facilities, carriers, customers, products, docks_by_facility, history_plan, future_plan, anchor: date) -> dict[str, Any]:
    facility_by_id = {f.facility_id: f for f in facilities}
    all_plans = [(day, fid, volume) for (fid, day), volume in {**history_plan, **future_plan}.items()]
    all_plans.sort()
    current_hour = datetime.now().hour if anchor == date.today() else 12
    seq = 1
    totals = defaultdict(int)
    turn_times: list[int] = []
    sla_misses = 0

    appts: list[tuple[Any,...]] = []
    lines: list[tuple[Any,...]] = []
    resources: list[tuple[Any,...]] = []
    events: list[tuple[Any,...]] = []
    predictions: list[tuple[Any,...]] = []

    def flush(cur: psycopg.Cursor[Any]) -> None:
        nonlocal appts, lines, resources, events, predictions
        if not appts:
            return
        copy_rows(cur, """COPY appointments (appt_id, appt_date, customer_id, customer_name, facility_id, carrier_id, scheduled_time, estimated_arrival_time, actual_arrival_time, planned_start_time, actual_start_time, planned_end_time, actual_end_time, assigned_dock_id, status, appointment_type, load_type, trailer_number, pallet_count, sku_count, total_weight, total_cube, priority, sla_minutes, detention_cost_per_hour, actual_loading_start_time, actual_loading_end_time, actual_departure_time, actual_arrival_delay_minutes, actual_loading_duration_minutes, actual_turn_time_minutes, actual_sla_missed, distance_band, traffic_severity, weather_severity, surge_indicator) FROM STDIN""", appts)
        copy_rows(cur, "COPY appointment_products (appt_id, product_id, quantity, case_count, pallet_count, line_weight_lb, line_volume_cuft) FROM STDIN", lines)
        copy_rows(cur, "COPY appointment_resource_allocations (appt_id, planned_loaders, actual_loaders, planned_forklifts, actual_forklifts, planned_staging_labor, actual_staging_labor, queue_depth_at_arrival, dock_congestion_percent, labor_utilization_percent, forklift_utilization_percent, resource_plan_source) FROM STDIN", resources)
        if events:
            copy_rows(cur, "COPY appointment_events (appt_id, event_type, event_time, notes, performed_by) FROM STDIN", events)
        copy_rows(cur, "COPY appointment_predictions (appt_id, predicted_arrival_time, predicted_delay_minutes, predicted_duration_minutes, sla_miss_probability, sla_recovery_probability, turn_risk_score, predicted_missed, model_version) FROM STDIN", predictions)
        appts, lines, resources, events, predictions = [], [], [], [], []

    with conn.cursor() as cur:
        for day, facility_id, volume in all_plans:
            facility = facility_by_id[facility_id]
            for _ in range(volume):
                carrier = rng.choice(carriers)
                customer = rng.choice(customers)
                appointment, product_lines, resource, appointment_events, prediction = appointment_record(
                    rng, seq, day, volume, facility, carrier, customer, products, docks_by_facility[facility_id], anchor, current_hour
                )
                appts.append(appointment); lines.extend(product_lines); resources.append(resource); events.extend(appointment_events); predictions.append(prediction)
                totals[appointment[14]] += 1
                if appointment[30] is not None:
                    turn_times.append(int(appointment[30]))
                    sla_misses += int(bool(appointment[31]))
                seq += 1
                if len(appts) >= 2000:
                    flush(cur)
        flush(cur)
    conn.commit()
    return {
        "appointments": seq - 1,
        "status_counts": dict(totals),
        "completed_avg_turn_minutes": round(mean(turn_times), 1) if turn_times else None,
        "completed_sla_miss_rate_percent": round(sla_misses / len(turn_times) * 100, 2) if turn_times else None,
    }


def seed_historical_recovery_actions(cur: psycopg.Cursor[Any], anchor: date) -> None:
    """Populate realistic historical action outcomes for Root Cause / recovery analytics.

    Future appointments intentionally receive no appointment-level recovery plans; those will
    be generated by the multi-appointment optimizer in the next phase.
    """
    cur.execute(
        """
        WITH candidates AS (
            SELECT
                a.appt_id,
                a.assigned_dock_id,
                a.detention_cost_per_hour,
                a.actual_turn_time_minutes,
                a.sla_minutes,
                a.pallet_count,
                a.sku_count,
                r.planned_loaders,
                r.actual_loaders,
                r.planned_forklifts,
                r.actual_forklifts,
                CASE
                    WHEN a.pallet_count >= 30 OR r.actual_loaders < r.planned_loaders THEN 'ADD_LOADER'
                    WHEN a.sku_count >= 9 OR r.actual_forklifts < r.planned_forklifts THEN 'ADD_FORKLIFT'
                    WHEN r.dock_congestion_percent >= 75 THEN 'PROTECT_DOCK_WINDOW'
                    ELSE 'PRE_STAGE_PRODUCTS'
                END AS action_code,
                CASE
                    WHEN a.pallet_count >= 30 OR r.actual_loaders < r.planned_loaders THEN 'Assign one additional loader'
                    WHEN a.sku_count >= 9 OR r.actual_forklifts < r.planned_forklifts THEN 'Assign an additional forklift'
                    WHEN r.dock_congestion_percent >= 75 THEN 'Protect the assigned dock window'
                    ELSE 'Pre-stage appointment products'
                END AS action_title,
                GREATEST(6, LEAST(24, ROUND((a.actual_turn_time_minutes - a.sla_minutes * .72) / 3.0)))::int AS minutes_saved,
                (MOD(ABS(hashtext(a.appt_id)), 100) < CASE WHEN a.actual_sla_missed = FALSE THEN 78 ELSE 48 END) AS accepted
            FROM appointments a
            JOIN appointment_resource_allocations r ON r.appt_id = a.appt_id
            WHERE a.status = 'Completed'
              AND a.scheduled_time < %s::date
              AND (a.actual_arrival_delay_minutes > 10 OR a.actual_turn_time_minutes >= a.sla_minutes * .82)
              AND MOD(ABS(hashtext(a.appt_id || '-recovery')), 100) < 42
        ),
        inserted AS (
            INSERT INTO appointment_recommendations (
                appt_id, recommendation_type, recommended_action, recommended_dock_id,
                recommended_sequence, additional_labor, estimated_loss_without_action,
                estimated_cost_of_action, estimated_savings, status, created_at
            )
            SELECT
                c.appt_id, 'Historical Recovery', c.action_title, c.assigned_dock_id, 1,
                CASE WHEN c.action_code='ADD_LOADER' THEN 1 ELSE 0 END,
                ROUND(GREATEST(0, c.actual_turn_time_minutes-c.sla_minutes)/60.0*c.detention_cost_per_hour,2),
                CASE WHEN c.action_code='ADD_LOADER' THEN 42.00 WHEN c.action_code='ADD_FORKLIFT' THEN 32.00 ELSE 18.00 END,
                ROUND(c.minutes_saved/60.0*c.detention_cost_per_hour,2),
                CASE WHEN c.accepted THEN 'Completed' ELSE 'Rejected' END,
                %s::date + INTERVAL '12 hours'
            FROM candidates c
            RETURNING recommendation_id, appt_id
        )
        INSERT INTO recommendation_actions (
            recommendation_id, sequence_number, action_code, action_title, action_description,
            owner_role, estimated_minutes_saved, additional_loaders, additional_forklifts,
            required_dock_id, estimated_action_cost, status, decision_status, decision_at, decision_by
        )
        SELECT
            i.recommendation_id, 1, c.action_code, c.action_title,
            CASE c.action_code
                WHEN 'ADD_LOADER' THEN 'Increase labor capacity during the highest-volume handling window.'
                WHEN 'ADD_FORKLIFT' THEN 'Increase material-handling capacity for the appointment product mix.'
                WHEN 'PROTECT_DOCK_WINDOW' THEN 'Keep the assigned dock clear to prevent additional queue delay.'
                ELSE 'Stage the highest-volume products before service begins.'
            END,
            CASE WHEN c.action_code='ADD_FORKLIFT' THEN 'Equipment Coordinator' WHEN c.action_code='PROTECT_DOCK_WINDOW' THEN 'Dock Supervisor' ELSE 'Shift Supervisor' END,
            c.minutes_saved, CASE WHEN c.action_code='ADD_LOADER' THEN 1 ELSE 0 END,
            CASE WHEN c.action_code='ADD_FORKLIFT' THEN 1 ELSE 0 END, c.assigned_dock_id,
            CASE WHEN c.action_code='ADD_LOADER' THEN 42.00 WHEN c.action_code='ADD_FORKLIFT' THEN 32.00 ELSE 18.00 END,
            CASE WHEN c.accepted THEN 'Completed' ELSE 'Rejected' END,
            CASE WHEN c.accepted THEN 'Accepted' ELSE 'Rejected' END,
            %s::date + INTERVAL '12 hours', 'Historical Operations'
        FROM inserted i
        JOIN candidates c ON c.appt_id = i.appt_id;
        """,
        (anchor, anchor, anchor),
    )


def rebuild_product_history(cur: psycopg.Cursor[Any], anchor: date) -> None:
    cur.execute("DELETE FROM product_handling_history")
    cur.execute("""
        INSERT INTO product_handling_history (
            product_id, facility_id, as_of_date, sample_size,
            avg_minutes_per_pallet, p50_minutes_per_pallet, p90_minutes_per_pallet,
            avg_loaders, avg_forklifts, sla_success_rate
        )
        SELECT
            ap.product_id,
            a.facility_id,
            %s::date,
            COUNT(*)::int,
            ROUND(AVG(a.actual_loading_duration_minutes::numeric / NULLIF(a.pallet_count,0)),3),
            ROUND(PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY a.actual_loading_duration_minutes::numeric / NULLIF(a.pallet_count,0))::numeric,3),
            ROUND(PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY a.actual_loading_duration_minutes::numeric / NULLIF(a.pallet_count,0))::numeric,3),
            ROUND(AVG(r.actual_loaders),2),
            ROUND(AVG(r.actual_forklifts),2),
            ROUND(AVG(CASE WHEN a.actual_sla_missed = FALSE THEN 1.0 ELSE 0.0 END),4)
        FROM appointment_products ap
        JOIN appointments a ON a.appt_id = ap.appt_id
        JOIN appointment_resource_allocations r ON r.appt_id = a.appt_id
        WHERE a.status = 'Completed'
          AND a.actual_loading_duration_minutes IS NOT NULL
          AND a.scheduled_time < %s::date
        GROUP BY ap.product_id, a.facility_id
        HAVING COUNT(*) >= 8;
    """, (anchor, anchor))


def validate_db(cur: psycopg.Cursor[Any], anchor: date, future_days: int) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    cur.execute("SELECT COUNT(*) FROM appointments WHERE scheduled_time < %s::date AND status='Completed'", (anchor,)); checks["historical_completed"] = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM appointments WHERE scheduled_time >= %s::date AND scheduled_time < %s::date + INTERVAL '1 day'", (anchor, anchor)); checks["today"] = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM appointments WHERE scheduled_time >= %s::date + INTERVAL '1 day' AND scheduled_time < %s::date + (%s || ' days')::interval", (anchor, anchor, future_days+1)); checks["future"] = cur.fetchone()[0]
    cur.execute("SELECT ROUND(AVG(actual_turn_time_minutes),1), ROUND(100.0*AVG(CASE WHEN actual_sla_missed THEN 1 ELSE 0 END),2) FROM appointments WHERE status='Completed'"); row=cur.fetchone(); checks["avg_turn_minutes"], checks["sla_miss_rate_percent"] = row
    cur.execute("SELECT ROUND(AVG(actual_arrival_delay_minutes),1), ROUND(PERCENTILE_CONT(.90) WITHIN GROUP (ORDER BY actual_arrival_delay_minutes)::numeric,1) FROM appointments WHERE status='Completed'"); row=cur.fetchone(); checks["avg_arrival_delay_minutes"], checks["p90_arrival_delay_minutes"] = row
    cur.execute("SELECT COUNT(*) FROM product_handling_history"); checks["product_history_profiles"] = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM appointment_recommendations WHERE recommendation_type='Historical Recovery'"); checks["historical_recovery_plans"] = cur.fetchone()[0]
    cur.execute("SELECT MIN(scheduled_time)::date, MAX(scheduled_time)::date FROM appointments"); row=cur.fetchone(); checks["min_date"], checks["max_date"] = map(str,row)
    return checks


def dry_run_summary(rng: random.Random, facilities: list[FacilityProfile], history_plan, future_plan, anchor: date) -> dict[str, Any]:
    historical = sum(history_plan.values()); future = sum(future_plan.values())
    by_facility_future = defaultdict(int)
    for (fid, _), value in future_plan.items(): by_facility_future[fid] += value
    return {
        "anchor_date": str(anchor),
        "historical_appointments": historical,
        "future_appointments_including_today": future,
        "planning_days_including_today": (max(d for _,d in future_plan) - anchor).days + 1 if future_plan else 0,
        "future_days_after_today": (max(d for _,d in future_plan) - anchor).days if future_plan else 0,
        "future_by_facility": dict(sorted(by_facility_future.items())),
        "historical_date_range": [str(min(d for _,d in history_plan)), str(max(d for _,d in history_plan))],
        "future_date_range": [str(min(d for _,d in future_plan)), str(max(d for _,d in future_plan))],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate realistic ML-v2 warehouse data.")
    parser.add_argument("--database-url", default=DEFAULT_DATABASE_URL)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--anchor-date", type=date.fromisoformat, default=date.today())
    parser.add_argument("--history-days", type=int, default=DEFAULT_HISTORY_DAYS)
    parser.add_argument("--historical-count", type=int, default=DEFAULT_HISTORICAL_APPOINTMENTS)
    parser.add_argument("--future-days", type=int, default=DEFAULT_FUTURE_DAYS)
    parser.add_argument("--reset", action="store_true", help="Required to delete and replace current demo/reference data.")
    parser.add_argument("--dry-run", action="store_true", help="Show planned volumes without connecting to PostgreSQL.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rng = random.Random(args.seed)
    facilities, carriers, customers, products = build_profiles(rng)
    history_start = args.anchor_date - timedelta(days=args.history_days)
    history_end = args.anchor_date - timedelta(days=1)
    future_start = args.anchor_date
    future_end = args.anchor_date + timedelta(days=args.future_days)
    history_plan = build_volume_plan(rng, facilities, history_start, history_end, args.historical_count)
    future_plan = build_volume_plan(rng, facilities, future_start, future_end, None)

    if args.dry_run:
        print(json.dumps(dry_run_summary(rng, facilities, history_plan, future_plan, args.anchor_date), indent=2))
        return
    if not args.reset:
        raise SystemExit("Refusing to modify the database without --reset. Run with --dry-run first, then add --reset.")

    if psycopg is None:
        raise SystemExit("psycopg is required for database writes. Activate backend/.venv and retry.")

    with psycopg.connect(args.database_url) as conn:
        with conn.cursor() as cur:
            reset_database(cur)
            docks_by_facility = insert_reference_data(cur, facilities, carriers, customers, products, rng)
            insert_labor_shifts(cur, facilities, history_start, future_end, rng)
        conn.commit()
        summary = seed_operational_data(conn, rng, facilities, carriers, customers, products, docks_by_facility, history_plan, future_plan, args.anchor_date)
        with conn.cursor() as cur:
            seed_historical_recovery_actions(cur, args.anchor_date)
            rebuild_product_history(cur, args.anchor_date)
            validation = validate_db(cur, args.anchor_date, args.future_days)
        conn.commit()

    print(json.dumps({"generation": summary, "validation": validation}, indent=2, default=str))


if __name__ == "__main__":
    main()
