import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { ApiVersion } from "@/lib/types";

export type PlatformInfo = { api: ApiVersion | null; environment: string | null; database: string | null };

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-wrap items-baseline justify-between gap-2 py-3">
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className="text-sm font-medium">{value}</dd>
    </div>
  );
}

export function AboutSection({ platform, apiHost }: { platform: PlatformInfo; apiHost: string }) {
  const unavailable = "Unavailable";
  return (
    <Card>
      <CardHeader>
        <CardTitle>About ZURUV</CardTitle>
        <CardDescription>Version and platform information. Include it when contacting support.</CardDescription>
      </CardHeader>
      <CardContent>
        <dl className="divide-y divide-border">
          <Row label="Product" value="ZURUV Admin Console" />
          <Row label="Admin console version" value={process.env.NEXT_PUBLIC_APP_VERSION ?? unavailable} />
          <Row label="API version" value={platform.api ? `${platform.api.version} (${platform.api.api_version})` : unavailable} />
          <Row label="Environment" value={platform.environment ?? unavailable} />
          <Row label="Database" value={platform.database ?? unavailable} />
          <Row label="API host" value={apiHost || unavailable} />
        </dl>
      </CardContent>
    </Card>
  );
}
