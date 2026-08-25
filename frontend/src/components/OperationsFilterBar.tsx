import type { AppointmentReferenceItem } from "../types/appointments";
import type { DashboardResponse } from "../types/dashboard";

export type DatePreset =
  | "previous-7-days"
  | "today"
  | "yesterday"
  | "tomorrow"
  | "next-week"
  | "custom";

export type CompareMode =
  | "off"
  | "same-day-last-week"
  | "previous-week";

export interface OperationsGlobalFilters {
  customerId?: string;
  carrierId?: string;
  appointmentType?: "Inbound" | "Outbound";
  datePreset: DatePreset;
  customDate?: string;
  customDateEnd?: string;
  timeFrom?: string;
  timeTo?: string;
  compareMode: CompareMode;
}

interface OperationsFilterBarProps {
  filters: OperationsGlobalFilters;
  customers: AppointmentReferenceItem[];
  carriers: AppointmentReferenceItem[];
  appointmentTypes: AppointmentReferenceItem[];
  onChange: (filters: OperationsGlobalFilters) => void;
  currentDashboard?: DashboardResponse | null;
  comparisonDashboard?: DashboardResponse | null;
  comparisonLoading?: boolean;
}

export interface DateRange {
  dateFrom: string;
  dateTo: string;
}

export function OperationsFilterBar({
  filters,
  customers,
  carriers,
  appointmentTypes,
  onChange,
  currentDashboard,
  comparisonDashboard,
  comparisonLoading,
}: OperationsFilterBarProps) {
  const update = <K extends keyof OperationsGlobalFilters>(
    key: K,
    value: OperationsGlobalFilters[K],
  ) => onChange({ ...filters, [key]: value });

  const activePickerRange = getPresetRange(
    filters.datePreset,
    filters.customDate,
    filters.customDateEnd,
  );

  const activePickerEnd = fromLocalDate(activePickerRange.dateTo);
  activePickerEnd.setDate(activePickerEnd.getDate() - 1);

  const pickerStart =
    filters.datePreset === "custom"
      ? filters.customDate ?? activePickerRange.dateFrom
      : activePickerRange.dateFrom;

  const pickerEnd =
    filters.datePreset === "custom"
      ? filters.customDateEnd ?? pickerStart
      : toLocalDate(activePickerEnd);

  const pickerTimeFrom =
    filters.timeFrom ?? "00:00";

  const pickerTimeTo =
    filters.timeTo ?? "23:59";
  return (
    <section className="operations-filter-shell compact-filter-shell" aria-label="Dashboard filters">
      <div className="operations-filter-row">
        <div className="date-view-copy">
          <span className="filter-eyebrow">Operating window</span>
          <strong>{datePresetLabel(filters.datePreset, filters.customDate, filters.customDateEnd)}</strong>
        </div>

        <div
          className="custom-date-range-control"
          aria-label="Operating date range"
        >
          <div className="custom-date-range-track">
            <label>
              <span>From</span>
              <input
                type="date"
                value={pickerStart}
                max={pickerEnd}
                onChange={(event) => {
                  const nextStart = event.target.value;
                  const nextEnd =
                    pickerEnd && pickerEnd < nextStart
                      ? nextStart
                      : pickerEnd;

                  onChange({
                    ...filters,
                    datePreset: "custom",
                    customDate: nextStart,
                    customDateEnd: nextEnd,
                  });
                }}
              />
            </label>

            <span
              className="custom-date-range-arrow"
              aria-hidden="true"
            >
              →
            </span>

            <label>
              <span>To</span>
              <input
                type="date"
                value={pickerEnd}
                min={pickerStart}
                onChange={(event) =>
                  onChange({
                    ...filters,
                    datePreset: "custom",
                    customDate: pickerStart,
                    customDateEnd: event.target.value,
                  })
                }
              />
            </label>
          </div>
        </div>

        <div
          className="custom-time-range-control"
          aria-label="Operating time range"
        >
          <div className="custom-time-range-track">
            <label>
              <span>From</span>

              <input
                type="time"
                value={pickerTimeFrom}
                max={pickerTimeTo}
                onChange={(event) => {
                  const nextStart =
                    event.target.value;

                  const nextEnd =
                    pickerTimeTo &&
                      pickerTimeTo < nextStart
                      ? nextStart
                      : pickerTimeTo;

                  onChange({
                    ...filters,
                    timeFrom: nextStart,
                    timeTo: nextEnd,
                  });
                }}
              />
            </label>

            <span
              className="custom-time-range-arrow"
              aria-hidden="true"
            >
              →
            </span>

            <label>
              <span>To</span>

              <input
                type="time"
                value={pickerTimeTo}
                min={pickerTimeFrom}
                onChange={(event) =>
                  onChange({
                    ...filters,
                    timeFrom: pickerTimeFrom,
                    timeTo: event.target.value,
                  })
                }
              />
            </label>
          </div>
        </div>

        <label className="compare-control">
          <span className="filter-eyebrow">Compare</span>
          <select
            value={filters.compareMode}
            onChange={(event) =>
              update("compareMode", event.target.value as CompareMode)
            }
          >
            <option value="off">Comparison off</option>
            <option value="same-day-last-week">Same day last week</option>
            <option value="previous-week">Previous week</option>
          </select>
        </label>

        <label className="filter-field">
          <span>Customer</span>
          <select
            value={filters.customerId ?? ""}
            onChange={(event) =>
              update("customerId", event.target.value || undefined)
            }
          >
            <option value="">All customers</option>
            {customers.map((customer) => (
              <option key={customer.id} value={customer.id}>
                {customer.label}
              </option>
            ))}
          </select>
        </label>

        <label className="filter-field">
          <span>Carrier</span>
          <select
            value={filters.carrierId ?? ""}
            onChange={(event) =>
              update("carrierId", event.target.value || undefined)
            }
          >
            <option value="">All carriers</option>
            {carriers.map((carrier) => (
              <option key={carrier.id} value={carrier.id}>
                {carrier.label}
              </option>
            ))}
          </select>
        </label>

        <label className="filter-field">
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
            <option value="">All</option>
            {appointmentTypes.map((type) => (
              <option key={type.id} value={type.id}>
                {type.label}
              </option>
            ))}
          </select>
        </label>

        <button
          type="button"
          className="clear-global-filters"
          onClick={() =>
            onChange({
              datePreset: "today",
              timeFrom: undefined,
              timeTo: undefined,
              compareMode: "off",
              appointmentType: undefined,
            })
          }
        >
          Reset
        </button>
      </div>

      {filters.compareMode !== "off" && (
        <div className="comparison-panel">
          <div className="comparison-banner">
            <span className="comparison-icon">↔</span>
            <div>
              <strong>{comparisonTitle(filters.compareMode)}</strong>
              <span>
                {comparisonLabel(
                  filters.compareMode,
                  filters.datePreset,
                  filters.customDate,
                  filters.customDateEnd,
                )}
              </span>
            </div>
          </div>

          {comparisonLoading ? (
            <div className="comparison-loading">Loading comparison…</div>
          ) : currentDashboard && comparisonDashboard ? (
            <div className="comparison-metrics">
              <ComparisonMetric
                label="Appointments"
                current={currentDashboard.summary.total_appointments}
                previous={comparisonDashboard.summary.total_appointments}
              />
              <ComparisonMetric
                label="Late arrivals"
                current={currentDashboard.summary.late_arrivals}
                previous={comparisonDashboard.summary.late_arrivals}
                lowerIsBetter
              />
              <ComparisonMetric
                label="SLA misses"
                current={currentDashboard.summary.sla_misses}
                previous={comparisonDashboard.summary.sla_misses}
                lowerIsBetter
              />
              <ComparisonMetric
                label="Late turns recovered"
                current={currentDashboard.summary.late_turned_on_time}
                previous={comparisonDashboard.summary.late_turned_on_time}
              />
            </div>
          ) : null}
        </div>
      )}
    </section>
  );
}

