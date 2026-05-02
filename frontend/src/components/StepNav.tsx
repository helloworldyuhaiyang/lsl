import { Link } from 'react-router-dom';
import { cn } from '@/lib/utils';

interface Step {
  label: string;
  path: string;
  status: 'current' | 'completed' | 'upcoming';
}

interface StepNavProps {
  steps: Step[];
}

export function StepNav({ steps }: StepNavProps) {
  return (
    <div className="flex items-center justify-center gap-2 py-4">
      {steps.map((step, index) => (
        <div key={step.label} className="flex items-center gap-2">
          <Link
            to={step.path}
            className={cn(
              'flex items-center gap-2 transition-opacity duration-150',
              step.status === 'upcoming' && 'pointer-events-none opacity-60'
            )}
          >
            <span
              className={cn(
                'w-6 h-6 rounded-full flex items-center justify-center text-[11px] font-medium transition-colors duration-200',
                step.status === 'current' && 'bg-[#1C1917] text-white',
                step.status === 'completed' && 'bg-[#10B981] text-white',
                step.status === 'upcoming' && 'bg-[#F5F5F4] text-[#A8A29E]'
              )}
            >
              {index + 1}
            </span>
            <span
              className={cn(
                'text-[13px] transition-colors duration-150',
                step.status === 'current' && 'text-[#1C1917] font-medium',
                step.status === 'completed' && 'text-[#1C1917]',
                step.status === 'upcoming' && 'text-[#A8A29E]'
              )}
            >
              {step.label}
            </span>
          </Link>
          {index < steps.length - 1 && (
            <div
              className={cn(
                'w-8 h-[1px] transition-colors duration-200',
                step.status === 'completed' ? 'bg-[#10B981]' : 'bg-[#E7E5E4]'
              )}
            />
          )}
        </div>
      ))}
    </div>
  );
}
