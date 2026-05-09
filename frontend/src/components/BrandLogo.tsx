import type { SVGProps } from 'react';
import { cn } from '@/lib/utils';

type BrandMarkTone = 'ink' | 'paper' | 'mono';

type BrandMarkProps = Omit<SVGProps<SVGSVGElement>, 'color'> & {
  title?: string;
  tone?: BrandMarkTone;
};

const palettes = {
  ink: {
    surface: '#111827',
    bracket: '#F8F3E8',
    wave: '#D97706',
  },
  paper: {
    surface: '#F8F3E8',
    bracket: '#111827',
    wave: '#B45309',
  },
  mono: {
    surface: 'currentColor',
    bracket: '#FFFFFF',
    wave: '#FFFFFF',
  },
} as const;

export function BrandMark({ className, title, tone = 'ink', ...props }: BrandMarkProps) {
  const palette = palettes[tone];

  return (
    <svg
      viewBox="0 0 48 48"
      fill="none"
      className={cn('shrink-0', className)}
      role={title ? 'img' : undefined}
      aria-label={title}
      aria-hidden={title ? undefined : true}
      {...props}
    >
      {title ? <title>{title}</title> : null}
      <rect width="48" height="48" rx="10" fill={palette.surface} />
      <path
        d="M19 12H13V36H19"
        stroke={palette.bracket}
        strokeWidth="3.2"
        strokeLinecap="round"
        strokeLinejoin="round"
        vectorEffect="non-scaling-stroke"
      />
      <path
        d="M29 12H35V36H29"
        stroke={palette.bracket}
        strokeWidth="3.2"
        strokeLinecap="round"
        strokeLinejoin="round"
        vectorEffect="non-scaling-stroke"
      />
      <path
        d="M18 24C20.3 17.9 23.5 17.9 25 24C26.5 30.1 29.7 30.1 32 24"
        stroke={palette.wave}
        strokeWidth="3.6"
        strokeLinecap="round"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}

type BrandWordmarkProps = {
  className?: string;
  markClassName?: string;
  sublabel?: string;
  sublabelClassName?: string;
  textClassName?: string;
  tone?: BrandMarkTone;
};

export function BrandWordmark({
  className,
  markClassName,
  sublabel,
  sublabelClassName,
  textClassName,
  tone = 'ink',
}: BrandWordmarkProps) {
  return (
    <div className={cn('flex items-center gap-2.5', className)}>
      <BrandMark className={cn('h-8 w-8', markClassName)} tone={tone} />
      <div className="min-w-0">
        <div className={cn('text-[15px] font-bold leading-none tracking-tight', textClassName)}>
          LSL
        </div>
        {sublabel ? (
          <div className={cn('mt-1 text-[10px] font-semibold uppercase tracking-widest', sublabelClassName)}>
            {sublabel}
          </div>
        ) : null}
      </div>
    </div>
  );
}