export function getPresetRange(
  preset: DatePreset,
  customDate?: string,
  customDateEnd?: string,
): DateRange {
  const start = getPresetStart(preset, customDate);
  const end = new Date(start);

  if (preset === "custom") {
    const inclusiveEnd = customDateEnd
      ? fromLocalDate(customDateEnd)
      : new Date(start);
    const normalizedEnd =
      inclusiveEnd < start
        ? new Date(start)
        : inclusiveEnd;

    normalizedEnd.setDate(normalizedEnd.getDate() + 1);

    return {
      dateFrom: toLocalDate(start),
      dateTo: toLocalDate(normalizedEnd),
    };
  }

  end.setDate(
    end.getDate() +
    (preset === "next-week" || preset === "previous-7-days" ? 7 : 1),
  );

  return {
    dateFrom: toLocalDate(start),
    dateTo: toLocalDate(end),
  };
}

export function getComparisonRange(
  preset: DatePreset,
  mode: CompareMode,
  customDate?: string,
  customDateEnd?: string,
): DateRange | undefined {
  if (mode === "off") return undefined;

  if (mode === "previous-week") {
    return getWeekComparisonRanges().previous;
  }

  const active = getPresetRange(preset, customDate, customDateEnd);
  const activeStart = fromLocalDate(active.dateFrom);
  const activeEnd = fromLocalDate(active.dateTo);

  activeStart.setDate(activeStart.getDate() - 7);
  activeEnd.setDate(activeEnd.getDate() - 7);

  return {
    dateFrom: toLocalDate(activeStart),
    dateTo: toLocalDate(activeEnd),
  };
}

