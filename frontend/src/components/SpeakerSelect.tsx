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

interface SpeakerSelectProps {
  speakers: string[];
  mappings: SpeakerMapping[];
  onMappingChange: (speaker: string, voice: string) => void;
  voices?: TtsSpeakerItem[];
}

export function SpeakerSelect({ speakers, mappings, onMappingChange, voices = [] }: SpeakerSelectProps) {
  const getVoiceIdForSpeaker = (speaker: string) => {
    return mappings.find(m => m.speaker === speaker)?.voice || voices[0]?.speaker_id || '';
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Users className="w-4 h-4 text-slate-500" />
        <h4 className="text-[13px] font-semibold text-slate-700">Speaker Mapping</h4>
      </div>
      <p className="text-[11px] text-slate-500">Map each speaker to a TTS voice</p>

      <div className="space-y-2.5">
        {speakers.map(speaker => {
          const selectedVoice = getVoiceForSpeaker(speaker, mappings, voices);
          return (
          <div key={speaker} className="flex items-center gap-3 bg-slate-50 rounded-lg p-2.5">
            <div className="flex items-center justify-center w-8">
              <VoiceAvatar voice={selectedVoice} fallbackLabel={speaker} />
            </div>
            <Select
              value={getVoiceIdForSpeaker(speaker)}
              onValueChange={(value) => onMappingChange(speaker, value)}
            >
              <SelectTrigger className="flex-1 h-8 text-[12px] border-slate-200 bg-white">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {voices.map(voice => (
                  <SelectItem key={voice.speaker_id} value={voice.speaker_id} className="text-[12px]">
                    {getVoiceDisplayName(voice)}{getVoiceSubtitle(voice) ? ` (${getVoiceSubtitle(voice)})` : ''}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          );
        })}
      </div>
    </div>
  );
}
