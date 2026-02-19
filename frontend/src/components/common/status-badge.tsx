import { cn } from '@/lib/utils'
import type { TaskStatus } from '@/types/domain'

const STATUS_STYLE: Record<TaskStatus, string> = {
  uploaded: 'bg-slate-200 text-slate-700',
  transcribing: 'bg-cyan-100 text-cyan-700',
  analyzing: 'bg-amber-100 text-amber-700',
  completed: 'bg-emerald-100 text-emerald-700',
  failed: 'bg-rose-100 text-rose-700',
}

interface StatusBadgeProps {
  status: TaskStatus
}

export function StatusBadge({ status }: StatusBadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex rounded-full px-2.5 py-1 text-xs font-medium capitalize tracking-wide',
        STATUS_STYLE[status],
      )}
    >
      {status}
    </span>
  )
}
