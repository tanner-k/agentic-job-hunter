import { createClient } from "@/lib/supabase/server";
import { ApplicationsTable } from "./applications-table";
import type { Application } from "@/lib/use-applications-realtime";

export default async function AdminPage() {
  const supabase = await createClient();
  const { data: applications } = await supabase
    .from("applications")
    .select("*")
    .order("applied_at", { ascending: false })
    .limit(100);

  const rows: Application[] = applications ?? [];

  return <ApplicationsTable initialData={rows} />;
}
