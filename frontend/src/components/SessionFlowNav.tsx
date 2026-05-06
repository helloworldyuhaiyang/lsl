import { Link } from 'react-router-dom';
import { ArrowLeft, ArrowRight, Lock } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useI18n } from '@/i18n';

type SessionFlowStep = 'overview' | 'revise' | 'listen';

interface SessionFlowNavProps {
  sessionId: string;
  currentStep: SessionFlowStep;
  canRevise: boolean;
  canListen: boolean;
  className?: string;
}

export function SessionFlowNav({
  sessionId,
  currentStep,
  canRevise,
  canListen,
  className,
}: SessionFlowNavProps) {
  const { t } = useI18n();
  const steps: Array<{ id: SessionFlowStep; label: string; path: string; enabled: boolean }> = [
    { id: 'overview', label: t('sessionFlow.overview'), path: `/session/${sessionId}`, enabled: true },
    { id: 'revise', label: t('sessionFlow.revise'), path: `/session/${sessionId}/revise`, enabled: canRevise },
    { id: 'listen', label: t('sessionFlow.listen'), path: `/session/${sessionId}/listening`, enabled: canListen },
  ];

  return (
    <nav className={cn('space-y-3 sm:flex sm:items-center sm:justify-between sm:gap-4 sm:space-y-0', className)} aria-label={t('sessionFlow.label')}>
      <Link
        to="/"
        className="inline-flex shrink-0 items-center gap-1.5 text-[12px] font-medium text-slate-500 transition-colors hover:text-indigo-600"
      >
        <ArrowLeft className="h-3.5 w-3.5" />
        {t('sessionFlow.backToSessions')}
      </Link>

      <div className="rounded-xl border border-indigo-100 bg-white p-2 shadow-sm shadow-indigo-50 sm:rounded-lg sm:p-1.5">
        <div className="grid w-full grid-cols-3 gap-1.5 sm:mx-auto sm:flex sm:w-max sm:gap-2">
          {steps.map((step, index) => {
            const isCurrent = step.id === currentStep;
            const stepContent = (
              <>
                <span
                  className={cn(
                    'flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[10px] font-bold',
                    isCurrent
                      ? 'bg-white text-indigo-600'
                      : step.enabled
                        ? 'bg-indigo-100 text-indigo-700'
                        : 'bg-slate-100 text-slate-400',
                  )}
                >
                  {index + 1}
                </span>
                <span className="min-w-0 truncate">{step.label}</span>
                {step.enabled && !isCurrent && (
                  <ArrowRight className="h-3.5 w-3.5 shrink-0 opacity-70 transition-transform group-hover:translate-x-0.5" />
                )}
                {!step.enabled && <Lock className="h-3.5 w-3.5 shrink-0 opacity-70" />}
              </>
            );
            const stepClassName = cn(
              'group flex h-10 min-w-0 items-center justify-center gap-1.5 rounded-lg border px-1.5 text-[11px] font-semibold transition-all sm:h-9 sm:min-w-[7.25rem] sm:gap-2 sm:px-3 sm:text-[12px]',
              isCurrent
                ? 'border-indigo-500 bg-indigo-500 text-white shadow-sm shadow-indigo-200'
                : step.enabled
                  ? 'border-indigo-200 bg-indigo-50 text-indigo-700 shadow-sm shadow-indigo-100 hover:border-indigo-300 hover:bg-indigo-100 hover:shadow-md'
                  : 'cursor-not-allowed border-slate-100 bg-slate-50 text-slate-400',
            );

            return step.enabled ? (
              <Link
                key={step.id}
                to={step.path}
                aria-current={isCurrent ? 'step' : undefined}
                className={stepClassName}
              >
                {stepContent}
              </Link>
            ) : (
              <span key={step.id} className={stepClassName} aria-disabled="true">
                {stepContent}
              </span>
            );
          })}
        </div>
      </div>
    </nav>
  );
}
