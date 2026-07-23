from __future__ import annotations

import argparse
import math
import random
from datetime import date, datetime, timedelta
from typing import Iterable, Sequence

import psycopg


DATABASE_URL = (
    "postgresql://turntime:localpassword"
    "@localhost:5432/turn_time"
)

DEFAULT_SEED = 42
PRODUCT_COUNT = 250
CUSTOMER_COUNT = 100
CARRIER_COUNT = 20
DOCKS_PER_FACILITY = 10
EQUIPMENT_PER_FACILITY = 20

FACILITIES = [
    (
        "FAC001",
        "Atlanta Distribution Center",
        "America/New_York",
    ),
    (
        "FAC002",
        "Dallas Distribution Center",
        "America/Chicago",
    ),
    (
        "FAC003",
        "Chicago Distribution Center",
        "America/Chicago",
    ),
    (
        "FAC004",
        "New Jersey Distribution Center",
        "America/New_York",
    ),
    (
        "FAC005",
        "Los Angeles Distribution Center",
        "America/Los_Angeles",
    ),
]

CARRIER_NAMES = [
    "NorthStar Logistics",
    "BlueLine Transport",
    "Rapid Freight",
    "Summit Carriers",
    "Atlas Transportation",
    "Pioneer Logistics",
    "Redwood Freight",
    "Metro Haulage",
    "Prime Distribution",
    "Eagle Transport",
    "Horizon Freight",
    "United Cargo",
    "Coastal Logistics",
    "National Express",
    "Silver Road Transport",
    "Continental Freight",
    "Velocity Logistics",
    "Evergreen Carriers",
    "Interstate Transport",
    "Gateway Freight",
]

CUSTOMER_PREFIXES = [
    "FreshMart",
    "Value Foods",
    "Metro Grocery",
    "Home Essentials",
    "Premier Wholesale",
    "Urban Markets",
    "Regional Pharmacy",
    "Quick Commerce",
    "Industrial Supply",
    "Consumer Goods",
]

INDUSTRIES = [
    "Grocery",
    "Retail",
    "Pharmaceutical",
    "Consumer Goods",
    "Industrial",
    "Electronics",
]

PRODUCT_CATEGORIES = [
    "Beverages",
    "Frozen Foods",
    "Produce",
    "Dairy",
    "Packaged Foods",
    "Household",
    "Personal Care",
    "Electronics",
    "Industrial Supplies",
    "Pet Products",
]

HANDLING_TYPES = [
    "Standard",
    "Fragile",
    "Hazardous",
    "Oversized",
    "High Value",
]

DISTANCE_BANDS = [
    "Local",
    "Regional",
    "Long Haul",
    "Cross Country",
]

EQUIPMENT_TYPES = [
    "Forklift",
    "Reach Truck",
    "Pallet Jack",
    "Clamp Truck",
    "Yard Tractor",
]

LABOR_ROLES = [
    "Loader",
    "Forklift Operator",
    "Dock Coordinator",
]


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate warehouse demo and ML data."
    )

    parser.add_argument(
        "--appointments",
        type=int,
        default=1_000,
        help="Number of appointments to generate.",
    )

    parser.add_argument(
        "--mode",
        choices=["demo", "historical"],
        default="demo",
        help="Dataset type.",
    )

    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete previously generated data first.",
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help="Random seed.",
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=5_000,
        help="Rows written per database batch.",
    )

    return parser.parse_args()


def chunks(
    rows: Sequence[tuple],
    batch_size: int,
) -> Iterable[Sequence[tuple]]:
    for start in range(0, len(rows), batch_size):
        yield rows[start : start + batch_size]


def execute_batches(
    cursor: psycopg.Cursor,
    statement: str,
    rows: Sequence[tuple],
    batch_size: int,
) -> None:
    for batch in chunks(rows, batch_size):
        cursor.executemany(statement, batch)


