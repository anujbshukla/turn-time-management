from pathlib import Path
import re

ROOT = Path.cwd()
drawer_path = ROOT / "frontend/src/components/AppointmentDetailsDrawer.tsx"
css_path = ROOT / "frontend/src/App.css"

if not drawer_path.exists():
    raise RuntimeError(f"Missing {drawer_path}")

text = drawer_path.read_text(encoding="utf-8")


def find_section_containing(source: str, marker_pattern: str):
    match = re.search(marker_pattern, source, re.I | re.S)
    if not match:
        return None
    start = source.rfind("<section", 0, match.start())
    if start < 0:
        return None
    token_pattern = re.compile(r"<section\b|</section>", re.I)
    depth = 0
    for token in token_pattern.finditer(source, start):
        if token.group(0).lower().startswith("<section"):
            depth += 1
        else:
            depth -= 1
            if depth == 0:
                return start, token.end()
    return None

# Imports
op_import = 'import { AppointmentOperationalIntelligence } from "./AppointmentOperationalIntelligence";\n'
ship_import = 'import { ShipmentItemsTable } from "./ShipmentItemsTable";\n'

if op_import not in text:
    anchor = 'import { AppointmentCopilot } from "./AppointmentCopilot";\n'
    if anchor not in text:
        raise RuntimeError("AppointmentCopilot import anchor not found")
    text = text.replace(anchor, anchor + op_import, 1)

if ship_import not in text:
    text = text.replace(op_import, op_import + ship_import, 1)

# Replace current Operational Snapshot section with the reorganized component.
operational_section = find_section_containing(text, r">\s*Operational snapshot\s*<")
if operational_section is None:
    raise RuntimeError("Could not locate Operational snapshot section")

start, end = operational_section
replacement = '''<section className="drawer-section appointment-operational-intelligence-section">
                                {appointment && recovery && (
                                    <AppointmentOperationalIntelligence
                                        appointment={appointment}
                                        prediction={prediction ?? null}
                                        recovery={recovery}
                                    />
                                )}
                            </section>'''
text = text[:start] + replacement + text[end:]

# Replace old product cards section with compact ShipmentItemsTable.
product_section = find_section_containing(
    text,
    r">\s*Products\s*<[\s\S]{0,800}?>\s*Shipment items\s*<",
)
if product_section is None:
    product_section = find_section_containing(text, r">\s*Products\s*<")
if product_section is None:
    raise RuntimeError("Could not locate Products / Shipment items section")

start, end = product_section
replacement = '''<ShipmentItemsTable
                                products={details.products}
                            />'''
text = text[:start] + replacement + text[end:]

drawer_path.write_text(text, encoding="utf-8", newline="\n")

css_text = css_path.read_text(encoding="utf-8")
marker = "/* Appointment drawer requested layout - 2026-08-21 */"
css_patch = r'''
/* Appointment drawer requested layout - 2026-08-21 */
.appointment-operational-intelligence-section {
    display: block;
}

.operational-snapshot-card {
    margin-top: 12px;
}

.operational-snapshot-card .details-grid {
    margin-top: 10px;
}

.shipment-items-section .drawer-section-heading {
    align-items: flex-start;
}

.shipment-line-count {
    color: #7c879b;
    font-size: 12px;
    white-space: nowrap;
}

.shipment-items-section .shipment-items-card {
    margin-top: 12px;
}

.shipment-items-section .shipment-items-table-wrap {
    overflow-x: auto;
}

.shipment-items-section .shipment-items-table {
    width: 100%;
    min-width: 620px;
    border-collapse: collapse;
}

.shipment-items-section .shipment-items-table th,
.shipment-items-section .shipment-items-table td {
    padding: 10px 8px;
    border-bottom: 1px solid #e5eaf2;
    text-align: left;
    vertical-align: middle;
}

.shipment-items-section .shipment-items-table th {
    color: #344057;
    font-size: 11px;
    font-weight: 750;
}

.shipment-items-section .shipment-items-table td {
    color: #344057;
    font-size: 12px;
}

.shipment-items-section .shipment-items-table td:first-child {
    min-width: 180px;
}

.shipment-items-section .shipment-items-table td strong,
.shipment-items-section .shipment-items-table td small {
    display: block;
}

.shipment-items-section .shipment-items-table td small {
    margin-top: 2px;
    color: #7c879b;
    font-size: 10px;
}
'''.strip()

if marker not in css_text:
    css_path.write_text(
        css_text.rstrip() + "\n\n" + css_patch + "\n",
        encoding="utf-8",
        newline="\n",
    )

print("Appointment Drawer layout fix applied successfully.")
print("Driver & Route -> Current Operational Status -> Timeline/SLA")
print("Compact Shipment Items table now replaces the old product-card list.")
