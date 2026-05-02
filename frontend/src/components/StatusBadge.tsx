import { cn } from '@/lib/utils';
import type { SessionStatus } from '@/types';
import { CheckCircle2, XCircle, Loader2, Clock } from 'lucide-react';

interface StatusBadgeProps {
  status: SessionStatus;
  showIcon?: boolean;
}

const statusConfig: Record<SessionStatus, { label: string; className: string; icon: React.ElementType }> = {
  completed: {
    label: 'Completed',
    className: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    icon: CheckCircle2,
  },
  failed: {
    label: 'Failed',
    className: 'bg-red-50 text-red-700 border-red-200',
    icon: XCircle,
  },
  processing: {
    label: 'Processing',
    className: 'bg-amber-50 text-amber-700 border-amber-200',
    icon: Loader2,
  },
  pending: {
    label: 'Pending',
    className: 'bg-slate-100 text-slate-600 border-slate-200',
    icon: Clock,
  },
};

export function StatusBadge({ status, showIcon = true }: StatusBadgeProps) {
  const config = statusConfig[status];
  const Icon = config.icon;

  return (
    <span className={cn(
      'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold border',
      config.className
    )}>
      {showIcon && <Icon className={cn('w-3 h-3', status === 'processing' && 'animate-spin')} />}
      {config.label}
    </span>
  );
}