def reset_generated_data(
    cursor: psycopg.Cursor,
) -> None:
    cursor.execute(
        """
        TRUNCATE TABLE
            appointment_recommendations,
            appointment_predictions,
            appointment_events,
            appointment_products,
            equipment_status_events,
            labor_shifts,
            equipment,
            appointments,
            products,
            customers,
            docks,
            carriers,
            facilities
        RESTART IDENTITY CASCADE;
        """
    )


def seed_facilities(
    cursor: psycopg.Cursor,
) -> list[str]:
    cursor.executemany(
        """
        INSERT INTO facilities (
            facility_id,
            facility_name,
            timezone,
            active
        )
        VALUES (%s, %s, %s, TRUE)
        ON CONFLICT (facility_id)
        DO UPDATE SET
            facility_name = EXCLUDED.facility_name,
            timezone = EXCLUDED.timezone,
            active = TRUE;
        """,
        FACILITIES,
    )

    return [facility[0] for facility in FACILITIES]


def seed_carriers(
    cursor: psycopg.Cursor,
) -> list[str]:
    rows = [
        (
            f"CAR{index:03d}",
            name,
        )
        for index, name in enumerate(
            CARRIER_NAMES[:CARRIER_COUNT],
            start=1,
        )
    ]

    cursor.executemany(
        """
        INSERT INTO carriers (
            carrier_id,
            carrier_name,
            active
        )
        VALUES (%s, %s, TRUE)
        ON CONFLICT (carrier_id)
        DO UPDATE SET
            carrier_name = EXCLUDED.carrier_name,
            active = TRUE;
        """,
        rows,
    )

    return [row[0] for row in rows]


def seed_customers(
    cursor: psycopg.Cursor,
    facility_ids: list[str],
    rng: random.Random,
) -> list[dict]:
    rows = []
    customers = []

    tiers = ["Standard", "Preferred", "Strategic", "VIP"]
    tier_weights = [55, 25, 15, 5]

    for number in range(1, CUSTOMER_COUNT + 1):
        tier = rng.choices(
            tiers,
            weights=tier_weights,
            k=1,
        )[0]

        if tier == "VIP":
            default_sla = 90
            annual_revenue = rng.uniform(
                50_000_000,
                250_000_000,
            )
        elif tier == "Strategic":
            default_sla = 105
            annual_revenue = rng.uniform(
                20_000_000,
                80_000_000,
            )
        elif tier == "Preferred":
            default_sla = 120
            annual_revenue = rng.uniform(
                5_000_000,
                30_000_000,
            )
        else:
            default_sla = 150
            annual_revenue = rng.uniform(
                500_000,
                10_000_000,
            )

        customer_id = f"CUST{number:04d}"
        customer_name = (
            f"{rng.choice(CUSTOMER_PREFIXES)} {number}"
        )
        preferred_facility = rng.choice(facility_ids)

        rows.append(
            (
                customer_id,
                customer_name,
                rng.choice(INDUSTRIES),
                tier,
                default_sla,
                round(annual_revenue, 2),
                preferred_facility,
            )
        )

        customers.append(
            {
                "customer_id": customer_id,
                "customer_name": customer_name,
                "priority_tier": tier,
                "default_sla_minutes": default_sla,
                "preferred_facility_id": (
                    preferred_facility
                ),
            }
        )

    cursor.executemany(
        """
        INSERT INTO customers (
            customer_id,
            customer_name,
            industry,
            priority_tier,
            default_sla_minutes,
            annual_revenue,
            preferred_facility_id,
            active
        )
        VALUES (
            %s, %s, %s, %s,
            %s, %s, %s, TRUE
        )
        ON CONFLICT (customer_id)
        DO UPDATE SET
            customer_name = EXCLUDED.customer_name,
            industry = EXCLUDED.industry,
            priority_tier = EXCLUDED.priority_tier,
            default_sla_minutes =
                EXCLUDED.default_sla_minutes,
            annual_revenue = EXCLUDED.annual_revenue,
            preferred_facility_id =
                EXCLUDED.preferred_facility_id,
            active = TRUE;
        """,
        rows,
    )

    return customers


