export type SectionGenerationStatus = 'pending' | 'processing' | 'completed' | 'failed';

export type SectionGenerationProgressItem = {
  index: number;
  title: string;
  summary: string;
  targetCount: number;
  generatedCount: number;
  status: SectionGenerationStatus;
};

type SectionGenerationProgressProps = {
  title: string;
  percent: number;
  sections: SectionGenerationProgressItem[];
  fallbackTitle: string;
  statusLabels: Record<SectionGenerationStatus, string>;
  renderProgress: (section: SectionGenerationProgressItem) => string;
};

export function SectionGenerationProgress({
  title,
  percent,
  sections,
  fallbackTitle,
  statusLabels,
  renderProgress,
}: SectionGenerationProgressProps) {
  if (sections.length === 0) return null;

  return (
    <div className="rounded-lg border border-indigo-100 bg-indigo-50/70 px-4 py-3">
      <div className="flex items-center justify-between gap-3">
        <span className="text-[12px] font-semibold text-slate-800">{title}</span>
        <span className="text-[12px] font-bold text-indigo-600">{percent}%</span>
      </div>
      <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-white">
        <div
          className="h-full rounded-full bg-indigo-500 transition-all duration-300"
          style={{ width: `${percent}%` }}
        />
      </div>
      <div className="mt-4 space-y-2">
        {sections.map((section) => (
          <div key={section.index} className="rounded-md border border-white/80 bg-white/70 px-3 py-2">
            <div className="flex items-center justify-between gap-3">
              <p className="text-[12px] font-semibold text-slate-800">
                {section.index}. {section.title || fallbackTitle}
              </p>
              <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                section.status === 'completed'
                  ? 'bg-emerald-50 text-emerald-600'
                  : section.status === 'processing'
                    ? 'bg-indigo-100 text-indigo-600'
                    : section.status === 'failed'
                      ? 'bg-red-50 text-red-600'
                      : 'bg-slate-100 text-slate-500'
              }`}>
                {statusLabels[section.status]}
              </span>
            </div>
            {section.summary && <p className="mt-1 text-[11px] leading-relaxed text-slate-500">{section.summary}</p>}
            <p className="mt-1 text-[11px] text-slate-400">{renderProgress(section)}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
