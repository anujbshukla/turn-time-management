import type { AppointmentFilterReferenceData } from "../types/appointments";
import type {
  DelaySlaReasonItem,
  RecoveryPlanPerformanceItem,
} from "../types/dashboard";
import { DashboardIntelligenceTables } from "./DashboardIntelligenceTables";

export interface IntelligenceFilters {
  facilityId?: string;
  customerId?: string;
  carrierId?: string;
  appointmentType?: "Inbound" | "Outbound";
  dateFrom?: string;
  dateTo?: string;
}

interface RootCauseIntelligenceSectionProps {
  filters: IntelligenceFilters;
  referenceData: AppointmentFilterReferenceData;
  delayReasons: DelaySlaReasonItem[];
  recoveryPlans: RecoveryPlanPerformanceItem[];
  loading: boolean;
  error: string | null;
  onChange: (filters: IntelligenceFilters) => void;
}

export function RootCauseIntelligenceSection({
  filters,
  referenceData,
  delayReasons,
  recoveryPlans,
  loading,
  error,
  onChange,
}: RootCauseIntelligenceSectionProps) {
  const update = <K extends keyof IntelligenceFilters>(
    key: K,
    value: IntelligenceFilters[K],
  ) => onChange({ ...filters, [key]: value });

  return (
    <section className="independent-intelligence-section">
      <div className="independent-intelligence-heading">
        <div>
          <span>Independent analysis window</span>
          <h2>Root Cause Intelligence</h2>
          <p>
            Facility follows the global facility selection. Customer, carrier,
            appointment type and analysis dates remain independent from the page operating window.
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            const { dateFrom, dateTo } = getLastMonthRange();
            onChange({
              facilityId: filters.facilityId,
              dateFrom,
              dateTo,
            });
          }}
        >
          Reset analysis filters
        </button>
      </div>

      <div className="intelligence-filter-row">
        <label>
          <span>Customer</span>
          <select
            value={filters.customerId ?? ""}
            onChange={(event) =>
              update("customerId", event.target.value || undefined)
            }
          >
            <option value="">All customers</option>
            {referenceData.customers.map((item) => (
              <option key={item.id} value={item.id}>
                {item.label}
              </option>
            ))}
          </select>
        </label>

        <label>
          <span>Carrier</span>
          <select
            value={filters.carrierId ?? ""}
            onChange={(event) =>
              update("carrierId", event.target.value || undefined)
            }
          >
            <option value="">All carriers</option>
            {referenceData.carriers.map((item) => (
              <option key={item.id} value={item.id}>
                {item.label}
              </option>
            ))}
          </select>
        </label>

        <label>
          <span>Appointment</span>
          <select
            value={filters.appointmentType ?? ""}
            onChange={(event) =>
              update(
                "appointmentType",
                (event.target.value || undefined) as
                  | "Inbound"
                  | "Outbound"
                  | undefined,
              )
            }
          >
            <option value="">Inbound & outbound</option>
            {referenceData.appointmentTypes.map((item) => (
              <option key={item.id} value={item.id}>
                {item.label}
              </option>
            ))}
          </select>
        </label>

        <label>
          <span>From</span>
          <input
            type="date"
            value={filters.dateFrom ?? ""}
            onChange={(event) =>
              update("dateFrom", event.target.value || undefined)
            }
          />
        </label>

        <label>
          <span>To</span>
          <input
            type="date"
            value={filters.dateTo ?? ""}
            onChange={(event) =>
              update("dateTo", event.target.value || undefined)
            }
          />
        </label>
      </div>

      {error && <div className="table-error">{error}</div>}
      {loading && !error ? (
        <div className="intelligence-loading">Loading analysis…</div>
      ) : (
        <DashboardIntelligenceTables
          delayReasons={delayReasons}
          recoveryPlans={recoveryPlans}
        />
      )}
    </section>
  );
}

function getLastMonthRange() {
  const end = new Date();
  end.setHours(0, 0, 0, 0);
  const start = new Date(end);
  start.setDate(start.getDate() - 30);
  return {
    dateFrom: toLocalDate(start),
    dateTo: toLocalDate(end),
  };
}

function toLocalDate(value: Date) {
  const pad = (part: number) => String(part).padStart(2, "0");
  return `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}`;
}
