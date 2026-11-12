import type { Metadata } from "next";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export const metadata: Metadata = { title: "Dashboard" };

export default function DashboardPage() {
  return (
    <div className="mx-auto max-w-5xl">
      <h2 className="text-2xl font-semibold">Dashboard</h2>
      <p className="mt-1 text-sm text-muted-foreground">Discover. Book. Play.</p>
      <Card className="mt-6">
        <CardHeader>
          <CardTitle>Admin console foundation</CardTitle>
          <CardDescription>Placeholder. No data or admin features exist yet.</CardDescription>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          You are signed in as a verified administrator. Admin modules and analytics arrive in Step 8.
        </CardContent>
      </Card>
    </div>
  );
}
