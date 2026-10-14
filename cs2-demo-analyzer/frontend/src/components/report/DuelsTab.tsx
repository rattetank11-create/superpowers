"use client";

import { t } from "@/i18n";
import type { Report, WinRate } from "@/lib/api";

import { ApproxBadge, Card, SectionTitle, Stat, fmtNum, fmtPct } from "../ui";
import { AngleHistogram, DuelsByRound } from "./charts";

function WinRateRow({ label, wr }: { label: string; wr?: WinRate }) {
  const v = wr?.winrate ?? null;
  return (
    <li>
      <div className="flex justify-between text-sm">
        <span className="text-ink-2">{label}</span>
        <span className="tabular">
          <span className="font-semibold">{fmtPct(v)}</span>{" "}
          <span className="text-xs text-muted">({wr?.wins ?? 0}/{wr?.count ?? 0})</span>
        </span>
      </div>
      <div className="mt-1 h-1.5 rounded-full bg-surface-2">
        <div className="h-full rounded-full bg-win" style={{ width: `${v ?? 0}%` }} />
      </div>
    </li>
  );
}

export function DuelsTab({ report }: { report: Report }) {
  const { duels, overview, accuracy, trades, crosshair } = report;
  const pitch = crosshair.median_pitch_err;
  return (
    <div className="space-y-5">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label={t("duels.winrate")} value={fmtPct(duels.winrate)} hint={t("duels.winrate.hint", { w: duels.wins, n: duels.decided })} accent />
        <Stat label={t("duels.opening")} value={fmtPct(duels.opening?.winrate)} hint={`${duels.opening?.wins ?? 0} / ${duels.opening?.count ?? 0}`} />
        <Stat label={t("duels.first")} value={fmtPct(duels.shot_first_pct)} hint={<span className="inline-flex items-center gap-1">{t("common.samples", { n: duels.total })}</span>} />
        <Stat label={t("duels.ttk")} value={fmtNum(duels.median_ttk_ms, " мс")} hint={t("duels.ttk.hint")} />
        <Stat label={t("duels.fb")} value={fmtPct(accuracy.first_bullet_accuracy_pct)} hint={`${accuracy.first_bullet_hits ?? ""}${accuracy.first_bullets ? ` / ${accuracy.first_bullets}` : ""}`} />
        <Stat label={t("duels.hs")} value={fmtPct(overview.hs_pct)} hint={`${overview.kills} kills`} />
        <Stat label={t("duels.kd")} value={`${overview.kills} / ${overview.deaths}`} hint={`K/D ${overview.kd}`} />
        <Stat label={t("duels.adr")} value={overview.adr.toFixed(0)} hint={`KPR ${overview.kpr}`} />
      </div>

      <Card>
        <SectionTitle>{t("duels.byround")}</SectionTitle>
        <DuelsByRound data={duels.by_round} />
      </Card>

      <div className="grid gap-5 md:grid-cols-2">
        <Card>
          <SectionTitle aside={<ApproxBadge />}>{t("duels.peek")}</SectionTitle>
          <ul className="space-y-3">
            <WinRateRow label={t("duels.peek.with")} wr={duels.peek_with_flash} />
            <WinRateRow label={t("duels.peek.without")} wr={duels.peek_without_flash} />
            <WinRateRow label={t("duels.holding")} wr={duels.holding} />
            <WinRateRow label={t("duels.shotfirst")} wr={duels.when_shot_first} />
            <WinRateRow label={t("duels.shotsecond")} wr={duels.when_shot_second} />
          </ul>
        </Card>
        <Card>
          <SectionTitle>{t("duels.trades")}</SectionTitle>
          <div className="grid grid-cols-2 gap-3">
            <Stat label={t("duels.traded")} value={fmtPct(trades.traded_pct)} hint={`${trades.traded_deaths} / ${trades.deaths}`} />
            <Stat label={t("duels.tradekills")} value={fmtPct(trades.trade_kill_pct)} hint={`${trades.trade_kills} / ${trades.kills}`} />
          </div>
        </Card>
      </div>

      <Card>
        <SectionTitle aside={<ApproxBadge />}>{t("duels.xhair")}</SectionTitle>
        <div className="grid gap-3 sm:grid-cols-3">
          <Stat label={t("duels.xhair.median")} value={crosshair.median_angle === null ? t("common.na") : `${crosshair.median_angle}°`} hint={t("common.samples", { n: crosshair.front_samples ?? 0 })} accent />
          <Stat label={t("duels.xhair.good")} value={fmtPct(crosshair.good_pct)} />
          <Stat
            label={t("duels.xhair.pitch")}
            value={pitch === null || pitch === undefined ? t("common.na") : `${Math.abs(pitch)}°`}
            hint={pitch === null || pitch === undefined ? undefined : pitch > 0 ? t("duels.xhair.pitch.low") : t("duels.xhair.pitch.high")}
          />
        </div>
        <p className="mb-2 mt-5 text-xs text-muted">{t("duels.xhair.hist")}</p>
        <AngleHistogram data={crosshair.histogram} />
        <p className="mt-3 text-xs text-muted">≈ {crosshair.method}</p>
      </Card>
    </div>
  );
}