def seed_docks(
    cursor: psycopg.Cursor,
    facility_ids: list[str],
) -> dict[str, list[str]]:
    rows = []
    docks_by_facility = {}

    for facility_id in facility_ids:
        facility_docks = []

        for dock_number in range(
            1,
            DOCKS_PER_FACILITY + 1,
        ):
            dock_id = (
                f"{facility_id}-DOCK-{dock_number:02d}"
            )

            if dock_number <= 6:
                temperature_zone = "Ambient"
            elif dock_number <= 8:
                temperature_zone = "Chilled"
            else:
                temperature_zone = "Frozen"

            rows.append(
                (
                    dock_id,
                    facility_id,
                    f"Dock {dock_number}",
                    "Standard",
                    temperature_zone,
                )
            )

            facility_docks.append(dock_id)

        docks_by_facility[facility_id] = facility_docks

    cursor.executemany(
        """
        INSERT INTO docks (
            dock_id,
            facility_id,
            dock_name,
            dock_type,
            temperature_zone,
            active
        )
        VALUES (%s, %s, %s, %s, %s, TRUE)
        ON CONFLICT (dock_id)
        DO UPDATE SET
            dock_name = EXCLUDED.dock_name,
            dock_type = EXCLUDED.dock_type,
            temperature_zone =
                EXCLUDED.temperature_zone,
            active = TRUE;
        """,
        rows,
    )

    return docks_by_facility


def seed_products(
    cursor: psycopg.Cursor,
    rng: random.Random,
) -> list[dict]:
    rows = []
    products = []

    for number in range(1, PRODUCT_COUNT + 1):
        category = rng.choice(PRODUCT_CATEGORIES)

        if category == "Frozen Foods":
            temperature_zone = "Frozen"
        elif category in {"Dairy", "Produce"}:
            temperature_zone = "Chilled"
        else:
            temperature_zone = "Ambient"

        length = round(rng.uniform(4, 48), 2)
        width = round(rng.uniform(4, 36), 2)
        height = round(rng.uniform(2, 30), 2)
        weight = round(rng.uniform(0.5, 80), 2)

        volume = round(
            length * width * height / 1728,
            4,
        )

        units_per_case = rng.choice(
            [1, 4, 6, 8, 12, 18, 24],
        )
        cases_per_pallet = rng.choice(
            [12, 16, 20, 24, 30, 36, 40, 48],
        )

        product_id = f"PROD{number:04d}"

        rows.append(
            (
                product_id,
                f"{category} Product {number}",
                f"SKU-{number:05d}",
                category,
                "Each",
                weight,
                length,
                width,
                height,
                volume,
                units_per_case,
                cases_per_pallet,
                temperature_zone,
                rng.choice(HANDLING_TYPES),
            )
        )

        products.append(
            {
                "product_id": product_id,
                "category": category,
                "temperature_zone": temperature_zone,
                "handling_type": rows[-1][13],
                "unit_weight_lb": weight,
                "unit_volume_cuft": volume,
                "units_per_case": units_per_case,
                "cases_per_pallet": cases_per_pallet,
            }
        )

    cursor.executemany(
        """
        INSERT INTO products (
            product_id,
            product_name,
            sku,
            category,
            unit_of_measure,
            unit_weight_lb,
            length_in,
            width_in,
            height_in,
            unit_volume_cuft,
            units_per_case,
            cases_per_pallet,
            temperature_zone,
            handling_type,
            active
        )
        VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, TRUE
        )
        ON CONFLICT (product_id)
        DO UPDATE SET
            product_name = EXCLUDED.product_name,
            category = EXCLUDED.category,
            active = TRUE;
        """,
        rows,
    )

    return products