export function getWeekComparisonRanges() {
  const now = new Date();
  const currentStart = new Date(
    now.getFullYear(),
    now.getMonth(),
    now.getDate(),
  );
  const mondayOffset = (currentStart.getDay() + 6) % 7;
  currentStart.setDate(currentStart.getDate() - mondayOffset);

  const currentEnd = new Date(currentStart);
  currentEnd.setDate(currentEnd.getDate() + 7);

  const previousStart = new Date(currentStart);
  previousStart.setDate(previousStart.getDate() - 7);

  const previousEnd = new Date(currentEnd);
  previousEnd.setDate(previousEnd.getDate() - 7);

  return {
    current: {
      dateFrom: toLocalDate(currentStart),
      dateTo: toLocalDate(currentEnd),
    },
    previous: {
      dateFrom: toLocalDate(previousStart),
      dateTo: toLocalDate(previousEnd),
    },
  };
}

function getPresetStart(preset: DatePreset, customDate?: string) {
  const now = new Date();
  const start = new Date(now.getFullYear(), now.getMonth(), now.getDate());

  if (preset === "previous-7-days") start.setDate(start.getDate() - 7);
  if (preset === "yesterday") start.setDate(start.getDate() - 1);
  if (preset === "tomorrow") start.setDate(start.getDate() + 1);
  if (preset === "custom" && customDate) return fromLocalDate(customDate);

  return start;
}

function fromLocalDate(value: string) {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, month - 1, day);
}

function toLocalDate(value: Date) {
  const pad = (part: number) => String(part).padStart(2, "0");
  return `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}`;
}

function datePresetLabel(
  preset: DatePreset,
  customDate?: string,
  customDateEnd?: string,
) {
  if (preset === "previous-7-days") return "Previous 7 days";
  if (preset === "today") return "Today";
  if (preset === "yesterday") return "Yesterday";
  if (preset === "tomorrow") return "Tomorrow";
  if (preset === "next-week") return "Next 7 days";

  if (customDate) {
    const formatter = new Intl.DateTimeFormat(undefined, {
      month: "short",
      day: "numeric",
    });
    const start = formatter.format(fromLocalDate(customDate));
    const end = formatter.format(
      fromLocalDate(customDateEnd ?? customDate),
    );
    return start === end ? start : `${start}–${end}`;
  }

  return "Custom date";
}

function comparisonTitle(mode: CompareMode) {
  return mode === "previous-week"
    ? "Week-over-week comparison"
    : "Same weekday comparison";
}

function comparisonLabel(
  mode: CompareMode,
  preset: DatePreset,
  customDate?: string,
  customDateEnd?: string,
) {
  const current = mode === "previous-week"
    ? getWeekComparisonRanges().current
    : getPresetRange(preset, customDate, customDateEnd);
  const previous = getComparisonRange(preset, mode, customDate, customDateEnd);
  if (!previous) return "";

  const format = (value: string) =>
    new Intl.DateTimeFormat(undefined, {
      weekday: "short",
      month: "short",
      day: "numeric",
    }).format(fromLocalDate(value));

  const currentDurationDays =
    Math.round(
      (fromLocalDate(current.dateTo).getTime() -
        fromLocalDate(current.dateFrom).getTime()) /
      86_400_000,
    );

  if (mode === "same-day-last-week" && currentDurationDays === 1) {
    return `${format(current.dateFrom)} vs ${format(previous.dateFrom)} — the same weekday last week.`;
  }

  const currentEnd = fromLocalDate(current.dateTo);
  currentEnd.setDate(currentEnd.getDate() - 1);
  const previousEnd = fromLocalDate(previous.dateTo);
  previousEnd.setDate(previousEnd.getDate() - 1);

  return `${format(current.dateFrom)}–${format(toLocalDate(currentEnd))} vs ${format(previous.dateFrom)}–${format(toLocalDate(previousEnd))}.`;
}

function ComparisonMetric({
  label,
  current,
  previous,
  lowerIsBetter = false,
}: {
  label: string;
  current: number;
  previous: number;
  lowerIsBetter?: boolean;
}) {
  const delta = current - previous;
  const improved = lowerIsBetter ? delta < 0 : delta > 0;
  const neutral = delta === 0;

  return (
    <div className="comparison-metric">
      <span>{label}</span>
      <div className="comparison-values">
        <strong className="comparison-current-value">
          {current.toLocaleString()}
        </strong>
        <span className="comparison-vs">vs</span>
        <strong className="comparison-previous-value">
          {previous.toLocaleString()}
        </strong>
      </div>
      <em className={neutral ? "neutral" : improved ? "positive" : "negative"}>
        {delta > 0 ? "+" : ""}
        {delta.toLocaleString()}
      </em>
    </div>
  );
}
