"use client";

import type { ReactNode } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { t } from "@/i18n";
import type { Category, Counterstrafe, CsShot, Duels } from "@/lib/api";

// Цвета совпадают с токенами в globals.css (проверены валидатором палитры).
export const CAT_COLORS: Record<Category, string> = {
  perfect: "#199e70",
  slow: "#c98500",
  moving: "#d55181",
  air: "#3987e5",
};
export const CATS: Category[] = ["perfect", "slow", "moving", "air"];
const SURFACE = "#15171c";
const GRID = "#2a2d34";
const AXIS = "#7d828e";
const SERIES = "#3987e5";
const WIN = "#3987e5";
const LOSS = "#d95926";
const NEUTRAL = "#5a5e68";

const axisProps = {
  stroke: AXIS,
  tick: { fill: AXIS, fontSize: 11 },
  tickLine: false,
  axisLine: { stroke: "#3a3d45" },
} as const;

function TooltipBox({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-md border border-line bg-[#0f1115]/95 px-3 py-2 text-xs text-ink shadow-xl">{children}</div>
  );
}

function Swatch({ color }: { color: string }) {
  return <span className="mr-1.5 inline-block h-2.5 w-2.5 rounded-sm align-middle" style={{ background: color }} />;
}

/** Легенда в заданном порядке (Recharts сортирует стековые серии по-своему). */
function OrderedLegend({ items }: { items: { name: string; color: string }[] }) {
  return (
    <ul className="mt-2 flex flex-wrap justify-center gap-x-4 gap-y-1 text-xs text-ink-2">
      {items.map((i) => (
        <li key={i.name}>
          <Swatch color={i.color} />
          {i.name}
        </li>
      ))}
    </ul>
  );
}

// ---------------------------------------------------------------------------

export function SpeedScatter({ shots, ratio }: { shots: CsShot[]; ratio: number }) {
  const data = shots.map((s, i) => ({ ...s, idx: i + 1, pct: Math.round(s.speed_ratio * 100) }));
  return (
    <ResponsiveContainer width="100%" height={260}>
      <ScatterChart margin={{ top: 10, right: 36, bottom: 8, left: -10 }}>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey="idx" type="number" name="#" {...axisProps} domain={[0, "dataMax + 1"]} allowDecimals={false} />
        <YAxis dataKey="pct" type="number" unit="%" {...axisProps} domain={[0, 110]} ticks={[0, 25, 50, 75, 100]} />
        <ReferenceLine
          y={ratio * 100}
          stroke="#f0efec"
          strokeDasharray="4 4"
          label={{ value: `${Math.round(ratio * 100)}%`, position: "right", fill: "#b4b8c2", fontSize: 11 }}
        />
        <Tooltip
          cursor={{ stroke: "#3a3d45" }}
          content={({ active, payload }) => {
            if (!active || !payload?.length) return null;
            const s = payload[0].payload as CsShot & { pct: number };
            return (
              <TooltipBox>
                <div className="font-semibold">
                  {s.weapon_name} · {s.pct}% ({Math.round(s.speed)} u/s)
                </div>
                <div className="mt-0.5 text-ink-2">
                  <Swatch color={CAT_COLORS[s.category]} />
                  {t(`cat.${s.category}`)}
                  {s.timing ? ` · ${t(`timing.${s.timing}`)}` : ""}
                </div>
                <div className="mt-0.5 text-muted">
                  {t("common.round")} {s.round ?? "?"} · {t("common.tick")} {s.tick}
                </div>
              </TooltipBox>
            );
          }}
        />
        <Scatter data={data} fill={SERIES} stroke={SURFACE} strokeWidth={2} shape="circle" isAnimationActive={false} />
      </ScatterChart>
    </ResponsiveContainer>
  );
}

export function SpeedHistogram({ data }: { data: Counterstrafe["speed_histogram"] }) {
  const rows = data.filter((d, i) => i < 10 || CATS.some((c) => d[c] > 0));
  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={rows} margin={{ top: 10, right: 8, bottom: 8, left: -20 }} barCategoryGap={4}>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey="bin" {...axisProps} interval={0} angle={-30} textAnchor="end" height={48} />
        <YAxis {...axisProps} allowDecimals={false} />
        <Tooltip
          cursor={{ fill: "rgb(255 255 255 / 0.04)" }}
          content={({ active, payload, label }) =>
            active && payload?.length ? (
              <TooltipBox>
                <div className="mb-1 font-semibold">{label}</div>
                {payload
                  .filter((p) => Number(p.value) > 0)
                  .map((p) => (
                    <div key={String(p.dataKey)}>
                      <Swatch color={String(p.color)} />
                      {p.name}: {p.value}
                    </div>
                  ))}
              </TooltipBox>
            ) : null
          }
        />
        <Legend content={() => <OrderedLegend items={CATS.map((c) => ({ name: t(`cat.${c}`), color: CAT_COLORS[c] }))} />} />
        {CATS.map((c, i) => (
          <Bar
            key={c}
            dataKey={c}
            name={t(`cat.${c}`)}
            stackId="a"
            fill={CAT_COLORS[c]}
            stroke={SURFACE}
            strokeWidth={2}
            radius={i === CATS.length - 1 ? [4, 4, 0, 0] : 0}
            isAnimationActive={false}
          />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}

/** Доли категорий одной полосой с прямыми подписями (без библиотеки). */
export function CategoryBar({ counts }: { counts: Record<Category, number> }) {
  const total = CATS.reduce((s, c) => s + (counts[c] ?? 0), 0);
  if (!total) return <div className="text-sm text-muted">{t("common.na")}</div>;
  return (
    <div>
      <div className="flex h-7 w-full gap-[2px] overflow-hidden rounded-md">
        {CATS.filter((c) => counts[c] > 0).map((c) => (
          <div
            key={c}
            title={`${t(`cat.${c}`)}: ${counts[c]} (${Math.round((100 * counts[c]) / total)}%)`}
            style={{ width: `${(100 * counts[c]) / total}%`, background: CAT_COLORS[c] }}
          />
        ))}
      </div>
      <ul className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
        {CATS.map((c) => (
          <li key={c} className="text-sm">
            <Swatch color={CAT_COLORS[c]} />
            <span className="text-ink-2">{t(`cat.${c}`)}</span>{" "}
            <span className="font-semibold tabular">{Math.round((100 * (counts[c] ?? 0)) / total)}%</span>{" "}
            <span className="text-xs text-muted tabular">({counts[c] ?? 0})</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function DuelsByRound({ data }: { data: Duels["by_round"] }) {
  const keys = [
    { key: "wins", name: t("duels.wins"), color: WIN },
    { key: "losses", name: t("duels.losses"), color: LOSS },
    { key: "none", name: t("duels.none"), color: NEUTRAL },
  ];
  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={data} margin={{ top: 10, right: 8, bottom: 4, left: -20 }} barCategoryGap="25%">
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey="round" {...axisProps} />
        <YAxis {...axisProps} allowDecimals={false} />
        <Tooltip
          cursor={{ fill: "rgb(255 255 255 / 0.04)" }}
          content={({ active, payload, label }) =>
            active && payload?.length ? (
              <TooltipBox>
                <div className="mb-1 font-semibold">
                  {t("common.round")} {label}
                </div>
                {payload.map((p) => (
                  <div key={String(p.dataKey)}>
                    <Swatch color={String(p.color)} />
                    {p.name}: {p.value}
                  </div>
                ))}
              </TooltipBox>
            ) : null
          }
        />
        <Legend content={() => <OrderedLegend items={keys} />} />
        {keys.map((k, i) => (
          <Bar
            key={k.key}
            dataKey={k.key}
            name={k.name}
            stackId="r"
            fill={k.color}
            stroke={SURFACE}
            strokeWidth={2}
            radius={i === keys.length - 1 ? [4, 4, 0, 0] : 0}
            isAnimationActive={false}
          />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}

export function AngleHistogram({ data }: { data: { bin: string; count: number }[] }) {
  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data} margin={{ top: 10, right: 8, bottom: 4, left: -20 }} barCategoryGap="20%">
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey="bin" {...axisProps} />
        <YAxis {...axisProps} allowDecimals={false} />
        <Tooltip
          cursor={{ fill: "rgb(255 255 255 / 0.04)" }}
          content={({ active, payload, label }) =>
            active && payload?.length ? (
              <TooltipBox>
                {label}: <span className="font-semibold">{String(payload[0].value)}</span>
              </TooltipBox>
            ) : null
          }
        />
        <Bar dataKey="count" fill={SERIES} radius={[4, 4, 0, 0]} isAnimationActive={false} />
      </BarChart>
    </ResponsiveContainer>
  );
}
