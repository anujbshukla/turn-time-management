from pathlib import Path

ROOT = Path(r"C:\turn-time-management")

def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        print(f"[already updated] {label}")
        return
    if old not in text:
        raise RuntimeError(f"Could not find expected block for {label} in {path}")
    text = text.replace(old, new, 1)
    path.write_text(text, encoding="utf-8", newline="\n")
    print(f"[updated] {label}")

dashboard_api = ROOT / "backend/app/api/dashboard.py"
replace_once(
    dashboard_api,
    "        return service.get_dashboard(\n"
    "            facility_id,\n"
    "            customer_id=customer_id,\n"
    "            carrier_id=carrier_id,\n"
    "            appointment_type=appointment_type,\n"
    "            date_from=date_from,\n"
    "            date_to=date_to,\n"
    "        )\n",
    "        return service.get_dashboard(\n"
    "            facility_id,\n"
    "            customer_id=customer_id,\n"
    "            carrier_id=carrier_id,\n"
    "            appointment_type=appointment_type,\n"
    "            date_from=date_from,\n"
    "            date_to=date_to,\n"
    "            time_from=time_from,\n"
    "            time_to=time_to,\n"
    "        )\n",
    "dashboard.py -> pass time range to DashboardService",
)

dashboard_service = ROOT / "backend/app/services/dashboard_service.py"
replace_once(
    dashboard_service,
    "        appointment_type: str | None = None,\n"
    "        date_from=None,\n"
    "        date_to=None,\n"
    "    ) -> dict[str, Any]:\n",
    "        appointment_type: str | None = None,\n"
    "        date_from=None,\n"
    "        date_to=None,\n"
    "        time_from=None,\n"
    "        time_to=None,\n"
    "    ) -> dict[str, Any]:\n",
    "dashboard_service.py -> accept time range",
)

replace_once(
    dashboard_service,
    "                appointment_type=appointment_type,\n"
    "                date_from=date_from,\n"
    "                date_to=date_to,\n"
    "            )\n"
    "        )\n"
    "        normalized_dashboard[\"operations_feed\"] = normalize_value(\n",
    "                appointment_type=appointment_type,\n"
    "                date_from=date_from,\n"
    "                date_to=date_to,\n"
    "                time_from=time_from,\n"
    "                time_to=time_to,\n"
    "            )\n"
    "        )\n"
    "        normalized_dashboard[\"operations_feed\"] = normalize_value(\n",
    "dashboard_service.py -> pass time range to KpiIntelligenceService",
)

kpi_service = ROOT / "backend/app/services/kpi_intelligence_service.py"
replace_once(
    kpi_service,
    "from datetime import date, timedelta\n",
    "from datetime import date, time, timedelta\n",
    "kpi_intelligence_service.py -> import time",
)

replace_once(
    kpi_service,
    "        appointment_type: str | None = None,\n"
    "        date_from: date | None = None,\n"
    "        date_to: date | None = None,\n"
    "    ) -> list[dict[str, Any]]:\n",
    "        appointment_type: str | None = None,\n"
    "        date_from: date | None = None,\n"
    "        date_to: date | None = None,\n"
    "        time_from: time | None = None,\n"
    "        time_to: time | None = None,\n"
    "    ) -> list[dict[str, Any]]:\n",
    "kpi_intelligence_service.py -> build accepts time range",
)

replace_once(
    kpi_service,
    "            appointment_type=appointment_type,\n"
    "        )\n"
    "        by_date = {row[\"operation_date\"]: row for row in rows}\n",
    "            appointment_type=appointment_type,\n"
    "            time_from=time_from,\n"
    "            time_to=time_to,\n"
    "        )\n"
    "        by_date = {row[\"operation_date\"]: row for row in rows}\n",
    "kpi_intelligence_service.py -> pass time range to daily query",
)

replace_once(
    kpi_service,
    "        facility_id: str | None,\n"
    "        customer_id: str | None,\n"
    "        carrier_id: str | None,\n"
    "        appointment_type: str | None,\n"
    "    ) -> list[dict[str, Any]]:\n",
    "        facility_id: str | None,\n"
    "        customer_id: str | None,\n"
    "        carrier_id: str | None,\n"
    "        appointment_type: str | None,\n"
    "        time_from: time | None,\n"
    "        time_to: time | None,\n"
    "    ) -> list[dict[str, Any]]:\n",
    "kpi_intelligence_service.py -> _daily_rows accepts time range",
)

replace_once(
    kpi_service,
    "                  AND (\n"
    "                      CAST(:appointment_type AS VARCHAR) IS NULL\n"
    "                      OR LOWER(appointment.appointment_type) =\n"
    "                         LOWER(CAST(:appointment_type AS VARCHAR))\n"
    "                  )\n"
    "                GROUP BY DATE(appointment.scheduled_time)\n",
    "                  AND (\n"
    "                      CAST(:appointment_type AS VARCHAR) IS NULL\n"
    "                      OR LOWER(appointment.appointment_type) =\n"
    "                         LOWER(CAST(:appointment_type AS VARCHAR))\n"
    "                  )\n"
    "                  AND (\n"
    "                      CAST(:time_from AS VARCHAR) IS NULL\n"
    "                      OR TO_CHAR(appointment.scheduled_time, 'HH24:MI')\n"
    "                         >= CAST(:time_from AS VARCHAR)\n"
    "                  )\n"
    "                  AND (\n"
    "                      CAST(:time_to AS VARCHAR) IS NULL\n"
    "                      OR TO_CHAR(appointment.scheduled_time, 'HH24:MI')\n"
    "                         <= CAST(:time_to AS VARCHAR)\n"
    "                  )\n"
    "                GROUP BY DATE(appointment.scheduled_time)\n",
    "kpi_intelligence_service.py -> SQL time filter",
)

replace_once(
    kpi_service,
    "                \"carrier_id\": carrier_id,\n"
    "                \"appointment_type\": appointment_type,\n"
    "            },\n",
    "                \"carrier_id\": carrier_id,\n"
    "                \"appointment_type\": appointment_type,\n"
    "                \"time_from\": (\n"
    "                    time_from.strftime(\"%H:%M\") if time_from else None\n"
    "                ),\n"
    "                \"time_to\": (\n"
    "                    time_to.strftime(\"%H:%M\") if time_to else None\n"
    "                ),\n"
    "            },\n",
    "kpi_intelligence_service.py -> bind time parameters",
)

print("\nOperational Health KPI time-filter patch completed.")
