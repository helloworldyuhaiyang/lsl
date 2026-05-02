import { useState } from 'react';
import { parseCueText } from '@/utils/cueParser';
import { formatTime } from '@/utils/formatTime';
import { speakerColors } from '@/data/mockData';
import type { RevisionItem } from '@/types';
import { cn } from '@/lib/utils';
import { ChevronDown } from 'lucide-react';

interface SubtitleCardProps {
  item: RevisionItem;
  index: number;
  isActive: boolean;
  onClick: (time: number) => void;
}

export function SubtitleCard({ item, index, isActive, onClick }: SubtitleCardProps) {
  const [showOriginal, setShowOriginal] = useState(false);
  const parsed = parseCueText(item.fullText);

  return (
    <div
      onClick={() => {
        onClick(item.startTime);
        setShowOriginal(!showOriginal);
      }}
      className={cn(
        'bg-white rounded-xl border p-4 cursor-pointer transition-all duration-300',
        isActive
          ? 'border-indigo-300 ring-1 ring-indigo-200 shadow-md shadow-indigo-100'
          : 'border-slate-200 hover:border-slate-300 hover:shadow-sm'
      )}
    >
      <div className="flex items-center gap-2.5 mb-1.5">
        <span className="text-[12px] font-semibold text-slate-600">Sentence {index + 1}</span>
        <span className="w-2 h-2 rounded-full" style={{ backgroundColor: speakerColors[item.speaker] || '#94A3B8' }} />
        <span className="text-[11px] text-slate-400">{item.speaker}</span>
        <span className="text-[10px] text-slate-400 font-mono ml-auto">
          {formatTime(item.startTime)}-{formatTime(item.endTime)}
        </span>
        <ChevronDown className={cn(
          'w-3.5 h-3.5 text-slate-400 transition-transform duration-200',
          showOriginal && 'rotate-180'
        )} />
      </div>

      {!showOriginal ? (
        <p className="text-[12px] text-slate-400 italic pl-0.5">Click to show text</p>
      ) : (
        <div className="space-y-1.5 animate-in fade-in slide-in-from-top-1 duration-200">
          {parsed.cue && (
            <span className="inline-block font-mono text-[11px] bg-amber-50 text-amber-700 border border-amber-200 rounded-md px-2 py-0.5 font-medium">
              [{parsed.cue}]
            </span>
          )}
          <p className="text-[14px] text-slate-700 leading-relaxed">{parsed.content}</p>
        </div>
      )}
    </div>
  );
}
