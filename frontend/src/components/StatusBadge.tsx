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
      'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold border',
      config.className
    )}>
      {showIcon && <Icon className={cn('w-3 h-3', status === 'processing' && 'animate-spin')} />}
      {t(config.labelKey)}
    </span>
  );
}