def seed_equipment(
    cursor: psycopg.Cursor,
    facility_ids: list[str],
    rng: random.Random,
) -> None:
    equipment_rows = []
    event_rows = []
    now = datetime.now().replace(microsecond=0)

    for facility_id in facility_ids:
        for number in range(
            1,
            EQUIPMENT_PER_FACILITY + 1,
        ):
            equipment_id = (
                f"{facility_id}-EQ-{number:03d}"
            )
            equipment_type = rng.choice(
                EQUIPMENT_TYPES
            )

            status = rng.choices(
                [
                    "Available",
                    "In Use",
                    "Maintenance",
                    "Out of Service",
                ],
                weights=[55, 30, 10, 5],
                k=1,
            )[0]

            equipment_rows.append(
                (
                    equipment_id,
                    facility_id,
                    equipment_type,
                    f"{equipment_type} {number}",
                    f"Zone {rng.randint(1, 4)}",
                    status,
                    round(rng.uniform(8, 45), 2),
                    round(rng.uniform(2_000, 12_000), 2),
                )
            )

            if status in {
                "Maintenance",
                "Out of Service",
            }:
                event_time = now - timedelta(
                    hours=rng.randint(1, 12)
                )

                event_rows.append(
                    (
                        equipment_id,
                        status.upper().replace(" ", "_"),
                        event_time,
                        event_time
                        + timedelta(
                            hours=rng.randint(2, 24)
                        ),
                        f"{equipment_type} unavailable",
                    )
                )

    cursor.executemany(
        """
        INSERT INTO equipment (
            equipment_id,
            facility_id,
            equipment_type,
            equipment_name,
            zone,
            status,
            hourly_operating_cost,
            capacity,
            active
        )
        VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s, TRUE
        )
        ON CONFLICT (equipment_id)
        DO UPDATE SET
            status = EXCLUDED.status,
            active = TRUE;
        """,
        equipment_rows,
    )

    if event_rows:
        cursor.executemany(
            """
            INSERT INTO equipment_status_events (
                equipment_id,
                event_type,
                event_time,
                expected_resolution_time,
                notes
            )
            VALUES (%s, %s, %s, %s, %s);
            """,
            event_rows,
        )


def seed_labor_shifts(
    cursor: psycopg.Cursor,
    facility_ids: list[str],
    mode: str,
    rng: random.Random,
) -> None:
    rows = []

    today = date.today()
    day_range = 14 if mode == "demo" else 730

    for day_offset in range(-day_range, day_range + 1):
        shift_date = today + timedelta(
            days=day_offset
        )

        for facility_id in facility_ids:
            for shift_name in [
                "First",
                "Second",
                "Third",
            ]:
                for role in LABOR_ROLES:
                    planned = rng.randint(4, 20)

                    shortage = rng.choices(
                        [0, 1, 2, 3, 4],
                        weights=[45, 25, 15, 10, 5],
                        k=1,
                    )[0]

                    available = max(
                        0,
                        planned - shortage,
                    )

                    certified = (
                        available
                        if role == "Forklift Operator"
                        else rng.randint(
                            0,
                            min(available, 4),
                        )
                    )

                    rows.append(
                        (
                            facility_id,
                            shift_date,
                            shift_name,
                            role,
                            planned,
                            available,
                            certified,
                            round(
                                rng.uniform(20, 42),
                                2,
                            ),
                        )
                    )

    cursor.executemany(
        """
        INSERT INTO labor_shifts (
            facility_id,
            shift_date,
            shift_name,
            role,
            planned_headcount,
            available_headcount,
            forklift_certified_count,
            hourly_rate
        )
        VALUES (
            %s, %s, %s, %s,
            %s, %s, %s, %s
        )
        ON CONFLICT (
            facility_id,
            shift_date,
            shift_name,
            role
        )
        DO UPDATE SET
            planned_headcount =
                EXCLUDED.planned_headcount,
            available_headcount =
                EXCLUDED.available_headcount,
            forklift_certified_count =
                EXCLUDED.forklift_certified_count,
            hourly_rate = EXCLUDED.hourly_rate;
        """,
        rows,
    )


