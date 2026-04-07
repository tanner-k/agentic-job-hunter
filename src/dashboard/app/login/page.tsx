import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default async function LoginPage() {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();

  if (user) redirect("/admin");

  async function signInWithGitHub() {
    "use server";
    const supabase = await createClient();
    const { data, error } = await supabase.auth.signInWithOAuth({
      provider: "github",
      options: {
        redirectTo: `${process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000"}/auth/callback`,
      },
    });
    if (data.url) redirect(data.url);
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <Card className="w-full max-w-sm">
        <CardHeader className="text-center">
          <CardTitle className="text-2xl">Agentic Job Hunter</CardTitle>
          <CardDescription>Sign in to manage your job search</CardDescription>
        </CardHeader>
        <CardContent>
          <form action={signInWithGitHub}>
            <Button type="submit" className="w-full">
              Sign in with GitHub
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
