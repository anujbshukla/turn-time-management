import type { AppointmentProduct } from "../types/appointmentDetails";

type Props = {
    products: AppointmentProduct[];
};

function formatWeight(value: number | null | undefined) {
    if (value == null) return "—";
    return `${Math.round(value).toLocaleString()} lb`;
}

export function ShipmentItemsTable({ products }: Props) {
    return (
        <section className="drawer-section shipment-items-section">
            <div className="drawer-section-heading">
                <div>
                    <span className="drawer-section-label">Products</span>
                    <h3>Shipment items</h3>
                </div>
                <span className="shipment-line-count">
                    {products.length} {products.length === 1 ? "line" : "lines"}
                </span>
            </div>

            <div className="intelligence-card shipment-items-card">
                <div className="shipment-items-table-wrap">
                    <table className="shipment-items-table">
                        <thead>
                            <tr>
                                <th>Item</th>
                                <th>Qty</th>
                                <th>Dimensions (in)</th>
                                <th>Unit wt.</th>
                                <th>Line wt.</th>
                            </tr>
                        </thead>
                        <tbody>
                            {products.map((item) => (
                                <tr key={item.product_id}>
                                    <td><strong>{item.product_name}</strong><small>{item.sku}</small></td>
                                    <td>{item.quantity}</td>
                                    <td>{item.length_in} × {item.width_in} × {item.height_in}</td>
                                    <td>{formatWeight(item.unit_weight_lb)}</td>
                                    <td>{formatWeight(item.line_weight_lb)}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
        </section>
    );
}
