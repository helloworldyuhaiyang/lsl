import type { TtsSpeakerItem } from '@/types/api';
import { getVoiceDisplayName, getVoiceSubtitle } from '@/lib/voice';
import { cn } from '@/lib/utils';

interface VoiceAvatarProps {
  voice?: TtsSpeakerItem | null;
  fallbackLabel?: string;
  className?: string;
  locale?: string;
}

export function VoiceAvatar({ voice, fallbackLabel = '?', className, locale }: VoiceAvatarProps) {
  const label = getVoiceDisplayName(voice, locale) || fallbackLabel;
  const title = [label, getVoiceSubtitle(voice, locale)].filter(Boolean).join(' - ');
  const color = voice?.avatar?.color || '#94A3B8';
  const initials = voice?.avatar?.initials || Array.from(label).slice(0, 2).join('');

  if (voice?.avatar?.url) {
    return (
      <img
        src={voice.avatar.url}
        alt={label}
        title={title}
        className={cn('h-7 w-7 rounded-full border border-white object-cover shadow-sm', className)}
      />
    );
  }

  return (
    <span
      title={title}
      aria-label={label}
      className={cn(
        'inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-white text-[10px] font-bold text-white shadow-sm',
        className,
      )}
      style={{ backgroundColor: color }}
    >
      {initials}
    </span>
  );
}
