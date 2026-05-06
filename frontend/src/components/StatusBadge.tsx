import { cn } from '@/lib/utils';
import type { SessionStatus } from '@/types';
import { CheckCircle2, XCircle, Loader2, Clock } from 'lucide-react';
import { useI18n } from '@/i18n';

interface StatusBadgeProps {
  status: SessionStatus;
  showIcon?: boolean;
}

const statusConfig: Record<SessionStatus, { labelKey: 'status.completed' | 'status.failed' | 'status.processing' | 'status.pending'; className: string; icon: React.ElementType }> = {
  completed: {
    labelKey: 'status.completed',
    className: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    icon: CheckCircle2,
  },
  failed: {
    labelKey: 'status.failed',
    className: 'bg-red-50 text-red-700 border-red-200',
    icon: XCircle,
  },
  processing: {
    labelKey: 'status.processing',
    className: 'bg-amber-50 text-amber-700 border-amber-200',
    icon: Loader2,
  },
  pending: {
    labelKey: 'status.pending',
    className: 'bg-slate-100 text-slate-600 border-slate-200',
    icon: Clock,
  },
};

export function StatusBadge({ status, showIcon = true }: StatusBadgeProps) {
  const config = statusConfig[status];
  const Icon = config.icon;
  const { t } = useI18n();

  return (
    <span className={cn(
      'inline-flex max-w-full items-center gap-1 rounded-full border px-2 py-1 text-[10px] font-semibold leading-none whitespace-nowrap sm:gap-1.5 sm:px-2.5 sm:text-[11px]',
      config.className
    )}>
      {showIcon && <Icon className={cn('h-3 w-3 shrink-0', status === 'processing' && 'animate-spin')} />}
      <span className="min-w-0 truncate">{t(config.labelKey)}</span>
    </span>
  );
}
