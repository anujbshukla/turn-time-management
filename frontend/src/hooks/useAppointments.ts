import { useEffect, useState } from "react";

import {
  getPaginatedAppointments,
} from "../services/appointments";

import type {
  AppointmentFilters,
  AppointmentListItem,
  AppointmentPagination,
  AppointmentSortField,
  SortDirection,
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

  const [sortBy, setSortBy] =
    useState<AppointmentSortField | undefined>(
      undefined,
    );

  const [sortDirection, setSortDirection] =
    useState<SortDirection | undefined>(
      undefined,
    );

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
    filters.customerId,
    filters.carrierId,
    filters.dockId,
    filters.appointmentType,
    filters.dateFrom,
    filters.dateTo,
    filters.timeFrom,
    filters.timeTo,
    filters.palletMin,
    filters.palletMax,
    filters.skuMin,
    filters.skuMax,
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

            customerId:
              filters.customerId,

            carrierId:
              filters.carrierId,

            dockId:
              filters.dockId,

            appointmentType:
              filters.appointmentType,

            dateFrom:
              filters.dateFrom,

            dateTo:
              filters.dateTo,

            timeFrom:
              filters.timeFrom,

            timeTo:
              filters.timeTo,

            palletMin:
              filters.palletMin,

            palletMax:
              filters.palletMax,

            skuMin:
              filters.skuMin,

            skuMax:
              filters.skuMax,

            status:
              filters.status,

            riskLevel:
              filters.riskLevel,

            outcome:
              filters.outcome,

            search:
              filters.search,

            sortBy,
            sortDirection,
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
    filters.customerId,
    filters.carrierId,
    filters.dockId,
    filters.appointmentType,
    filters.dateFrom,
    filters.dateTo,
    filters.timeFrom,
    filters.timeTo,
    filters.palletMin,
    filters.palletMax,
    filters.skuMin,
    filters.skuMax,
    filters.status,
    filters.riskLevel,
    filters.outcome,
    filters.search,
    sortBy,
    sortDirection,
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

  function changeSort(
    field: AppointmentSortField,
  ) {
    if (sortBy !== field) {
      setSortBy(field);
      setSortDirection("asc");
      setPage(1);
      return;
    }

    if (sortDirection === "asc") {
      setSortDirection("desc");
      setPage(1);
      return;
    }

    setSortBy(undefined);
    setSortDirection(undefined);
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
    sortBy,
    sortDirection,
    loading,
    error,
    goToPreviousPage,
    goToNextPage,
    changePageSize,
    changeSort,
    refresh,
  };
}