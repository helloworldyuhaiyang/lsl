import { Languages, Loader2, RefreshCw } from 'lucide-react'
import { cn } from '@/lib/utils'

interface TranslationButtonProps {
  active?: boolean
  isTranslating?: boolean
  needsUpdate?: boolean
  failed?: boolean
  disabled?: boolean
  onClick: () => void
  className?: string
}

export function TranslationButton({
  active = false,
  isTranslating = false,
  needsUpdate = false,
  failed = false,
  disabled = false,
  onClick,
  className,
}: TranslationButtonProps) {
  const icon = isTranslating
    ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
    : needsUpdate || failed
      ? <RefreshCw className="h-3.5 w-3.5" />
      : <Languages className="h-3.5 w-3.5" />
  const label = isTranslating ? '翻译中' : failed ? '重试翻译' : needsUpdate ? '更新译文' : '译'

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled || isTranslating}
      className={cn(
        'inline-flex h-8 items-center gap-1.5 rounded-lg border px-2.5 text-[11px] font-semibold transition-colors disabled:pointer-events-none disabled:opacity-60',
        active
          ? 'border-indigo-200 bg-indigo-50 text-indigo-700'
          : 'border-slate-200 bg-white text-slate-500 hover:bg-slate-50 hover:text-slate-700',
        className
      )}
    >
      {icon}
      {label}
    </button>
  )
}
