import { cn } from '@/lib/utils'

interface TranslationLineProps {
  text?: string | null
  stale?: boolean
  className?: string
}

export function TranslationLine({ text, stale = false, className }: TranslationLineProps) {
  if (!text) return null
  return (
    <p className={cn('mt-1.5 text-[12px] leading-relaxed text-slate-500', stale && 'text-amber-700', className)}>
      {text}
    </p>
  )
}
