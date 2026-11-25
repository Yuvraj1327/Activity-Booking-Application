"use client";

import dynamic from "next/dynamic";

/**
 * Recharts is ~400 KB. Loading it lazily lets the page shell, stat cards and tables paint first;
 * the charts fill in as soon as the chunk arrives. The placeholder reserves the exact chart
 * height, so nothing shifts when the chart appears.
 */
function Placeholder({ height = 280 }: { height?: number }) {
  return <div className="animate-pulse rounded-lg bg-muted/60" style={{ height }} role="status" aria-label="Loading chart" />;
}

export const TrendChart = dynamic(() => import("./charts-impl").then((m) => m.TrendChart), { ssr: false, loading: () => <Placeholder /> });
export const DonutChart = dynamic(() => import("./charts-impl").then((m) => m.DonutChart), { ssr: false, loading: () => <Placeholder /> });
export const HBarChart = dynamic(() => import("./charts-impl").then((m) => m.HBarChart), { ssr: false, loading: () => <Placeholder /> });

export type { Series } from "./charts-impl";
