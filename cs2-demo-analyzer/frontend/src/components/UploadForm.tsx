"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { t } from "@/i18n";
import { api, ApiError } from "@/lib/api";
import { uploadDemo } from "@/lib/upload";

import { Card, ProgressBar, cx } from "./ui";

export function UploadForm() {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [maxMb, setMaxMb] = useState(500);
  const [file, setFile] = useState<File | null>(null);
  const [drag, setDrag] = useState(false);
  const [progress, setProgress] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.config().then((c) => setMaxMb(c.max_upload_mb)).catch(() => undefined);
  }, []);

  function pick(f: File | undefined | null) {
    setError(null);
    if (!f) return;
    if (!f.name.toLowerCase().endsWith(".dem")) return setError(t("upload.err.ext"));
    if (f.size > maxMb * 1024 * 1024) return setError(t("upload.err.size", { mb: maxMb }));
    setFile(f);
  }

  async function start() {
    if (!file) return;
    setError(null);
    setProgress(0);
    try {
      const matchId = await uploadDemo(file, (p) => setProgress(p * 100));
      router.push(`/m/${matchId}`);
    } catch (err) {
      setProgress(null);
      setError(err instanceof ApiError ? err.message : t("upload.err.network"));
    }
  }

  const busy = progress !== null;

  return (
    <Card className="mx-auto max-w-2xl">
      <div
        role="button"
        tabIndex={0}
        onClick={() => !busy && inputRef.current?.click()}
        onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && !busy && inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          if (!busy) pick(e.dataTransfer.files[0]);
        }}
        className={cx(
          "flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed px-6 py-12 text-center transition-colors",
          drag ? "border-accent bg-accent/5" : "border-line hover:border-accent/60",
          busy && "cursor-default opacity-80",
        )}
      >
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" className="mb-3 text-accent" aria-hidden>
          <path d="M12 16V4m0 0l-4 4m4-4l4 4M4 16v3a1 1 0 001 1h14a1 1 0 001-1v-3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        <div className="font-semibold">{file ? file.name : t("upload.drop")}</div>
        <div className="mt-1 text-xs text-muted">
          {file ? `${(file.size / 1024 / 1024).toFixed(1)} МБ` : t("upload.limit", { mb: maxMb })}
        </div>
        <input
          ref={inputRef}
          type="file"
          accept=".dem"
          className="hidden"
          onChange={(e) => pick(e.target.files?.[0])}
        />
      </div>

      {busy ? (
        <div className="mt-5">
          <ProgressBar value={progress ?? 0} label={t("upload.uploading", { pct: Math.round(progress ?? 0) })} />
        </div>
      ) : (
        <button
          type="button"
          disabled={!file}
          onClick={start}
          className="mt-5 w-full rounded-lg bg-accent px-4 py-3 text-sm font-extrabold uppercase tracking-widest text-black transition hover:bg-accent-2 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {t("upload.button")}
        </button>
      )}

      {error ? (
        <div role="alert" className="mt-4 rounded-md border border-bad/40 bg-bad/10 px-3 py-2 text-sm text-ink">
          ⚠ {error}
        </div>
      ) : null}

      <div className="mt-6 border-t border-line pt-5">
        <label className="label-caps flex items-center gap-2" htmlFor="demo-link">
          {t("upload.link")}
          <span className="rounded bg-accent/15 px-1.5 py-0.5 text-[0.6rem] text-accent">{t("upload.soon")}</span>
        </label>
        <input
          id="demo-link"
          type="url"
          disabled
          placeholder={t("upload.link.placeholder")}
          className="mt-2 w-full cursor-not-allowed rounded-md border border-line bg-surface-2/50 px-3 py-2 text-sm text-muted placeholder:text-muted/60"
        />
      </div>
    </Card>
  );
}
