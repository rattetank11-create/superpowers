import type { ReactNode } from "react";

import { t } from "@/i18n";

export function cx(...parts: (string | false | null | undefined)[]) {
  return parts.filter(Boolean).join(" ");
}

export function fmtPct(v: number | null | undefined, digits = 0): string {
  return v === null || v === undefined ? t("common.na") : `${v.toFixed(digits)}%`;
}

export function fmtNum(v: number | null | undefined, suffix = ""): string {
  return v === null || v === undefined ? t("common.na") : `${v}${suffix}`;
}

export function Card({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <section className={cx("rounded-xl border border-line bg-surface/90 p-5 shadow-lg shadow-black/20", className)}>
      {children}
    </section>
  );
}

export function SectionTitle({ children, aside }: { children: ReactNode; aside?: ReactNode }) {
  return (
    <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
      <h3 className="text-sm font-bold uppercase tracking-wider text-ink">{children}</h3>
      {aside}
    </div>
  );
}

export function Stat({ label, value, hint, accent }: { label: string; value: ReactNode; hint?: ReactNode; accent?: boolean }) {
  return (
    <div className="rounded-lg border border-line bg-surface-2/60 p-4">
      <div className="label-caps">{label}</div>
      <div className={cx("mt-1 text-2xl font-bold", accent ? "text-accent" : "text-ink")}>{value}</div>
      {hint ? <div className="mt-1 text-xs text-muted">{hint}</div> : null}
    </div>
  );
}

export function ApproxBadge() {
  return (
    <span
      className="rounded border border-warn/40 bg-warn/10 px-1.5 py-0.5 text-[0.65rem] font-semibold uppercase tracking-wider text-warn"
      title="Метрика вычислена приближённо"
    >
      ≈ {t("duels.approx")}
    </span>
  );
}

export function ProgressBar({ value, label }: { value: number; label?: string }) {
  const pct = Math.max(0, Math.min(100, value));
  return (
    <div>
      <div className="h-2.5 w-full overflow-hidden rounded-full bg-surface-2" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
        <div
          className="h-full rounded-full bg-gradient-to-r from-accent to-accent-2 transition-[width] duration-300"
          style={{ width: `${pct}%` }}
        />
      </div>
      {label ? <div className="mt-2 flex justify-between text-xs text-ink-2"><span>{label}</span><span className="tabular">{pct.toFixed(0)}%</span></div> : null}
    </div>
  );
}

/** Значок уровня FACEIT (1–10). Цвет — от уровня, номер всегда подписан. */
export function LevelBadge({ level, size = 44 }: { level: number; size?: number }) {
  const color = level <= 1 ? "#d0d0d0" : level <= 3 ? "#1ce400" : level <= 7 ? "#ffc800" : level <= 9 ? "#ff6309" : "#fe1f00";
  return (
    <span
      className="inline-flex items-center justify-center rounded-full font-black tabular"
      style={{
        width: size,
        height: size,
        border: `3px solid ${color}`,
        color,
        fontSize: size * 0.42,
        background: "rgb(0 0 0 / 0.35)",
      }}
      aria-label={`Уровень ${level}`}
    >
      {level}
    </span>
  );
}

export function Spinner() {
  return <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-accent border-t-transparent" />;
}
