from __future__ import annotations

from typing import Any

from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.copilot_analytics_repository import CopilotAnalyticsRepository
from app.schemas import GlobalCopilotRequest
from app.services.query_planner import WarehouseQueryPlan, WarehouseQueryPlanner


class DataCopilotService:
    """Safe natural-language analytics over approved warehouse data."""

    def __init__(self, analytics_repository: CopilotAnalyticsRepository, appointment_repository: AppointmentRepository) -> None:
        self.analytics_repository = analytics_repository
        self.appointment_repository = appointment_repository
        self.planner = WarehouseQueryPlanner()

    def answer(self, payload: GlobalCopilotRequest) -> dict[str, Any] | None:
        plan = self.planner.plan(payload.question, conversation_history=payload.conversation_history)
        if not plan.understood:
            return None

        references = self.appointment_repository.get_reference_data()
        clarification = self._resolve_entities(plan=plan, question=payload.question, references=references)
        if clarification:
            return {"mode":"answer","answer":clarification,"facts":[],"suggested_questions":[],"quick_actions":[],"action_intent":None}

        if payload.facility_id and "facility_id" not in plan.filters:
            plan.filters["facility_id"] = payload.facility_id

        if plan.intent == "top_risk":
            return self._top_risk_response(plan)
        if plan.intent == "ranking" and plan.group_by:
            return self._ranking_response(plan)
        return self._summary_response(plan)

    def _summary_response(self, plan: WarehouseQueryPlan) -> dict[str, Any]:
        result = self.analytics_repository.appointment_summary(**plan.filters)
        count=int(result.get("appointment_count") or 0)
        late=int(result.get("late_appointments") or 0)
        misses=int(result.get("sla_risk_or_misses") or 0)
        critical=int(result.get("critical_appointments") or 0)
        answer=(f"I found {count:,} appointments in the requested operating scope. "
                f"{late:,} are late, {misses:,} have an actual or predicted SLA miss, "
                f"and {critical:,} are Critical risk.")
        facts=[{"label":"Appointments","value":f"{count:,}"},{"label":"Late","value":f"{late:,}"},
               {"label":"SLA risk / misses","value":f"{misses:,}"},{"label":"Critical","value":f"{critical:,}"}]
        if result.get("average_delay_minutes") is not None:
            facts.append({"label":"Average delay","value":f"{float(result['average_delay_minutes']):.1f} min"})
        return {"mode":"answer","answer":answer,"facts":facts,
                "suggested_questions":["Which facility has the most Critical appointments?","Rank carriers by average delay","Show the highest-risk appointments"],
                "quick_actions":self._summary_quick_actions(plan, count, critical),"action_intent":None}

    def _ranking_response(self, plan: WarehouseQueryPlan) -> dict[str, Any]:
        rows=self.analytics_repository.grouped_appointment_metrics(group_by=plan.group_by or "facility",limit=plan.limit,**plan.filters)
        if not rows:
            return {"mode":"answer","answer":"No warehouse records matched that combination of filters.","facts":[],"suggested_questions":[],"quick_actions":[],"action_intent":None}
        metric=plan.metric
        rows.sort(key=lambda row: float(row.get(metric) or 0), reverse=True)
        top_rows=rows[:plan.limit]; leader=top_rows[0]
        leader_label=str(leader.get("group_label") or leader.get("group_id"))
        answer=f"{leader_label} ranks first for {self._metric_label(metric).lower()} at {self._format_metric(metric, leader.get(metric))}."
        facts=[{"label":str(row.get("group_label") or row.get("group_id")),"value":self._format_metric(metric,row.get(metric))} for row in top_rows[:5]]
        return {"mode":"answer","answer":answer,"facts":facts,
                "suggested_questions":["What about only inbound appointments?","Show the top five","Which appointments are driving that result?"],
                "quick_actions":self._ranking_quick_actions(plan, leader),"action_intent":None}

    def _top_risk_response(self, plan: WarehouseQueryPlan) -> dict[str, Any]:
        rows=self.analytics_repository.top_risk_appointments(limit=plan.limit,**plan.filters)
        if not rows:
            return {"mode":"answer","answer":"No scored appointments matched the requested scope.","facts":[],"suggested_questions":[],"quick_actions":[],"action_intent":None}
        first=rows[0]
        answer=f"{first['appt_id']} is currently the highest-risk matching appointment with a risk score of {float(first['turn_risk_score'] or 0):.1f}."
        facts=[{"label":row["appt_id"],"value":f"{float(row['turn_risk_score'] or 0):.1f} risk"} for row in rows]
        return {"mode":"answer","answer":answer,"facts":facts,
                "suggested_questions":[f"Open {first['appt_id']}","Why is this appointment at risk?","Run a recovery scenario"],
                "quick_actions":[
                    {"label":f"Open {first['appt_id']}","action":"open_appointment","metadata":{"appt_id":str(first['appt_id'])}},
                    {"label":"Filter Critical queue","action":"filter_appointments","metadata":{"risk_level":"Critical"}},
                    {"label":"Run recovery What-If","action":"run_what_if","metadata":{"extra_loaders":"1","extra_forklifts":"1","pre_stage_products":"false"}},
                ],"action_intent":None}

    def _summary_quick_actions(self, plan: WarehouseQueryPlan, count: int, critical: int) -> list[dict[str, Any]]:
        actions=[]
        metadata=self._filter_metadata(plan)
        if metadata and count:
            actions.append({"label":"Apply to appointment queue","action":"filter_appointments","metadata":metadata})
        if critical:
            critical_metadata=dict(metadata); critical_metadata["risk_level"]="Critical"
            actions.append({"label":f"Show {critical:,} Critical","action":"filter_appointments","metadata":critical_metadata})
        actions.extend([
            {"label":"Compare facilities","action":"ask","prompt":"Compare facilities for this operating scope","metadata":{}},
            {"label":"Show highest risk","action":"ask","prompt":"Show the five highest-risk appointments in this operating scope","metadata":{}},
        ])
        return actions[:4]

    def _ranking_quick_actions(self, plan: WarehouseQueryPlan, leader: dict[str, Any]) -> list[dict[str, Any]]:
        actions=[]; group_id=str(leader.get("group_id") or "")
        if plan.group_by == "facility" and group_id:
            actions.append({"label":"Filter leader facility","action":"filter_appointments","metadata":{"facility_id":group_id}})
        actions.append({"label":"Show highest-risk drivers","action":"ask","prompt":f"Show the five highest-risk appointments for {leader.get('group_label') or group_id}","metadata":{}})
        actions.append({"label":"Only inbound","action":"ask","prompt":"What about only inbound appointments?","metadata":{}})
        actions.append({"label":"Run What-If","action":"run_what_if","metadata":{"extra_loaders":"1","extra_forklifts":"1","pre_stage_products":"false"}})
        return actions[:4]

    @staticmethod
    def _filter_metadata(plan: WarehouseQueryPlan) -> dict[str,str]:
        mapping={"facility_id":"facility_id","status":"status","risk_level":"risk_level"}
        return {target:str(plan.filters[source]) for source,target in mapping.items() if source in plan.filters}

    def _resolve_entities(self, *, plan: WarehouseQueryPlan, question: str, references: dict[str,list[dict[str,Any]]]) -> str | None:
        specs=(("facility","facility_id",references["facilities"]),("customer","customer_id",references["customers"]),("carrier","carrier_id",references["carriers"]),("product","product_id",references["products"]))
        for entity_name,filter_name,rows in specs:
            match,candidates=self._match_reference(question,rows)
            if len(candidates)>1:
                options=", ".join(f"{row['label']} ({row['id']})" for row in candidates[:5])
                return f"I found multiple {entity_name} matches: {options}. Which one did you mean?"
            if match: plan.filters[filter_name]=str(match["id"])
        return None

    @staticmethod
    def _match_reference(question: str, rows: list[dict[str,Any]]) -> tuple[dict[str,Any] | None,list[dict[str,Any]]]:
        normalized=WarehouseQueryPlanner.normalize(question); contained=[]
        for row in rows:
            aliases={WarehouseQueryPlanner.normalize(str(row.get("id") or "")),WarehouseQueryPlanner.normalize(str(row.get("label") or "")),WarehouseQueryPlanner.normalize(str(row.get("sku") or ""))}; aliases.discard("")
            for alias in aliases:
                if len(alias)>=3 and alias in normalized:
                    contained.append((len(alias),row)); break
        if not contained: return None,[]
        longest=max(length for length,_ in contained); best={str(row["id"]):row for length,row in contained if length==longest}; matches=list(best.values())
        return (matches[0],[]) if len(matches)==1 else (None,matches)

    @staticmethod
    def _metric_label(metric: str) -> str:
        return {"appointment_count":"Appointment count","late_appointments":"Late appointments","sla_risk_or_misses":"SLA risk or misses","critical_appointments":"Critical appointments","average_delay_minutes":"Average delay","average_turn_time_minutes":"Average turn time","average_risk_score":"Average risk score","detention_exposure":"Detention exposure"}.get(metric,metric.replace("_"," ").title())

    @staticmethod
    def _format_metric(metric: str, value: Any) -> str:
        numeric=float(value or 0)
        if metric=="detention_exposure": return f"${numeric:,.0f}"
        if metric in {"average_delay_minutes","average_turn_time_minutes"}: return f"{numeric:.1f} min"
        if metric=="average_risk_score": return f"{numeric:.1f}"
        return f"{int(numeric):,}"
