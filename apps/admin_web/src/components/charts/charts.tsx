"use client";

import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";

const C = ["var(--chart-1)", "var(--chart-2)", "var(--chart-3)", "var(--chart-4)", "var(--chart-5)", "var(--chart-6)"];
const axis = { fontSize: 12, fill: "var(--muted-foreground)" } as const;

export type Series = { key: string; label: string; color?: number };

function Box({ title, empty, children, height = 280 }: { title: string; empty: boolean; children: React.ReactElement; height?: number }) {
  return (
    <figure className="m-0" aria-label={title} data-testid="chart">
      <figcaption className="sr-only">{title}</figcaption>
      {empty ? (
        <div className="flex items-center justify-center text-sm text-muted-foreground" style={{ height }} data-testid="chart-empty">
          No data in this period.
        </div>
      ) : (
        <div style={{ height }}>
          <ResponsiveContainer width="100%" height="100%" minWidth={0}>
            {children}
          </ResponsiveContainer>
        </div>
      )}
    </figure>
  );
}

type Row = Record<string, string | number>;

export function TrendChart({
  title, data, series, kind = "area", valueFormat,
}: { title: string; data: Row[]; series: Series[]; kind?: "area" | "line" | "bar"; valueFormat?: "money" }) {
  const empty = data.every((d) => series.every((s) => !Number(d[s.key])));
  const fmt = (v: number) => (valueFormat === "money" ? `₹${(v / 100).toLocaleString("en-IN", { maximumFractionDigits: 0 })}` : String(v));
  const common = { data, margin: { top: 8, right: 8, bottom: 0, left: 0 } };
  const grid = <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />;
  const xy = (
    <>
      <XAxis dataKey="label" tick={axis} tickLine={false} axisLine={false} minTickGap={16} />
      <YAxis tick={axis} tickLine={false} axisLine={false} allowDecimals={false} width={48} tickFormatter={fmt} />
      <Tooltip formatter={(v) => fmt(Number(v))} contentStyle={{ borderRadius: 8, borderColor: "var(--border)", backgroundColor: "var(--card)", color: "var(--foreground)" }} />
      {series.length > 1 && <Legend formatter={(v) => <span style={{ color: "var(--muted-foreground)" }}>{v}</span>} />}
    </>
  );
  return (
    <Box title={title} empty={empty}>
      {kind === "bar" ? (
        <BarChart {...common}>{grid}{xy}{series.map((s, i) => <Bar key={s.key} dataKey={s.key} name={s.label} fill={C[s.color ?? i]} stackId={series.length > 1 ? "a" : undefined} maxBarSize={28} />)}</BarChart>
      ) : kind === "line" ? (
        <LineChart {...common}>{grid}{xy}{series.map((s, i) => <Line key={s.key} type="monotone" dataKey={s.key} name={s.label} stroke={C[s.color ?? i]} strokeWidth={2} dot={false} />)}</LineChart>
      ) : (
        <AreaChart {...common}>{grid}{xy}{series.map((s, i) => <Area key={s.key} type="monotone" dataKey={s.key} name={s.label} stroke={C[s.color ?? i]} fill={C[s.color ?? i]} fillOpacity={0.15} strokeWidth={2} />)}</AreaChart>
      )}
    </Box>
  );
}

export function DonutChart({ title, data }: { title: string; data: { name: string; value: number }[] }) {
  const total = data.reduce((a, d) => a + d.value, 0);
  return (
    <Box title={title} empty={total === 0}>
      <PieChart>
        <Pie data={data} dataKey="value" nameKey="name" cy="42%" innerRadius={56} outerRadius={86} paddingAngle={2}>
          {data.map((d, i) => <Cell key={d.name} fill={C[i % C.length]} />)}
        </Pie>
        <Tooltip contentStyle={{ borderRadius: 8, borderColor: "var(--border)", backgroundColor: "var(--card)", color: "var(--foreground)" }} />
        <Legend formatter={(v) => <span style={{ color: "var(--muted-foreground)" }}>{v}</span>} />
      </PieChart>
    </Box>
  );
}

export function HBarChart({ title, data, color = 0 }: { title: string; data: { name: string; value: number }[]; color?: number }) {
  return (
    <Box title={title} empty={data.length === 0} height={Math.max(200, data.length * 36 + 40)}>
      <BarChart data={data} layout="vertical" margin={{ top: 4, right: 16, bottom: 0, left: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" horizontal={false} />
        <XAxis type="number" tick={axis} tickLine={false} axisLine={false} allowDecimals={false} />
        <YAxis type="category" dataKey="name" tick={axis} tickLine={false} axisLine={false} width={120} />
        <Tooltip contentStyle={{ borderRadius: 8, borderColor: "var(--border)", backgroundColor: "var(--card)", color: "var(--foreground)" }} />
        <Bar dataKey="value" fill={C[color]} radius={[0, 4, 4, 0]} />
      </BarChart>
    </Box>
  );
}
