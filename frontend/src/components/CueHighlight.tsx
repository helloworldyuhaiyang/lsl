import { parseCueText } from '@/utils/cueParser';

interface CueHighlightProps {
  text: string;
  className?: string;
}

export function CueHighlight({ text, className = '' }: CueHighlightProps) {
  const result = parseCueText(text);

  if (!result.cue) {
    return <span className={className}>{text}</span>;
  }

  return (
    <span className={className}>
      <span className="font-mono text-[12px] bg-amber-50 text-amber-700 border border-amber-200 rounded-md px-2 py-0.5 mr-1.5 font-medium">
        [{result.cue}]
      </span>
      <span className="text-slate-700">{result.content}</span>
    </span>
  );
}
