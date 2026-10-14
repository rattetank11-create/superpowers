import { UploadForm } from "@/components/UploadForm";
import { t } from "@/i18n";

const FEATURES = [
  ["Контрстрейфы", "Скорость и тайминг каждого первого выстрела, разбивка по оружию."],
  ["Дуэли", "Winrate, opening, кто стрелял первым, TTK, трейды, пики без флешки."],
  ["Crosshair placement", "Угол между прицелом и головой врага в момент его появления."],
  ["Рекомендации", "Что подкачать и что перестать делать — с конкретными тренировками."],
];

export default function Home() {
  return (
    <div>
      <div className="mx-auto mb-8 max-w-2xl text-center">
        <h1 className="text-3xl font-black uppercase tracking-wide sm:text-4xl">
          {t("upload.title")}
        </h1>
        <p className="mt-3 text-ink-2">{t("upload.subtitle")}</p>
      </div>
      <UploadForm />
      <div className="mx-auto mt-10 grid max-w-4xl gap-4 sm:grid-cols-2">
        {FEATURES.map(([title, text]) => (
          <div key={title} className="rounded-lg border border-line bg-surface/60 p-4">
            <div className="text-sm font-bold uppercase tracking-wider text-accent">{title}</div>
            <div className="mt-1 text-sm text-ink-2">{text}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
