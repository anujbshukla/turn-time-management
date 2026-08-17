from __future__ import annotations

import math
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


class ResourcePlanningService:
    """Create/update the planned resource context required by ML-v2.

    Generated demo appointments already have allocations. This service makes
    appointments created or edited through the application use the same
    feature contract instead of silently scoring with zero resource features.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def ensure_allocation(
        self,
        appt_id: str,
    ) -> dict[str, Any]:
        row = self.db.execute(
            text(
                """
                SELECT
                    appointment.appt_id,
                    appointment.facility_id,
                    appointment.scheduled_time,
                    COALESCE(appointment.pallet_count, 0) AS pallet_count,
                    COALESCE(appointment.sku_count, 0) AS sku_count,

                    COALESCE(
                        profile.base_loader_capacity,
                        12
                    ) AS loader_capacity,

                    COALESCE(
                        profile.base_forklift_capacity,
                        6
                    ) AS forklift_capacity,

                    COALESCE(
                        (
                            SELECT AVG(
                                product_profile.handling_complexity_factor
                            )
                            FROM appointment_products line
                            JOIN product_operational_profiles product_profile
                              ON product_profile.product_id = line.product_id
                            WHERE line.appt_id = appointment.appt_id
                        ),
                        1.0
                    ) AS product_complexity,

                    COALESCE(
                        (
                            SELECT AVG(
                                product_profile.forklift_intensity
                            )
                            FROM appointment_products line
                            JOIN product_operational_profiles product_profile
                              ON product_profile.product_id = line.product_id
                            WHERE line.appt_id = appointment.appt_id
                        ),
                        1.0
                    ) AS forklift_intensity,

                    COALESCE(
                        (
                            SELECT AVG(
                                product_profile.staging_intensity
                            )
                            FROM appointment_products line
                            JOIN product_operational_profiles product_profile
                              ON product_profile.product_id = line.product_id
                            WHERE line.appt_id = appointment.appt_id
                        ),
                        1.0
                    ) AS staging_intensity,

                    (
                        SELECT COUNT(*)
                        FROM docks dock
                        WHERE dock.facility_id = appointment.facility_id
                          AND dock.active = TRUE
                    ) AS active_docks,

                    (
                        SELECT COUNT(*)
                        FROM appointments peer
                        WHERE peer.appt_id LIKE 'DEMO%'
                          AND peer.appt_id <> appointment.appt_id
                          AND peer.facility_id = appointment.facility_id
                          AND peer.status NOT IN ('Completed', 'Cancelled')
                          AND peer.scheduled_time >=
                              appointment.scheduled_time - INTERVAL '60 minutes'
                          AND peer.scheduled_time <
                              appointment.scheduled_time + INTERVAL '60 minutes'
                    ) AS nearby_appointments,

                    COALESCE(
                        (
                            SELECT SUM(allocation.planned_loaders)
                            FROM appointments peer
                            JOIN appointment_resource_allocations allocation
                              ON allocation.appt_id = peer.appt_id
                            WHERE peer.appt_id <> appointment.appt_id
                              AND peer.facility_id = appointment.facility_id
                              AND peer.status NOT IN ('Completed', 'Cancelled')
                              AND peer.scheduled_time >=
                                  appointment.scheduled_time - INTERVAL '60 minutes'
                              AND peer.scheduled_time <
                                  appointment.scheduled_time + INTERVAL '60 minutes'
                        ),
                        0
                    ) AS nearby_loaders,

                    COALESCE(
                        (
                            SELECT SUM(allocation.planned_forklifts)
                            FROM appointments peer
                            JOIN appointment_resource_allocations allocation
                              ON allocation.appt_id = peer.appt_id
                            WHERE peer.appt_id <> appointment.appt_id
                              AND peer.facility_id = appointment.facility_id
                              AND peer.status NOT IN ('Completed', 'Cancelled')
                              AND peer.scheduled_time >=
                                  appointment.scheduled_time - INTERVAL '60 minutes'
                              AND peer.scheduled_time <
                                  appointment.scheduled_time + INTERVAL '60 minutes'
                        ),
                        0
                    ) AS nearby_forklifts

                FROM appointments appointment
                LEFT JOIN facility_operational_profiles profile
                  ON profile.facility_id = appointment.facility_id
                WHERE appointment.appt_id = :appt_id;
                """
            ),
            {"appt_id": appt_id},
        ).mappings().one_or_none()

        if row is None:
            raise ValueError(
                f"Appointment {appt_id} does not exist."
            )

        pallet_count = int(row["pallet_count"] or 0)
        sku_count = int(row["sku_count"] or 0)
        complexity = float(row["product_complexity"] or 1.0)
        forklift_intensity = float(
            row["forklift_intensity"] or 1.0
        )
        staging_intensity = float(
            row["staging_intensity"] or 1.0
        )

        planned_loaders = 1
        planned_loaders += int(pallet_count >= 18)
        planned_loaders += int(pallet_count >= 36)
        planned_loaders += int(complexity >= 1.30)
        planned_loaders = max(1, min(4, planned_loaders))

        planned_forklifts = 1
        if pallet_count >= 30 or forklift_intensity >= 1.25:
            planned_forklifts += 1
        if pallet_count >= 45 and forklift_intensity >= 1.35:
            planned_forklifts += 1
        planned_forklifts = max(
            1,
            min(3, planned_forklifts),
        )

        planned_staging_labor = 0
        if (
            pallet_count >= 24
            or sku_count >= 8
            or staging_intensity >= 1.15
        ):
            planned_staging_labor = 1
        if (
            pallet_count >= 40
            and sku_count >= 12
            and staging_intensity >= 1.20
        ):
            planned_staging_labor = 2

        queue_depth = int(row["nearby_appointments"] or 0)
        active_docks = max(1, int(row["active_docks"] or 1))

        dock_congestion = min(
            100.0,
            (queue_depth / active_docks) * 75.0,
        )

        loader_capacity = max(
            1,
            int(row["loader_capacity"] or 1),
        )
        forklift_capacity = max(
            1,
            int(row["forklift_capacity"] or 1),
        )

        labor_utilization = min(
            100.0,
            (
                (
                    int(row["nearby_loaders"] or 0)
                    + planned_loaders
                    + planned_staging_labor
                )
                / loader_capacity
            )
            * 100.0,
        )

        forklift_utilization = min(
            100.0,
            (
                (
                    int(row["nearby_forklifts"] or 0)
                    + planned_forklifts
                )
                / forklift_capacity
            )
            * 100.0,
        )

        values = {
            "appt_id": appt_id,
            "planned_loaders": planned_loaders,
            "planned_forklifts": planned_forklifts,
            "planned_staging_labor": planned_staging_labor,
            "queue_depth_at_arrival": queue_depth,
            "dock_congestion_percent": round(
                dock_congestion,
                2,
            ),
            "labor_utilization_percent": round(
                labor_utilization,
                2,
            ),
            "forklift_utilization_percent": round(
                forklift_utilization,
                2,
            ),
        }

        self.db.execute(
            text(
                """
                INSERT INTO appointment_resource_allocations (
                    appt_id,
                    planned_loaders,
                    planned_forklifts,
                    planned_staging_labor,
                    queue_depth_at_arrival,
                    dock_congestion_percent,
                    labor_utilization_percent,
                    forklift_utilization_percent,
                    resource_plan_source
                )
                VALUES (
                    :appt_id,
                    :planned_loaders,
                    :planned_forklifts,
                    :planned_staging_labor,
                    :queue_depth_at_arrival,
                    :dock_congestion_percent,
                    :labor_utilization_percent,
                    :forklift_utilization_percent,
                    'ML-v2 Planner'
                )
                ON CONFLICT (appt_id)
                DO UPDATE SET
                    planned_loaders =
                        EXCLUDED.planned_loaders,
                    planned_forklifts =
                        EXCLUDED.planned_forklifts,
                    planned_staging_labor =
                        EXCLUDED.planned_staging_labor,
                    queue_depth_at_arrival =
                        EXCLUDED.queue_depth_at_arrival,
                    dock_congestion_percent =
                        EXCLUDED.dock_congestion_percent,
                    labor_utilization_percent =
                        EXCLUDED.labor_utilization_percent,
                    forklift_utilization_percent =
                        EXCLUDED.forklift_utilization_percent,
                    resource_plan_source =
                        EXCLUDED.resource_plan_source;
                """
            ),
            values,
        )
        self.db.commit()
        return values
