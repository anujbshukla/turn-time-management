import { useEffect, useState } from "react";
import type { FormEvent } from "react";

import {
  rescheduleAppointment,
} from "../services/appointments";

import type {
  AppointmentDetailsAppointment,
} from "../types/appointmentDetails";

type Props = {
  open: boolean;
  appointment:
  AppointmentDetailsAppointment;
  onClose: () => void;
  onSaved: () => void | Promise<void>;
};

function toLocalInputValue(
  value: string,
) {
  const date = new Date(value);

  const local =
    new Date(
      date.getTime() -
      date.getTimezoneOffset() *
      60_000,
    );

  return local
    .toISOString()
    .slice(0, 16);
}

function formatDateTime(
  value: string,
) {
  return new Date(
    value,
  ).toLocaleString([], {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function RescheduleAppointmentDialog({
  open,
  appointment,
  onClose,
  onSaved,
}: Props) {
  const [scheduledTime, setScheduledTime] =
    useState(
      toLocalInputValue(
        appointment.scheduled_time,
      ),
    );

  const [reason, setReason] =
    useState("");

  const [submitting, setSubmitting] =
    useState(false);

  const [error, setError] =
    useState<string | null>(null);

  useEffect(() => {
    if (!open) return;

    setScheduledTime(
      toLocalInputValue(
        appointment.scheduled_time,
      ),
    );

    setReason("");
    setError(null);
  }, [
    open,
    appointment.scheduled_time,
  ]);

  if (!open) return null;

  const rescheduleDisabled =
    appointment.status === "Arrived" ||
    appointment.status === "Waiting" ||
    appointment.status ===
    "Dock Assigned" ||
    appointment.status ===
    "In Progress" ||
    appointment.status ===
    "Completed" ||
    Boolean(
      appointment.actual_arrival_time,
    );

  async function handleSubmit(
    event:
      FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    if (rescheduleDisabled) {
      setError(
        "This appointment can no longer be rescheduled because it has already arrived or completed.",
      );
      return;
    }

    if (!reason.trim()) {
      setError(
        "Enter a reason for the reschedule.",
      );
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      await rescheduleAppointment(
        appointment.appt_id,
        {
          // Send the warehouse-local date/time
          // exactly as selected.
          scheduled_time: scheduledTime,
          reason: reason.trim(),
        },
      );

      await onSaved();
      onClose();
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Unable to reschedule appointment.",
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
        aria-label="Close reschedule appointment"
        onClick={onClose}
      />

      <aside
        className="appointment-drawer reschedule-appointment-drawer"
        aria-label="Reschedule appointment"
      >
        <header className="drawer-header">
          <div>
            <span className="drawer-eyebrow">
              Appointment scheduling
            </span>

            <h2>
              Reschedule appointment
            </h2>

            <p>
              {appointment.appt_id}
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
          className="reschedule-appointment-form"
          onSubmit={handleSubmit}
        >
          {error && (
            <div className="table-error">
              {error}
            </div>
          )}

          {rescheduleDisabled && (
            <div className="appointment-change-notice">
              Rescheduling is disabled after
              arrival, while work is in
              progress, and after completion.
            </div>
          )}

          <section className="drawer-section">
            <span className="drawer-section-label">
              Current schedule
            </span>

            <div className="reschedule-current-time">
              {formatDateTime(
                appointment.scheduled_time,
              )}
            </div>
          </section>

          <section className="drawer-section">
            <span className="drawer-section-label">
              New schedule
            </span>

            <div className="create-form-grid">
              <label>
                <span>
                  New appointment date/time
                </span>

                <input
                  required
                  type="datetime-local"
                  value={scheduledTime}
                  disabled={
                    rescheduleDisabled
                  }
                  onChange={(event) =>
                    setScheduledTime(
                      event.target.value,
                    )
                  }
                />
              </label>

              <label className="reschedule-reason-field">
                <span>Reason</span>

                <textarea
                  required
                  rows={4}
                  value={reason}
                  disabled={
                    rescheduleDisabled
                  }
                  placeholder="Carrier delay, customer request, dock capacity change…"
                  onChange={(event) =>
                    setReason(
                      event.target.value,
                    )
                  }
                />
              </label>
            </div>
          </section>

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
                submitting ||
                rescheduleDisabled
              }
            >
              {submitting
                ? "Rescheduling and rescoring…"
                : "Reschedule"}
            </button>
          </div>
        </form>
      </aside>
    </>
  );
}
