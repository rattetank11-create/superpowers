"use client";

import { useState } from "react";

import { t } from "@/i18n";
import type { Report } from "@/lib/api";

import { Card, SectionTitle } from "../ui";

interface Moment {
  kind: "cs" | "duel" | "xhair";
  round: number | null;
  tick: number;
  roundTime?: number | null;
  text: string;
}

function collect(report: Report): Moment[] {
  const out: Moment[] = [];
  for (const s of report.counterstrafe.worst.slice(0, 5)) {
    out.push({
      kind: "cs",
      round: s.round,
      tick: s.tick,
      roundTime: s.round_time,
      text: `${s.weapon_name}: ${Math.round(s.speed)} u/s · ${t(`cat.${s.category}`)}`,
    });
  }
  for (const d of report.duels.worst.slice(0, 5)) {
    const parts = [`vs ${d.opponent_name}`];
    if (d.opening) parts.push("opening");
    if (d.shot_first) parts.push("стрелял первым");
    if (d.peeked && !d.flash_support) parts.push("пик без флешки");
    parts.push(`урон ${d.dmg_dealt}`);
    out.push({ kind: "duel", round: d.round, tick: Math.max(0, d.start_tick - 64), text: parts.join(" · ") });
  }
  for (const x of report.crosshair.worst.slice(0, 3)) {
    if (x.angle < 15) continue;
    out.push({ kind: "xhair", round: x.round, tick: x.tick, roundTime: x.round_time, text: `${x.enemy}: ${x.angle}°` });
  }
  return out.sort((a, b) => a.tick - b.tick);
}

const KIND_STYLE = {
  cs: "bg-cat-moving/15 text-cat-moving",
  duel: "bg-loss/15 text-loss",
  xhair: "bg-cat-air/15 text-cat-air",
} as const;

export function WorstMoments({ report }: { report: Report }) {
  const moments = collect(report);
  const [copied, setCopied] = useState<number | null>(null);
  if (!moments.length) return null;

  async function copy(tick: number) {
    try {
      await navigator.clipboard.writeText(`demo_gototick ${tick}`);
      setCopied(tick);
      setTimeout(() => setCopied(null), 1500);
    } catch {
      /* clipboard недоступен — команда всё равно видна */
    }
  }

  return (
    <Card>
      <SectionTitle>{t("report.worst")}</SectionTitle>
      <p className="-mt-2 mb-4 text-xs text-muted">{t("report.worst.hint")}</p>
      <ul className="divide-y divide-line">
        {moments.map((m, i) => (
          <li key={`${m.kind}-${m.tick}-${i}`} className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2.5 text-sm">
            <span className={`rounded px-1.5 py-0.5 text-[0.62rem] font-bold uppercase tracking-wider ${KIND_STYLE[m.kind]}`}>
              {t(`worst.${m.kind}`)}
            </span>
            <span className="tabular text-ink-2">
              {t("common.round")} {m.round ?? "?"}
              {m.roundTime !== undefined && m.roundTime !== null ? ` · ${m.roundTime.toFixed(0)} с` : ""}
            </span>
            <span className="min-w-0 flex-1 truncate">{m.text}</span>
            <button
              type="button"
              onClick={() => copy(m.tick)}
              className="rounded border border-line px-2 py-1 font-mono text-xs text-ink-2 hover:border-accent hover:text-accent"
              title={t("report.worst.copy")}
            >
              {copied === m.tick ? "✓" : "⧉"} demo_gototick {m.tick}
            </button>
          </li>
        ))}
      </ul>
    </Card>
  );
}
