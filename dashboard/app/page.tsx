import { createClient } from "@/lib/supabase/server";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface DayStat {
  date: string;
  status: string;
  count: number;
}

export default async function PublicPage() {
  const supabase = await createClient();
  const { data: stats } = await supabase.from("public_stats").select("*");

  const typedStats: DayStat[] = stats ?? [];

  const totalApplied = typedStats
    .filter((s) => s.status === "applied")
    .reduce((sum, s) => sum + s.count, 0);

  const totalFailed = typedStats
    .filter((s) => s.status === "failed")
    .reduce((sum, s) => sum + s.count, 0);

  const successRate =
    totalApplied + totalFailed > 0
      ? Math.round((totalApplied / (totalApplied + totalFailed)) * 100)
      : 0;

  return (
    <main className="min-h-screen bg-background p-8">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-3xl font-bold mb-2">Agentic Job Hunter</h1>
        <p className="text-muted-foreground mb-8">
          Autonomous job application stats — powered by local AI
        </p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Total Applied
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-4xl font-bold">{totalApplied}</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Failed Attempts
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-4xl font-bold">{totalFailed}</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Success Rate
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-4xl font-bold">{successRate}%</p>
            </CardContent>
          </Card>
        </div>

        <p className="text-xs text-muted-foreground text-center">
          Company names and personal data are not displayed publicly.
        </p>
      </div>
    </main>
  );
}