def appointment_time(
    mode: str,
    rng: random.Random,
) -> datetime:
    now = datetime.now().replace(
        second=0,
        microsecond=0,
    )

    if mode == "historical":
        days_back = rng.randint(30, 730)

        return (
            now
            - timedelta(days=days_back)
            + timedelta(
                minutes=rng.randrange(
                    0,
                    24 * 60,
                    15,
                )
            )
        )

    return now + timedelta(
        days=rng.randint(-2, 5),
        minutes=rng.randrange(
            0,
            24 * 60,
            15,
        ),
    )


def generate_outcomes(
    *,
    carrier_index: int,
    pallet_count: int,
    sku_count: int,
    total_weight: float,
    priority: int,
    traffic_severity: int,
    weather_severity: int,
    surge_indicator: bool,
    labor_shortage: int,
    equipment_shortage: int,
    distance_band: str,
    rng: random.Random,
) -> tuple[int, int]:
    carrier_delay_factor = (
        carrier_index % 6
    ) * 4

    distance_factor = {
        "Local": -8,
        "Regional": 4,
        "Long Haul": 14,
        "Cross Country": 24,
    }[distance_band]

    arrival_delay = (
        carrier_delay_factor
        + distance_factor
        + traffic_severity * 8
        + weather_severity * 10
        + (18 if surge_indicator else 0)
        + rng.gauss(0, 24)
    )

    actual_arrival_delay = max(
        -45,
        min(240, round(arrival_delay)),
    )

    loading_duration = (
        18
        + pallet_count * 1.75
        + sku_count * 1.4
        + total_weight / 15_000
        + labor_shortage * 12
        + equipment_shortage * 10
        + (12 if surge_indicator else 0)
        - priority * 1.5
        + rng.gauss(0, 10)
    )

    actual_loading_duration = max(
        15,
        min(300, round(loading_duration)),
    )

    return (
        actual_arrival_delay,
        actual_loading_duration,
    )


