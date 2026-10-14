"use client";

import { t } from "@/i18n";
import type { Counterstrafe } from "@/lib/api";

import { Card, SectionTitle, Stat, fmtNum, fmtPct } from "../ui";
import { CategoryBar, SpeedHistogram, SpeedScatter } from "./charts";

function Split<K extends string>({ data, prefix }: { data: Partial<Record<K, number>> | undefined; prefix: "timing" | "tech" }) {
  const entries = Object.entries(data ?? {}) as [K, number][];
  if (!entries.length) return <div className="text-sm text-muted">{t("common.na")}</div>;
  return (
    <ul className="space-y-2">
      {entries
        .sort((a, b) => b[1] - a[1])
        .map(([k, v]) => (
          <li key={k}>
            <div className="flex justify-between text-sm">
              <span className="text-ink-2">{t(`${prefix}.${k}` as never)}</span>
              <span className="font-semibold tabular">{v.toFixed(0)}%</span>
            </div>
            <div className="mt-1 h-1.5 rounded-full bg-surface-2">
              <div className="h-full rounded-full bg-ink-2/70" style={{ width: `${v}%` }} />
            </div>
          </li>
        ))}
    </ul>
  );
}

export function CounterstrafeTab({ cs, accuracyRatio }: { cs: Counterstrafe; accuracyRatio: number }) {
  return (
    <div className="space-y-5">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label={t("report.perfect")} value={fmtPct(cs.perfect_pct)} hint={t("report.perfect.hint", { n: cs.strafe_shots })} accent />
        <Stat label={t("cs.accurate")} value={fmtPct(cs.accurate_pct)} hint={t("cs.accurate.hint")} />
        <Stat label={t("cs.brake")} value={fmtNum(cs.median_brake_to_shot_ms, " мс")} hint={t("cs.brake.hint")} />
        <Stat label={t("cat.moving")} value={fmtPct(cs.first_shots ? (100 * (cs.categories.moving + cs.categories.air)) / cs.first_shots : null)} hint={`${cs.categories.moving + cs.categories.air} / ${cs.first_shots}`} />
      </div>

      <Card>
        <SectionTitle>{t("cs.cats.title")}</SectionTitle>
        <p className="-mt-2 mb-3 text-xs text-muted">{t("cs.cats.hint", { n: cs.first_shots })}</p>
        <CategoryBar counts={cs.categories} />
      </Card>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <SectionTitle>{t("cs.speed.title")}</SectionTitle>
          <p className="-mt-2 mb-3 text-xs text-muted">{t("cs.speed.hint", { pct: Math.round(accuracyRatio * 100) })}</p>
          <SpeedScatter shots={cs.shots} ratio={accuracyRatio} />
        </Card>
        <Card>
          <SectionTitle>{t("cs.hist.title")}</SectionTitle>
          <SpeedHistogram data={cs.speed_histogram} />
        </Card>
      </div>

      <div className="grid gap-5 md:grid-cols-2">
        <Card>
          <SectionTitle>{t("cs.timing")}</SectionTitle>
          <Split data={cs.timing_pct} prefix="timing" />
          {!cs.buttons_available ? <p className="mt-3 text-xs text-muted">{t("cs.buttons.no")}</p> : null}
        </Card>
        <Card>
          <SectionTitle>{t("cs.technique")}</SectionTitle>
          <Split data={cs.technique_pct} prefix="tech" />
        </Card>
      </div>

      <Card>
        <SectionTitle>{t("cs.weapons.title")}</SectionTitle>
        <div className="-mx-2 overflow-x-auto">
          <table className="w-full min-w-[520px] text-sm">
            <thead>
              <tr className="label-caps text-left">
                <th className="px-2 py-2">{t("cs.col.weapon")}</th>
                <th className="px-2 py-2 text-right">{t("cs.col.shots")}</th>
                <th className="px-2 py-2 text-right">{t("cs.col.perfect")}</th>
                <th className="px-2 py-2 text-right">{t("cs.col.moving")}</th>
                <th className="px-2 py-2 text-right">{t("cs.col.speed")}</th>
              </tr>
            </thead>
            <tbody className="tabular">
              {cs.by_weapon.map((w) => (
                <tr key={w.weapon} className="border-t border-line">
                  <td className="px-2 py-2 font-semibold">{w.weapon_name}</td>
                  <td className="px-2 py-2 text-right">{w.first_shots}</td>
                  <td className="px-2 py-2 text-right">{fmtPct(w.perfect_pct)}</td>
                  <td className="px-2 py-2 text-right">{fmtPct(w.moving_pct)}</td>
                  <td className="px-2 py-2 text-right">{w.median_speed} u/s</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
