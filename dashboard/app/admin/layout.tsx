import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";

export default async function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();

  if (!user) redirect("/login");

  async function signOut() {
    "use server";
    const supabase = await createClient();
    await supabase.auth.signOut();
    redirect("/login");
  }

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-6">
            <span className="font-bold">Agentic Job Hunter</span>
            <nav className="flex gap-4 text-sm">
              <Link href="/admin" className="text-muted-foreground hover:text-foreground">
                Applications
              </Link>
              <Link href="/admin/search" className="text-muted-foreground hover:text-foreground">
                New Search
              </Link>
              <Link href="/admin/emails" className="text-muted-foreground hover:text-foreground">
                Emails
              </Link>
              <Link href="/" className="text-muted-foreground hover:text-foreground">
                Public View
              </Link>
            </nav>
          </div>
          <form action={signOut}>
            <Button variant="outline" size="sm" type="submit">
              Sign out
            </Button>
          </form>
        </div>
      </header>
      <main className="max-w-6xl mx-auto px-6 py-8">{children}</main>
    </div>
  );
}