def generate_appointments(
    cursor: psycopg.Cursor,
    *,
    appointment_count: int,
    mode: str,
    batch_size: int,
    facility_ids: list[str],
    carrier_ids: list[str],
    customers: list[dict],
    products: list[dict],
    docks_by_facility: dict[str, list[str]],
    rng: random.Random,
) -> None:
    prefix = "HIST" if mode == "historical" else "DEMO"

    appointments = []
    product_lines = []
    events = []
    predictions = []
    recommendations = []

    now = datetime.now().replace(
        second=0,
        microsecond=0,
    )

    for number in range(1, appointment_count + 1):
        appt_id = f"{prefix}{number:07d}"

        customer = rng.choice(customers)

        facility_id = (
            customer["preferred_facility_id"]
            if rng.random() < 0.65
            else rng.choice(facility_ids)
        )

        carrier_id = rng.choice(carrier_ids)
        carrier_index = carrier_ids.index(carrier_id)

        scheduled_time = appointment_time(mode, rng)

        selected_products = rng.sample(
            products,
            k=rng.randint(3, 9),
        )

        total_weight = 0.0
        total_volume = 0.0
        total_pallets = 0

        for product in selected_products:
            quantity = rng.randint(10, 500)

            case_count = math.ceil(
                quantity
                / product["units_per_case"]
            )

            pallet_count = math.ceil(
                case_count
                / product["cases_per_pallet"]
            )

            line_weight = round(
                product["unit_weight_lb"]
                * quantity,
                2,
            )

            line_volume = round(
                product["unit_volume_cuft"]
                * quantity,
                4,
            )

            total_weight += line_weight
            total_volume += line_volume
            total_pallets += pallet_count

            product_lines.append(
                (
                    appt_id,
                    product["product_id"],
                    quantity,
                    case_count,
                    pallet_count,
                    line_weight,
                    line_volume,
                )
            )

        sku_count = len(selected_products)

        priority = {
            "Standard": 1,
            "Preferred": 2,
            "Strategic": 4,
            "VIP": 5,
        }[customer["priority_tier"]]

        distance_band = rng.choices(
            DISTANCE_BANDS,
            weights=[25, 40, 25, 10],
            k=1,
        )[0]

        traffic_severity = rng.choices(
            [0, 1, 2, 3, 4, 5],
            weights=[20, 25, 25, 15, 10, 5],
            k=1,
        )[0]

        weather_severity = rng.choices(
            [0, 1, 2, 3, 4, 5],
            weights=[55, 20, 12, 7, 4, 2],
            k=1,
        )[0]

        surge_indicator = rng.random() < 0.12
        labor_shortage = rng.randint(0, 3)
        equipment_shortage = rng.randint(0, 2)

        (
            actual_arrival_delay,
            actual_loading_duration,
        ) = generate_outcomes(
            carrier_index=carrier_index,
            pallet_count=total_pallets,
            sku_count=sku_count,
            total_weight=total_weight,
            priority=priority,
            traffic_severity=traffic_severity,
            weather_severity=weather_severity,
            surge_indicator=surge_indicator,
            labor_shortage=labor_shortage,
            equipment_shortage=equipment_shortage,
            distance_band=distance_band,
            rng=rng,
        )

        actual_arrival = (
            scheduled_time
            + timedelta(
                minutes=actual_arrival_delay
            )
        )

        queue_minutes = max(
            0,
            round(
                rng.gauss(
                    10
                    + traffic_severity * 2
                    + labor_shortage * 4,
                    8,
                )
            ),
        )

        actual_loading_start = (
            actual_arrival
            + timedelta(minutes=queue_minutes)
        )

        actual_loading_end = (
            actual_loading_start
            + timedelta(
                minutes=actual_loading_duration
            )
        )

        actual_departure = (
            actual_loading_end
            + timedelta(
                minutes=rng.randint(5, 20)
            )
        )

        actual_turn_time = round(
            (
                actual_departure
                - actual_arrival
            ).total_seconds()
            / 60
        )

        sla_minutes = customer[
            "default_sla_minutes"
        ]

        actual_sla_missed = (
            actual_departure
            > scheduled_time
            + timedelta(minutes=sla_minutes)
        )

        estimated_arrival = (
            scheduled_time
            + timedelta(
                minutes=actual_arrival_delay
                + rng.randint(-20, 20)
            )
        )

        assigned_dock = rng.choice(
            docks_by_facility[facility_id]
        )

        if mode == "historical":
            status = "Completed"
        else:
            hours_from_now = (
                scheduled_time - now
            ).total_seconds() / 3600

            if hours_from_now > 3:
                status = "Scheduled"
            elif hours_from_now > 0:
                status = rng.choice(
                    ["En Route", "Arrived"]
                )
            elif hours_from_now > -3:
                status = rng.choice(
                    [
                        "Waiting",
                        "Dock Assigned",
                        "In Progress",
                    ]
                )
            else:
                status = "Completed"

        if mode == "demo" and status != "Completed":
            stored_actual_arrival = (
                actual_arrival
                if status
                in {
                    "Arrived",
                    "Waiting",
                    "Dock Assigned",
                    "In Progress",
                }
                else None
            )

            stored_loading_start = (
                actual_loading_start
                if status == "In Progress"
                else None
            )

            stored_loading_end = None
            stored_departure = None
            stored_loading_duration = None
            stored_turn_time = None
            stored_sla_missed = None
        else:
            stored_actual_arrival = actual_arrival
            stored_loading_start = actual_loading_start
            stored_loading_end = actual_loading_end
            stored_departure = actual_departure
            stored_loading_duration = (
                actual_loading_duration
            )
            stored_turn_time = actual_turn_time
            stored_sla_missed = actual_sla_missed

        appointments.append(
            (
                appt_id,
                scheduled_time,
                customer["customer_id"],
                customer["customer_name"],
                facility_id,
                carrier_id,
                scheduled_time,
                estimated_arrival,
                stored_actual_arrival,
                None,
                None,
                None,
                None,
                assigned_dock,
                status,
                rng.choice(["Inbound", "Outbound"]),
                rng.choice(
                    [
                        "Palletized",
                        "Floor Loaded",
                        "Mixed",
                    ]
                ),
                f"TRL-{rng.randint(10000, 99999)}",
                total_pallets,
                sku_count,
                round(total_weight, 2),
                round(total_volume, 2),
                priority,
                sla_minutes,
                rng.choice(
                    [100, 150, 200, 250, 350, 500]
                ),
                stored_loading_start,
                stored_loading_end,
                stored_departure,
                actual_arrival_delay,
                stored_loading_duration,
                stored_turn_time,
                stored_sla_missed,
                distance_band,
                traffic_severity,
                weather_severity,
                surge_indicator,
            )
        )

        events.append(
            (
                appt_id,
                "APPOINTMENT_CREATED",
                scheduled_time
                - timedelta(
                    days=rng.randint(1, 14)
                ),
                "Appointment created",
            )
        )

        if stored_actual_arrival is not None:
            events.append(
                (
                    appt_id,
                    "ARRIVED",
                    stored_actual_arrival,
                    "Carrier arrived",
                )
            )

        if stored_loading_start is not None:
            events.append(
                (
                    appt_id,
                    "LOADING_STARTED",
                    stored_loading_start,
                    "Loading started",
                )
            )

        if stored_loading_end is not None:
            events.append(
                (
                    appt_id,
                    "LOADING_COMPLETED",
                    stored_loading_end,
                    "Loading completed",
                )
            )

        if mode == "demo":
            predicted_delay = max(
                0,
                actual_arrival_delay
                + rng.randint(-12, 12),
            )

            predicted_duration = max(
                15,
                actual_loading_duration
                + rng.randint(-10, 10),
            )

            risk_score = min(
                100,
                max(
                    0,
                    round(
                        predicted_delay * 0.45
                        + predicted_duration * 0.20
                        + traffic_severity * 5
                        + weather_severity * 6
                        + labor_shortage * 8
                        + equipment_shortage * 7
                    ),
                ),
            )

            miss_probability = round(
                max(
                    0.01,
                    min(0.99, risk_score / 100),
                ),
                4,
            )

            recovery_probability = round(
                max(
                    0.02,
                    min(
                        0.98,
                        1
                        - miss_probability
                        + priority * 0.03,
                    ),
                ),
                4,
            )

            predicted_missed = risk_score >= 65

            predictions.append(
                (
                    appt_id,
                    estimated_arrival,
                    predicted_delay,
                    predicted_duration,
                    miss_probability,
                    recovery_probability,
                    risk_score,
                    predicted_missed,
                    "demo-rules-v1",
                )
            )

            if risk_score >= 65:
                recommended_dock = rng.choice(
                    docks_by_facility[facility_id]
                )

                exposure = round(
                    max(
                        0,
                        actual_turn_time
                        - sla_minutes,
                    )
                    / 60
                    * appointments[-1][24],
                    2,
                )

                savings = round(
                    exposure * 0.70,
                    2,
                )

                recommendations.append(
                    (
                        appt_id,
                        "SLA_RECOVERY",
                        (
                            "Prioritize the appointment, "
                            f"move it to {recommended_dock}, "
                            "and add one loader."
                        ),
                        recommended_dock,
                        1,
                        1,
                        exposure,
                        50.00,
                        savings,
                        "Pending",
                    )
                )

        if len(appointments) >= batch_size:
            write_appointment_batch(
                cursor,
                appointments,
                product_lines,
                events,
                predictions,
                recommendations,
            )

            appointments.clear()
            product_lines.clear()
            events.clear()
            predictions.clear()
            recommendations.clear()

    if appointments:
        write_appointment_batch(
            cursor,
            appointments,
            product_lines,
            events,
            predictions,
            recommendations,
        )


