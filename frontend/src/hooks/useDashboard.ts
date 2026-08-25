import { useEffect, useMemo, useState } from "react";

import { getDashboard } from "../services/dashboard";
import type { DashboardFilters } from "../services/dashboard";
import type { DashboardResponse } from "../types/dashboard";

export function useDashboard(
  filters: DashboardFilters = {},
  enabled = true,
) {
  const [dashboard, setDashboard] =
    useState<DashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] =
    useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  const filterKey = useMemo(
    () => JSON.stringify(filters),
    [
      filters.facilityId,
      filters.customerId,
      filters.carrierId,
      filters.appointmentType,
      filters.dateFrom,
      filters.dateTo,
      filters.timeFrom,
      filters.timeTo,
    ],
  );

  useEffect(() => {
    if (!enabled) {
      setLoading(false);
      return;
    }

    let cancelled = false;

    async function loadDashboard() {
      setLoading(true);
      setError(null);

      try {
        const response = await getDashboard(filters);
        if (!cancelled) setDashboard(response);
      } catch (loadError) {
        if (!cancelled) {
          setError(
            loadError instanceof Error
              ? loadError.message
              : "Unable to load dashboard",
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void loadDashboard();

    const refreshInterval = window.setInterval(() => {
      void loadDashboard();
    }, 30_000);

    return () => {
      cancelled = true;
      window.clearInterval(refreshInterval);
    };
  }, [filterKey, refreshKey, enabled]);

  function refresh() {
    setRefreshKey(
      (currentRefreshKey) => currentRefreshKey + 1,
    );
  }

  return { dashboard, loading, error, refresh };
}
