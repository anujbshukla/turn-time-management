import { useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";

import {
  getAppointmentReferenceData,
  updateAppointment,
} from "../services/appointments";
import type {
  AppointmentReferenceData,
  AppointmentProductReferenceItem,
  UpdateAppointmentPayload,
} from "../types/appointments";
import type {
  AppointmentDetailsResponse,
} from "../types/appointmentDetails";

type Props = {
  open: boolean;
  details: AppointmentDetailsResponse;
  onClose: () => void;
  onSaved: () => void | Promise<void>;
};

const EMPTY_OPTIONS: AppointmentReferenceData = {
  facilities: [],
  customers: [],
  carriers: [],
  docks: [],
  products: [],
};

type SelectedProduct = {
  product: AppointmentProductReferenceItem;
  quantity: number;
};

function toLocalInputValue(value: string | null | undefined) {
  if (!value) return "";

  const date = new Date(value);
  const local = new Date(
    date.getTime() - date.getTimezoneOffset() * 60_000,
  );

  return local.toISOString().slice(0, 16);
}

export function EditAppointmentDialog({
  open,
  details,
  onClose,
  onSaved,
}: Props) {
  const appointment = details.appointment;

  const [options, setOptions] =
    useState<AppointmentReferenceData>(EMPTY_OPTIONS);
  const [loadingOptions, setLoadingOptions] =
    useState(false);
  const [submitting, setSubmitting] =
    useState(false);
  const [error, setError] =
    useState<string | null>(null);
  const [selectedProducts, setSelectedProducts] =
    useState<SelectedProduct[]>([]);
  const [productToAdd, setProductToAdd] =
    useState("");
  const [productQuantity, setProductQuantity] =
    useState(1);

  const [form, setForm] = useState(() => ({
    customer_id: appointment.customer_id ?? "",
    facility_id: appointment.facility_id,
    carrier_id: appointment.carrier_id ?? "",
    assigned_dock_id: appointment.assigned_dock_id ?? "",
    scheduled_time: toLocalInputValue(appointment.scheduled_time),
    estimated_arrival_time:
      toLocalInputValue(appointment.estimated_arrival_time),
    appointment_type:
      appointment.appointment_type === "Outbound"
        ? "Outbound" as const
        : "Inbound" as const,
    load_type: appointment.load_type ?? "Palletized",
    trailer_number: appointment.trailer_number ?? "",
    priority: appointment.priority ?? 1,
    sla_minutes: appointment.sla_minutes ?? 120,
    detention_cost_per_hour:
      appointment.detention_cost_per_hour ?? 100,
    distance_band: appointment.distance_band ?? "Regional",
    traffic_severity: appointment.traffic_severity ?? 0,
    weather_severity: appointment.weather_severity ?? 0,
    surge_indicator: appointment.surge_indicator ?? false,
  }));

  useEffect(() => {
    if (!open) return;

    setForm({
      customer_id: appointment.customer_id ?? "",
      facility_id: appointment.facility_id,
      carrier_id: appointment.carrier_id ?? "",
      assigned_dock_id: appointment.assigned_dock_id ?? "",
      scheduled_time: toLocalInputValue(appointment.scheduled_time),
      estimated_arrival_time:
        toLocalInputValue(appointment.estimated_arrival_time),
      appointment_type:
        appointment.appointment_type === "Outbound"
          ? "Outbound"
          : "Inbound",
      load_type: appointment.load_type ?? "Palletized",
      trailer_number: appointment.trailer_number ?? "",
      priority: appointment.priority ?? 1,
      sla_minutes: appointment.sla_minutes ?? 120,
      detention_cost_per_hour:
        appointment.detention_cost_per_hour ?? 100,
      distance_band: appointment.distance_band ?? "Regional",
      traffic_severity: appointment.traffic_severity ?? 0,
      weather_severity: appointment.weather_severity ?? 0,
      surge_indicator: appointment.surge_indicator ?? false,
    });

    setError(null);
    setLoadingOptions(true);

    void getAppointmentReferenceData()
      .then((data) => {
        setOptions(data);

        const productById = new Map(
          data.products.map((product) => [product.id, product]),
        );

        setSelectedProducts(
          details.products.flatMap((line) => {
            const product = productById.get(line.product_id);
            return product
              ? [{ product, quantity: line.quantity }]
              : [];
          }),
        );
      })
      .catch((requestError) =>
        setError(
          requestError instanceof Error
            ? requestError.message
            : "Unable to load appointment options.",
        ),
      )
      .finally(() => setLoadingOptions(false));
  }, [open, appointment, details.products]);

  const availableDocks = useMemo(
    () =>
      options.docks.filter(
        (dock) => dock.facility_id === form.facility_id,
      ),
    [options.docks, form.facility_id],
  );

  useEffect(() => {
    if (
      form.assigned_dock_id &&
      !availableDocks.some(
        (dock) => dock.id === form.assigned_dock_id,
      )
    ) {
      setForm((current) => ({
        ...current,
        assigned_dock_id: "",
      }));
    }
  }, [availableDocks, form.assigned_dock_id]);

  if (!open) return null;

  const readOnly = appointment.status === "Completed";

  function update<K extends keyof typeof form>(
    key: K,
    value: (typeof form)[K],
  ) {
    setForm((current) => ({
      ...current,
      [key]: value,
    }));
  }

  function addSelectedProduct() {
    const product = options.products.find(
      (item) => item.id === productToAdd,
    );

    if (!product) {
      setError("Select a product before adding it.");
      return;
    }

    if (
      selectedProducts.some(
        (line) => line.product.id === product.id,
      )
    ) {
      setError("That product is already included.");
      return;
    }

    setSelectedProducts((current) => [
      ...current,
      {
        product,
        quantity: Math.max(1, productQuantity),
      },
    ]);

    setProductToAdd("");
    setProductQuantity(1);
    setError(null);
  }

  function updateProductQuantity(
    productId: string,
    quantity: number,
  ) {
    setSelectedProducts((current) =>
      current.map((line) =>
        line.product.id === productId
          ? {
            ...line,
            quantity: Math.max(1, quantity),
          }
          : line,
      ),
    );
  }

  function removeSelectedProduct(productId: string) {
    setSelectedProducts((current) =>
      current.filter(
        (line) => line.product.id !== productId,
      ),
    );
  }

  async function handleSubmit(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    const payload: UpdateAppointmentPayload = {
      customer_id: form.customer_id || null,
      facility_id: form.facility_id,
      carrier_id: form.carrier_id || null,
      assigned_dock_id: form.assigned_dock_id || null,

      // Edit keeps the existing schedule.
      scheduled_time: form.scheduled_time,

      estimated_arrival_time:
        form.estimated_arrival_time || null,

      appointment_type: form.appointment_type,
      load_type: form.load_type || null,
      trailer_number: form.trailer_number || null,
      priority: form.priority,
      sla_minutes: form.sla_minutes,
      detention_cost_per_hour:
        form.detention_cost_per_hour,
      distance_band: form.distance_band || null,
      traffic_severity: form.traffic_severity,
      weather_severity: form.weather_severity,
      surge_indicator: form.surge_indicator,
      products: selectedProducts.map((line) => ({
        product_id: line.product.id,
        quantity: line.quantity,
      })),
    };

    setSubmitting(true);
    setError(null);

    try {
      await updateAppointment(
        appointment.appt_id,
        payload,
      );
      await onSaved();
      onClose();
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Unable to edit appointment.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <button
        type="button"
        className="drawer-backdrop appointment-change-backdrop"
        aria-label="Close edit appointment"
        onClick={onClose}
      />

      <aside
        className="appointment-drawer appointment-change-drawer"
        aria-label="Edit appointment"
      >
        <header className="drawer-header">
          <div>
            <span className="drawer-eyebrow">
              Appointment maintenance
            </span>
            <h2>Edit appointment</h2>
            <p>
              {appointment.appt_id} ·{" "}
              {appointment.customer_name ?? "Unknown customer"}
            </p>
          </div>

          <button
            type="button"
            className="drawer-close"
            onClick={onClose}
            aria-label="Close"
          >
            ×
          </button>
        </header>

        <form
          className="create-appointment-form"
          onSubmit={handleSubmit}
        >
          {error && (
            <div className="table-error">{error}</div>
          )}

          {readOnly && (
            <div className="appointment-change-notice">
              Completed appointments are read-only.
            </div>
          )}

          {loadingOptions ? (
            <div className="table-state">
              Loading appointment options…
            </div>
          ) : (
            <>
              <section className="drawer-section">
                <span className="drawer-section-label">
                  Parties and location
                </span>

                <div className="create-form-grid">
                  <label>
                    <span>Customer</span>
                    <select
                      value={form.customer_id}
                      disabled={readOnly}
                      onChange={(event) =>
                        update(
                          "customer_id",
                          event.target.value,
                        )
                      }
                    >
                      <option value="">
                        Select customer
                      </option>
                      {options.customers.map((item) => (
                        <option
                          key={item.id}
                          value={item.id}
                        >
                          {item.label}
                        </option>
                      ))}
                    </select>
                  </label>

                  <label>
                    <span>Carrier</span>
                    <select
                      value={form.carrier_id}
                      disabled={readOnly}
                      onChange={(event) =>
                        update(
                          "carrier_id",
                          event.target.value,
                        )
                      }
                    >
                      <option value="">
                        Select carrier
                      </option>
                      {options.carriers.map((item) => (
                        <option
                          key={item.id}
                          value={item.id}
                        >
                          {item.label}
                        </option>
                      ))}
                    </select>
                  </label>

                  <label>
                    <span>Facility</span>
                    <select
                      value={form.facility_id}
                      disabled={readOnly}
                      onChange={(event) =>
                        update(
                          "facility_id",
                          event.target.value,
                        )
                      }
                    >
                      {options.facilities.map((item) => (
                        <option
                          key={item.id}
                          value={item.id}
                        >
                          {item.label}
                        </option>
                      ))}
                    </select>
                  </label>

                  <label>
                    <span>Dock</span>
                    <select
                      value={form.assigned_dock_id}
                      disabled={readOnly}
                      onChange={(event) =>
                        update(
                          "assigned_dock_id",
                          event.target.value,
                        )
                      }
                    >
                      <option value="">
                        Unassigned
                      </option>
                      {availableDocks.map((item) => (
                        <option
                          key={item.id}
                          value={item.id}
                        >
                          {item.label}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
              </section>

              <section className="drawer-section">
                <span className="drawer-section-label">
                  Execution details
                </span>

                <div className="create-form-grid">
                  <label>
                    <span>Scheduled time</span>
                    <input
                      type="datetime-local"
                      value={form.scheduled_time}
                      disabled
                    />
                    <small>
                      Use Reschedule to change appointment date/time.
                    </small>
                  </label>

                  <label>
                    <span>Estimated arrival</span>
                    <input
                      type="datetime-local"
                      value={form.estimated_arrival_time}
                      disabled={readOnly}
                      onChange={(event) =>
                        update(
                          "estimated_arrival_time",
                          event.target.value,
                        )
                      }
                    />
                  </label>

                  <label>
                    <span>Appointment type</span>
                    <select
                      value={form.appointment_type}
                      disabled={readOnly}
                      onChange={(event) =>
                        update(
                          "appointment_type",
                          event.target.value as
                          | "Inbound"
                          | "Outbound",
                        )
                      }
                    >
                      <option>Inbound</option>
                      <option>Outbound</option>
                    </select>
                  </label>

                  <label>
                    <span>Load type</span>
                    <select
                      value={form.load_type}
                      disabled={readOnly}
                      onChange={(event) =>
                        update(
                          "load_type",
                          event.target.value,
                        )
                      }
                    >
                      <option>Palletized</option>
                      <option>Floor Loaded</option>
                      <option>Mixed</option>
                    </select>
                  </label>

                  <label>
                    <span>Trailer number</span>
                    <input
                      value={form.trailer_number}
                      disabled={readOnly}
                      onChange={(event) =>
                        update(
                          "trailer_number",
                          event.target.value,
                        )
                      }
                    />
                  </label>

                  <label>
                    <span>Priority</span>
                    <select
                      value={form.priority}
                      disabled={readOnly}
                      onChange={(event) =>
                        update(
                          "priority",
                          Number(event.target.value),
                        )
                      }
                    >
                      {[1, 2, 3, 4, 5].map((value) => (
                        <option
                          key={value}
                          value={value}
                        >
                          {value}
                        </option>
                      ))}
                    </select>
                  </label>

                  <label>
                    <span>SLA minutes</span>
                    <input
                      type="number"
                      min="15"
                      value={form.sla_minutes}
                      disabled={readOnly}
                      onChange={(event) =>
                        update(
                          "sla_minutes",
                          Number(event.target.value),
                        )
                      }
                    />
                  </label>

                  <label>
                    <span>Detention cost/hour</span>
                    <input
                      type="number"
                      min="0"
                      value={
                        form.detention_cost_per_hour
                      }
                      disabled={readOnly}
                      onChange={(event) =>
                        update(
                          "detention_cost_per_hour",
                          Number(event.target.value),
                        )
                      }
                    />
                  </label>
                </div>
              </section>

              <section className="drawer-section appointment-items-section">
                <span className="drawer-section-label">
                  Shipment items
                </span>

                <div className="appointment-item-picker">
                  <label>
                    <span>Product</span>
                    <select
                      value={productToAdd}
                      disabled={readOnly}
                      onChange={(event) =>
                        setProductToAdd(
                          event.target.value,
                        )
                      }
                    >
                      <option value="">
                        Select product
                      </option>
                      {options.products.map((product) => (
                        <option
                          key={product.id}
                          value={product.id}
                        >
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
                      disabled={readOnly}
                      onChange={(event) =>
                        setProductQuantity(
                          Math.max(
                            1,
                            Number(event.target.value),
                          ),
                        )
                      }
                    />
                  </label>

                  <button
                    type="button"
                    className="secondary-button appointment-item-add"
                    disabled={readOnly}
                    onClick={addSelectedProduct}
                  >
                    Add item
                  </button>
                </div>

                <div className="appointment-item-list">
                  {selectedProducts.map((line) => (
                    <div
                      className="appointment-item-row"
                      key={line.product.id}
                    >
                      <div className="appointment-item-copy">
                        <strong>
                          {line.product.label}
                        </strong>
                        <span>
                          {line.product.category}
                        </span>
                      </div>

                      <label>
                        <span>Qty</span>
                        <input
                          type="number"
                          min="1"
                          value={line.quantity}
                          disabled={readOnly}
                          onChange={(event) =>
                            updateProductQuantity(
                              line.product.id,
                              Number(event.target.value),
                            )
                          }
                        />
                      </label>

                      <button
                        type="button"
                        className="appointment-item-remove"
                        disabled={readOnly}
                        onClick={() =>
                          removeSelectedProduct(
                            line.product.id,
                          )
                        }
                      >
                        ×
                      </button>
                    </div>
                  ))}
                </div>
              </section>

              <section className="drawer-section">
                <span className="drawer-section-label">
                  Prediction context
                </span>

                <div className="create-form-grid">
                  <label>
                    <span>Distance band</span>
                    <select
                      value={form.distance_band}
                      disabled={readOnly}
                      onChange={(event) =>
                        update(
                          "distance_band",
                          event.target.value,
                        )
                      }
                    >
                      <option>Local</option>
                      <option>Regional</option>
                      <option>Long Haul</option>
                    </select>
                  </label>

                  <label>
                    <span>Traffic severity</span>
                    <input
                      type="number"
                      min="0"
                      max="5"
                      value={form.traffic_severity}
                      disabled={readOnly}
                      onChange={(event) =>
                        update(
                          "traffic_severity",
                          Number(event.target.value),
                        )
                      }
                    />
                  </label>

                  <label>
                    <span>Weather severity</span>
                    <input
                      type="number"
                      min="0"
                      max="5"
                      value={form.weather_severity}
                      disabled={readOnly}
                      onChange={(event) =>
                        update(
                          "weather_severity",
                          Number(event.target.value),
                        )
                      }
                    />
                  </label>

                  <label className="create-checkbox">
                    <input
                      type="checkbox"
                      checked={form.surge_indicator}
                      disabled={readOnly}
                      onChange={(event) =>
                        update(
                          "surge_indicator",
                          event.target.checked,
                        )
                      }
                    />
                    <span>
                      Surge conditions active
                    </span>
                  </label>
                </div>
              </section>
            </>
          )}

          <div className="create-appointment-actions">
            <button
              type="button"
              className="secondary-button"
              disabled={submitting}
              onClick={onClose}
            >
              Cancel
            </button>

            <button
              type="submit"
              className="primary-button"
              disabled={
                readOnly ||
                loadingOptions ||
                submitting
              }
            >
              {submitting
                ? "Saving and rescoring…"
                : "Save changes"}
            </button>
          </div>
        </form>
      </aside>
    </>
  );
}
