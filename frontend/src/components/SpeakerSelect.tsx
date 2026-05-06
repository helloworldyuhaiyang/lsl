import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { VoiceAvatar } from '@/components/VoiceAvatar';
import { getVoiceDisplayName, getVoiceForSpeaker, getVoiceSubtitle } from '@/lib/voice';
import type { SpeakerMapping } from '@/types';
import type { TtsSpeakerItem } from '@/types/api';
import { Users } from 'lucide-react';
import { useI18n } from '@/i18n';

interface SpeakerSelectProps {
  speakers: string[];
  mappings: SpeakerMapping[];
  onMappingChange: (speaker: string, voice: string) => void;
  voices?: TtsSpeakerItem[];
}

export function SpeakerSelect({ speakers, mappings, onMappingChange, voices = [] }: SpeakerSelectProps) {
  const { t, language } = useI18n();
  const getVoiceIdForSpeaker = (speaker: string) => {
    return mappings.find(m => m.speaker === speaker)?.voice || voices[0]?.speaker_id || '';
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Users className="w-4 h-4 text-slate-500" />
        <h4 className="text-[13px] font-semibold text-slate-700">{t('speaker.mapping')}</h4>
      </div>
      <p className="text-[11px] text-slate-500">{t('speaker.mappingHelp')}</p>

      <div className="space-y-2.5">
        {speakers.map(speaker => {
          const selectedVoice = getVoiceForSpeaker(speaker, mappings, voices);
          return (
          <div key={speaker} className="flex min-w-0 items-center gap-2.5 rounded-lg bg-slate-50 p-2.5 sm:gap-3">
            <div className="flex w-8 shrink-0 items-center justify-center">
              <VoiceAvatar voice={selectedVoice} fallbackLabel={speaker} locale={language} />
            </div>
            <Select
              value={getVoiceIdForSpeaker(speaker)}
              onValueChange={(value) => onMappingChange(speaker, value)}
            >
              <SelectTrigger className="h-8 min-w-0 flex-1 overflow-hidden border-slate-200 bg-white text-[12px] [&_[data-slot=select-value]]:min-w-0 [&_[data-slot=select-value]]:truncate">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {voices.map(voice => {
                  const subtitle = getVoiceSubtitle(voice, language);
                  return (
                    <SelectItem key={voice.speaker_id} value={voice.speaker_id} className="text-[12px]">
                      {getVoiceDisplayName(voice, language)}{subtitle ? ` (${subtitle})` : ''}
                    </SelectItem>
                  );
                })}
              </SelectContent>
            </Select>
          </div>
          );
        })}
      </div>
    </div>
  );
}
