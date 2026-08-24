from pathlib import Path

ROOT = Path.cwd()
drawer = ROOT / "frontend/src/components/AppointmentDetailsDrawer.tsx"
css = ROOT / "frontend/src/App.css"

text = drawer.read_text(encoding="utf-8")

text = text.replace(
    "prediction={prediction}\n                                        products={details.products}",
    "prediction={prediction ?? null}\n                                        products={details.products}",
)

sku_block = '''                                    <div>
                                        <span>SKUs</span>
                                        <strong>
                                            {appointment?.sku_count ??
                                                0}
                                        </strong>
                                    </div>'''

weight_block = sku_block + '''\n
                                    <div>
                                        <span>Total weight</span>
                                        <strong>
                                            {appointment?.total_weight != null
                                                ? `${Math.round(
                                                    appointment.total_weight,
                                                ).toLocaleString()} lb`
                                                : "—"}
                                        </strong>
                                    </div>'''

if "<span>Total weight</span>" not in text:
    if sku_block not in text:
        raise RuntimeError("Could not find SKUs block in AppointmentDetailsDrawer.tsx")
    text = text.replace(sku_block, weight_block, 1)

text = text.replace("Appointment Load", "Shipment items")
text = text.replace("Appointment load", "Shipment items")

drawer.write_text(text, encoding="utf-8", newline="\n")

css_text = css.read_text(encoding="utf-8")
css_patch = '''/* Turn time KPI follow-up */
.turn-time-kpi-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 12px;
}

@media (max-width: 900px) {
    .turn-time-kpi-grid {
        grid-template-columns: 1fr;
    }
}'''

if "/* Turn time KPI follow-up */" not in css_text:
    css.write_text(
        css_text.rstrip() + "\n\n" + css_patch + "\n",
        encoding="utf-8",
        newline="\n",
    )

print("Appointment Drawer turn-time follow-up patch applied successfully.")
