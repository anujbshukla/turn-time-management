import { useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";

import {
  createAppointment,
  getAppointmentReferenceData,
} from "../services/appointments";
import type {
  AppointmentReferenceData,
  CreateAppointmentPayload,
  CreateAppointmentResponse,
  AppointmentProductReferenceItem,
} from "../types/appointments";

type Props = {
  open: boolean;
  onClose: () => void;
  onCreated: (result: CreateAppointmentResponse) => void | Promise<void>;
};

const EMPTY_OPTIONS: AppointmentReferenceData = {
  facilities: [], customers: [], carriers: [], docks: [], products: [],
};

type SelectedProduct = {
  product: AppointmentProductReferenceItem;
  quantity: number;
};

function toLocalInputValue(date: Date) {
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
}

export function CreateAppointmentDrawer({ open, onClose, onCreated }: Props) {
  const [options, setOptions] = useState(EMPTY_OPTIONS);
  const [loadingOptions, setLoadingOptions] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedProducts, setSelectedProducts] = useState<SelectedProduct[]>([]);
  const [productToAdd, setProductToAdd] = useState("");
  const [productQuantity, setProductQuantity] = useState(1);
  const [form, setForm] = useState({
    customer_id: "",
    facility_id: "",
    carrier_id: "",
    assigned_dock_id: "",
    scheduled_time: toLocalInputValue(new Date(Date.now() + 60 * 60 * 1000)),
    estimated_arrival_time: "",
    status: "Scheduled",
    appointment_type: "Inbound",
    load_type: "Palletized",
    trailer_number: "",
    pallet_count: 20,
    sku_count: 10,
    total_weight: 20000,
    total_cube: 1200,
    priority: 1,
    sla_minutes: 120,
    detention_cost_per_hour: 100,
    distance_band: "Regional",
    traffic_severity: 0,
    weather_severity: 0,
    surge_indicator: false,
  });

  useEffect(() => {
    if (!open) return;
    setLoadingOptions(true);
    setError(null);
    void getAppointmentReferenceData()
      .then((data) => {
        setOptions(data);
        setForm((current) => ({
          ...current,
          facility_id: current.facility_id || data.facilities[0]?.id || "",
          customer_id: current.customer_id || data.customers[0]?.id || "",
          carrier_id: current.carrier_id || data.carriers[0]?.id || "",
        }));
      })
      .catch((requestError) => setError(requestError instanceof Error ? requestError.message : "Unable to load form options."))
      .finally(() => setLoadingOptions(false));
  }, [open]);

  const availableDocks = useMemo(
    () => options.docks.filter((dock) => dock.facility_id === form.facility_id),
    [options.docks, form.facility_id],
  );


  const loadSummary = useMemo(() => {
    return selectedProducts.reduce(
      (summary, line) => {
        const unitsPerCase = Math.max(1, line.product.units_per_case || 1);
        const casesPerPallet = Math.max(1, line.product.cases_per_pallet || 1);
        const cases = Math.ceil(line.quantity / unitsPerCase);
        const pallets = Math.ceil(cases / casesPerPallet);
        return {
          skus: summary.skus + 1,
          pallets: summary.pallets + pallets,
          weight: summary.weight + line.quantity * line.product.unit_weight_lb,
          cube: summary.cube + line.quantity * line.product.unit_volume_cuft,
        };
      },
      { skus: 0, pallets: 0, weight: 0, cube: 0 },
    );
  }, [selectedProducts]);

  function addSelectedProduct() {
    const product = options.products.find((item) => item.id === productToAdd);
    if (!product) {
      setError("Select a product before adding it.");
      return;
    }
    if (productQuantity < 1) {
      setError("Product quantity must be at least 1.");
      return;
    }
    if (selectedProducts.some((line) => line.product.id === product.id)) {
      setError("That product is already included. Update its quantity instead.");
      return;
    }
    setSelectedProducts((current) => [...current, { product, quantity: productQuantity }]);
    setProductToAdd("");
    setProductQuantity(1);
    setError(null);
  }

  function updateProductQuantity(productId: string, quantity: number) {
    setSelectedProducts((current) => current.map((line) =>
      line.product.id === productId ? { ...line, quantity: Math.max(1, quantity) } : line
    ));
  }

  function removeSelectedProduct(productId: string) {
    setSelectedProducts((current) => current.filter((line) => line.product.id !== productId));
  }

  useEffect(() => {
    if (form.assigned_dock_id && !availableDocks.some((dock) => dock.id === form.assigned_dock_id)) {
      setForm((current) => ({ ...current, assigned_dock_id: "" }));
    }
  }, [availableDocks, form.assigned_dock_id]);

  if (!open) return null;

  function update<K extends keyof typeof form>(key: K, value: (typeof form)[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!form.facility_id || !form.scheduled_time) {
      setError("Facility and scheduled time are required.");
      return;
    }

    const payload: CreateAppointmentPayload = {
      ...form,
      customer_id: form.customer_id || null,
      carrier_id: form.carrier_id || null,
      assigned_dock_id: form.assigned_dock_id || null,
      scheduled_time: new Date(form.scheduled_time).toISOString(),
      estimated_arrival_time: form.estimated_arrival_time
        ? new Date(form.estimated_arrival_time).toISOString()
        : null,
      trailer_number: form.trailer_number || null,
      pallet_count: selectedProducts.length ? loadSummary.pallets : form.pallet_count,
      sku_count: selectedProducts.length ? loadSummary.skus : form.sku_count,
      total_weight: selectedProducts.length ? Number(loadSummary.weight.toFixed(2)) : form.total_weight,
      total_cube: selectedProducts.length ? Number(loadSummary.cube.toFixed(4)) : form.total_cube,
      products: selectedProducts.map((line) => ({
        product_id: line.product.id,
        quantity: line.quantity,
      })),
    };

    setSubmitting(true);
    setError(null);
    try {
      const result = await createAppointment(payload);
      await onCreated(result);
      onClose();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to create appointment.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <button type="button" className="drawer-backdrop" aria-label="Close create appointment" onClick={onClose} />
      <aside className="appointment-drawer create-appointment-drawer" aria-label="Create appointment">
        <header className="drawer-header">
          <div>
            <span className="drawer-eyebrow">Appointment planning</span>
            <h2>Create Appointment</h2>
            <p>The active ML models will score the appointment after it is saved.</p>
          </div>
          <button type="button" className="drawer-close" onClick={onClose}>×</button>
        </header>

        <form className="create-appointment-form" onSubmit={handleSubmit}>
          {error && <div className="table-error">{error}</div>}
          {loadingOptions ? <div className="table-state">Loading appointment options…</div> : (
            <>
              <section className="drawer-section">
                <span className="drawer-section-label">Parties and location</span>
                <div className="create-form-grid">
                  <label><span>Customer</span><select value={form.customer_id} onChange={(e) => update("customer_id", e.target.value)}><option value="">Select customer</option>{options.customers.map((x) => <option key={x.id} value={x.id}>{x.label}</option>)}</select></label>
                  <label><span>Carrier</span><select value={form.carrier_id} onChange={(e) => update("carrier_id", e.target.value)}><option value="">Select carrier</option>{options.carriers.map((x) => <option key={x.id} value={x.id}>{x.label}</option>)}</select></label>
                  <label><span>Facility *</span><select required value={form.facility_id} onChange={(e) => update("facility_id", e.target.value)}>{options.facilities.map((x) => <option key={x.id} value={x.id}>{x.label}</option>)}</select></label>
                  <label><span>Dock</span><select value={form.assigned_dock_id} onChange={(e) => update("assigned_dock_id", e.target.value)}><option value="">Unassigned</option>{availableDocks.map((x) => <option key={x.id} value={x.id}>{x.label}</option>)}</select></label>
                </div>
              </section>

              <section className="drawer-section">
                <span className="drawer-section-label">Schedule and execution</span>
                <div className="create-form-grid">
                  <label><span>Scheduled time *</span><input required type="datetime-local" value={form.scheduled_time} onChange={(e) => update("scheduled_time", e.target.value)} /></label>
                  <label><span>Estimated arrival</span><input type="datetime-local" value={form.estimated_arrival_time} onChange={(e) => update("estimated_arrival_time", e.target.value)} /></label>
                  <label><span>Appointment type</span><select value={form.appointment_type} onChange={(e) => update("appointment_type", e.target.value)}><option>Inbound</option><option>Outbound</option><option>Transfer</option></select></label>
                  <label><span>Load type</span><select value={form.load_type} onChange={(e) => update("load_type", e.target.value)}><option>Palletized</option><option>Floor Loaded</option><option>Mixed</option></select></label>
                  <label><span>Trailer number</span><input value={form.trailer_number} onChange={(e) => update("trailer_number", e.target.value)} /></label>
                  <label><span>Priority</span><select value={form.priority} onChange={(e) => update("priority", Number(e.target.value))}>{[1,2,3,4,5].map((n) => <option key={n} value={n}>{n}</option>)}</select></label>
                  <label><span>SLA minutes</span><input type="number" min="15" value={form.sla_minutes} onChange={(e) => update("sla_minutes", Number(e.target.value))} /></label>
                  <label><span>Detention cost/hour</span><input type="number" min="0" value={form.detention_cost_per_hour} onChange={(e) => update("detention_cost_per_hour", Number(e.target.value))} /></label>
                </div>
              </section>

              <section className="drawer-section appointment-items-section">
                <span className="drawer-section-label">Appointment items</span>
                <div className="appointment-item-picker">
                  <label>
                    <span>Product</span>
                    <select value={productToAdd} onChange={(event) => setProductToAdd(event.target.value)}>
                      <option value="">Select product</option>
                      {options.products.map((product) => (
                        <option key={product.id} value={product.id}>
                          {product.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    <span>Quantity</span>
                    <input
                      type="number"
                      min="1"
                      value={productQuantity}
                      onChange={(event) => setProductQuantity(Math.max(1, Number(event.target.value)))}
                    />
                  </label>
                  <button type="button" className="secondary-button appointment-item-add" onClick={addSelectedProduct}>
                    Add item
                  </button>
                </div>

                {selectedProducts.length > 0 ? (
                  <div className="appointment-item-list">
                    {selectedProducts.map((line) => (
                      <div className="appointment-item-row" key={line.product.id}>
                        <div className="appointment-item-copy">
                          <strong>{line.product.label}</strong>
                          <span>{line.product.category} · {line.product.unit_of_measure}</span>
                        </div>
                        <label>
                          <span>Qty</span>
                          <input
                            type="number"
                            min="1"
                            value={line.quantity}
                            onChange={(event) => updateProductQuantity(line.product.id, Number(event.target.value))}
                          />
                        </label>
                        <button
                          type="button"
                          className="appointment-item-remove"
                          onClick={() => removeSelectedProduct(line.product.id)}
                          aria-label={`Remove ${line.product.label}`}
                        >
                          ×
                        </button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="appointment-items-empty">
                    Add one or more products to calculate SKU count, weight, cube and estimated pallets automatically.
                  </div>
                )}

                <div className="create-form-grid appointment-item-summary">
                  <label>
                    <span>Total weight (lb)</span>
                    <input
                      type="number"
                      min="0"
                      readOnly={selectedProducts.length > 0}
                      value={selectedProducts.length ? Number(loadSummary.weight.toFixed(2)) : form.total_weight}
                      onChange={(e) => update("total_weight", Number(e.target.value))}
                    />
                  </label>
                  <label>
                    <span>Total cube (ft³)</span>
                    <input
                      type="number"
                      min="0"
                      readOnly={selectedProducts.length > 0}
                      value={selectedProducts.length ? Number(loadSummary.cube.toFixed(4)) : form.total_cube}
                      onChange={(e) => update("total_cube", Number(e.target.value))}
                    />
                  </label>
                </div>
              </section>

              <section className="drawer-section">
                <span className="drawer-section-label">Prediction context</span>
                <div className="create-form-grid">
                  <label><span>Distance band</span><select value={form.distance_band} onChange={(e) => update("distance_band", e.target.value)}><option>Local</option><option>Regional</option><option>Long Haul</option></select></label>
                  <label><span>Traffic severity</span><input type="number" min="0" max="5" value={form.traffic_severity} onChange={(e) => update("traffic_severity", Number(e.target.value))} /></label>
                  <label><span>Weather severity</span><input type="number" min="0" max="5" value={form.weather_severity} onChange={(e) => update("weather_severity", Number(e.target.value))} /></label>
                  <label className="create-checkbox"><input type="checkbox" checked={form.surge_indicator} onChange={(e) => update("surge_indicator", e.target.checked)} /><span>Surge conditions active</span></label>
                </div>
              </section>
            </>
          )}

          <div className="create-appointment-actions">
            <button type="button" className="secondary-button" disabled={submitting} onClick={onClose}>Cancel</button>
            <button type="submit" className="primary-button" disabled={submitting || loadingOptions}>{submitting ? "Creating and scoring…" : "Create Appointment"}</button>
          </div>
        </form>
      </aside>
    </>
  );
}
