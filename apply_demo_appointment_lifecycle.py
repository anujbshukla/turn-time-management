from pathlib import Path

ROOT = Path.cwd()

appointments_api = ROOT / "backend/app/api/appointments.py"
dashboard_api = ROOT / "backend/app/api/dashboard.py"

# appointments.py
text = appointments_api.read_text(encoding="utf-8")

import_anchor = '''from app.services.appointment_service import (
    AppointmentService,
)
'''

import_replacement = '''from app.services.appointment_service import (
    AppointmentService,
)
from app.services.demo_appointment_lifecycle_service import (
    DemoAppointmentLifecycleService,
)
'''

if "demo_appointment_lifecycle_service" not in text:
    if import_anchor not in text:
        raise RuntimeError(
            "Could not find AppointmentService import anchor."
        )
    text = text.replace(
        import_anchor,
        import_replacement,
        1,
    )

dependency_anchor = '''def get_appointment_service(
    db: Session = Depends(get_db),
) -> AppointmentService:
    repository = AppointmentRepository(db)

    return AppointmentService(repository)
'''

dependency_replacement = '''def get_appointment_service(
    db: Session = Depends(get_db),
) -> AppointmentService:
    DemoAppointmentLifecycleService(db).reconcile()

    repository = AppointmentRepository(db)

    return AppointmentService(repository)
'''

if "DemoAppointmentLifecycleService(db).reconcile()" not in text:
    if dependency_anchor not in text:
        raise RuntimeError(
            "Could not find get_appointment_service block."
        )
    text = text.replace(
        dependency_anchor,
        dependency_replacement,
        1,
    )

appointments_api.write_text(
    text,
    encoding="utf-8",
    newline="\n",
)

# dashboard.py
text = dashboard_api.read_text(encoding="utf-8")

dashboard_import_anchor = (
    "from app.services.dashboard_service import DashboardService\n"
)

dashboard_import_replacement = '''from app.services.dashboard_service import DashboardService
from app.services.demo_appointment_lifecycle_service import (
    DemoAppointmentLifecycleService,
)
'''

if "demo_appointment_lifecycle_service" not in text:
    if dashboard_import_anchor not in text:
        raise RuntimeError(
            "Could not find DashboardService import anchor."
        )
    text = text.replace(
        dashboard_import_anchor,
        dashboard_import_replacement,
        1,
    )

main_anchor = '''    repository = DashboardRepository(db)
    service = DashboardService(repository)

    filters = _filters(
'''

main_replacement = '''    DemoAppointmentLifecycleService(db).reconcile()

    repository = DashboardRepository(db)
    service = DashboardService(repository)

    filters = _filters(
'''

if "DemoAppointmentLifecycleService(db).reconcile()" not in text:
    if main_anchor not in text:
        raise RuntimeError(
            "Could not find main dashboard repository block."
        )
    text = text.replace(
        main_anchor,
        main_replacement,
        1,
    )

dashboard_api.write_text(
    text,
    encoding="utf-8",
    newline="\n",
)

print("Demo appointment lifecycle patch applied successfully.")
