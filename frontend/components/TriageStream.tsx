"use client";

import clsx from "clsx";
import type { Priority, Ticket } from "@/lib/types";

const BAR: Record<Priority | "", string> = {
  critical: "bg-critical",
  high: "bg-high",
  medium: "bg-medium",
  low: "bg-low",
  "": "bg-rule",
};

/**
 * The signature element: every ticket in the window as one tick, left to right
 * by arrival. Height is the model's confidence, colour is predicted priority.
 * A wall of short red ticks means the model is guessing on urgent work — which
 * is exactly the thing a support lead needs to see before it becomes a backlog.
 */
export default function TriageStream({
  tickets,
  activeId,
  onSelect,
}: {
  tickets: Ticket[];
  activeId?: string;
  onSelect: (id: string) => void;
}) {
  return (
    <section className="card mb-4 px-4 pb-3 pt-3">
      <div className="mb-2.5 flex items-baseline justify-between">
        <h2 className="eyebrow">Triage stream · last {tickets.length} arrivals</h2>
        <div className="flex gap-3 font-mono text-[10px] uppercase text-muted">
          {(["critical", "high", "medium", "low"] as Priority[]).map((p) => (
            <span key={p} className="flex items-center gap-1.5">
              <i className={clsx("h-2 w-[3px]", BAR[p])} />
              {p}
            </span>
          ))}
        </div>
      </div>

      <div className="flex h-16 items-end gap-[3px] overflow-hidden">
        {tickets.map((t, i) => {
          const p = (t.latest_triage?.predicted_priority ?? t.priority) as Priority | "";
          const confidence = t.latest_triage?.queue_confidence ?? 0.4;
          return (
            <button
              key={t.id}
              onClick={() => onSelect(t.id)}
              title={`${t.external_id} · ${p || "untriaged"} · ${(confidence * 100).toFixed(0)}% confident`}
              style={{
                height: `${28 + confidence * 72}%`,
                animationDelay: `${Math.min(i * 8, 600)}ms`,
              }}
              className={clsx(
                "w-[6px] shrink-0 origin-bottom animate-tick rounded-[1px] transition-all hover:w-[10px]",
                BAR[p],
                activeId === t.id ? "w-[10px] ring-2 ring-ink ring-offset-1" : "opacity-80"
              )}
            >
              <span className="sr-only">{t.subject}</span>
            </button>
          );
        })}
      </div>
    </section>
  );
}
