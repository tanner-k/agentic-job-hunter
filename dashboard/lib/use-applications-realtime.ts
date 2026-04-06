"use client";

import { useEffect, useState } from "react";
import { createClient } from "@/lib/supabase/client";

export type Application = {
  id: string;
  company: string;
  job_title: string;
  job_url: string;
  status: string;
  applied_at: string;
  error_message: string | null;
  requires_resume: boolean;
  search_task_id: string | null;
};

/**
 * Subscribes to real-time changes on the applications table.
 * Seeds state from initialData (SSR fetch) and patches on INSERT/UPDATE.
 */
export function useApplicationsRealtime(initialData: Application[]): Application[] {
  const [rows, setRows] = useState<Application[]>(initialData);

  useEffect(() => {
    const supabase = createClient();

    const channel = supabase
      .channel("applications-realtime")
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "applications" },
        (payload) => {
          if (payload.eventType === "INSERT") {
            setRows((prev) => [payload.new as Application, ...prev]);
          } else if (payload.eventType === "UPDATE") {
            setRows((prev) =>
              prev.map((row) =>
                row.id === (payload.new as Application).id
                  ? (payload.new as Application)
                  : row
              )
            );
          }
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, []);

  return rows;
}
