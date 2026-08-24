from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import Appointment


class AppointmentWriteRepositoryMixin:
    """Write/change operations composed into AppointmentRepository."""

    db: Session

    def generate_next_demo_id(self) -> str:
        value = self.db.execute(text("""
            SELECT COALESCE(MAX(CAST(SUBSTRING(appt_id FROM 5) AS INTEGER)), 0) + 1
            FROM appointments
            WHERE appt_id ~ '^DEMO[0-9]+$';
        """)).scalar_one()
        return f"DEMO{int(value):07d}"

    def validate_references(
        self,
        *,
        facility_id: str,
        customer_id: str | None,
        carrier_id: str | None,
        dock_id: str | None,
    ) -> dict[str, str | None]:
        facility = self.db.execute(text("SELECT facility_name FROM facilities WHERE facility_id=:id AND active=TRUE"), {"id": facility_id}).scalar_one_or_none()
        if facility is None:
            raise ValueError("Selected facility is unavailable.")
        customer = None
        if customer_id:
            customer = self.db.execute(text("SELECT customer_name FROM customers WHERE customer_id=:id"), {"id": customer_id}).scalar_one_or_none()
            if customer is None:
                raise ValueError("Selected customer was not found.")
        carrier = None
        if carrier_id:
            carrier = self.db.execute(text("SELECT carrier_name FROM carriers WHERE carrier_id=:id AND active=TRUE"), {"id": carrier_id}).scalar_one_or_none()
            if carrier is None:
                raise ValueError("Selected carrier is unavailable.")
        if dock_id:
            dock_facility = self.db.execute(text("SELECT facility_id FROM docks WHERE dock_id=:id AND active=TRUE"), {"id": dock_id}).scalar_one_or_none()
            if dock_facility is None:
                raise ValueError("Selected dock is unavailable.")
            if dock_facility != facility_id:
                raise ValueError("Selected dock does not belong to the selected facility.")
        return {"facility_name": facility, "customer_name": customer, "carrier_name": carrier}

    def validate_products(
        self,
        products: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if not products:
            return []

        product_ids = [item["product_id"] for item in products]
        if len(product_ids) != len(set(product_ids)):
            raise ValueError("Each product can only be added once per appointment.")

        rows = self.db.execute(
            text(
                """
                SELECT
                    product_id, product_name, sku, unit_of_measure,
                    unit_weight_lb, unit_volume_cuft,
                    units_per_case, cases_per_pallet
                FROM products
                WHERE active = TRUE
                  AND product_id = ANY(:product_ids);
                """
            ),
            {"product_ids": product_ids},
        ).mappings().all()

        by_id = {row["product_id"]: dict(row) for row in rows}
        missing = [product_id for product_id in product_ids if product_id not in by_id]
        if missing:
            raise ValueError(f"One or more selected products are unavailable: {', '.join(missing)}")

        validated: list[dict[str, Any]] = []
        for item in products:
            product = by_id[item["product_id"]]
            quantity = int(item["quantity"] or 0)
            if quantity < 1:
                raise ValueError("Product quantity must be at least 1.")

            units_per_case = max(1, int(product["units_per_case"] or 1))
            cases_per_pallet = max(1, int(product["cases_per_pallet"] or 1))
            case_count = (quantity + units_per_case - 1) // units_per_case
            pallet_count = (case_count + cases_per_pallet - 1) // cases_per_pallet

            validated.append({
                **product,
                "quantity": quantity,
                "case_count": case_count,
                "pallet_count": pallet_count,
                "line_weight_lb": round(float(product["unit_weight_lb"]) * quantity, 2),
                "line_volume_cuft": round(float(product["unit_volume_cuft"]) * quantity, 4),
            })

        return validated

    def create_appointment_products(
        self,
        *,
        appt_id: str,
        products: list[dict[str, Any]],
    ) -> None:
        for product in products:
            self.db.execute(
                text(
                    """
                    INSERT INTO appointment_products (
                        appt_id, product_id, quantity, case_count,
                        pallet_count, line_weight_lb, line_volume_cuft
                    ) VALUES (
                        :appt_id, :product_id, :quantity, :case_count,
                        :pallet_count, :line_weight_lb, :line_volume_cuft
                    );
                    """
                ),
                {"appt_id": appt_id, **product},
            )
        self.db.commit()

    def create_initial_event(self, appt_id: str, event_time: datetime) -> None:
        self.create_audit_event(
            appt_id=appt_id,
            event_type="APPOINTMENT_CREATED",
            event_time=event_time,
            notes="Appointment created in Control Tower portal",
            performed_by="Operations Planner",
            details={"source": "control_tower"},
        )

    def create_audit_event(
        self,
        *,
        appt_id: str,
        event_type: str,
        event_time: datetime,
        notes: str | None = None,
        performed_by: str | None = None,
        field_name: str | None = None,
        old_value: Any | None = None,
        new_value: Any | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        import json

        def serialize(value: Any | None) -> str | None:
            if value is None:
                return None
            if isinstance(value, datetime):
                return value.isoformat()
            return str(value)

        self.db.execute(
            text(
                """
                INSERT INTO appointment_events (
                    appt_id,
                    event_type,
                    event_time,
                    notes,
                    performed_by,
                    field_name,
                    old_value,
                    new_value,
                    details_json
                ) VALUES (
                    :appt_id,
                    :event_type,
                    :event_time,
                    :notes,
                    :performed_by,
                    :field_name,
                    :old_value,
                    :new_value,
                    CAST(:details_json AS JSONB)
                );
                """
            ),
            {
                "appt_id": appt_id,
                "event_type": event_type,
                "event_time": event_time,
                "notes": notes,
                "performed_by": performed_by,
                "field_name": field_name,
                "old_value": serialize(old_value),
                "new_value": serialize(new_value),
                "details_json": json.dumps(
                    details or {},
                    default=str,
                ),
            },
        )
        self.db.commit()

    def get_scoring_row(self, appt_id: str) -> dict[str, Any] | None:
        row = self.db.execute(text("""
            SELECT a.appt_id, a.scheduled_time, a.estimated_arrival_time, a.facility_id,
                   a.carrier_id, a.customer_id, a.assigned_dock_id, a.appointment_type,
                   a.load_type, a.pallet_count, a.sku_count, a.total_weight, a.total_cube,
                   a.priority, a.sla_minutes, a.detention_cost_per_hour, a.distance_band,
                   a.traffic_severity, a.weather_severity, a.surge_indicator
            FROM appointments a WHERE a.appt_id=:appt_id;
        """), {"appt_id": appt_id}).mappings().one_or_none()
        return dict(row) if row else None

    def save_prediction(self, prediction: dict[str, Any]) -> None:
        self.db.execute(text("""
            INSERT INTO appointment_predictions (
                appt_id, predicted_arrival_time, predicted_delay_minutes,
                predicted_duration_minutes, sla_miss_probability,
                sla_recovery_probability, turn_risk_score, predicted_missed,
                model_version, generated_at
            ) VALUES (
                :appt_id, :predicted_arrival_time, :predicted_delay_minutes,
                :predicted_duration_minutes, :sla_miss_probability,
                :sla_recovery_probability, :turn_risk_score, :predicted_missed,
                :model_version, NOW()
            );
        """), prediction)
        self.db.commit()

    def create_initial_recommendation(
        self,
        *,
        appt_id: str,
        dock_id: str | None,
        predicted_duration_minutes: int,
        sla_minutes: int,
        detention_cost_per_hour: float,
    ) -> int:
        minutes_over = max(0, predicted_duration_minutes - sla_minutes)
        estimated_loss = round((minutes_over / 60) * detention_cost_per_hour, 2)
        action_cost = 75.0
        estimated_savings = max(0.0, round(estimated_loss - action_cost, 2))
        recommendation_id = self.db.execute(text("""
            INSERT INTO appointment_recommendations (
                appt_id, recommendation_type, recommended_action,
                recommended_dock_id, recommended_sequence, additional_labor,
                estimated_loss_without_action, estimated_cost_of_action,
                estimated_savings, status, created_at
            ) VALUES (
                :appt_id, 'SLA Recovery',
                'Add one loader, pre-stage products and protect the assigned dock window',
                :dock_id, 1, 1, :estimated_loss, :action_cost,
                :estimated_savings, 'Pending', NOW()
            ) RETURNING recommendation_id;
        """), {
            "appt_id": appt_id,
            "dock_id": dock_id,
            "estimated_loss": estimated_loss,
            "action_cost": action_cost,
            "estimated_savings": estimated_savings,
        }).scalar_one()
        actions = [
            {
                "sequence_number": 1,
                "action_code": "ADD_LOADER",
                "action_title": "Assign one additional loader",
                "action_description": "Add temporary labor capacity to reduce handling time.",
                "owner_role": "Warehouse Supervisor",
                "estimated_minutes_saved": min(20, max(8, minutes_over // 3 or 8)),
                "additional_loaders": 1,
                "additional_forklifts": 0,
                "required_dock_id": None,
                "estimated_action_cost": 40.0,
            },
            {
                "sequence_number": 2,
                "action_code": "PRE_STAGE_PRODUCTS",
                "action_title": "Pre-stage appointment products",
                "action_description": "Stage high-volume products before the trailer reaches the dock.",
                "owner_role": "Inventory Coordinator",
                "estimated_minutes_saved": min(18, max(6, minutes_over // 4 or 6)),
                "additional_loaders": 0,
                "additional_forklifts": 0,
                "required_dock_id": None,
                "estimated_action_cost": 20.0,
            },
            {
                "sequence_number": 3,
                "action_code": "RESERVE_DOCK",
                "action_title": "Reserve the assigned dock",
                "action_description": "Protect the dock window from conflicting appointment moves.",
                "owner_role": "Dock Coordinator",
                "estimated_minutes_saved": min(15, max(5, minutes_over // 5 or 5)),
                "additional_loaders": 0,
                "additional_forklifts": 0,
                "required_dock_id": dock_id,
                "estimated_action_cost": 15.0,
            },
        ]
        for action in actions:
            self.db.execute(text("""
                INSERT INTO recommendation_actions (
                    recommendation_id, sequence_number, action_code,
                    action_title, action_description, owner_role,
                    estimated_minutes_saved, additional_loaders,
                    additional_forklifts, required_dock_id,
                    estimated_action_cost, status, created_at
                ) VALUES (
                    :recommendation_id, :sequence_number, :action_code,
                    :action_title, :action_description, :owner_role,
                    :estimated_minutes_saved, :additional_loaders,
                    :additional_forklifts, :required_dock_id,
                    :estimated_action_cost, 'Proposed', NOW()
                );
            """), {"recommendation_id": recommendation_id, **action})
        self.db.commit()
        return int(recommendation_id)

    def update_appointment(
        self,
        *,
        appt_id: str,
        values: dict[str, Any],
    ) -> Appointment:
        appointment = self.get_by_id(appt_id)
        if appointment is None:
            raise ValueError("Appointment not found.")
        for key, value in values.items():
            setattr(appointment, key, value)
        self.db.commit()
        self.db.refresh(appointment)
        return appointment

    def reschedule_appointment(
        self,
        *,
        appt_id: str,
        scheduled_time: datetime,
        changed_at: datetime,
    ) -> dict[str, Any]:
        row = self.db.execute(
            text(
                """
                UPDATE appointments
                SET
                    original_scheduled_time = COALESCE(original_scheduled_time, scheduled_time),
                    estimated_arrival_time =
                        CASE
                            WHEN estimated_arrival_time IS NULL THEN NULL
                            ELSE estimated_arrival_time + (CAST(:scheduled_time AS TIMESTAMP) - scheduled_time)
                        END,
                    scheduled_time = CAST(:scheduled_time AS TIMESTAMP),
                    appt_date = CAST(:scheduled_time AS TIMESTAMP),
                    is_rescheduled = TRUE,
                    reschedule_count = COALESCE(reschedule_count, 0) + 1,
                    rescheduled_at = CAST(:changed_at AS TIMESTAMP),
                    status = 'Scheduled',
                    updated_at = CAST(:changed_at AS TIMESTAMP)
                WHERE appt_id = :appt_id
                RETURNING
                    appt_id,
                    original_scheduled_time,
                    scheduled_time,
                    estimated_arrival_time,
                    is_rescheduled,
                    reschedule_count,
                    rescheduled_at;
                """
            ),
            {
                "appt_id": appt_id,
                "scheduled_time": scheduled_time,
                "changed_at": changed_at,
            },
        ).mappings().one()
        self.db.commit()
        return dict(row)

    def replace_appointment_products(
        self,
        *,
        appt_id: str,
        products: list[dict[str, Any]],
    ) -> None:
        self.db.execute(
            text("DELETE FROM appointment_products WHERE appt_id = :appt_id"),
            {"appt_id": appt_id},
        )
        for product in products:
            self.db.execute(
                text(
                    """
                    INSERT INTO appointment_products (
                        appt_id, product_id, quantity, case_count,
                        pallet_count, line_weight_lb, line_volume_cuft
                    ) VALUES (
                        :appt_id, :product_id, :quantity, :case_count,
                        :pallet_count, :line_weight_lb, :line_volume_cuft
                    )
                    """
                ),
                {"appt_id": appt_id, **product},
            )
        self.db.commit()

    def create_update_event(
        self,
        *,
        appt_id: str,
        event_time: datetime,
        notes: str,
        performed_by: str = "Operations Planner",
    ) -> None:
        self.create_audit_event(
            appt_id=appt_id,
            event_type="APPOINTMENT_UPDATED",
            event_time=event_time,
            notes=notes,
            performed_by=performed_by,
        )

    def supersede_pending_recommendations(self, appt_id: str) -> None:
        self.db.execute(
            text(
                """
                UPDATE appointment_recommendations
                SET status = 'Superseded'
                WHERE appt_id = :appt_id
                  AND status = 'Pending'
                """
            ),
            {"appt_id": appt_id},
        )
        self.db.commit()

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