def write_appointment_batch(
    cursor: psycopg.Cursor,
    appointments: list[tuple],
    product_lines: list[tuple],
    events: list[tuple],
    predictions: list[tuple],
    recommendations: list[tuple],
) -> None:
    with cursor.copy(
        """
        COPY appointments (
            appt_id,
            appt_date,
            customer_id,
            customer_name,
            facility_id,
            carrier_id,
            scheduled_time,
            estimated_arrival_time,
            actual_arrival_time,
            planned_start_time,
            actual_start_time,
            planned_end_time,
            actual_end_time,
            assigned_dock_id,
            status,
            appointment_type,
            load_type,
            trailer_number,
            pallet_count,
            sku_count,
            total_weight,
            total_cube,
            priority,
            sla_minutes,
            detention_cost_per_hour,
            actual_loading_start_time,
            actual_loading_end_time,
            actual_departure_time,
            actual_arrival_delay_minutes,
            actual_loading_duration_minutes,
            actual_turn_time_minutes,
            actual_sla_missed,
            distance_band,
            traffic_severity,
            weather_severity,
            surge_indicator
        )
        FROM STDIN
        """
    ) as copy:
        for row in appointments:
            copy.write_row(row)

    with cursor.copy(
        """
        COPY appointment_products (
            appt_id,
            product_id,
            quantity,
            case_count,
            pallet_count,
            line_weight_lb,
            line_volume_cuft
        )
        FROM STDIN
        """
    ) as copy:
        for row in product_lines:
            copy.write_row(row)

    with cursor.copy(
        """
        COPY appointment_events (
            appt_id,
            event_type,
            event_time,
            notes
        )
        FROM STDIN
        """
    ) as copy:
        for row in events:
            copy.write_row(row)

    if predictions:
        with cursor.copy(
            """
            COPY appointment_predictions (
                appt_id,
                predicted_arrival_time,
                predicted_delay_minutes,
                predicted_duration_minutes,
                sla_miss_probability,
                sla_recovery_probability,
                turn_risk_score,
                predicted_missed,
                model_version
            )
            FROM STDIN
            """
        ) as copy:
            for row in predictions:
                copy.write_row(row)

    if recommendations:
        with cursor.copy(
            """
            COPY appointment_recommendations (
                appt_id,
                recommendation_type,
                recommended_action,
                recommended_dock_id,
                recommended_sequence,
                additional_labor,
                estimated_loss_without_action,
                estimated_cost_of_action,
                estimated_savings,
                status
            )
            FROM STDIN
            """
        ) as copy:
            for row in recommendations:
                copy.write_row(row)


