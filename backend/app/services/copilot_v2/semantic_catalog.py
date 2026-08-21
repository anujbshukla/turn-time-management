from __future__ import annotations


class WarehouseSemanticCatalog:
    DOMAINS = (
        "appointments",
        "predictions",
        "missions",
        "action_effectiveness",
        "resource_effectiveness",
        "products",
    )

    METRICS = (
        "appointment_count",
        "late_appointments",
        "sla_risk_or_misses",
        "critical_appointments",
        "sla_miss_rate_percent",
        "late_rate_percent",
        "average_delay_minutes",
        "average_turn_time_minutes",
        "average_risk_score",
        "average_pallet_count",
        "average_sku_count",
        "average_dock_congestion_percent",
        "average_labor_utilization_percent",
        "average_forklift_utilization_percent",
        "detention_exposure",
        "avg_realized_minutes_saved",
        "sla_success_rate",
        "avg_realized_net_savings",
    )

    FILTERS = (
        "facility_id",
        "customer_id",
        "carrier_id",
        "dock_id",
        "assigned_dock_id",
        "appointment_type",
        "status",
        "risk_level",
        "product_id",
        "load_type",
        "temperature_zone",
        "pallet_band",
        "congestion_band",
        "pallet_min",
        "pallet_max",
        "sku_min",
        "sku_max",
        "date_from",
        "date_to",
    )

    def prompt_text(self) -> str:
        return (
            "WAREHOUSE SEMANTIC CATALOG\n"
            "Domains: " + ", ".join(self.DOMAINS) + "\n"
            "Metrics: " + ", ".join(self.METRICS) + "\n"
            "Supported filters: " + ", ".join(self.FILTERS) + "\n"
            "\nMETRIC MEANING AND SELECTION RULES\n"
            "- appointment_count: raw number of distinct appointments.\n"
            "- late_appointments: raw number of late appointments.\n"
            "- late_rate_percent: normalized percent of appointments that are late. "
            "Use this for comparing/ranking groups by lateness performance unless "
            "the user explicitly asks for the number/count/volume of late appointments.\n"
            "- sla_risk_or_misses: raw number of actual or predicted SLA misses. "
            "Use this for count/number/volume questions such as asking how many misses occurred.\n"
            "- sla_miss_rate_percent: normalized percent of appointments with an actual "
            "or predicted SLA miss. Use this for worst/best SLA performance, rates, "
            "percentages, or ranking/comparing facilities, carriers, customers, docks, "
            "or other groups by SLA performance unless the user explicitly asks for "
            "the raw number/count/volume of misses.\n"
            "- average_turn_time_minutes: average realized turn time.\n"
            "- detention_exposure: monetary detention exposure.\n"
            "- avg_realized_minutes_saved: observed realized minutes saved by executed recovery actions.\n"
"- sla_success_rate: observed SLA success rate for learned recovery actions.\n"
"- avg_realized_net_savings: observed realized monetary savings from executed recovery actions.\n"
"\nACTION EFFECTIVENESS RULES\n"
"- Questions about recovery actions, interventions, or which recovery action worked/performed "
"best historically use domain=action_effectiveness and intent=action_effectiveness.\n"
"- Action effectiveness evaluates learned outcomes of EXECUTED recovery actions, such as "
"reassigning a dock, pre-staging products, adding a loader, adding a forklift, or changing "
"priority sequence.\n"
"- If the user asks generally which recovery actions worked, performed, helped, or were most "
"effective historically without specifying an outcome, use avg_realized_minutes_saved as "
"the default effectiveness metric.\n"
"- If the user explicitly asks about SLA success, SLA recovery, or success rate of recovery "
"actions, use sla_success_rate.\n"
"- If the user explicitly asks about money, dollars, cost savings, financial savings, or "
"net savings from recovery actions, use avg_realized_net_savings.\n"
"- Do not select avg_realized_net_savings merely because monetary data exists. Financial "
"language must be explicit when choosing it over the neutral effectiveness default.\n"
"\nRESOURCE EFFECTIVENESS RULES\n"
"- Questions about whether having or allocating MORE LOADERS or MORE FORKLIFTS helps operational "
"performance use domain=resource_effectiveness and intent=resource_effectiveness.\n"
"- For loader questions set resource_type=loaders. For forklift questions set "
"resource_type=forklifts.\n"
"- Resource effectiveness compares historical realized appointment performance across resource "
"allocation levels. Its default comparison metric is average_turn_time_minutes.\n"
"- Questions such as whether extra loaders/forklifts help, improve performance, reduce turn "
"time, or make operations faster should therefore use average_turn_time_minutes unless the "
"user explicitly requests another supported outcome.\n"
"- Preserve other semantic filters. For example, a resource-effectiveness question restricted "
"to outbound appointments must retain appointment_type=Outbound.\n"
"- Do not confuse a RESOURCE EFFECTIVENESS question with an ACTION EFFECTIVENESS question. "
"Adding a loader or forklift may exist as an executed recovery action, but a question about "
"whether more loaders/forklifts generally help historical appointment performance is resource "
"effectiveness, not recovery-action effectiveness.\n"
"\nGENERAL ANALYTICAL RULES\n"
            "- Distinguish raw counts from normalized rates. For performance comparisons "
            "across groups, prefer a rate when group sizes can differ.\n"
            "- Use raw counts only when the user asks for count, number, total, volume, "
            "how many, or equivalent quantity language.\n"
            "- Never invent a metric, filter, entity, or database field.\n"
            "- appointment_type canonical values are Inbound and Outbound.\n"
            "- risk_level canonical values are Low, Medium, High, and Critical.\n"
            "- SLA risk/miss uses realized SLA outcomes when available and predicted "
            "misses for appointments without realized outcomes.\n"
            "- action effectiveness uses learned outcomes of executed recovery actions.\n"
        )
