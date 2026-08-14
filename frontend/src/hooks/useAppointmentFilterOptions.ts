import { useEffect, useState } from "react";

import { getAppointmentFilterOptions } from "../services/appointments";
import type {
  AppointmentFilterReferenceData,
  AppointmentQuery,
} from "../types/appointments";

const EMPTY_OPTIONS: AppointmentFilterReferenceData = {
  facilities: [],
  customers: [],
  carriers: [],
  appointmentTypes: [],
};

export function useAppointmentFilterOptions(
  query: Pick<
    AppointmentQuery,
    | "facilityId"
    | "customerId"
    | "carrierId"
    | "appointmentType"
    | "dateFrom"
    | "dateTo"
  >,
) {
  const [options, setOptions] =
    useState<AppointmentFilterReferenceData>(EMPTY_OPTIONS);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);

    getAppointmentFilterOptions(query, controller.signal)
      .then((result) => {
        setOptions(result);
      })
      .catch((error) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        console.error("Unable to load cascading filter options", error);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [
    query.facilityId,
    query.customerId,
    query.carrierId,
    query.appointmentType,
    query.dateFrom,
    query.dateTo,
  ]);

  return { options, loading };
}
