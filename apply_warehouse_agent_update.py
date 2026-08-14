from __future__ import annotations

import ast
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
SERVICE_FILE = PROJECT_ROOT / "backend/app/services/global_copilot_service.py"
AGENT_SOURCE = PROJECT_ROOT / "patch_files/backend/app/services/warehouse_agent.py"
AGENT_TARGET = PROJECT_ROOT / "backend/app/services/warehouse_agent.py"


def fail(message: str) -> None:
    raise SystemExit(message)


if not SERVICE_FILE.exists():
    fail(
        "Run this script from C:\\turn-time-management. "
        "backend/app/services/global_copilot_service.py was not found."
    )

if not AGENT_SOURCE.exists():
    fail(
        "Missing patch file: "
        "patch_files/backend/app/services/warehouse_agent.py"
    )

AGENT_TARGET.parent.mkdir(parents=True, exist_ok=True)
shutil.copy2(AGENT_SOURCE, AGENT_TARGET)

backup = SERVICE_FILE.with_suffix(".py.warehouse_agent_backup")
if not backup.exists():
    shutil.copy2(SERVICE_FILE, backup)

text = SERVICE_FILE.read_text(encoding="utf-8")

# Add imports without depending on one exact formatting style.
warehouse_import = (
    "from app.services.warehouse_agent import (\n"
    "    WarehouseAgent,\n"
    ")\n"
)
if "from app.services.warehouse_agent import" not in text:
    class_marker = "\n\nclass GlobalCopilotService"
    class_index = text.find(class_marker)
    if class_index < 0:
        fail("Could not locate class GlobalCopilotService.")
    text = text[:class_index] + "\n" + warehouse_import + text[class_index:]

analytics_import = (
    "from app.repositories.copilot_analytics_repository import (\n"
    "    CopilotAnalyticsRepository,\n"
    ")\n"
)
if "from app.repositories.copilot_analytics_repository import" not in text:
    class_marker = "\n\nclass GlobalCopilotService"
    class_index = text.find(class_marker)
    if class_index < 0:
        fail("Could not locate class GlobalCopilotService.")
    text = text[:class_index] + "\n" + analytics_import + text[class_index:]

# Parse the actual current file so multiline function signatures are supported.
try:
    tree = ast.parse(text)
except SyntaxError as exc:
    fail(f"global_copilot_service.py has a syntax error before patching: {exc}")

service_class = next(
    (
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "GlobalCopilotService"
    ),
    None,
)
if service_class is None:
    fail("Could not locate class GlobalCopilotService.")

init_method = next(
    (
        node
        for node in service_class.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "__init__"
    ),
    None,
)
if init_method is None or init_method.end_lineno is None:
    fail("Could not locate GlobalCopilotService.__init__().")

if "self.warehouse_agent" not in text:
    lines = text.splitlines(keepends=True)
    insert_at = init_method.end_lineno
    init_block = (
        "\n"
        "        self.warehouse_agent = WarehouseAgent(\n"
        "            data_service=self.data_copilot_service,\n"
        "            analytics_repository=CopilotAnalyticsRepository(\n"
        "                repository.db,\n"
        "            ),\n"
        "            dashboard_service=self.dashboard_service,\n"
        "        )\n"
    )
    lines.insert(insert_at, init_block)
    text = "".join(lines)

# Route analytical requests through the orchestrator. Booking and direct
# dashboard actions remain in GlobalCopilotService.
old_call = "self.data_copilot_service.answer("
new_call = "self.warehouse_agent.answer("
if old_call in text:
    text = text.replace(old_call, new_call, 1)
elif new_call not in text:
    fail(
        "Could not locate the DataCopilotService answer call. "
        "Search global_copilot_service.py for "
        "'data_copilot_service.answer' and apply the one-line replacement manually."
    )

# Validate before overwriting the source file.
try:
    compile(text, str(SERVICE_FILE), "exec")
    compile(
        AGENT_TARGET.read_text(encoding="utf-8"),
        str(AGENT_TARGET),
        "exec",
    )
except SyntaxError as exc:
    fail(f"Patch validation failed; original file was preserved: {exc}")

SERVICE_FILE.write_text(text, encoding="utf-8")

print("Warehouse Agent integration applied successfully.")
print("Updated:")
print("- backend/app/services/global_copilot_service.py")
print("- backend/app/services/warehouse_agent.py")
print("Backup:")
print(f"- {backup}")