def main() -> None:
    args = parse_arguments()

    if args.appointments < 1:
        raise ValueError(
            "--appointments must be greater than zero"
        )

    rng = random.Random(args.seed)

    with psycopg.connect(DATABASE_URL) as connection:
        with connection.cursor() as cursor:
            if args.reset:
                print("Resetting generated data...")
                reset_generated_data(cursor)

            print("Seeding reference data...")

            facility_ids = seed_facilities(cursor)
            carrier_ids = seed_carriers(cursor)

            customers = seed_customers(
                cursor,
                facility_ids,
                rng,
            )

            docks_by_facility = seed_docks(
                cursor,
                facility_ids,
            )

            products = seed_products(cursor, rng)

            seed_equipment(
                cursor,
                facility_ids,
                rng,
            )

            seed_labor_shifts(
                cursor,
                facility_ids,
                args.mode,
                rng,
            )

            print(
                f"Generating {args.appointments:,} "
                f"{args.mode} appointments..."
            )

            generate_appointments(
                cursor,
                appointment_count=args.appointments,
                mode=args.mode,
                batch_size=args.batch_size,
                facility_ids=facility_ids,
                carrier_ids=carrier_ids,
                customers=customers,
                products=products,
                docks_by_facility=docks_by_facility,
                rng=rng,
            )

        connection.commit()

    print()
    print("Data generation completed successfully.")
    print(f"Mode: {args.mode}")
    print(f"Appointments added: {args.appointments:,}")
    print(f"Random seed: {args.seed}")


if __name__ == "__main__":
    main()