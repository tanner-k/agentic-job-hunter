"use client";

import { useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function SearchPage() {
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setLoading(true);
    setSuccess(false);
    setError(null);

    const formData = new FormData(e.currentTarget);
    const keywordsRaw = formData.get("keywords") as string;
    const keywords = keywordsRaw
      ? keywordsRaw.split(",").map((k) => k.trim()).filter(Boolean)
      : [];

    const supabase = createClient();
    const { error: insertError } = await supabase.from("search_tasks").insert({
      job_title: formData.get("job_title") as string,
      location: formData.get("location") as string,
      min_salary: parseInt(formData.get("min_salary") as string) || null,
      keywords,
      company: formData.get("company") as string || null,
      job_website: formData.get("job_website") as string || null,
    });

    if (insertError) {
      setError(insertError.message);
    } else {
      setSuccess(true);
      (e.target as HTMLFormElement).reset();
    }
    setLoading(false);
  }

  return (
    <div className="max-w-xl">
      <h1 className="text-2xl font-bold mb-6">New Search Task</h1>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Search Parameters</CardTitle>
          <CardDescription>
            The worker will pick this up instantly and start searching.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1">
              <Label htmlFor="job_title">Job Title *</Label>
              <Input id="job_title" name="job_title" placeholder="Software Engineer" required />
            </div>

            <div className="space-y-1">
              <Label htmlFor="location">Location *</Label>
              <Input id="location" name="location" placeholder="San Francisco, CA or Remote" required />
            </div>

            <div className="space-y-1">
              <Label htmlFor="min_salary">Minimum Salary (USD/year)</Label>
              <Input id="min_salary" name="min_salary" type="number" placeholder="100000" />
            </div>

            <div className="space-y-1">
              <Label htmlFor="keywords">Keywords (comma-separated)</Label>
              <Input id="keywords" name="keywords" placeholder="Python, FastAPI, AWS" />
            </div>

            <div className="space-y-1">
              <Label htmlFor="company">Target Company (optional)</Label>
              <Input id="company" name="company" placeholder="Acme Corp" />
            </div>

            <div className="space-y-1">
              <Label htmlFor="job_website">Target Website (optional)</Label>
              <Input id="job_website" name="job_website" placeholder="greenhouse.io/acme" />
            </div>

            {error && (
              <p className="text-sm text-destructive">{error}</p>
            )}
            {success && (
              <p className="text-sm text-green-600">
                Search task submitted! The worker will pick it up shortly.
              </p>
            )}

            <Button type="submit" disabled={loading} className="w-full">
              {loading ? "Submitting..." : "Start Search"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
