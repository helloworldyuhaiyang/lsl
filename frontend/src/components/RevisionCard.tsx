import { useCallback, useRef } from 'react';
import { formatTime } from '@/utils/formatTime';
import type { RevisionItem } from '@/types';
import type { TtsSpeakerItem } from '@/types/api';
import { VoiceAvatar } from '@/components/VoiceAvatar';
import { Loader2, RotateCcw, Volume2 } from 'lucide-react';

interface RevisionCardProps {
  item: RevisionItem;
  voice?: TtsSpeakerItem;
  onUpdate: (id: string, fullText: string) => void;
  onRestore: (id: string) => void;
  onSynthesize: (item: RevisionItem) => void;
  isSynthesizing?: boolean;
}

/**
 * Split text into segments: normal text and CUE text (wrapped in [])
 */
function parseCueSegments(text: string): Array<{ type: 'cue' | 'text'; content: string }> {
  const segments: Array<{ type: 'cue' | 'text'; content: string }> = [];
  const regex = /(\[[^\]]*\])/g;
  let lastIndex = 0;
  let match;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      segments.push({ type: 'text', content: text.slice(lastIndex, match.index) });
    }
    segments.push({ type: 'cue', content: match[1] });
    lastIndex = regex.lastIndex;
  }

  if (lastIndex < text.length) {
    segments.push({ type: 'text', content: text.slice(lastIndex) });
  }

  return segments;
}

export function RevisionCard({ item, voice, onUpdate, onRestore, onSynthesize, isSynthesizing = false }: RevisionCardProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const highlightRef = useRef<HTMLDivElement>(null);

  const handleTextChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    onUpdate(item.id, e.target.value);
  }, [item.id, onUpdate]);

  // Sync scroll between textarea and highlight layer
  const handleScroll = useCallback(() => {
    if (textareaRef.current && highlightRef.current) {
      highlightRef.current.scrollTop = textareaRef.current.scrollTop;
      highlightRef.current.scrollLeft = textareaRef.current.scrollLeft;
    }
  }, []);

  const segments = parseCueSegments(item.fullText);

  const scoreColor = item.score >= 90 ? 'text-emerald-600' : item.score >= 70 ? 'text-amber-600' : 'text-red-500';
  const scoreBg = item.score >= 90 ? 'bg-emerald-50' : item.score >= 70 ? 'bg-amber-50' : 'bg-red-50';

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5 hover:border-slate-300 hover:shadow-sm transition-all duration-200">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <VoiceAvatar voice={voice} fallbackLabel={item.speaker} />
          <span className="text-[11px] text-slate-400 font-mono">
            {formatTime(item.startTime)} - {formatTime(item.endTime)}
          </span>
          <span className="text-[10px] text-slate-400 font-mono">#{item.id}</span>
        </div>
        <div className={`${scoreBg} px-2.5 py-1 rounded-full`}>
          <span className={`text-[11px] font-bold ${scoreColor}`}>{item.score}</span>
        </div>
      </div>

      {/* Backdrop-highlight textarea: CUE + text on same line, CUE highlighted */}
      <div className="relative font-mono text-[13px] leading-relaxed rounded-lg border border-slate-200 bg-slate-50 focus-within:border-indigo-300 focus-within:ring-2 focus-within:ring-indigo-100 transition-all">
        {/* Highlight layer (non-interactive) */}
        <div
          ref={highlightRef}
          className="absolute inset-0 px-3 py-2.5 pointer-events-none overflow-hidden whitespace-pre-wrap break-words select-none z-10"
          aria-hidden="true"
        >
          {segments.map((seg, i) =>
            seg.type === 'cue' ? (
              <span key={i} className="text-[#C2410C] bg-[#FFF7ED] rounded px-0.5">
                {seg.content}
              </span>
            ) : (
              <span key={i} className="text-slate-700">{seg.content}</span>
            )
          )}
        </div>

        {/* Actual textarea for editing */}
        <textarea
          ref={textareaRef}
          value={item.fullText}
          onChange={handleTextChange}
          onScroll={handleScroll}
          className="relative z-20 w-full px-3 py-2.5 bg-transparent text-transparent caret-slate-800 resize-none focus:outline-none"
          rows={2}
          spellCheck={false}
        />
      </div>

      {/* Buttons */}
      <div className="flex items-center gap-2 mt-2.5">
        <button
          onClick={() => onRestore(item.id)}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-medium text-slate-500 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded-lg transition-colors"
        >
          <RotateCcw className="w-3 h-3" /> Original
        </button>
        <button
          type="button"
          onClick={() => onSynthesize(item)}
          disabled={isSynthesizing}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-medium text-white bg-indigo-500 hover:bg-indigo-600 rounded-lg transition-colors disabled:pointer-events-none disabled:opacity-60"
        >
          {isSynthesizing ? <Loader2 className="w-3 h-3 animate-spin" /> : <Volume2 className="w-3 h-3" />}
          Synthesize
        </button>
      </div>
    </div>
  );
}
