import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { getAppointmentReferenceData } from "../services/appointments";
import type { AppointmentReferenceData } from "../types/appointments";
import type { ComparisonMode, DatePreset, DashboardQueryFilters, OperationsFilters, } from "../types/appointments";

const emptyReferenceData: AppointmentReferenceData = {
  facilities: [], customers: [], carriers: [], docks: [], products: [],
};

function formatLocalDate(date: Date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function addDays(value: string, days: number) {
  const [year, month, day] = value.split("-").map(Number);
  const date = new Date(year, month - 1, day);
  date.setDate(date.getDate() + days);
  return formatLocalDate(date);
}

function rangeForPreset(preset: DatePreset): Pick<OperationsFilters, "dateFrom" | "dateTo"> {
  const today = formatLocalDate(new Date());
  if (preset === "yesterday") return { dateFrom: addDays(today, -1), dateTo: addDays(today, -1) };
  if (preset === "tomorrow") return { dateFrom: addDays(today, 1), dateTo: addDays(today, 1) };
  if (preset === "next7") return { dateFrom: today, dateTo: addDays(today, 6) };
  return { dateFrom: today, dateTo: today };
}

function currentWeekRange() {
  const now = new Date();
  const day = now.getDay();
  const mondayOffset = day === 0 ? -6 : 1 - day;
  const monday = new Date(now);
  monday.setDate(now.getDate() + mondayOffset);
  const sunday = new Date(monday);
  sunday.setDate(monday.getDate() + 6);
  return { dateFrom: formatLocalDate(monday), dateTo: formatLocalDate(sunday) };
}

interface OperationsFilterContextValue {
  filters: OperationsFilters;
  comparisonMode: ComparisonMode;
  comparisonFilters: DashboardQueryFilters | null;
  referenceData: AppointmentReferenceData;
  referenceLoading: boolean;
  setDimensionFilter: (key: "facilityId" | "customerId" | "carrierId" | "appointmentType", value?: string) => void;
  setDatePreset: (preset: DatePreset) => void;
  setCustomDateRange: (dateFrom: string, dateTo: string) => void;
  setComparisonMode: (mode: ComparisonMode) => void;
  clearDimensions: () => void;
}

const OperationsFilterContext = createContext<OperationsFilterContextValue | null>(null);

export function OperationsFilterProvider({ children }: { children: ReactNode }) {
  const initialRange = rangeForPreset("today");
  const [filters, setFilters] = useState<OperationsFilters>({ ...initialRange, datePreset: "today" });
  const [comparisonMode, setComparisonModeState] = useState<ComparisonMode>("none");
  const [referenceData, setReferenceData] = useState<AppointmentReferenceData>(emptyReferenceData);
  const [referenceLoading, setReferenceLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    getAppointmentReferenceData()
      .then((data) => { if (!cancelled) setReferenceData(data); })
      .finally(() => { if (!cancelled) setReferenceLoading(false); });
    return () => { cancelled = true; };
  }, []);

  function setDimensionFilter(key: "facilityId" | "customerId" | "carrierId" | "appointmentType", value?: string) {
    setFilters((current) => ({ ...current, [key]: value || undefined }));
  }

  function setDatePreset(preset: DatePreset) {
    const range = rangeForPreset(preset);
    setFilters((current) => ({ ...current, ...range, datePreset: preset }));
    if (comparisonMode === "week-over-week") setComparisonModeState("none");
  }

  function setCustomDateRange(dateFrom: string, dateTo: string) {
    setFilters((current) => ({ ...current, dateFrom, dateTo: dateTo || dateFrom, datePreset: "custom" }));
    if (comparisonMode === "week-over-week") setComparisonModeState("none");
  }

  function setComparisonMode(mode: ComparisonMode) {
    setComparisonModeState(mode);
    if (mode === "week-over-week") {
      const range = currentWeekRange();
      setFilters((current) => ({ ...current, ...range, datePreset: "custom" }));
    }
  }

  function clearDimensions() {
    setFilters((current) => ({ ...current, facilityId: undefined, customerId: undefined, carrierId: undefined, appointmentType: undefined }));
  }

  const comparisonFilters = useMemo<DashboardQueryFilters | null>(() => {
    if (comparisonMode === "none") return null;
    return {
      facilityId: filters.facilityId,
      customerId: filters.customerId,
      carrierId: filters.carrierId,
      appointmentType: filters.appointmentType,
      dateFrom: addDays(filters.dateFrom, -7),
      dateTo: addDays(filters.dateTo, -7),
    };
  }, [comparisonMode, filters]);

  return (
    <OperationsFilterContext.Provider value={{
      filters, comparisonMode, comparisonFilters, referenceData, referenceLoading,
      setDimensionFilter, setDatePreset, setCustomDateRange, setComparisonMode, clearDimensions,
    }}>
      {children}
    </OperationsFilterContext.Provider>
  );
}

export function useOperationsFilters() {
  const value = useContext(OperationsFilterContext);
  if (!value) throw new Error("useOperationsFilters must be used within OperationsFilterProvider");
  return value;
}
