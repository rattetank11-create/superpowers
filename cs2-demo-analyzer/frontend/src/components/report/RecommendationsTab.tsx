import { t } from "@/i18n";
import type { Recommendation } from "@/lib/api";

import { Card, cx } from "../ui";

export function RecCard({ rec, compact }: { rec: Recommendation; compact?: boolean }) {
  const stop = rec.kind === "stop";
  return (
    <article
      className={cx(
        "rounded-lg border bg-surface-2/60 p-4",
        stop ? "border-loss/40" : "border-win/40",
      )}
    >
      <div className="mb-1 flex items-center gap-2">
        <span
          className={cx(
            "rounded px-1.5 py-0.5 text-[0.62rem] font-bold uppercase tracking-wider",
            stop ? "bg-loss/15 text-loss" : "bg-win/15 text-win",
          )}
        >
          {stop ? "✕ " : "↑ "}
          {t(stop ? "kind.stop" : "kind.improve")}
        </span>
        <span className="text-[0.65rem] text-muted" aria-label={`Важность ${rec.severity} из 3`}>
          {"●".repeat(rec.severity)}
          {"○".repeat(Math.max(0, 3 - rec.severity))}
        </span>
      </div>
      <h4 className="font-bold">{rec.title}</h4>
      <p className={cx("mt-1 text-sm text-ink-2", compact && "line-clamp-4")}>{rec.text}</p>
    </article>
  );
}

export function RecommendationsTab({ improve, stop }: { improve: Recommendation[]; stop: Recommendation[] }) {
  return (
    <div className="grid gap-5 md:grid-cols-2">
      {[
        { title: t("kind.improve"), items: improve },
        { title: t("kind.stop"), items: stop },
      ].map((col) => (
        <Card key={col.title}>
          <h3 className="mb-4 text-sm font-bold uppercase tracking-wider">{col.title}</h3>
          {col.items.length ? (
            <div className="space-y-3">
              {col.items.map((r, i) => (
                <RecCard key={`${r.id}-${i}`} rec={r} />
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted">{t("report.top.empty")}</p>
          )}
        </Card>
      ))}
    </div>
  );
}
