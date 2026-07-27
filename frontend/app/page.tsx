"use client";

import { useMemo, useState } from "react";
import useSWR from "swr";
import clsx from "clsx";
import { fetcher } from "@/lib/api";
import TicketDetail from "@/components/TicketDetail";
import TicketList from "@/components/TicketList";
import TriageStream from "@/components/TriageStream";
import type { Ticket } from "@/lib/types";

const FILTERS = ["all", "critical", "high", "untriaged"] as const;
type Filter = (typeof FILTERS)[number];

export default function InboxPage() {
  const [filter, setFilter] = useState<Filter>("all");
  const [activeId, setActiveId] = useState<string>();

  const query =
    filter === "untriaged" ? "?untriaged=true&limit=60" : filter === "all" ? "?limit=60" : `?priority=${filter}&limit=60`;

  const { data, isLoading, error } = useSWR<{ results: Ticket[]; count: number }>(
    `/tickets/${query}`,
    fetcher,
    { refreshInterval: 15000 }
  );

  const tickets = useMemo(() => data?.results ?? [], [data]);
  const selected = activeId ?? tickets[0]?.id;

  return (
    <div className="pt-4">
      <div className="mb-3 flex items-end justify-between">
        <div>
          <h1 className="board text-[22px] font-bold">Inbox</h1>
          <p className="mt-0.5 text-[13px] text-muted">
            Routed on arrival. Confidence below 70% waits for you.
          </p>
        </div>
        <div className="flex gap-1">
          {FILTERS.map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={clsx(
                "board border px-2.5 py-1 text-[11px] font-semibold capitalize",
                filter === f ? "border-ink bg-ink text-paper" : "border-rule text-muted hover:text-ink"
              )}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <p className="card border-l-[3px] border-l-critical px-4 py-3 text-[13px]">
          The API did not respond. Check that <code className="font-mono">api</code> is running on
          port 8000, then reload.
        </p>
      )}

      <TriageStream tickets={tickets} activeId={selected} onSelect={setActiveId} />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,420px)_minmax(0,1fr)]">
        <div className="max-h-[calc(100vh-260px)] overflow-y-auto pr-1">
          {isLoading ? (
            <div className="space-y-1.5">
              {Array.from({ length: 8 }).map((_, i) => (
                <div key={i} className="card h-[76px] animate-pulse" />
              ))}
            </div>
          ) : (
            <TicketList tickets={tickets} activeId={selected} onSelect={setActiveId} />
          )}
        </div>
        <div className="max-h-[calc(100vh-260px)]">
          {selected ? (
            <TicketDetail id={selected} />
          ) : (
            <div className="card grid h-full place-items-center text-[13px] text-muted">
              Pick a ticket to see its routing and draft.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
