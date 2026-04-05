"use server";

import { createClient as createServerClient } from "@/lib/supabase/server";
import { createClient as createServiceClient } from "@supabase/supabase-js";

export async function createSearchTask(formData: FormData): Promise<{ error: string | null }> {
  // Verify the caller is authenticated before touching the DB
  const supabase = await createServerClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return { error: "Not authenticated" };

  // Use service role key for the insert — bypasses RLS, runs server-side only
  const admin = createServiceClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SERVICE_ROLE_KEY!
  );

  const keywordsRaw = formData.get("keywords") as string;
  const keywords = keywordsRaw
    ? keywordsRaw.split(",").map((k) => k.trim()).filter(Boolean)
    : [];

  const { error } = await admin.from("search_tasks").insert({
    job_title: formData.get("job_title") as string,
    location: formData.get("location") as string,
    min_salary: parseInt(formData.get("min_salary") as string) || null,
    keywords,
    company: (formData.get("company") as string) || null,
    job_website: (formData.get("job_website") as string) || null,
  });

  return { error: error?.message ?? null };
}
