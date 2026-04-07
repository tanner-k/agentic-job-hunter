import { createClient } from "@/lib/supabase/server";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

const SENTIMENT_VARIANT: Record<
  string,
  "default" | "destructive" | "secondary" | "outline"
> = {
  interest: "default",
  rejection: "destructive",
  spam: "secondary",
};

export default async function EmailLogsPage() {
  const supabase = await createClient();
  const { data: logs } = await supabase
    .from("email_logs")
    .select("*")
    .order("received_at", { ascending: false })
    .limit(100);

  const rows = logs ?? [];

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Email Logs</h1>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">
            {rows.length} email{rows.length !== 1 ? "s" : ""} processed
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Sender</TableHead>
                <TableHead>Subject</TableHead>
                <TableHead>Sentiment</TableHead>
                <TableHead>Summary</TableHead>
                <TableHead>Received</TableHead>
                <TableHead>Draft</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.length === 0 ? (
                <TableRow>
                  <TableCell
                    colSpan={6}
                    className="text-center text-muted-foreground py-8"
                  >
                    No emails processed yet. Configure Gmail to begin.
                  </TableCell>
                </TableRow>
              ) : (
                rows.map((log) => (
                  <TableRow key={log.id}>
                    <TableCell className="text-sm">{log.sender}</TableCell>
                    <TableCell className="font-medium">{log.subject}</TableCell>
                    <TableCell>
                      <Badge
                        variant={SENTIMENT_VARIANT[log.sentiment] ?? "outline"}
                      >
                        {log.sentiment}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground max-w-xs truncate">
                      {log.summary}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {new Date(log.received_at).toLocaleDateString()}
                    </TableCell>
                    <TableCell>
                      {log.draft_link ? (
                        <a
                          href={log.draft_link}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-sm underline text-muted-foreground hover:text-foreground"
                        >
                          View
                        </a>
                      ) : (
                        <span className="text-sm text-muted-foreground">—</span>
                      )}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
