"use client";

import clsx from "clsx";
import { formatDistanceToNowStrict } from "date-fns";
import type { Ticket } from "@/lib/types";

const FLAG: Record<string, string> = {
  critical: "flag-critical",
  high: "flag-high",
  medium: "flag-medium",
  low: "flag-low",
  "": "border-l border-l-rule",
};

const QUEUE_LABEL = (q: string) =>
  q ? q.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()) : "Unassigned";

export default function TicketList({
  tickets,
  activeId,
  onSelect,
}: {
  tickets: Ticket[];
  activeId?: string;
  onSelect: (id: string) => void;
}) {
  if (tickets.length === 0) {
    return (
      <div className="card flex h-full flex-col items-center justify-center gap-2 p-10 text-center">
        <p className="board text-sm">Queue is clear</p>
        <p className="text-[13px] text-muted">
          Nothing matches these filters. Widen the window or clear a filter to see more.
        </p>
      </div>
    );
  }

  return (
    <ul className="flex flex-col gap-1.5">
      {tickets.map((t, i) => {
        const p = t.latest_triage?.predicted_priority ?? t.priority;
        const predicted = !t.priority && t.latest_triage;
        return (
          <li key={t.id} style={{ animationDelay: `${i * 18}ms` }} className="animate-slide">
            <button
              onClick={() => onSelect(t.id)}
              className={clsx(
                "card w-full px-3 py-2.5 text-left transition-all hover:shadow-lift",
                FLAG[p ?? ""],
                activeId === t.id && "bg-signal-wash shadow-lift"
              )}
            >
              <div className="flex items-baseline gap-2">
                <span className="font-mono text-[11px] text-muted">{t.external_id}</span>
                <span className="board text-[10px] tracking-[0.12em] text-muted">
                  {QUEUE_LABEL(t.queue)}
                </span>
                {predicted && (
                  <span className="rounded-[2px] bg-signal-wash px-1 font-mono text-[9px] uppercase text-signal">
                    predicted
                  </span>
                )}
                <span className="ml-auto font-mono text-[11px] text-muted">
                  {formatDistanceToNowStrict(new Date(t.received_at))} ago
                </span>
              </div>
              <p className="mt-1 line-clamp-1 text-[14px] font-medium leading-snug">{t.subject}</p>
              <div className="mt-1.5 flex items-center gap-3 font-mono text-[10px] uppercase text-muted">
                <span>{p || "untriaged"}</span>
                <span>·</span>
                <span>{t.status.replace(/_/g, " ")}</span>
                {t.latest_triage && (
                  <>
                    <span>·</span>
                    <span>{(t.latest_triage.queue_confidence * 100).toFixed(0)}% conf</span>
                    <span>·</span>
                    <span>{t.latest_triage.latency_ms}ms</span>
                  </>
                )}
              </div>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
