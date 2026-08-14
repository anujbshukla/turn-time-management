import { useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";

import { getAppointmentReferenceData, updateAppointment } from "../services/appointments";
import type { AppointmentDetailsResponse } from "../types/appointmentDetails";
import type { AppointmentProductReferenceItem, AppointmentReferenceData, UpdateAppointmentPayload } from "../types/appointments";

type Props = {
  open: boolean;
  details: AppointmentDetailsResponse;
  onClose: () => void;
  onUpdated: () => void | Promise<void>;
};

type SelectedProduct = { product: AppointmentProductReferenceItem; quantity: number };
const EMPTY_OPTIONS: AppointmentReferenceData = { facilities: [], customers: [], carriers: [], docks: [], products: [] };

function toLocalInputValue(value: string | null | undefined) {
  if (!value) return "";
  const date = new Date(value);
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
}

export function EditAppointmentDrawer({ open, details, onClose, onUpdated }: Props) {
  const appointment = details.appointment;
  const [options, setOptions] = useState(EMPTY_OPTIONS);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [productToAdd, setProductToAdd] = useState("");
  const [productQuantity, setProductQuantity] = useState(1);
  const [selectedProducts, setSelectedProducts] = useState<SelectedProduct[]>([]);
  const [form, setForm] = useState({
    customer_id: appointment.customer_id ?? "",
    facility_id: appointment.facility_id,
    carrier_id: appointment.carrier_id ?? "",
    assigned_dock_id: appointment.assigned_dock_id ?? "",
    scheduled_time: toLocalInputValue(appointment.scheduled_time),
    estimated_arrival_time: toLocalInputValue(appointment.estimated_arrival_time),
    appointment_type: appointment.appointment_type === "Outbound" ? "Outbound" : "Inbound",
    load_type: appointment.load_type ?? "Palletized",
    trailer_number: appointment.trailer_number ?? "",
    priority: appointment.priority,
    sla_minutes: appointment.sla_minutes,
    detention_cost_per_hour: appointment.detention_cost_per_hour,
    distance_band: appointment.distance_band ?? "Regional",
    traffic_severity: appointment.traffic_severity,
    weather_severity: appointment.weather_severity,
    surge_indicator: appointment.surge_indicator,
  });

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    setError(null);
    void getAppointmentReferenceData()
      .then((data) => {
        setOptions(data);
        setSelectedProducts(details.products.map((line) => {
          const product = data.products.find((item) => item.id === line.product_id);
          return product ? { product, quantity: line.quantity } : null;
        }).filter((item): item is SelectedProduct => item !== null));
      })
      .catch((requestError) => setError(requestError instanceof Error ? requestError.message : "Unable to load appointment options."))
      .finally(() => setLoading(false));
  }, [open, details]);

  const availableDocks = useMemo(
    () => options.docks.filter((dock) => dock.facility_id === form.facility_id),
    [options.docks, form.facility_id],
  );

  const loadSummary = useMemo(() => selectedProducts.reduce((summary, line) => {
    const cases = Math.ceil(line.quantity / Math.max(1, line.product.units_per_case || 1));
    const pallets = Math.ceil(cases / Math.max(1, line.product.cases_per_pallet || 1));
    return {
      skus: summary.skus + 1,
      pallets: summary.pallets + pallets,
      weight: summary.weight + line.quantity * line.product.unit_weight_lb,
      cube: summary.cube + line.quantity * line.product.unit_volume_cuft,
    };
  }, { skus: 0, pallets: 0, weight: 0, cube: 0 }), [selectedProducts]);

  useEffect(() => {
    if (form.assigned_dock_id && !availableDocks.some((dock) => dock.id === form.assigned_dock_id)) {
      setForm((current) => ({ ...current, assigned_dock_id: "" }));
    }
  }, [availableDocks, form.assigned_dock_id]);

  if (!open) return null;
  function update<K extends keyof typeof form>(key: K, value: (typeof form)[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }
  function addProduct() {
    const product = options.products.find((item) => item.id === productToAdd);
    if (!product) return setError("Select a product before adding it.");
    if (selectedProducts.some((line) => line.product.id === product.id)) return setError("That product is already included.");
    setSelectedProducts((current) => [...current, { product, quantity: Math.max(1, productQuantity) }]);
    setProductToAdd(""); setProductQuantity(1); setError(null);
  }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const payload: UpdateAppointmentPayload = {
      ...form,
      customer_id: form.customer_id || null,
      carrier_id: form.carrier_id || null,
      assigned_dock_id: form.assigned_dock_id || null,
      scheduled_time: new Date(form.scheduled_time).toISOString(),
      estimated_arrival_time: form.estimated_arrival_time ? new Date(form.estimated_arrival_time).toISOString() : null,
      appointment_type: form.appointment_type as "Inbound" | "Outbound",
      trailer_number: form.trailer_number || null,
      products: selectedProducts.map((line) => ({ product_id: line.product.id, quantity: line.quantity })),
    };
    setSubmitting(true); setError(null);
    try {
      await updateAppointment(appointment.appt_id, payload);
      await onUpdated();
      onClose();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to update appointment.");
    } finally { setSubmitting(false); }
  }

  return <>
    <button type="button" className="drawer-backdrop lifecycle-backdrop" aria-label="Close edit appointment" onClick={onClose} />
    <aside className="appointment-drawer create-appointment-drawer lifecycle-edit-drawer" aria-label="Edit appointment">
      <header className="drawer-header">
        <div><span className="drawer-eyebrow">Appointment lifecycle</span><h2>Edit {appointment.appt_id}</h2><p>Saving reruns ML scoring and refreshes recovery recommendations.</p></div>
        <button type="button" className="drawer-close" onClick={onClose}>×</button>
      </header>
      <form className="create-appointment-form" onSubmit={submit}>
        {error && <div className="table-error">{error}</div>}
        {loading ? <div className="table-state">Loading appointment options…</div> : <>
          <section className="drawer-section"><span className="drawer-section-label">Parties and location</span><div className="create-form-grid">
            <label><span>Customer</span><select value={form.customer_id} onChange={(e) => update("customer_id", e.target.value)}><option value="">Select customer</option>{options.customers.map((x) => <option key={x.id} value={x.id}>{x.label}</option>)}</select></label>
            <label><span>Carrier</span><select value={form.carrier_id} onChange={(e) => update("carrier_id", e.target.value)}><option value="">Select carrier</option>{options.carriers.map((x) => <option key={x.id} value={x.id}>{x.label}</option>)}</select></label>
            <label><span>Facility</span><select value={form.facility_id} onChange={(e) => update("facility_id", e.target.value)}>{options.facilities.map((x) => <option key={x.id} value={x.id}>{x.label}</option>)}</select></label>
            <label><span>Dock</span><select value={form.assigned_dock_id} onChange={(e) => update("assigned_dock_id", e.target.value)}><option value="">Unassigned</option>{availableDocks.map((x) => <option key={x.id} value={x.id}>{x.label}</option>)}</select></label>
          </div></section>
          <section className="drawer-section"><span className="drawer-section-label">Schedule and execution</span><div className="create-form-grid">
            <label><span>Scheduled time</span><input required type="datetime-local" value={form.scheduled_time} onChange={(e) => update("scheduled_time", e.target.value)} /></label>
            <label><span>Estimated arrival</span><input type="datetime-local" value={form.estimated_arrival_time} onChange={(e) => update("estimated_arrival_time", e.target.value)} /></label>
            <label><span>Appointment type</span><select value={form.appointment_type} onChange={(e) => update("appointment_type", e.target.value)}><option>Inbound</option><option>Outbound</option></select></label>
            <label><span>Load type</span><select value={form.load_type} onChange={(e) => update("load_type", e.target.value)}><option>Palletized</option><option>Floor Loaded</option><option>Mixed</option></select></label>
            <label><span>Trailer number</span><input value={form.trailer_number} onChange={(e) => update("trailer_number", e.target.value)} /></label>
            <label><span>Priority</span><select value={form.priority} onChange={(e) => update("priority", Number(e.target.value))}>{[1,2,3,4,5].map((n) => <option key={n}>{n}</option>)}</select></label>
            <label><span>SLA minutes</span><input type="number" min="15" value={form.sla_minutes} onChange={(e) => update("sla_minutes", Number(e.target.value))} /></label>
            <label><span>Detention cost/hour</span><input type="number" min="0" value={form.detention_cost_per_hour} onChange={(e) => update("detention_cost_per_hour", Number(e.target.value))} /></label>
          </div></section>
          <section className="drawer-section appointment-items-section"><span className="drawer-section-label">Appointment items</span>
            <div className="appointment-item-picker"><label><span>Product</span><select value={productToAdd} onChange={(e) => setProductToAdd(e.target.value)}><option value="">Select product</option>{options.products.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}</select></label><label><span>Quantity</span><input type="number" min="1" value={productQuantity} onChange={(e) => setProductQuantity(Math.max(1, Number(e.target.value)))} /></label><button type="button" className="secondary-button appointment-item-add" onClick={addProduct}>Add item</button></div>
            <div className="appointment-item-list">{selectedProducts.map((line) => <div className="appointment-item-row" key={line.product.id}><div><strong>{line.product.label}</strong><span>{line.product.category}</span></div><input type="number" min="1" value={line.quantity} onChange={(e) => setSelectedProducts((current) => current.map((item) => item.product.id === line.product.id ? { ...item, quantity: Math.max(1, Number(e.target.value)) } : item))} /><button type="button" onClick={() => setSelectedProducts((current) => current.filter((item) => item.product.id !== line.product.id))}>Remove</button></div>)}</div>
            <div className="appointment-item-summary details-grid"><div><span>SKUs</span><strong>{loadSummary.skus}</strong></div><div><span>Pallets</span><strong>{loadSummary.pallets}</strong></div><div><span>Total weight</span><strong>{loadSummary.weight.toFixed(2)} lb</strong></div><div><span>Total cube</span><strong>{loadSummary.cube.toFixed(4)} ft³</strong></div></div>
          </section>
          <footer className="create-appointment-actions"><button type="button" className="secondary-button" onClick={onClose}>Cancel</button><button type="submit" className="primary-button" disabled={submitting}>{submitting ? "Saving…" : "Save changes"}</button></footer>
        </>}
      </form>
    </aside>
  </>;
}
