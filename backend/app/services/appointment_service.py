from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
from decimal import Decimal
from typing import Any
from app.engines.what_if_engine import WhatIfEngine
from app.schemas import WhatIfRequest
from sqlalchemy.exc import IntegrityError

from app.errors import AppError
from app.models import Appointment
from app.repositories.appointment_repository import (
    AppointmentRepository,
)
from app.schemas import AppointmentCreate, AppointmentUpdate
from app.services.prediction_orchestration_service import PredictionOrchestrationService


def normalize_database_value(
    value: Any,
) -> Any:
    """
    Convert PostgreSQL-specific types into JSON-serializable values.
    """

    if isinstance(value, Decimal):
        return float(value)

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    if isinstance(value, dict):
        return {
            key: normalize_database_value(item)
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [
            normalize_database_value(item)
            for item in value
        ]

    return value


class AppointmentService:
    def run_what_if(
        self,
        *,
        appt_id: str,
        payload: WhatIfRequest,
    ) -> dict[str, Any]:
        details = self.repository.get_details(
            appt_id
        )

        if details is None:
            raise AppError(
                message="Appointment not found",
                code="APPOINTMENT_NOT_FOUND",
                status_code=404,
                details={"appt_id": appt_id},
            )

        engine = WhatIfEngine()

        scenario_prediction = None
        try:
            scenario_prediction = (
                PredictionOrchestrationService(
                    self.repository.db,
                    self.repository,
                ).predict_scenario(
                    appt_id=appt_id,
                    actions=details[
                        "recommendation_actions"
                    ],
                    selected_action_ids=(
                        payload.selected_action_ids
                    ),
                    extra_loaders=(
                        payload.extra_loaders
                    ),
                    extra_forklifts=(
                        payload.extra_forklifts
                    ),
                    pre_stage_products=(
                        payload.pre_stage_products
                    ),
                )
            )
        except Exception:
            # Keep What-If available if artifacts are temporarily
            # unavailable; the engine retains its deterministic fallback.
            scenario_prediction = None

        try:
            result = engine.simulate(
                appointment=details["appointment"],
                prediction=details["prediction"],
                actions=details[
                    "recommendation_actions"
                ],
                selected_action_ids=(
                    payload.selected_action_ids
                ),
                extra_loaders=payload.extra_loaders,
                extra_forklifts=(
                    payload.extra_forklifts
                ),
                pre_stage_products=(
                    payload.pre_stage_products
                ),
                scenario_prediction=(
                    scenario_prediction
                ),
            )
        except ValueError as exc:
            raise AppError(
                message=str(exc),
                code="WHAT_IF_SIMULATION_FAILED",
                status_code=400,
                details={"appt_id": appt_id},
            ) from exc

        return normalize_database_value(
            {
                "appt_id": appt_id,
                "selected_action_ids":
                    payload.selected_action_ids,
                **result,
            }
        )
    def __init__(
            self,
            repository: AppointmentRepository,
        ) -> None:
            self.repository = repository

    def get_paginated(
        self,
        *,
        page: int,
        page_size: int,
        facility_id: str | None,
        customer_id: str | None,
        carrier_id: str | None,
        assigned_dock_id: str | None,
        appointment_type: str | None,
        date_from: date | None,
        date_to: date | None,
        pallet_min: int | None,
        pallet_max: int | None,
        sku_min: int | None,
        sku_max: int | None,
        status: str | None,
        risk_level: str | None,
        outcome: str | None,
        search: str | None,
        sort_by: str | None,
        sort_direction: str | None,
    ) -> dict[str, Any]:
        return self.repository.get_paginated(
            page=page,
            page_size=page_size,
            facility_id=facility_id,
            customer_id=customer_id,
            carrier_id=carrier_id,
            assigned_dock_id=assigned_dock_id,
            appointment_type=appointment_type,
            date_from=date_from,
            date_to=date_to,
            pallet_min=pallet_min,
            pallet_max=pallet_max,
            sku_min=sku_min,
            sku_max=sku_max,
            status=status,
            risk_level=risk_level,
            outcome=outcome,
            search=search,
            sort_by=sort_by,
            sort_direction=sort_direction,
        )

    def get_all(self) -> list[Appointment]:
        return self.repository.get_all()

    def get_by_id(
        self,
        appt_id: str,
    ) -> Appointment:
        appointment = self.repository.get_by_id(
            appt_id
        )

        if appointment is None:
            raise AppError(
                message="Appointment not found",
                code="APPOINTMENT_NOT_FOUND",
                status_code=404,
                details={"appt_id": appt_id},
            )

        return appointment

    def get_details(
        self,
        appt_id: str,
    ) -> dict[str, Any]:
        details = self.repository.get_details(
            appt_id
        )

        if details is None:
            raise AppError(
                message="Appointment not found",
                code="APPOINTMENT_NOT_FOUND",
                status_code=404,
                details={"appt_id": appt_id},
            )

        return normalize_database_value(details)

    def get_reference_data(self) -> dict[str, Any]:
        return self.repository.get_reference_data()

    def get_filter_reference_data(
        self,
        *,
        facility_id: str | None = None,
        customer_id: str | None = None,
        carrier_id: str | None = None,
        appointment_type: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> dict[str, Any]:
        return self.repository.get_filter_reference_data(
            facility_id=facility_id,
            customer_id=customer_id,
            carrier_id=carrier_id,
            appointment_type=appointment_type,
            date_from=date_from,
            date_to=date_to,
        )


    def update(
        self,
        appt_id: str,
        payload: AppointmentUpdate,
    ) -> dict[str, Any]:
        existing = self.get_by_id(appt_id)
        existing_details = self.repository.get_details(appt_id) or {}
        previous_prediction = existing_details.get("prediction")
        if existing.status == "Completed":
            raise AppError(
                message="Completed appointments are read-only.",
                code="APPOINTMENT_READ_ONLY",
                status_code=409,
                details={"appt_id": appt_id},
            )

        try:
            references = self.repository.validate_references(
                facility_id=payload.facility_id,
                customer_id=payload.customer_id,
                carrier_id=payload.carrier_id,
                dock_id=payload.assigned_dock_id,
            )
            validated_products = self.repository.validate_products(
                [item.model_dump() for item in payload.products]
            )
        except ValueError as exc:
            raise AppError(
                message=str(exc),
                code="INVALID_APPOINTMENT_UPDATE",
                status_code=400,
            ) from exc

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        values = payload.model_dump(exclude={"products"})
        values["customer_name"] = references.get("customer_name")
        values["appt_date"] = payload.scheduled_time
        values["updated_at"] = now
        values["sku_count"] = len(validated_products)
        values["pallet_count"] = sum(item["pallet_count"] for item in validated_products)
        values["total_weight"] = round(sum(item["line_weight_lb"] for item in validated_products), 2)
        values["total_cube"] = round(sum(item["line_volume_cuft"] for item in validated_products), 4)

        tracked = [
            "customer_id", "facility_id", "carrier_id", "assigned_dock_id",
            "scheduled_time", "estimated_arrival_time", "appointment_type",
            "load_type", "trailer_number", "priority", "sla_minutes",
            "detention_cost_per_hour", "distance_band", "traffic_severity",
            "weather_severity", "surge_indicator",
        ]
        changed_fields = [
            key for key in tracked
            if getattr(existing, key, None) != values.get(key)
        ]
        old_products = existing_details.get("products", [])
        new_product_signature = sorted((item["product_id"], item["quantity"]) for item in validated_products)
        old_product_signature = sorted((item["product_id"], item["quantity"]) for item in old_products)
        if new_product_signature != old_product_signature:
            changed_fields.append("products")

        previous_values = {
            key: getattr(existing, key, None)
            for key in tracked
        }

        try:
            updated = self.repository.update_appointment(
                appt_id=appt_id,
                values=values,
            )
            self.repository.replace_appointment_products(
                appt_id=appt_id,
                products=validated_products,
            )
            notes = "Updated fields: " + (", ".join(changed_fields) if changed_fields else "no material changes")
            self.repository.create_update_event(
                appt_id=appt_id,
                event_time=now,
                notes=notes,
            )

            event_types = {
                "customer_id": "CUSTOMER_CHANGED",
                "facility_id": "FACILITY_CHANGED",
                "carrier_id": "CARRIER_CHANGED",
                "assigned_dock_id": "DOCK_CHANGED",
                "scheduled_time": "SCHEDULE_CHANGED",
                "estimated_arrival_time": "ETA_UPDATED",
                "appointment_type": "APPOINTMENT_TYPE_CHANGED",
                "load_type": "LOAD_TYPE_CHANGED",
                "trailer_number": "TRAILER_CHANGED",
                "priority": "PRIORITY_CHANGED",
                "sla_minutes": "SLA_CHANGED",
                "detention_cost_per_hour": "DETENTION_RATE_CHANGED",
                "traffic_severity": "TRAFFIC_CONDITION_CHANGED",
                "weather_severity": "WEATHER_CONDITION_CHANGED",
                "surge_indicator": "SURGE_STATUS_CHANGED",
            }
            for field_name in changed_fields:
                if field_name == "products":
                    continue
                self.repository.create_audit_event(
                    appt_id=appt_id,
                    event_type=event_types.get(field_name, "FIELD_CHANGED"),
                    event_time=now,
                    notes=f"{field_name.replace('_', ' ').title()} updated.",
                    performed_by="Operations Planner",
                    field_name=field_name,
                    old_value=previous_values.get(field_name),
                    new_value=values.get(field_name),
                )

            if "products" in changed_fields:
                old_map = {
                    item["product_id"]: int(item["quantity"])
                    for item in old_products
                }
                new_map = {
                    item["product_id"]: int(item["quantity"])
                    for item in validated_products
                }
                for product_id in sorted(set(old_map) | set(new_map)):
                    old_quantity = old_map.get(product_id)
                    new_quantity = new_map.get(product_id)
                    if old_quantity == new_quantity:
                        continue
                    if old_quantity is None:
                        event_type = "PRODUCT_ADDED"
                    elif new_quantity is None:
                        event_type = "PRODUCT_REMOVED"
                    else:
                        event_type = "QUANTITY_CHANGED"
                    self.repository.create_audit_event(
                        appt_id=appt_id,
                        event_type=event_type,
                        event_time=now,
                        notes=f"Product {product_id} updated.",
                        performed_by="Operations Planner",
                        field_name=f"product:{product_id}",
                        old_value=old_quantity,
                        new_value=new_quantity,
                        details={"product_id": product_id},
                    )

            self.repository.supersede_pending_recommendations(appt_id)
        except Exception as exc:
            self.repository.rollback()
            raise AppError(
                message=f"Unable to update appointment: {exc}",
                code="APPOINTMENT_UPDATE_FAILED",
                status_code=500,
                details={"appt_id": appt_id},
            ) from exc

        prediction = None
        scoring_status = "model_unavailable"
        message = (
            "Appointment updated. ML-v2 artifacts are unavailable, "
            "so rescoring was skipped."
        )

        try:
            prediction = (
                PredictionOrchestrationService(
                    self.repository.db,
                    self.repository,
                ).score_and_persist(appt_id)
            )
            self.repository.create_audit_event(
                appt_id=appt_id,
                event_type="PREDICTION_UPDATED",
                event_time=now,
                notes=(
                    "ML-v2 prediction recalculated after "
                    "the appointment update."
                ),
                performed_by="Warehouse ML-v2 Service",
                field_name="turn_risk_score",
                old_value=(
                    (previous_prediction or {}).get(
                        "turn_risk_score"
                    )
                ),
                new_value=prediction[
                    "turn_risk_score"
                ],
                details={
                    "previous_prediction":
                        previous_prediction or {},
                    "new_prediction": prediction,
                    "model_version":
                        prediction["model_version"],
                },
            )
            scoring_status = "scored"
            message = (
                "Appointment updated and rescored by "
                f"{prediction['model_version']}."
            )
        except Exception:
            scoring_status = "failed"
            message = (
                "Appointment updated, but ML-v2 "
                "rescoring failed."
            )

        return normalize_database_value({
            "appt_id": appt_id,
            "appointment": {column.name: getattr(updated, column.name) for column in updated.__table__.columns},
            "prediction": prediction,
            "scoring_status": scoring_status,
            "changed_fields": changed_fields,
            "message": message,
        })

    def create(self, payload: AppointmentCreate) -> dict[str, Any]:
        try:
            references = self.repository.validate_references(
                facility_id=payload.facility_id,
                customer_id=payload.customer_id,
                carrier_id=payload.carrier_id,
                dock_id=payload.assigned_dock_id,
            )
        except ValueError as exc:
            raise AppError(
                message=str(exc),
                code="INVALID_APPOINTMENT_REFERENCE",
                status_code=400,
            ) from exc

        try:
            validated_products = self.repository.validate_products(
                [item.model_dump() for item in payload.products]
            )
        except ValueError as exc:
            raise AppError(
                message=str(exc),
                code="INVALID_APPOINTMENT_PRODUCT",
                status_code=400,
            ) from exc

        appt_id = self.repository.generate_next_demo_id()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        values = payload.model_dump(exclude={"products"})

        if validated_products:
            values["sku_count"] = len(validated_products)
            values["pallet_count"] = sum(
                item["pallet_count"] for item in validated_products
            )
            values["total_weight"] = round(sum(
                item["line_weight_lb"] for item in validated_products
            ), 2)
            values["total_cube"] = round(sum(
                item["line_volume_cuft"] for item in validated_products
            ), 4)
        if not values.get("customer_name"):
            values["customer_name"] = references.get("customer_name")

        appointment = Appointment(
            appt_id=appt_id,
            appt_date=payload.scheduled_time,
            created_at=now,
            updated_at=now,
            **values,
        )

        try:
            created = self.repository.create(appointment)
            self.repository.create_appointment_products(
                appt_id=appt_id,
                products=validated_products,
            )
            self.repository.create_initial_event(appt_id, now)
        except IntegrityError as exc:
            self.repository.rollback()
            raise AppError(
                message="Unable to create appointment because one or more values conflict with existing database data.",
                code="APPOINTMENT_CREATE_FAILED",
                status_code=400,
                details={
                    "appt_id": appt_id,
                    "error_type": type(exc.orig).__name__
                    if getattr(exc, "orig", None)
                    else type(exc).__name__,
                },
            ) from exc
        except Exception as exc:
            self.repository.rollback()
            raise AppError(
                message=f"Unable to create appointment: {exc}",
                code="APPOINTMENT_CREATE_FAILED",
                status_code=500,
                details={
                    "appt_id": appt_id,
                    "error_type": type(exc).__name__,
                },
            ) from exc

        prediction = None
        scoring_status = "model_unavailable"
        message = (
            "Appointment created. ML-v2 artifacts are unavailable, "
            "so scoring was skipped."
        )

        try:
            prediction = (
                PredictionOrchestrationService(
                    self.repository.db,
                    self.repository,
                ).score_and_persist(appt_id)
            )
            self.repository.create_audit_event(
                appt_id=appt_id,
                event_type="PREDICTION_CREATED",
                event_time=now,
                notes=(
                    "Appointment scored by the production "
                    "ML-v2 model."
                ),
                performed_by="Warehouse ML-v2 Service",
                field_name="turn_risk_score",
                new_value=prediction[
                    "turn_risk_score"
                ],
                details={
                    "prediction": prediction,
                    "model_version":
                        prediction["model_version"],
                },
            )
            scoring_status = "scored"
            message = (
                "Appointment created and scored by "
                f"{prediction['model_version']}."
            )
        except Exception:
            scoring_status = "failed"
            message = (
                "Appointment created, but ML-v2 "
                "scoring failed."
            )

        return normalize_database_value({
            "appt_id": appt_id,
            "appointment": {
                column.name: getattr(created, column.name)
                for column in created.__table__.columns
            },
            "prediction": prediction,
            "scoring_status": scoring_status,
            "message": message,
        })

