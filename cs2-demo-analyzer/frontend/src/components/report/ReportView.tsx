"use client";

import Link from "next/link";
import { useState } from "react";

import { t } from "@/i18n";
import type { ReportResponse } from "@/lib/api";

import { Card, cx, fmtPct } from "../ui";
import { CounterstrafeTab } from "./CounterstrafeTab";
import { EloCard } from "./EloCard";
import { DuelsTab } from "./DuelsTab";
import { RecommendationsTab } from "./RecommendationsTab";
import { WorstMoments } from "./WorstMoments";

type Tab = "counterstrafe" | "duels" | "recommendations";
const TABS: Tab[] = ["counterstrafe", "duels", "recommendations"];

function PerfectRing({ value }: { value: number | null }) {
  const r = 52;
  const c = 2 * Math.PI * r;
  const v = value ?? 0;
  return (
    <svg width="132" height="132" viewBox="0 0 132 132" aria-hidden>
      <circle cx="66" cy="66" r={r} fill="none" stroke="#1f232b" strokeWidth="12" />
      <circle
        cx="66"
        cy="66"
        r={r}
        fill="none"
        stroke="url(#ring)"
        strokeWidth="12"
        strokeLinecap="round"
        strokeDasharray={`${(c * v) / 100} ${c}`}
        transform="rotate(-90 66 66)"
      />
      <defs>
        <linearGradient id="ring" x1="0" x2="1">
          <stop offset="0%" stopColor="#ff7a1a" />
          <stop offset="100%" stopColor="#ffb547" />
        </linearGradient>
      </defs>
    </svg>
  );
}

export function ReportView({ data }: { data: ReportResponse }) {
  const r = data.report;
  const [tab, setTab] = useState<Tab>("counterstrafe");
  const [copied, setCopied] = useState(false);
  const rating = r.rating;

  async function share() {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* нет доступа к буферу обмена */
    }
  }

  return (
    <div className="space-y-6">
      {/* Шапка */}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
          <div className="label-caps">
            {r.match.map} · {r.match.score.t}:{r.match.score.ct} · {t("report.rounds", { n: r.overview.rounds })}
          </div>
          <h1 className="mt-1 truncate text-3xl font-black tracking-wide">{r.player.name}</h1>
          <div className="mt-1 text-sm text-ink-2 tabular">
            {r.overview.kills}–{r.overview.deaths} · ADR {r.overview.adr.toFixed(0)} · HS {fmtPct(r.overview.hs_pct)}
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <select
            aria-label={t("report.other")}
            className="rounded-md border border-line bg-surface px-3 py-2 text-sm text-ink-2"
            value={data.id}
            onChange={(e) => (window.location.href = `/r/${e.target.value}`)}
          >
            {data.players.map((p) => (
              <option key={p.steamid} value={p.report_id}>
                {p.name}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={share}
            className="rounded-md bg-accent px-4 py-2 text-sm font-bold uppercase tracking-wider text-black hover:bg-accent-2"
          >
            {copied ? `✓ ${t("report.copied")}` : t("report.share")}
          </button>
        </div>
      </div>

      {/* Главное */}
      <div className="grid gap-5 lg:grid-cols-[1fr_1fr_1.4fr]">
        <Card className="flex items-center gap-5">
          <div className="relative">
            <PerfectRing value={r.counterstrafe.perfect_pct} />
            <div className="absolute inset-0 grid place-items-center text-3xl font-black tabular">
              {fmtPct(r.counterstrafe.perfect_pct)}
            </div>
          </div>
          <div>
            <div className="label-caps">{t("report.perfect")}</div>
            <div className="mt-1 text-sm text-ink-2">{t("report.perfect.hint", { n: r.counterstrafe.strafe_shots })}</div>
          </div>
        </Card>

        <EloCard reportId={data.id} rating={rating} initial={r.faceit} />

        <Card>
          <div className="label-caps mb-3">{t("report.top")}</div>
          {r.recommendations.top.length ? (
            <div className="space-y-2">
              {r.recommendations.top.map((rec, i) => (
                <div key={`${rec.id}-${i}`} className="flex gap-3">
                  <span className="mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-full bg-accent text-xs font-black text-black">
                    {i + 1}
                  </span>
                  <div>
                    <div className="text-sm font-bold">{rec.title}</div>
                    <div className="line-clamp-2 text-xs text-ink-2">{rec.text}</div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted">{t("report.top.empty")}</p>
          )}
        </Card>
      </div>

      {/* Вкладки */}
      <div>
        <div role="tablist" className="mb-5 flex gap-1 overflow-x-auto border-b border-line">
          {TABS.map((id) => (
            <button
              key={id}
              role="tab"
              aria-selected={tab === id}
              type="button"
              onClick={() => setTab(id)}
              className={cx(
                "-mb-px whitespace-nowrap border-b-2 px-4 py-2.5 text-sm font-bold uppercase tracking-wider transition",
                tab === id ? "border-accent text-accent" : "border-transparent text-muted hover:text-ink",
              )}
            >
              {t(`report.tab.${id}`)}
              {id === "recommendations" ? (
                <span className="ml-2 rounded bg-surface-2 px-1.5 text-xs text-ink-2">{r.recommendations.items.length}</span>
              ) : null}
            </button>
          ))}
        </div>
        <div role="tabpanel">
          {tab === "counterstrafe" && (
            <CounterstrafeTab cs={r.counterstrafe} accuracyRatio={r.counterstrafe.accuracy_speed_ratio ?? 0.34} />
          )}
          {tab === "duels" && <DuelsTab report={r} />}
          {tab === "recommendations" && (
            <RecommendationsTab improve={r.recommendations.improve} stop={r.recommendations.stop} />
          )}
        </div>
      </div>

      <WorstMoments report={r} />

      <div className="text-center">
        <Link href={`/m/${data.match_id}`} className="text-sm text-muted underline-offset-4 hover:text-accent hover:underline">
          ← {t("report.other")}
        </Link>
      </div>
    </div>
  );
}

