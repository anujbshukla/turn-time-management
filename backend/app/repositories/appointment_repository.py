from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Appointment
from typing import Any

from sqlalchemy import text

class AppointmentRepository:
    def get_paginated(
        self,
        *,
        page: int = 1,
        page_size: int = 10,
        facility_id: str | None = None,
        status: str | None = None,
        risk_level: str | None = None,
        outcome: str | None = None,
        search: str | None = None,
    ) -> dict[str, Any]:
        offset = (page - 1) * page_size

        parameters = {
            "page_size": page_size,
            "offset": offset,
            "facility_id": facility_id,
            "status": status,
            "risk_level": risk_level,
            "outcome": outcome,
            "search": f"%{search.strip()}%" if search else None,
        }

        rows = self.db.execute(
            text(
                """
                SELECT
                    a.appt_id,
                    a.customer_name,
                    a.customer_id,
                    a.facility_id,
                    f.facility_name,
                    a.carrier_id,
                    c.carrier_name,
                    a.scheduled_time,
                    a.estimated_arrival_time,
                    a.actual_arrival_time,
                    a.assigned_dock_id,
                    d.dock_name,
                    a.status,
                    a.pallet_count,
                    a.sku_count,
                    a.priority,
                    a.sla_minutes,
                    a.actual_arrival_delay_minutes,
                    p.predicted_duration_minutes,
                    p.turn_risk_score,
                    p.sla_recovery_probability,
                    p.predicted_missed,
                    r.recommended_action,
                    r.estimated_savings

                FROM appointments a

                JOIN facilities f
                    ON f.facility_id = a.facility_id

                LEFT JOIN carriers c
                    ON c.carrier_id = a.carrier_id

                LEFT JOIN docks d
                    ON d.dock_id = a.assigned_dock_id

                LEFT JOIN LATERAL (
                    SELECT
                        predicted_duration_minutes,
                        turn_risk_score,
                        sla_recovery_probability,
                        predicted_missed
                    FROM appointment_predictions
                    WHERE appt_id = a.appt_id
                    ORDER BY generated_at DESC
                    LIMIT 1
                ) p ON TRUE

                LEFT JOIN LATERAL (
                    SELECT
                        recommended_action,
                        estimated_savings
                    FROM appointment_recommendations
                    WHERE appt_id = a.appt_id
                    ORDER BY created_at DESC
                    LIMIT 1
                ) r ON TRUE

                WHERE a.appt_id LIKE 'DEMO%'

                AND (
                    CAST(:facility_id AS VARCHAR) IS NULL
                    OR a.facility_id = :facility_id
                )

                AND (
                    CAST(:status AS VARCHAR) IS NULL
                    OR a.status = :status
                )

                AND (
                    CAST(:search AS VARCHAR) IS NULL
                    OR a.appt_id ILIKE :search
                    OR a.customer_name ILIKE :search
                    OR c.carrier_name ILIKE :search
                )

                AND (
    CAST(:risk_level AS VARCHAR) IS NULL

    OR (
        :risk_level = 'Low'
        AND p.turn_risk_score < 30
    )

    OR (
        :risk_level = 'Medium'
        AND p.turn_risk_score >= 30
        AND p.turn_risk_score < 60
    )

    OR (
        :risk_level = 'High'
        AND p.turn_risk_score >= 60
        AND p.turn_risk_score < 80
    )

    OR (
        :risk_level = 'Critical'
        AND p.turn_risk_score >= 80
    )
)

AND (
    CAST(:outcome AS VARCHAR) IS NULL

    OR (
        :outcome = 'Recovered with recommendations'
        AND a.status = 'Completed'
        AND a.actual_arrival_delay_minutes > 0
        AND a.actual_sla_missed = FALSE
        AND EXISTS (
            SELECT 1
            FROM appointment_recommendations outcome_r
            WHERE outcome_r.appt_id = a.appt_id
              AND outcome_r.status IN (
                  'Accepted',
                  'Completed'
              )
        )
    )

    OR (
        :outcome = 'Recovered without recommendations'
        AND a.status = 'Completed'
        AND a.actual_arrival_delay_minutes > 0
        AND a.actual_sla_missed = FALSE
        AND NOT EXISTS (
            SELECT 1
            FROM appointment_recommendations outcome_r
            WHERE outcome_r.appt_id = a.appt_id
              AND outcome_r.status IN (
                  'Accepted',
                  'Completed'
              )
        )
    )

    OR (
        :outcome = 'Missed SLA'
        AND a.status = 'Completed'
        AND a.actual_arrival_delay_minutes > 0
        AND a.actual_sla_missed = TRUE
    )
)

                ORDER BY
                    p.turn_risk_score DESC NULLS LAST,
                    a.scheduled_time ASC

                LIMIT :page_size
                OFFSET :offset;
                """
            ),
            parameters,
        ).mappings().all()

        total = self.db.execute(
            text(
                """
                SELECT COUNT(*)

                FROM appointments a

                LEFT JOIN carriers c
                    ON c.carrier_id = a.carrier_id

                LEFT JOIN LATERAL (
                    SELECT turn_risk_score
                    FROM appointment_predictions
                    WHERE appt_id = a.appt_id
                    ORDER BY generated_at DESC
                    LIMIT 1
                ) p ON TRUE

                WHERE a.appt_id LIKE 'DEMO%'

                AND (
                    CAST(:facility_id AS VARCHAR) IS NULL
                    OR a.facility_id = :facility_id
                )

                AND (
                    CAST(:status AS VARCHAR) IS NULL
                    OR a.status = :status
                )

                AND (
                    CAST(:search AS VARCHAR) IS NULL
                    OR a.appt_id ILIKE :search
                    OR a.customer_name ILIKE :search
                    OR c.carrier_name ILIKE :search
                )

                AND (
    CAST(:risk_level AS VARCHAR) IS NULL

    OR (
        :risk_level = 'Low'
        AND p.turn_risk_score < 30
    )

    OR (
        :risk_level = 'Medium'
        AND p.turn_risk_score >= 30
        AND p.turn_risk_score < 60
    )

    OR (
        :risk_level = 'High'
        AND p.turn_risk_score >= 60
        AND p.turn_risk_score < 80
    )

    OR (
        :risk_level = 'Critical'
        AND p.turn_risk_score >= 80
    )
)

AND (
    CAST(:outcome AS VARCHAR) IS NULL

    OR (
        :outcome = 'Recovered with recommendations'
        AND a.status = 'Completed'
        AND a.actual_arrival_delay_minutes > 0
        AND a.actual_sla_missed = FALSE
        AND EXISTS (
            SELECT 1
            FROM appointment_recommendations outcome_r
            WHERE outcome_r.appt_id = a.appt_id
              AND outcome_r.status IN (
                  'Accepted',
                  'Completed'
              )
        )
    )

    OR (
        :outcome = 'Recovered without recommendations'
        AND a.status = 'Completed'
        AND a.actual_arrival_delay_minutes > 0
        AND a.actual_sla_missed = FALSE
        AND NOT EXISTS (
            SELECT 1
            FROM appointment_recommendations outcome_r
            WHERE outcome_r.appt_id = a.appt_id
              AND outcome_r.status IN (
                  'Accepted',
                  'Completed'
              )
        )
    )

    OR (
        :outcome = 'Missed SLA'
        AND a.status = 'Completed'
        AND a.actual_arrival_delay_minutes > 0
        AND a.actual_sla_missed = TRUE
    )

                );
                """
            ),
            parameters,
        ).scalar_one()

        total_pages = max(
            1,
            (total + page_size - 1) // page_size,
        )

        return {
            "items": [dict(row) for row in rows],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_items": total,
                "total_pages": total_pages,
                "has_previous": page > 1,
                "has_next": page < total_pages,
            },
        }

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_all(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Appointment]:
        statement = (
            select(Appointment)
            .order_by(Appointment.scheduled_time)
            .limit(limit)
            .offset(offset)
        )

        return list(self.db.scalars(statement).all())

    def count_all(self) -> int:
        statement = select(
            func.count(Appointment.appt_id)
        )

        return int(
            self.db.scalar(statement) or 0
        )

    def get_by_id(
        self,
        appt_id: str,
    ) -> Appointment | None:
        return self.db.get(
            Appointment,
            appt_id,
        )

    def create(
        self,
        appointment: Appointment,
    ) -> Appointment:
        self.db.add(appointment)
        self.db.commit()
        self.db.refresh(appointment)

        return appointment

    def rollback(self) -> None:
        self.db.rollback()