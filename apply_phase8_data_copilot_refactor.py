from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(r"C:\turn-time-management")
SERVICE_PATH = ROOT / "backend" / "app" / "services" / "data_copilot_service.py"
MIXIN_PATH = ROOT / "backend" / "app" / "services" / "data_copilot_responses.py"

CORE_METHODS = {
    "__init__",
    "_conversation_state_from_history",
    "answer",
    "_apply_request_context",
    "_resolve_entities",
    "_match_reference",
}

source = SERVICE_PATH.read_text(encoding="utf-8")
tree = ast.parse(source)

service_class = next(
    (
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "DataCopilotService"
    ),
    None,
)

if service_class is None:
    raise RuntimeError("DataCopilotService class was not found.")

method_nodes = [
    node
    for node in service_class.body
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
]

moved_nodes = [
    node for node in method_nodes
    if node.name not in CORE_METHODS
]

if not moved_nodes:
    raise RuntimeError("No response/helper methods were found to extract.")

lines = source.splitlines(keepends=True)

def node_start_line(node):
    decorators = getattr(node, "decorator_list", [])
    if decorators:
        return min([node.lineno, *[item.lineno for item in decorators]])
    return node.lineno

def extract_node_text(node):
    start = node_start_line(node) - 1
    end = node.end_lineno
    return "".join(lines[start:end]).rstrip() + "\n"

moved_method_text = "\n".join(
    extract_node_text(node)
    for node in moved_nodes
)

mixin_header = (
    "from __future__ import annotations\n\n"
    "from datetime import datetime, timedelta\n"
    "from typing import Any\n\n"
    "from app.services.query_planner import WarehouseQueryPlan\n\n\n"
    "class DataCopilotResponseMixin:\n"
    "    \"\"\"Response builders and presentation helpers for DataCopilotService.\"\"\"\n\n"
)

MIXIN_PATH.write_text(
    mixin_header + moved_method_text,
    encoding="utf-8",
    newline="\n",
)

new_lines = list(lines)
ranges = []

for node in moved_nodes:
    start = node_start_line(node) - 1
    end = node.end_lineno
    while end < len(new_lines) and new_lines[end].strip() == "":
        end += 1
    ranges.append((start, end))

for start, end in sorted(ranges, reverse=True):
    del new_lines[start:end]

service_source = "".join(new_lines)

import_anchor = "from app.services.copilot_v2 import NaturalLanguageQueryEngine\n"
import_line = "from app.services.data_copilot_responses import DataCopilotResponseMixin\n"

if import_line not in service_source:
    if import_anchor not in service_source:
        raise RuntimeError("Could not find DataCopilotService import anchor.")
    service_source = service_source.replace(
        import_anchor,
        import_anchor + import_line,
        1,
    )

class_anchor = "class DataCopilotService:"
class_replacement = "class DataCopilotService(DataCopilotResponseMixin):"

if class_anchor not in service_source:
    raise RuntimeError("Could not find DataCopilotService class declaration.")

service_source = service_source.replace(
    class_anchor,
    class_replacement,
    1,
)

SERVICE_PATH.write_text(
    service_source,
    encoding="utf-8",
    newline="\n",
)

ast.parse(SERVICE_PATH.read_text(encoding="utf-8"))
ast.parse(MIXIN_PATH.read_text(encoding="utf-8"))

print("Phase 8 applied successfully.")
print(f"Updated: {SERVICE_PATH}")
print(f"Added:   {MIXIN_PATH}")
print()
print("Methods moved:")
for node in moved_nodes:
    print(f"  {node.name}")
