import { useEffect, useState } from "react";

import {
  getAppointments,
} from "../services/appointments";

import type {
  AppointmentApiModel,
} from "../services/appointments";

interface UseAppointmentsResult {
  appointments: AppointmentApiModel[];
  loading: boolean;
  error: string | null;
  refreshAppointments: () => Promise<void>;
}

export function useAppointments(): UseAppointmentsResult {
  const [appointments, setAppointments] = useState<
    AppointmentApiModel[]
  >([]);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function refreshAppointments(): Promise<void> {
    setLoading(true);
    setError(null);

    try {
      const data = await getAppointments();
      setAppointments(data);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Unable to load appointments",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refreshAppointments();
  }, []);

  return {
    appointments,
    loading,
    error,
    refreshAppointments,
  };
}