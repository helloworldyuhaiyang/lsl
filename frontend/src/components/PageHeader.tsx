import { Link } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';

interface PageHeaderProps {
  label?: string;
  title: string;
  subtitle?: string | React.ReactNode;
  action?: React.ReactNode;
  backTo?: string;
  backLabel?: string;
}

export function PageHeader({ label, title, subtitle, action, backTo, backLabel }: PageHeaderProps) {
  return (
    <div className="space-y-4">
      {backTo && (
        <Link
          to={backTo}
          className="inline-flex items-center gap-1.5 text-[13px] text-[#78716C] hover:text-[#1C1917] transition-colors duration-150"
        >
          <ArrowLeft className="w-4 h-4" />
          {backLabel || 'Back to Dashboard'}
        </Link>
      )}

      <div className="flex items-start justify-between gap-4">
        <div className="space-y-1">
          {label && (
            <p className="text-[11px] font-medium text-[#A8A29E] uppercase tracking-[0.1em]">
              {label}
            </p>
          )}
          <h1 className="text-[28px] font-normal text-[#1C1917] leading-tight tracking-tight">
            {title}
          </h1>
          {subtitle && (
            <p className="text-[15px] text-[#78716C] leading-relaxed pt-1">
              {subtitle}
            </p>
          )}
        </div>
        {action && <div className="flex-shrink-0 pt-1">{action}</div>}
      </div>
    </div>
  );
}
