import { useEffect, useMemo, useState } from "react";

import {
  getDashboardIntelligence,
  getDashboardIntelligenceFilterOptions,
  type DashboardFilters,
  type DashboardIntelligenceResponse,
} from "../services/dashboard";
import type { AppointmentFilterReferenceData } from "../types/appointments";

export function useDashboardIntelligence(
  filters: DashboardFilters = {},
) {
  const [data, setData] =
    useState<DashboardIntelligenceResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const filterKey = useMemo(
    () => JSON.stringify(filters),
    [
      filters.facilityId,
      filters.customerId,
      filters.carrierId,
      filters.appointmentType,
      filters.dateFrom,
      filters.dateTo,
    ],
  );

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);

      try {
        const response = await getDashboardIntelligence(filters);
        if (!cancelled) setData(response);
      } catch (loadError) {
        if (!cancelled) {
          setError(
            loadError instanceof Error
              ? loadError.message
              : "Unable to load root-cause intelligence",
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [filterKey]);

  return { data, loading, error };
}


const EMPTY_INTELLIGENCE_FILTER_OPTIONS: AppointmentFilterReferenceData = {
  facilities: [],
  customers: [],
  carriers: [],
  appointmentTypes: [],
};

export function useDashboardIntelligenceFilterOptions(
  filters: DashboardFilters = {},
) {
  const [options, setOptions] = useState<AppointmentFilterReferenceData>(
    EMPTY_INTELLIGENCE_FILTER_OPTIONS,
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const filterKey = useMemo(
    () => JSON.stringify(filters),
    [
      filters.facilityId,
      filters.customerId,
      filters.carrierId,
      filters.appointmentType,
      filters.dateFrom,
      filters.dateTo,
    ],
  );

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const result = await getDashboardIntelligenceFilterOptions(filters);
        if (!cancelled) setOptions(result);
      } catch (loadError) {
        if (!cancelled) {
          setOptions(EMPTY_INTELLIGENCE_FILTER_OPTIONS);
          setError(
            loadError instanceof Error
              ? loadError.message
              : "Unable to load root-cause filter options",
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [filterKey]);

  return { options, loading, error };
}
