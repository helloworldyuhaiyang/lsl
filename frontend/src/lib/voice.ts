import type { SpeakerMapping } from '@/types';
import type { TtsSpeakerItem } from '@/types/api';

const DEFAULT_LOCALE = 'zh-CN';

export function getVoiceDisplayName(voice?: TtsSpeakerItem | null, locale = DEFAULT_LOCALE): string {
  if (!voice) return '';
  return (
    voice.i18n?.[locale]?.name
    || voice.display_name
    || voice.name.replace(/\s+\d+(?:\.\d+)*$/, '').trim()
    || voice.name
  );
}

export function getVoiceSubtitle(voice?: TtsSpeakerItem | null, locale = DEFAULT_LOCALE): string {
  if (!voice) return '';
  const localized = voice.i18n?.[locale];
  const language = localized?.language || voice.language || '';
  const style = localized?.style || voice.style || '';
  return [style, language].filter(Boolean).join(' · ');
}

export function getVoiceForSpeaker(
  speaker: string,
  mappings: SpeakerMapping[],
  voices: TtsSpeakerItem[],
): TtsSpeakerItem | undefined {
  const providerSpeakerId = mappings.find(mapping => mapping.speaker === speaker)?.voice;
  if (!providerSpeakerId) return undefined;
  return voices.find(voice => voice.speaker_id === providerSpeakerId);
}
