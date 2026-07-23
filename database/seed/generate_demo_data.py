from __future__ import annotations

import math
import random
from datetime import datetime, timedelta
from decimal import Decimal

import psycopg


DATABASE_URL = (
    "postgresql://turntime:localpassword"
    "@localhost:5432/turn_time"
)

RANDOM_SEED = 42
APPOINTMENT_COUNT = 1_000
PRODUCT_COUNT = 250

random.seed(RANDOM_SEED)


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

CATEGORIES = [
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

TEMPERATURE_ZONES = [
    "Ambient",
    "Chilled",
    "Frozen",
]

HANDLING_TYPES = [
    "Standard",
    "Fragile",
    "Hazardous",
    "Oversized",
    "High Value",
]

STATUS_OPTIONS = [
    "Scheduled",
    "En Route",
    "Arrived",
    "Waiting",
    "Dock Assigned",
    "In Progress",
    "Completed",
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

CUSTOMERS = [
    "FreshMart",
    "Value Foods",
    "National Retail Group",
    "Metro Grocery",
    "Home Essentials",
    "Premier Wholesale",
    "Urban Markets",
    "Regional Pharmacy",
    "Quick Commerce",
    "Industrial Supply Co",
    "Consumer Goods Group",
    "Global Retail Partners",
]


def calculate_volume_cuft(
    length_in: float,
    width_in: float,
    height_in: float,
) -> Decimal:
    cubic_inches = length_in * width_in * height_in
    return Decimal(str(round(cubic_inches / 1728, 4)))


def clear_demo_data(cursor: psycopg.Cursor) -> None:
    cursor.execute(
        """
        TRUNCATE TABLE
            appointment_recommendations,
            appointment_predictions,
            appointment_events,
            appointment_products,
            appointments,
            products,
            docks,
            carriers,
            facilities
        RESTART IDENTITY CASCADE;
        """
    )


def seed_facilities(cursor: psycopg.Cursor) -> None:
    cursor.executemany(
        """
        INSERT INTO facilities (
            facility_id,
            facility_name,
            timezone,
            active
        )
        VALUES (%s, %s, %s, TRUE);
        """,
        FACILITIES,
    )


def seed_carriers(cursor: psycopg.Cursor) -> list[str]:
    rows = [
        (
            f"CAR{index:03d}",
            name,
        )
        for index, name in enumerate(
            CARRIER_NAMES,
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
        VALUES (%s, %s, TRUE);
        """,
        rows,
    )

    return [row[0] for row in rows]


def seed_docks(cursor: psycopg.Cursor) -> list[str]:
    rows = []

    for facility_index, facility in enumerate(
        FACILITIES,
        start=1,
    ):
        facility_id = facility[0]

        for dock_number in range(1, 11):
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
        VALUES (%s, %s, %s, %s, %s, TRUE);
        """,
        rows,
    )

    return [row[0] for row in rows]


def seed_products(cursor: psycopg.Cursor) -> list[dict]:
    products: list[dict] = []
    insert_rows = []

    for number in range(1, PRODUCT_COUNT + 1):
        category = random.choice(CATEGORIES)

        if category == "Frozen Foods":
            temperature_zone = "Frozen"
        elif category in {"Dairy", "Produce"}:
            temperature_zone = "Chilled"
        else:
            temperature_zone = "Ambient"

        length = round(random.uniform(4, 48), 2)
        width = round(random.uniform(4, 36), 2)
        height = round(random.uniform(2, 30), 2)
        unit_weight = round(
            random.uniform(0.5, 80),
            2,
        )

        unit_volume = calculate_volume_cuft(
            length,
            width,
            height,
        )

        units_per_case = random.choice(
            [1, 4, 6, 8, 12, 18, 24],
        )

        cases_per_pallet = random.choice(
            [12, 16, 20, 24, 30, 36, 40, 48],
        )

        product = {
            "product_id": f"PROD{number:04d}",
            "sku": f"SKU-{number:05d}",
            "unit_weight": Decimal(
                str(unit_weight)
            ),
            "unit_volume": unit_volume,
            "units_per_case": units_per_case,
            "cases_per_pallet": cases_per_pallet,
            "temperature_zone": temperature_zone,
        }

        products.append(product)

        insert_rows.append(
            (
                product["product_id"],
                f"{category} Product {number}",
                product["sku"],
                category,
                "Each",
                product["unit_weight"],
                Decimal(str(length)),
                Decimal(str(width)),
                Decimal(str(height)),
                product["unit_volume"],
                units_per_case,
                cases_per_pallet,
                temperature_zone,
                random.choice(HANDLING_TYPES),
            )
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
            %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, TRUE
        );
        """,
        insert_rows,
    )

    return products


def determine_status(
    scheduled_time: datetime,
    now: datetime,
) -> str:
    hours_from_now = (
        scheduled_time - now
    ).total_seconds() / 3600

    if hours_from_now > 8:
        return "Scheduled"

    if hours_from_now > 2:
        return random.choice(
            ["Scheduled", "En Route"],
        )

    if hours_from_now > 0:
        return random.choice(
            ["En Route", "Arrived", "Waiting"],
        )

    if hours_from_now > -2:
        return random.choice(
            [
                "Arrived",
                "Waiting",
                "Dock Assigned",
                "In Progress",
            ]
        )

    return random.choice(
        ["In Progress", "Completed"],
    )


def seed_appointments(
    cursor: psycopg.Cursor,
    carrier_ids: list[str],
    dock_ids: list[str],
    products: list[dict],
) -> None:
    now = datetime.now().replace(
        second=0,
        microsecond=0,
    )

    appointments = []
    appointment_products = []
    events = []
    predictions = []
    recommendations = []

    facility_ids = [
        facility[0]
        for facility in FACILITIES
    ]

    docks_by_facility: dict[str, list[str]] = {
        facility_id: [
            dock_id
            for dock_id in dock_ids
            if dock_id.startswith(facility_id)
        ]
        for facility_id in facility_ids
    }

    for number in range(1, APPOINTMENT_COUNT + 1):
        appt_id = f"APP{number:05d}"
        facility_id = random.choice(facility_ids)
        carrier_id = random.choice(carrier_ids)

        scheduled_time = now + timedelta(
            days=random.randint(-7, 7),
            minutes=random.randrange(
                0,
                24 * 60,
                15,
            ),
        )

        arrival_delay = int(
            max(
                -45,
                min(
                    180,
                    random.gauss(18, 42),
                ),
            )
        )

        estimated_arrival = (
            scheduled_time
            + timedelta(minutes=arrival_delay)
        )

        status = determine_status(
            scheduled_time,
            now,
        )

        actual_arrival = None

        if status in {
            "Arrived",
            "Waiting",
            "Dock Assigned",
            "In Progress",
            "Completed",
        }:
            actual_arrival = (
                scheduled_time
                + timedelta(
                    minutes=arrival_delay
                    + random.randint(-10, 10)
                )
            )

        appointment_type = random.choice(
            ["Inbound", "Outbound"],
        )

        priority = random.choices(
            [1, 2, 3, 4, 5],
            weights=[35, 30, 20, 10, 5],
            k=1,
        )[0]

        assigned_dock_id = None

        if status in {
            "Dock Assigned",
            "In Progress",
            "Completed",
        }:
            assigned_dock_id = random.choice(
                docks_by_facility[facility_id]
            )

        customer_index = random.randint(
            1,
            len(CUSTOMERS),
        )

        customer_name = CUSTOMERS[
            customer_index - 1
        ]

        selected_products = random.sample(
            products,
            k=random.randint(3, 10),
        )

        total_weight = Decimal("0")
        total_volume = Decimal("0")
        total_pallets = 0
        total_skus = len(selected_products)

        for product in selected_products:
            quantity = random.randint(10, 600)

            case_count = math.ceil(
                quantity
                / product["units_per_case"]
            )

            pallet_count = math.ceil(
                case_count
                / product["cases_per_pallet"]
            )

            line_weight = (
                product["unit_weight"]
                * quantity
            )

            line_volume = (
                product["unit_volume"]
                * quantity
            )

            total_weight += line_weight
            total_volume += line_volume
            total_pallets += pallet_count

            appointment_products.append(
                (
                    appt_id,
                    product["product_id"],
                    quantity,
                    case_count,
                    pallet_count,
                    line_weight.quantize(
                        Decimal("0.01")
                    ),
                    line_volume.quantize(
                        Decimal("0.0001")
                    ),
                )
            )

        predicted_duration = int(
            20
            + total_pallets * 2.2
            + total_skus * 1.5
            + random.gauss(0, 8)
        )

        predicted_duration = max(
            20,
            min(predicted_duration, 240),
        )

        sla_minutes = random.choice(
            [90, 120, 150],
        )

        sla_deadline = scheduled_time + timedelta(
            minutes=sla_minutes,
        )

        predicted_start = max(
            now,
            estimated_arrival,
        )

        predicted_completion = (
            predicted_start
            + timedelta(
                minutes=predicted_duration
            )
        )

        minutes_past_sla = max(
            0,
            int(
                (
                    predicted_completion
                    - sla_deadline
                ).total_seconds()
                / 60
            ),
        )

        predicted_missed = (
            predicted_completion > sla_deadline
        )

        turn_risk_score = min(
            100,
            max(
                0,
                int(
                    arrival_delay * 0.45
                    + predicted_duration * 0.25
                    + priority * 6
                    + (
                        20
                        if assigned_dock_id is None
                        else 0
                    )
                ),
            ),
        )

        miss_probability = Decimal(
            str(
                round(
                    min(
                        0.99,
                        max(
                            0.01,
                            turn_risk_score / 100,
                        ),
                    ),
                    4,
                )
            )
        )

        random_adjustment = Decimal(
            str(
                round(
                    random.uniform(-0.1, 0.2),
                    4,
                )
            )
        )

        recovery_probability = (
            Decimal("1.00")
            - miss_probability
            + random_adjustment
        )

        recovery_probability = max(
            Decimal("0.05"),
            min(
                Decimal("0.98"),
                recovery_probability,
            ),
        ).quantize(
            Decimal("0.0001")
        )

        detention_rate = Decimal(
            str(
                random.choice(
                    [100, 150, 200, 250, 350, 500]
                )
            )
        )
        appointments.append(
            (
                appt_id,
                scheduled_time.date(),
                f"CUST{customer_index:03d}",
                customer_name,
                facility_id,
                carrier_id,
                scheduled_time,
                estimated_arrival,
                actual_arrival,
                None,
                None,
                None,
                None,
                assigned_dock_id,
                status,
                appointment_type,
                random.choice(
                    [
                        "Palletized",
                        "Floor Loaded",
                        "Mixed",
                    ]
                ),
                f"TRL-{random.randint(10000, 99999)}",
                total_pallets,
                total_skus,
                total_weight.quantize(
                    Decimal("0.01")
                ),
                total_volume.quantize(
                    Decimal("0.01")
                ),
                priority,
                sla_minutes,
                detention_rate,
            )
        )

        events.append(
            (
                appt_id,
                "APPOINTMENT_CREATED",
                scheduled_time
                - timedelta(
                    days=random.randint(1, 10)
                ),
                "Appointment created",
            )
        )

        if actual_arrival:
            events.append(
                (
                    appt_id,
                    "ARRIVED",
                    actual_arrival,
                    "Carrier arrived at facility",
                )
            )

        predictions.append(
            (
                appt_id,
                estimated_arrival,
                max(0, arrival_delay),
                predicted_duration,
                miss_probability,
                recovery_probability,
                turn_risk_score,
                predicted_missed,
                "demo-rules-v1",
            )
        )

        if turn_risk_score >= 65:
            recommended_dock = random.choice(
                docks_by_facility[facility_id]
            )

            loss_without_action = (
                detention_rate
                * Decimal(
                    str(minutes_past_sla / 60)
                )
            )

            estimated_savings = (
                loss_without_action
                * Decimal("0.70")
            )

            recommendations.append(
                (
                    appt_id,
                    "SLA_RECOVERY",
                    (
                        "Prioritize this appointment and "
                        f"move it to {recommended_dock}."
                    ),
                    recommended_dock,
                    1,
                    random.choice([0, 1, 2]),
                    loss_without_action.quantize(
                        Decimal("0.01")
                    ),
                    Decimal("50.00"),
                    estimated_savings.quantize(
                        Decimal("0.01")
                    ),
                    "Pending",
                )
            )

    cursor.executemany(
        """
        INSERT INTO appointments (
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
            detention_cost_per_hour
        )
        VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s
        );
        """,
        appointments,
    )

    cursor.executemany(
        """
        INSERT INTO appointment_products (
            appt_id,
            product_id,
            quantity,
            case_count,
            pallet_count,
            line_weight_lb,
            line_volume_cuft
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s);
        """,
        appointment_products,
    )

    cursor.executemany(
        """
        INSERT INTO appointment_events (
            appt_id,
            event_type,
            event_time,
            notes
        )
        VALUES (%s, %s, %s, %s);
        """,
        events,
    )

    cursor.executemany(
        """
        INSERT INTO appointment_predictions (
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
        VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s
        );
        """,
        predictions,
    )

    if recommendations:
        cursor.executemany(
            """
            INSERT INTO appointment_recommendations (
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
            VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s
            );
            """,
            recommendations,
        )


def main() -> None:
    with psycopg.connect(DATABASE_URL) as connection:
        with connection.cursor() as cursor:
            clear_demo_data(cursor)

            seed_facilities(cursor)
            carrier_ids = seed_carriers(cursor)
            dock_ids = seed_docks(cursor)
            products = seed_products(cursor)

            seed_appointments(
                cursor,
                carrier_ids,
                dock_ids,
                products,
            )

        connection.commit()

    print("Demo data generated successfully.")
    print(f"Facilities: {len(FACILITIES)}")
    print(f"Products: {PRODUCT_COUNT}")
    print(f"Appointments: {APPOINTMENT_COUNT}")


if __name__ == "__main__":
    main()