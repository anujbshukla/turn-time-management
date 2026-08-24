import {
  useEffect,
  useState,
} from "react";

import {
  getAppointmentDetails,
} from "../services/appointments";

import type {
  AppointmentDetailsResponse,
} from "../types/appointmentDetails";

export function useAppointmentDetails(
  appointmentId?: string,
) {
  const [details, setDetails] =
    useState<AppointmentDetailsResponse | null>(
      null,
    );

  const [loading, setLoading] =
    useState(false);

  const [error, setError] =
    useState<string | null>(null);

  const [refreshKey, setRefreshKey] =
    useState(0);

  useEffect(() => {
    let cancelled = false;

    if (!appointmentId) {
      setDetails(null);
      setError(null);
      setLoading(false);
      return;
    }

    const currentAppointmentId =
      appointmentId;

    async function loadDetails() {
      setLoading(true);
      setError(null);

      try {
        const response =
          await getAppointmentDetails(
            currentAppointmentId,
          );

        if (!cancelled) {
          setDetails(response);
        }
      } catch (loadError) {
        if (!cancelled) {
          setDetails(null);

          setError(
            loadError instanceof Error
              ? loadError.message
              : "Unable to load appointment details",
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void loadDetails();

    return () => {
      cancelled = true;
    };
  }, [
    appointmentId,
    refreshKey,
  ]);

  function refresh() {
    setRefreshKey(
      (current) => current + 1,
    );
  }

  return {
    details,
    loading,
    error,
    refresh,
  };
}
