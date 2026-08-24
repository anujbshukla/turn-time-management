import type {
  AppointmentEvent,
} from "../types/appointmentDetails";

type Props = {
  events: AppointmentEvent[];
};

function formatDate(
  value: string | null | undefined,
) {
  if (!value) return "—";

  return new Date(value).toLocaleString([], {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function formatEventType(
  eventType: string,
) {
  const labels: Record<string, string> = {
    APPOINTMENT_CREATED:
      "Appointment created",
    SCHEDULED:
      "Appointment scheduled",
    ETA_UPDATED:
      "Carrier ETA updated",
    CARRIER_DELAYED:
      "Carrier delay detected",
    ARRIVED:
      "Carrier arrived",
    CHECKED_IN:
      "Carrier checked in",
    DOCK_ASSIGNED:
      "Dock assigned",
    LOADING_STARTED:
      "Loading started",
    LOADING_COMPLETED:
      "Loading completed",
    UNLOADING_STARTED:
      "Unloading started",
    UNLOADING_COMPLETED:
      "Unloading completed",
    DEPARTED:
      "Carrier departed",
    PREDICTION_GENERATED:
      "AI prediction generated",
    RECOMMENDATION_GENERATED:
      "AI recovery plan generated",
    RECOVERY_ACTION_ACCEPTED:
      "Recovery action accepted",
    RECOVERY_ACTION_REJECTED:
      "Recovery action rejected",
    RECOVERY_ACTION_RESET:
      "Recovery action reset to pending",
  };

  return (
    labels[eventType] ??
    eventType
      .replaceAll("_", " ")
      .toLowerCase()
      .replace(
        /^./,
        (firstCharacter) =>
          firstCharacter.toUpperCase(),
      )
  );
}

export function AppointmentEventHistory({
  events,
}: Props) {
  return (
    <section className="drawer-section">
      <span className="drawer-section-label">
        Operational timeline
      </span>

      <h3>
        Appointment events
      </h3>

      <div className="timeline">
        {events.map((event) => {
          const eventClass =
            event.event_type
              .toLowerCase()
              .replaceAll("_", "-");

          return (
            <div
              key={`${event.event_type}-${event.event_id}`}
              className={`timeline-item timeline-${eventClass}`}
            >
              <div className="timeline-marker" />

              <div>
                <strong>
                  {formatEventType(
                    event.event_type,
                  )}
                </strong>

                <span>
                  {formatDate(
                    event.event_time,
                  )}
                </span>

                {event.notes && (
                  <p>{event.notes}</p>
                )}
              </div>
            </div>
          );
        })}

        {events.length === 0 && (
          <p className="timeline-empty">
            No operational events are available.
          </p>
        )}
      </div>
    </section>
  );
}
