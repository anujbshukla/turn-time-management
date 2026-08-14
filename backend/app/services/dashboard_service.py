from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.schemas import DashboardWhatIfRequest
from app.services.executive_intelligence_service import ExecutiveIntelligenceService
from app.services.prediction_service import PredictionService
from app.services.operational_alert_service import OperationalAlertService
from app.services.ai_mission_service import AiMissionService
from app.services.kpi_intelligence_service import KpiIntelligenceService
from app.services.operations_feed_service import OperationsFeedService
from app.services.warehouse_heatmap_service import WarehouseHeatmapService
from app.services.predictive_timeline_service import PredictiveTimelineService

from app.repositories.dashboard_repository import (
    DashboardRepository,
)


def normalize_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)

    if isinstance(value, dict):
        return {
            key: normalize_value(item)
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [
            normalize_value(item)
            for item in value
        ]

    return value


class DashboardService:
    def __init__(
        self,
        repository: DashboardRepository,
    ) -> None:
        self.repository = repository

    def get_dashboard(
        self,
        facility_id: str | None = None,
        *,
        customer_id: str | None = None,
        carrier_id: str | None = None,
        appointment_type: str | None = None,
        date_from=None,
        date_to=None,
    ) -> dict[str, Any]:
        dashboard = {
            "summary": self.repository.get_summary(
                facility_id
            ),
            "status_distribution": (
                self.repository.get_status_distribution(
                    facility_id
                )
            ),
            "late_appointment_outcomes": (
                self.repository.get_late_outcomes(
                    facility_id
                )
            ),
            "facility_performance": (
                self.repository.get_facility_performance()
            ),
            "risk_distribution": (
                self.repository.get_risk_distribution(
                    facility_id
                )
            ),
            "daily_compliance_trend": (
                self.repository.get_daily_compliance_trend(
                    facility_id
                )
            ),
            "delay_sla_reasons": self.repository.get_delay_sla_reasons(facility_id),
            "recovery_plan_performance": self.repository.get_recovery_plan_performance(facility_id),
            "recommendation_savings": self.repository.get_recommendation_savings(facility_id),
            "high_risk_appointments": (
                self.repository.get_high_risk_appointments(
                    facility_id
                )
            ),
        }

        normalized_dashboard = normalize_value(dashboard)
        normalized_dashboard["executive_intelligence"] = (
            ExecutiveIntelligenceService().build(normalized_dashboard)
        )
        normalized_dashboard["prediction_center"] = (
            PredictionService().build(normalized_dashboard)
        )
        normalized_dashboard["operational_alerts"] = (
            OperationalAlertService().build(normalized_dashboard)
        )
        normalized_dashboard["ai_missions"] = (
            AiMissionService().build(normalized_dashboard)
        )
        normalized_dashboard["intelligent_kpis"] = (
            KpiIntelligenceService(self.repository).build(
                facility_id,
                customer_id=customer_id,
                carrier_id=carrier_id,
                appointment_type=appointment_type,
                date_from=date_from,
                date_to=date_to,
            )
        )
        normalized_dashboard["operations_feed"] = normalize_value(
            OperationsFeedService(self.repository).build(
                normalized_dashboard,
                facility_id,
            )
        )
        normalized_dashboard["warehouse_heatmap"] = normalize_value(
            WarehouseHeatmapService(self.repository).build(facility_id)
        )
        normalized_dashboard["predictive_timeline"] = normalize_value(
            PredictiveTimelineService(self.repository).build(facility_id)
        )
        return normalized_dashboard

    def get_intelligence_filter_reference_data(
        self,
        *,
        facility_id: str | None = None,
        customer_id: str | None = None,
        carrier_id: str | None = None,
        appointment_type: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> dict[str, Any]:
        return normalize_value(
            self.repository.get_intelligence_filter_reference_data(
                facility_id=facility_id,
                customer_id=customer_id,
                carrier_id=carrier_id,
                appointment_type=appointment_type,
                date_from=date_from,
                date_to=date_to,
            )
        )

    def get_intelligence(
        self,
        facility_id: str | None = None,
    ) -> dict[str, Any]:
        return normalize_value(
            {
                "delay_sla_reasons": (
                    self.repository.get_delay_sla_reasons(facility_id)
                ),
                "recovery_plan_performance": (
                    self.repository.get_recovery_plan_performance(facility_id)
                ),
            }
        )

    def run_what_if(
        self,
        payload: DashboardWhatIfRequest,
    ) -> dict[str, Any]:
        baseline = self.get_dashboard(payload.facility_id)
        candidates = self.repository.get_what_if_candidates(
            payload.facility_id
        )

        loader_capacity = payload.extra_loaders * 8
        forklift_capacity = payload.extra_forklifts * 6
        loader_ids = {
            row["appt_id"] for row in candidates[:loader_capacity]
        }
        forklift_ids = {
            row["appt_id"]
            for row in candidates[:forklift_capacity]
        }

        projected_rows: list[dict[str, Any]] = []
        total_action_cost = (
            payload.extra_loaders * 50.0
            + payload.extra_forklifts * 35.0
            + (20.0 if payload.pre_stage_products else 0.0)
        )

        for row in candidates:
            predicted_delay = max(
                0.0, float(row.get("predicted_delay_minutes") or 0)
            )
            predicted_duration = max(
                0.0, float(row.get("predicted_duration_minutes") or 0)
            )
            baseline_turn = predicted_delay + predicted_duration
            sla_minutes = int(row.get("sla_minutes") or 120)
            baseline_risk = float(row.get("turn_risk_score") or 0)
            baseline_probability = float(
                row.get("sla_miss_probability") or 0
            )

            minutes_saved = 0.0
            interventions: list[str] = []
            if row["appt_id"] in loader_ids:
                minutes_saved += 12.0
                interventions.append("Extra loader")
            if row["appt_id"] in forklift_ids:
                minutes_saved += 9.0
                interventions.append("Extra forklift")
            if payload.pre_stage_products and (
                int(row.get("sku_count") or 0) >= 18
                or int(row.get("pallet_count") or 0) >= 24
            ):
                minutes_saved += 15.0
                interventions.append("Pre-stage products")

            operational_floor = max(
                30.0, round(predicted_duration * 0.35, 1)
            )
            projected_turn = max(
                operational_floor, baseline_turn - minutes_saved
            )
            actual_minutes_saved = max(0.0, baseline_turn - projected_turn)
            improvement_ratio = (
                actual_minutes_saved / baseline_turn
                if baseline_turn > 0
                else 0.0
            )
            projected_probability = max(
                0.02,
                min(
                    0.99,
                    baseline_probability - improvement_ratio * 0.90,
                ),
            )
            if projected_turn <= sla_minutes:
                projected_probability = min(projected_probability, 0.25)
            projected_risk = max(
                0.0,
                min(100.0, baseline_risk - improvement_ratio * 85),
            )
            detention_rate = float(
                row.get("detention_cost_per_hour") or 0
            )
            baseline_exposure = (
                max(0.0, baseline_turn - sla_minutes) / 60.0
                * detention_rate
            )
            projected_exposure = (
                max(0.0, projected_turn - sla_minutes) / 60.0
                * detention_rate
            )
            projected_rows.append(
                {
                    **row,
                    "baseline_turn_time": baseline_turn,
                    "projected_turn_time": projected_turn,
                    "minutes_saved": actual_minutes_saved,
                    "baseline_exposure": baseline_exposure,
                    "projected_exposure": projected_exposure,
                    "projected_probability": projected_probability,
                    "projected_risk": projected_risk,
                    "interventions": interventions,
                }
            )

        projected_misses = sum(
            1
            for row in projected_rows
            if row["projected_probability"] >= 0.5
            or row["projected_turn_time"] > int(row.get("sla_minutes") or 120)
        )
        baseline_predicted_misses = sum(
            1
            for row in projected_rows
            if float(row.get("sla_miss_probability") or 0) >= 0.5
            or row["baseline_turn_time"] > int(row.get("sla_minutes") or 120)
        )
        late_rows = [
            row for row in projected_rows
            if float(row.get("actual_arrival_delay_minutes") or 0) > 0
            or float(row.get("predicted_delay_minutes") or 0) > 0
        ]
        projected_recovered = sum(
            1
            for row in late_rows
            if row["projected_probability"] < 0.5
            and row["projected_turn_time"] <= int(row.get("sla_minutes") or 120)
        )
        baseline_recovered = sum(
            1
            for row in late_rows
            if float(row.get("sla_miss_probability") or 0) < 0.5
            and row["baseline_turn_time"] <= int(row.get("sla_minutes") or 120)
        )

        risk_order = ("Low", "Medium", "High", "Critical")
        risk_counts = {level: 0 for level in risk_order}
        for row in projected_rows:
            score = row["projected_risk"]
            level = (
                "Low" if score < 30
                else "Medium" if score < 60
                else "High" if score < 80
                else "Critical"
            )
            risk_counts[level] += 1

        baseline_exposure = sum(
            row["baseline_exposure"] for row in projected_rows
        )
        projected_exposure = sum(
            row["projected_exposure"] for row in projected_rows
        )
        gross_savings = max(0.0, baseline_exposure - projected_exposure)
        net_savings = gross_savings - total_action_cost

        scenario_dashboard = {**baseline}
        scenario_summary = {**baseline["summary"]}
        scenario_summary.update(
            {
                "sla_misses": projected_misses,
                "late_turned_on_time": projected_recovered,
                "detention_exposure": round(projected_exposure, 2),
            }
        )
        scenario_dashboard["summary"] = scenario_summary
        scenario_dashboard["late_appointment_outcomes"] = [
            {
                "outcome": "Recovered with recommendations",
                "appointment_count": projected_recovered,
            },
            {
                "outcome": "Recovered without recommendations",
                "appointment_count": 0,
            },
            {
                "outcome": "Missed SLA",
                "appointment_count": projected_misses,
            },
        ]
        scenario_dashboard["risk_distribution"] = [
            {"risk_level": level, "appointment_count": risk_counts[level]}
            for level in risk_order
        ]
        scenario_dashboard["recommendation_savings"] = {
            "without_recommendations": round(baseline_exposure, 2),
            "detention_with_recommendations": round(projected_exposure, 2),
            "action_cost": round(total_action_cost, 2),
            "gross_savings": round(gross_savings, 2),
            "net_savings": round(net_savings, 2),
            "with_recommendations": round(
                projected_exposure + total_action_cost, 2
            ),
            "roi": round(
                gross_savings / total_action_cost
                if total_action_cost > 0
                else 0.0,
                2,
            ),
            "cost_reduction_percent": round(
                gross_savings / baseline_exposure * 100
                if baseline_exposure > 0
                else 0.0,
                1,
            ),
        }

        scenario_dashboard["executive_intelligence"] = (
            ExecutiveIntelligenceService().build(scenario_dashboard)
        )
        scenario_dashboard["prediction_center"] = (
            PredictionService().build(scenario_dashboard)
        )

        recovered_count = max(0, baseline_predicted_misses - projected_misses)
        return normalize_value(
            {
                "active": True,
                "inputs": payload.model_dump(),
                "baseline": {
                    "predicted_sla_misses": baseline_predicted_misses,
                    "late_turns_recovered": baseline_recovered,
                    "detention_exposure": round(baseline_exposure, 2),
                },
                "scenario": {
                    "predicted_sla_misses": projected_misses,
                    "late_turns_recovered": projected_recovered,
                    "additional_recoveries": recovered_count,
                    "appointments_impacted": sum(
                        1 for row in projected_rows if row["interventions"]
                    ),
                    "total_minutes_saved": round(
                        sum(row["minutes_saved"] for row in projected_rows), 1
                    ),
                    "detention_exposure": round(projected_exposure, 2),
                    "gross_savings": round(gross_savings, 2),
                    "action_cost": round(total_action_cost, 2),
                    "net_savings": round(net_savings, 2),
                },
                "assumptions": [
                    "Each extra loader is allocated to the eight highest-risk appointments.",
                    "Each extra forklift is allocated to the six highest-risk appointments.",
                    "Pre-staging applies to appointments with at least 18 SKUs or 24 pallets.",
                    "The simulation is read-only and does not update appointment records.",
                ],
                "dashboard": scenario_dashboard,
            }
        )
