from __future__ import annotations
from typing import Any
from app.services.query_planner import WarehouseQueryPlan
from .models import CanonicalCopilotQuery


class LegacyPlanBridge:
    @staticmethod
    def to_legacy_plan(query: CanonicalCopilotQuery) -> WarehouseQueryPlan:
        plan = WarehouseQueryPlan()
        plan.intent = query.intent
        plan.metric = query.metric
        plan.group_by = query.group_by
        plan.limit = query.limit
        plan.filters.update(query.filters)
        plan.resource_type = query.resource_type
        plan.understood = True
        plan.ignore_request_date_context = query.explicit_time
        return plan

    @staticmethod
    def dashboard_context(payload: Any) -> dict[str, Any]:
        return {key: getattr(payload, key, None) for key in ("facility_id", "customer_id", "carrier_id", "appointment_type", "status", "risk_level", "date_from", "date_to")}
