import { Badge } from "@/components/ui/badge";
import { titleCase, toneOf } from "@/lib/format";

export function StatusBadge({ status }: { status: string }) {
  return <Badge tone={toneOf(status)}>{titleCase(status)}</Badge>;
}
