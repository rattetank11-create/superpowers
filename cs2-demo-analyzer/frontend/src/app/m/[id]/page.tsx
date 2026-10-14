"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Card, ProgressBar, Spinner } from "@/components/ui";
import { hasKey, t } from "@/i18n";
import { api, ApiError, type MatchStatus, type PlayerRow } from "@/lib/api";

const POLL_MS = 1000;

export default function MatchPage() {
  const { id } = useParams<{ id: string }>();
  const [match, setMatch] = useState<MatchStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let stop = false;
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const m = await api.match(id);
        if (stop) return;
        setMatch(m);
        if (m.status === "queued" || m.status === "processing") timer = setTimeout(poll, POLL_MS);
      } catch (err) {
        if (stop) return;
        if (err instanceof ApiError && err.status === 404) setError(err.message);
        else timer = setTimeout(poll, POLL_MS * 3); // временная сетевая ошибка — продолжаем
      }
    }
    poll();
    return () => {
      stop = true;
      clearTimeout(timer);
    };
  }, [id]);

  if (error) return <Failure message={error} />;
  if (!match)
    return (
      <div className="flex justify-center py-20">
        <Spinner />
      </div>
    );
  if (match.status === "failed") return <Failure message={match.error?.message ?? t("error.generic")} />;
  if (match.status !== "done") {
    const stageKey = `progress.stage.${match.stage}`;
    return (
      <Card className="mx-auto max-w-xl">
        <h1 className="mb-1 text-lg font-extrabold uppercase tracking-wider">{t("progress.title")}</h1>
        <div className="mb-5 truncate text-xs text-muted">{match.filename}</div>
        <ProgressBar value={match.progress} label={hasKey(stageKey) ? t(stageKey) : match.stage} />
      </Card>
    );
  }
  return <PlayerPicker match={match} />;
}

function Failure({ message }: { message: string }) {
  return (
    <Card className="mx-auto max-w-xl text-center">
      <div className="text-4xl" aria-hidden>
        ⚠
      </div>
      <h1 className="mt-2 text-lg font-extrabold uppercase tracking-wider">{t("progress.failed")}</h1>
      <p className="mt-2 text-ink-2">{message}</p>
      <Link
        href="/"
        className="mt-6 inline-block rounded-lg bg-accent px-5 py-2.5 text-sm font-extrabold uppercase tracking-widest text-black hover:bg-accent-2"
      >
        {t("progress.retry")}
      </Link>
    </Card>
  );
}

function PlayerPicker({ match }: { match: MatchStatus }) {
  const teams = new Map<number, PlayerRow[]>();
  for (const p of match.players) teams.set(p.team, [...(teams.get(p.team) ?? []), p]);
  const order = [...teams.keys()].sort();
  return (
    <div>
      <div className="mb-6 text-center">
        <div className="label-caps">
          {match.match?.map} · {match.match?.score.t}:{match.match?.score.ct} ·{" "}
          {t("report.rounds", { n: match.match?.rounds ?? 0 })}
        </div>
        <h1 className="mt-2 text-2xl font-black uppercase tracking-wide">{t("pick.title")}</h1>
        <p className="mt-1 text-ink-2">{t("pick.subtitle")}</p>
      </div>
      <div className="grid gap-5 md:grid-cols-2">
        {order.map((team) => (
          <Card key={team}>
            <div className={`label-caps mb-3 ${team === 2 ? "text-accent-2" : team === 3 ? "text-cat-air" : ""}`}>
              {hasKey(`pick.team.${team}`) ? t(`pick.team.${team}` as never) : t("pick.team.0")}
            </div>
            <ul className="space-y-2">
              {teams.get(team)!.sort((a, b) => b.kills - a.kills).map((p) => (
                <li key={p.steamid}>
                  <Link
                    href={`/r/${p.report_id}`}
                    className="group flex items-center justify-between rounded-lg border border-line bg-surface-2/60 px-4 py-3 transition hover:border-accent hover:bg-accent/5"
                  >
                    <div className="min-w-0">
                      <div className="truncate font-semibold group-hover:text-accent">{p.name}</div>
                      <div className="text-xs text-muted tabular">SteamID {p.steamid}</div>
                    </div>
                    <div className="ml-3 shrink-0 text-sm text-ink-2 tabular">
                      {p.kills} / {p.deaths}
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          </Card>
        ))}
      </div>
    </div>
  );
}
