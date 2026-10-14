"use client";

import { useState } from "react";

import { t } from "@/i18n";
import { api, ApiError, type FaceitAdjustment, type FaceitBlock, type Rating } from "@/lib/api";

import { Card, LevelBadge, cx } from "../ui";

const TIER_STYLE: Record<FaceitAdjustment["tier"], string> = {
  normal: "border-win/40 bg-win/10 text-win",
  bad: "border-loss/40 bg-loss/10 text-loss",
  very_bad: "border-bad/50 bg-bad/15 text-bad",
};
const TIER_ICON: Record<FaceitAdjustment["tier"], string> = { normal: "▲", bad: "▼", very_bad: "▼▼" };

function signed(n: number) {
  return n > 0 ? `+${n}` : `${n}`;
}

/** Карточка ELO: реальный FACEIT + поправка по игре, иначе — оценка по метрикам. */
export function EloCard({ reportId, rating, initial }: { reportId: string; rating: Rating; initial?: FaceitBlock }) {
  const [faceit, setFaceit] = useState<FaceitBlock | undefined>(initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    setBusy(true);
    setError(null);
    try {
      setFaceit(await api.refreshFaceit(reportId));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("error.generic"));
    } finally {
      setBusy(false);
    }
  }

  const acc = faceit?.account;
  const adj = faceit?.adjustment;
  const refreshButton =
    faceit && faceit.status !== "no_key" ? (
      <button
        type="button"
        onClick={refresh}
        disabled={busy}
        className="text-xs text-muted underline-offset-4 hover:text-accent hover:underline disabled:opacity-50"
      >
        ↻ {t("faceit.refresh")}
      </button>
    ) : null;

  if (faceit?.status === "found" && acc && adj) {
    // «+100…+300» и «−100…−300»: сначала меньшая по модулю поправка.
    const [a, b] = adj.tier_delta_min >= 0 ? [adj.tier_delta_min, adj.tier_delta_max] : [adj.tier_delta_max, adj.tier_delta_min];
    const range = `${signed(a)}…${signed(b)}`;
    return (
      <Card>
        <div className="flex items-center justify-between">
          <div className="label-caps">{t("faceit.title")}</div>
          {refreshButton}
        </div>
        <div className="mt-3 flex items-center gap-3">
          {acc.avatar ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={acc.avatar} alt="" className="h-10 w-10 rounded-full border border-line object-cover" />
          ) : null}
          <div className="min-w-0">
            {acc.url ? (
              <a href={acc.url} target="_blank" rel="noopener noreferrer" className="block truncate font-bold hover:text-accent">
                {acc.nickname} ↗
              </a>
            ) : (
              <div className="truncate font-bold">{acc.nickname}</div>
            )}
            <div className="text-xs text-ink-2 tabular">
              {t("faceit.now", { elo: adj.current_elo, level: adj.current_level })}
            </div>
          </div>
        </div>

        <div className="mt-4 flex items-center gap-3">
          <LevelBadge level={adj.new_level} size={48} />
          <div>
            <div className="text-xs text-muted">{t("faceit.after")}</div>
            <div className="text-xl font-black tabular">
              <span className={adj.delta >= 0 ? "text-win" : "text-loss"}>{signed(adj.delta)}</span> → ≈{adj.new_elo}
            </div>
            <div className="text-xs text-ink-2">{t("report.elo.level", { range: String(adj.new_level) })}</div>
          </div>
        </div>

        <div className={cx("mt-3 inline-flex flex-wrap items-center gap-1.5 rounded border px-2 py-1 text-xs font-semibold", TIER_STYLE[adj.tier])}>
          <span aria-hidden>{TIER_ICON[adj.tier]}</span>
          {t(`faceit.tier.${adj.tier}`)}
          <span className="font-normal opacity-80">· {t("faceit.range", { range })}</span>
          {adj.reasons
            .filter((r) => r !== "perf")
            .map((r) => (
              <span key={r} className="font-normal opacity-80">
                · {t(`faceit.reason.${r}` as never)}
              </span>
            ))}
        </div>
        <p className="mt-3 text-xs text-muted">{t("faceit.disclaimer")}</p>
        {error ? <p className="mt-2 text-xs text-bad">⚠ {error}</p> : null}
      </Card>
    );
  }

  // FACEIT не найден / недоступен / не настроен — старая оценка по метрикам.
  const levelRange = rating.level_low === rating.level_high ? `${rating.level}` : `${rating.level_low}–${rating.level_high}`;
  return (
    <Card>
      <div className="flex items-center justify-between">
        <div className="label-caps">{t("report.elo")}</div>
        {refreshButton}
      </div>
      {faceit?.message ? (
        <div className="mt-2 rounded border border-line bg-surface-2/60 px-2 py-1 text-xs text-ink-2">{faceit.message}</div>
      ) : null}
      <div className="mt-3 flex items-center gap-4">
        <LevelBadge level={rating.level} size={56} />
        <div>
          <div className="text-2xl font-black tabular">
            {rating.elo_low}–{rating.elo_high}
          </div>
          <div className="text-sm text-ink-2">{t("report.elo.level", { range: levelRange })}</div>
        </div>
      </div>
      <p className="mt-3 text-xs text-muted">
        {t("report.elo.disclaimer")} {!rating.calibrated ? t("report.elo.uncalibrated") : null}
      </p>
      {error ? <p className="mt-2 text-xs text-bad">⚠ {error}</p> : null}
    </Card>
  );
}
