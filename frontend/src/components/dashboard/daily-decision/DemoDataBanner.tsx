import { useTranslation } from "@/lib/i18n";
import { GhostButton } from "@/components/ui/buttons";

export function DemoDataBanner({ onImportClick }: { onImportClick?: () => void }) {
  const { t } = useTranslation();
  return (
    <div
      role="alert"
      className="flex flex-col gap-3 rounded-xl border border-amber-500/30 bg-amber-500/8 px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded-full border border-amber-400/40 bg-amber-500/15 px-2.5 py-0.5 text-xs font-semibold text-amber-200">
          {t.home.dailyDemoModePill}
        </span>
        <p className="text-sm text-amber-100/95">{t.home.dailyDemoBanner}</p>
      </div>
      {onImportClick && (
        <GhostButton onClick={onImportClick} className="shrink-0 rounded-lg text-amber-100">
          {t.home.dailyImportCsv}
        </GhostButton>
      )}
    </div>
  );
}
