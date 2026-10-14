"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { ReportView } from "@/components/report/ReportView";
import { Card, Spinner } from "@/components/ui";
import { t } from "@/i18n";
import { api, ApiError, type ReportResponse } from "@/lib/api";

export default function ReportPage() {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<ReportResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .report(id)
      .then((d) => {
        setData(d);
        document.title = `${d.report.player.name} · ${d.report.match.map} — ${t("app.name")}`;
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : t("error.generic")));
  }, [id]);

  if (error)
    return (
      <Card className="mx-auto max-w-xl text-center">
        <h1 className="text-lg font-extrabold uppercase tracking-wider">{t("report.notfound")}</h1>
        <p className="mt-2 text-ink-2">{error}</p>
        <Link href="/" className="mt-5 inline-block text-accent hover:underline">
          {t("nav.new")}
        </Link>
      </Card>
    );
  if (!data)
    return (
      <div className="flex justify-center py-20">
        <Spinner />
      </div>
    );
  return <ReportView data={data} />;
}
