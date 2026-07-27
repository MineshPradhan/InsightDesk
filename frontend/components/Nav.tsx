"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";

const LINKS = [
  { href: "/", label: "Inbox" },
  { href: "/search", label: "Search" },
  { href: "/insights", label: "Insights" },
];

export default function Nav() {
  const path = usePathname();
  return (
    <header className="sticky top-0 z-30 border-b border-rule bg-paper/85 backdrop-blur">
      <div className="mx-auto flex max-w-[1440px] items-center gap-8 px-5 py-3">
        <Link href="/" className="board text-[17px] font-bold tracking-[0.06em]">
          Insight<span className="text-signal">Desk</span>
        </Link>
        <nav className="flex items-center gap-1">
          {LINKS.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className={clsx(
                "board px-3 py-1.5 text-[13px] font-semibold transition-colors",
                path === l.href
                  ? "bg-ink text-paper"
                  : "text-muted hover:text-ink"
              )}
            >
              {l.label}
            </Link>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-2 font-mono text-[11px] text-muted">
          <span className="relative flex h-1.5 w-1.5">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-ok opacity-60" />
            <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-ok" />
          </span>
          worker online
        </div>
      </div>
    </header>
  );
}
