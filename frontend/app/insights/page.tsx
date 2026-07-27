"use client";

import useSWR from "swr";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { fetcher } from "@/lib/api";
import type { Overview } from "@/lib/types";

const PRIORITY_COLOR: Record<string, string> = {
  critical: "#C31F45",
  high: "#D2760B",
  medium: "#3E7CB1",
  low: "#7C8698",
};

function Stat({ label, value, unit, note }: { label: string; value: string | number; unit?: string; note?: string }) {
  return (
    <div className="card px-4 py-3">
      <p className="eyebrow">{label}</p>
      <p className="mt-1.5 font-board text-[28px] font-bold leading-none">
        {value}
        {unit && <span className="ml-1 font-mono text-[12px] font-normal text-muted">{unit}</span>}
      </p>
      {note && <p className="mt-1 font-mono text-[10px] text-muted">{note}</p>}
    </div>
  );
}

export default function InsightsPage() {
  const { data: o } = useSWR<Overview>("/analytics/overview/?days=30", fetcher);
  const { data: volume } = useSWR<{ day: string; total: number; critical: number; resolved: number }[]>(
    "/analytics/volume/?days=30",
    fetcher
  );
  const { data: queues } = useSWR<{ queue: string; count: number; avg_csat: number }[]>(
    "/analytics/queues/?days=30",
    fetcher
  );
  const { data: priorities } = useSWR<{ priority: string; count: number }[]>(
    "/analytics/priorities/?days=30",
    fetcher
  );

  return (
    <div className="pt-4">
      <h1 className="board text-[22px] font-bold">Insights</h1>
      <p className="mt-0.5 text-[13px] text-muted">Rolling 30 days. Refreshed every five minutes.</p>

      <div className="mt-4 grid grid-cols-2 gap-2 md:grid-cols-3 xl:grid-cols-6">
        <Stat label="Tickets" value={o?.tickets ?? "—"} />
        <Stat label="Open" value={o?.open ?? "—"} note={`${o?.backlog_critical ?? 0} critical`} />
        <Stat label="Median resolution" value={o?.median_resolution_minutes ?? "—"} unit="min" />
        <Stat label="Routing accuracy" value={o ? (o.triage_accuracy * 100).toFixed(1) : "—"} unit="%" note={`p50 ${o?.triage_p50_latency_ms ?? 0}ms`} />
        <Stat label="Drafts grounded" value={o?.drafts_grounded_pct ?? "—"} unit="%" note={`${o?.drafts_generated ?? 0} generated`} />
        <Stat label="Avg CSAT" value={o?.avg_csat ?? "—"} unit="/5" />
      </div>

      <div className="mt-3 grid grid-cols-1 gap-3 xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <section className="card px-4 pb-3 pt-3">
          <h2 className="eyebrow">Arrivals vs resolutions</h2>
          <ResponsiveContainer width="100%" height={230}>
            <AreaChart data={volume ?? []} margin={{ top: 12, right: 4, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="g1" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#2A3FD4" stopOpacity={0.28} />
                  <stop offset="100%" stopColor="#2A3FD4" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="#CFD5E2" strokeDasharray="2 4" vertical={false} />
              <XAxis dataKey="day" tick={{ fontSize: 10, fontFamily: "IBM Plex Mono" }} tickLine={false} />
              <YAxis tick={{ fontSize: 10, fontFamily: "IBM Plex Mono" }} tickLine={false} axisLine={false} />
              <Tooltip contentStyle={{ borderRadius: 3, border: "1px solid #CFD5E2", fontSize: 12 }} />
              <Area type="monotone" dataKey="total" stroke="#2A3FD4" strokeWidth={1.75} fill="url(#g1)" />
              <Area type="monotone" dataKey="resolved" stroke="#1B7F62" strokeWidth={1.25} fill="none" />
              <Area type="monotone" dataKey="critical" stroke="#C31F45" strokeWidth={1.25} fill="none" />
            </AreaChart>
          </ResponsiveContainer>
        </section>

        <section className="card px-4 pb-3 pt-3">
          <h2 className="eyebrow">Priority mix</h2>
          <ResponsiveContainer width="100%" height={230}>
            <BarChart data={priorities ?? []} layout="vertical" margin={{ top: 12, right: 12, left: 12, bottom: 0 }}>
              <XAxis type="number" hide />
              <YAxis
                type="category"
                dataKey="priority"
                width={64}
                tick={{ fontSize: 10, fontFamily: "IBM Plex Mono"}}
                tickLine={false}
                axisLine={false}
              />
              <Tooltip cursor={{ fill: "#EDF0FF" }} contentStyle={{ borderRadius: 3, fontSize: 12 }} />
              <Bar dataKey="count" radius={[0, 2, 2, 0]}>
                {(priorities ?? []).map((p) => (
                  <Cell key={p.priority} fill={PRIORITY_COLOR[p.priority] ?? "#7C8698"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </section>
      </div>

      <section className="card mt-3 px-4 py-3">
        <h2 className="eyebrow">Load by queue</h2>
        <table className="mt-2 w-full text-[13px]">
          <thead>
            <tr className="border-b border-rule text-left font-mono text-[10px] uppercase text-muted">
              <th className="pb-1.5 font-normal">Queue</th>
              <th className="pb-1.5 text-right font-normal">Tickets</th>
              <th className="pb-1.5 text-right font-normal">Critical</th>
              <th className="pb-1.5 text-right font-normal">CSAT</th>
            </tr>
          </thead>
          <tbody>
            {(queues ?? []).map((q) => (
              <tr key={q.queue} className="border-b border-rule/60 last:border-0">
                <td className="py-1.5 capitalize">{q.queue.replace(/_/g, " ")}</td>
                <td className="py-1.5 text-right font-mono">{q.count}</td>
                <td className="py-1.5 text-right font-mono">
                  {(q as { critical?: number }).critical ?? 0}
                </td>
                <td className="py-1.5 text-right font-mono">{q.avg_csat?.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
