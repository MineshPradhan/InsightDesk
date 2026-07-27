"use client";

import { useState } from "react";
import clsx from "clsx";
import useSWR from "swr";
import { fetcher, patch, post } from "@/lib/api";
import type { Ticket } from "@/lib/types";

function Meter({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex-1">
      <div className="flex justify-between font-mono text-[10px] uppercase text-muted">
        <span>{label}</span>
        <span>{(value * 100).toFixed(0)}%</span>
      </div>
      <div className="mt-1 h-1 w-full bg-rule">
        <div
          className={clsx("h-full transition-[width] duration-700", value > 0.7 ? "bg-ok" : "bg-high")}
          style={{ width: `${value * 100}%` }}
        />
      </div>
    </div>
  );
}

export default function TicketDetail({ id }: { id: string }) {
  const { data: ticket, mutate } = useSWR<Ticket>(`/tickets/${id}/`, fetcher);
  const [busy, setBusy] = useState<string | null>(null);

  if (!ticket) {
    return <div className="card h-full animate-pulse" aria-busy />;
  }

  const triage = ticket.latest_triage;
  const draft = ticket.drafts?.[0];

  async function rate(accepted: boolean) {
    setBusy("triage");
    await post(`/tickets/${id}/triage/feedback`, { accepted });
    await mutate();
    setBusy(null);
  }

  async function requestDraft() {
    setBusy("draft");
    await post(`/tickets/${id}/draft/`);
    setTimeout(() => mutate().then(() => setBusy(null)), 2500);
  }

  return (
    <article className="card flex h-full flex-col overflow-y-auto">
      <header className="border-b border-rule px-5 py-4">
        <div className="flex items-baseline gap-2 font-mono text-[11px] text-muted">
          <span>{ticket.external_id}</span>
          <span>·</span>
          <span>{ticket.channel}</span>
          <span>·</span>
          <span className="uppercase">{ticket.language}</span>
        </div>
        <h1 className="mt-1.5 text-[19px] font-semibold leading-tight">{ticket.subject}</h1>
        {ticket.tags && ticket.tags.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {ticket.tags.map((tag) => (
              <span key={tag} className="border border-rule px-1.5 font-mono text-[10px] text-muted">
                {tag}
              </span>
            ))}
          </div>
        )}
      </header>

      <div className="whitespace-pre-wrap border-b border-rule px-5 py-4 text-[14px] leading-relaxed">
        {ticket.body}
      </div>

      {/* --- Triage --------------------------------------------------- */}
      <section className="border-b border-rule px-5 py-4">
        <div className="flex items-center justify-between">
          <h2 className="eyebrow">Model triage</h2>
          {triage && (
            <span className="font-mono text-[10px] text-muted">
              {triage.model_version} · {triage.latency_ms}ms
            </span>
          )}
        </div>

        {triage ? (
          <>
            <div className="mt-3 flex items-baseline gap-4">
              <span className="board text-[15px] font-semibold">
                {triage.predicted_queue.replace(/_/g, " ")}
              </span>
              <span
                className={clsx(
                  "board px-1.5 py-0.5 text-[11px] font-semibold text-white",
                  {
                    critical: "bg-critical",
                    high: "bg-high",
                    medium: "bg-medium",
                    low: "bg-low",
                  }[triage.predicted_priority]
                )}
              >
                {triage.predicted_priority}
              </span>
              <span className="ml-auto font-mono text-[11px] text-muted">
                sentiment {triage.sentiment > 0 ? "+" : ""}
                {triage.sentiment.toFixed(2)}
              </span>
            </div>

            <div className="mt-3 flex gap-4">
              <Meter label="queue confidence" value={triage.queue_confidence} />
              <Meter label="priority confidence" value={triage.priority_confidence} />
            </div>

            <div className="mt-3 flex gap-2">
              <button
                onClick={() => rate(true)}
                disabled={busy === "triage"}
                className="board bg-ink px-3 py-1.5 text-[12px] font-semibold text-paper disabled:opacity-40"
              >
                Accept routing
              </button>
              <button
                onClick={() => rate(false)}
                disabled={busy === "triage"}
                className="board border border-rule px-3 py-1.5 text-[12px] font-semibold disabled:opacity-40"
              >
                Reroute
              </button>
              {triage.accepted_by_agent !== null && (
                <span className="self-center font-mono text-[10px] uppercase text-ok">
                  feedback recorded
                </span>
              )}
            </div>
          </>
        ) : (
          <p className="mt-2 text-[13px] text-muted">
            Not triaged yet. The worker picks this up within a few seconds of arrival.
          </p>
        )}
      </section>

      {/* --- Grounded draft ------------------------------------------- */}
      <section className="px-5 py-4">
        <div className="flex items-center justify-between">
          <h2 className="eyebrow">Suggested reply</h2>
          <button
            onClick={requestDraft}
            disabled={busy === "draft"}
            className="board border border-signal px-2.5 py-1 text-[11px] font-semibold text-signal disabled:opacity-40"
          >
            {busy === "draft" ? "Drafting…" : "Draft from knowledge base"}
          </button>
        </div>

        {draft ? (
          <>
            {!draft.grounded && (
              <p className="mt-3 border-l-[3px] border-l-high bg-high/5 px-3 py-2 text-[13px]">
                No knowledge-base passage covers this. Handle manually, and consider writing an
                article — this shape of question has no answer on file.
              </p>
            )}
            <p className="mt-3 whitespace-pre-wrap text-[14px] leading-relaxed">{draft.text}</p>

            <div className="mt-4">
              <h3 className="eyebrow">Sources</h3>
              <ol className="mt-2 space-y-1">
                {draft.citations.map((c) => (
                  <li key={c.n} className="flex items-baseline gap-2 text-[12px]">
                    <span className="font-mono text-signal">[{c.n}]</span>
                    <span className="font-medium">{c.title}</span>
                    <span className="ml-auto font-mono text-[10px] text-muted">
                      sim {c.similarity.toFixed(2)} · rerank {c.rerank_score.toFixed(2)}
                    </span>
                  </li>
                ))}
              </ol>
            </div>

            <div className="mt-4 flex items-center gap-2">
              <button
                onClick={() => patch(`/drafts/${draft.id}/`, { was_sent: true }).then(() => mutate())}
                className="board bg-signal px-3 py-1.5 text-[12px] font-semibold text-white"
              >
                Send as-is
              </button>
              <button className="board border border-rule px-3 py-1.5 text-[12px] font-semibold">
                Edit before sending
              </button>
              <span className="ml-auto font-mono text-[10px] text-muted">
                {draft.model} · {draft.latency_ms}ms
              </span>
            </div>
          </>
        ) : (
          <p className="mt-2 text-[13px] text-muted">
            No draft yet. Generating one retrieves the five closest knowledge-base passages and
            answers only from those.
          </p>
        )}
      </section>
    </article>
  );
}
