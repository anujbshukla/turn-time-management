import { useEffect, useState } from "react";

import {
  getPaginatedAppointments,
} from "../services/appointments";

import type {
  AppointmentFilters,
  AppointmentListItem,
  AppointmentPagination,
} from "../types/appointments";

const DEFAULT_PAGINATION: AppointmentPagination = {
  page: 1,
  page_size: 10,
  total_items: 0,
  total_pages: 1,
  has_previous: false,
  has_next: false,
};

export function useAppointments(
  filters: AppointmentFilters = {},
) {
  const [appointments, setAppointments] = useState<
    AppointmentListItem[]
  >([]);

  const [pagination, setPagination] =
    useState<AppointmentPagination>(
      DEFAULT_PAGINATION,
    );

  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  const [refreshKey, setRefreshKey] =
    useState(0);

  const [loading, setLoading] =
    useState(false);

  const [error, setError] =
    useState<string | null>(null);

  useEffect(() => {
    setPage(1);
  }, [
    filters.facilityId,
    filters.status,
    filters.riskLevel,
    filters.outcome,
    filters.search,
  ]);

  useEffect(() => {
    let cancelled = false;

    async function loadAppointments() {
      setLoading(true);
      setError(null);

      try {
        const response =
          await getPaginatedAppointments({
            page,
            pageSize,
            facilityId:
              filters.facilityId,
            status:
              filters.status,
            riskLevel:
              filters.riskLevel,
            outcome:
              filters.outcome,
            search:
              filters.search,
          });

        if (!cancelled) {
          setAppointments(
            response.items,
          );

          setPagination(
            response.pagination,
          );
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(
            loadError instanceof Error
              ? loadError.message
              : "Unable to load appointments",
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void loadAppointments();

    return () => {
      cancelled = true;
    };
  }, [
    page,
    pageSize,
    filters.facilityId,
    filters.status,
    filters.riskLevel,
    filters.outcome,
    filters.search,
    refreshKey,
  ]);

  function goToPreviousPage() {
    setPage((currentPage) =>
      Math.max(
        1,
        currentPage - 1,
      ),
    );
  }

  function goToNextPage() {
    setPage((currentPage) =>
      Math.min(
        pagination.total_pages,
        currentPage + 1,
      ),
    );
  }

  function changePageSize(
    newPageSize: number,
  ) {
    setPageSize(newPageSize);
    setPage(1);
  }

  function refresh() {
    setRefreshKey(
      (current) => current + 1,
    );
  }

  return {
    appointments,
    pagination,
    page,
    pageSize,
    loading,
    error,
    goToPreviousPage,
    goToNextPage,
    changePageSize,
    refresh,
  };
}