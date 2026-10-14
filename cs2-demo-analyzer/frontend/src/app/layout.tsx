import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import { t } from "@/i18n";

import "./globals.css";

export const metadata: Metadata = {
  title: t("app.name"),
  description: t("upload.subtitle"),
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ru">
      <body className="font-sans antialiased">
        <header className="sticky top-0 z-20 border-b border-line bg-bg/80 backdrop-blur">
          <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
            <Link href="/" className="flex items-center gap-2">
              <span className="grid h-8 w-8 place-items-center rounded-md bg-accent text-sm font-black text-black">CS</span>
              <span className="text-sm font-extrabold uppercase tracking-widest">
                {t("app.name")}
              </span>
            </Link>
            <Link
              href="/"
              className="rounded-md border border-line px-3 py-1.5 text-xs font-semibold uppercase tracking-wider text-ink-2 hover:border-accent hover:text-accent"
            >
              {t("nav.new")}
            </Link>
          </div>
        </header>
        <main className="mx-auto max-w-6xl px-4 py-8">{children}</main>
        <footer className="mx-auto max-w-6xl px-4 pb-10 pt-6 text-xs text-muted">
          {t("app.name")} · {t("app.tagline")}
        </footer>
      </body>
    </html>
  );
}
