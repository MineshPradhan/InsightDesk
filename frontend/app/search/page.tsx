"use client";

import { useState } from "react";
import useSWR from "swr";
import clsx from "clsx";
import { fetcher } from "@/lib/api";

interface Result {
  id: string;
  score: number;
  text: string;
  meta: Record<string, string | number | null>;
}

export default function SearchPage() {
  const [input, setInput] = useState("");
  const [query, setQuery] = useState("");
  const [scope, setScope] = useState<"tickets" | "kb">("tickets");

  const { data, isLoading } = useSWR<{ results: Result[]; count: number }>(
    query ? `/search/?q=${encodeURIComponent(query)}&scope=${scope}` : null,
    fetcher
  );

  return (
    <div className="pt-4">
      <h1 className="board text-[22px] font-bold">Search</h1>
      <p className="mt-0.5 text-[13px] text-muted">
        Meaning first, keywords as a safety net — order numbers and error codes still match exactly.
      </p>

      <div className="mt-4 flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && setQuery(input)}
          placeholder="refund never arrived after cancelling"
          className="card flex-1 px-3 py-2.5 text-[14px] placeholder:text-muted"
        />
        <div className="flex">
          {(["tickets", "kb"] as const).map((s) => (
            <button
              key={s}
              onClick={() => setScope(s)}
              className={clsx(
                "board border px-3 text-[12px] font-semibold uppercase",
                scope === s ? "border-ink bg-ink text-paper" : "border-rule text-muted"
              )}
            >
              {s}
            </button>
          ))}
        </div>
        <button
          onClick={() => setQuery(input)}
          className="board bg-signal px-5 text-[12px] font-semibold text-white"
        >
          Search
        </button>
      </div>

      {isLoading && <p className="mt-6 font-mono text-[12px] text-muted">Searching…</p>}

      {data && (
        <>
          <p className="mt-6 eyebrow">
            {data.count} matches · {scope}
          </p>
          <ul className="mt-2 space-y-1.5">
            {data.results.map((r) => (
              <li key={r.id} className="card px-4 py-3">
                <div className="flex items-baseline gap-3">
                  <span className="font-mono text-[11px] text-signal">
                    {(r.score * 100).toFixed(0)}
                  </span>
                  <p className="flex-1 text-[14px] font-medium">{r.text.slice(0, 220)}</p>
                </div>
                <div className="mt-1.5 flex gap-3 font-mono text-[10px] uppercase text-muted">
                  {Object.entries(r.meta)
                    .filter(([, v]) => v !== null && v !== "")
                    .slice(0, 4)
                    .map(([k, v]) => (
                      <span key={k}>
                        {k}: {String(v)}
                      </span>
                    ))}
                </div>
              </li>
            ))}
          </ul>
        </>
      )}

      {data && data.count === 0 && (
        <p className="mt-6 card px-4 py-6 text-center text-[13px] text-muted">
          Nothing matched. Try describing the customer&apos;s problem in their words.
        </p>
      )}
    </div>
  );
}
