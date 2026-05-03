import { useState, useCallback, useEffect, useMemo, useRef } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { ArrowLeft, ArrowRight, Sparkles, Loader2, Volume2, Wand2 } from 'lucide-react';
import { RevisionCard } from '@/components/RevisionCard';
import { SpeakerSelect } from '@/components/SpeakerSelect';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Slider } from '@/components/ui/slider';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { useApp } from '@/context/AppContext';
import { ttsVoices } from '@/data/mockData';
import type { RevisionItem, SpeakerMapping } from '@/types';
import type { TtsSpeakerItem } from '@/types/api';
import { NotFound } from './NotFound';
import { getSession } from '@/lib/api/sessions';
import { createRevision, getRevision, updateRevisionItem } from '@/lib/api/revisions';
import { createTtsSynthesis, generateTtsItemAudio, getTtsSettings, getTtsSpeakers, getTtsSynthesis, updateTtsSettings } from '@/lib/api/tts';
import { applyTtsSettings, applyTtsSynthesis, mapRevision, mapSessionItem } from '@/lib/domain';
import { getVoiceForSpeaker } from '@/lib/voice';
import type { TtsSynthesisResponse } from '@/types/api';

const TTS_PARAM_RANGES = {
  emotionScale: { min: 1, max: 5, step: 0.1, defaultValue: 4 },
  speechRate: { min: -50, max: 100, step: 1, defaultValue: 0 },
  loudnessRate: { min: -50, max: 100, step: 1, defaultValue: 0 },
};

function clampTtsParam(value: number, range: { min: number; max: number; step: number; defaultValue: number }): number {
  if (!Number.isFinite(value)) return range.defaultValue;
  const clamped = Math.min(range.max, Math.max(range.min, value));
  return Math.round(clamped / range.step) * range.step;
}

export function Revise() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { getSessionById, dispatch } = useApp();
  const [loadedSession, setLoadedSession] = useState<ReturnType<typeof getSessionById> | null>(null);
  const [notFound, setNotFound] = useState(false);

  const session = useMemo(() => loadedSession || (id ? getSessionById(id) : undefined), [id, getSessionById, loadedSession]);

  const [revision, setRevision] = useState<RevisionItem[]>([]);
  const [userPrompt, setUserPrompt] = useState('');
  const [isRevising, setIsRevising] = useState(false);
  const [isSynthesizing, setIsSynthesizing] = useState(false);
  const [format, setFormat] = useState('mp3');
  const [emotionScale, setEmotionScale] = useState([TTS_PARAM_RANGES.emotionScale.defaultValue]);
  const [speechRate, setSpeechRate] = useState([TTS_PARAM_RANGES.speechRate.defaultValue]);
  const [loudnessRate, setLoudnessRate] = useState([TTS_PARAM_RANGES.loudnessRate.defaultValue]);
  const [speakerMappings, setSpeakerMappings] = useState<SpeakerMapping[]>([]);
  const [voiceList, setVoiceList] = useState<TtsSpeakerItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [synthesizingItemId, setSynthesizingItemId] = useState<string | null>(null);
  const [playingOriginalItemId, setPlayingOriginalItemId] = useState<string | null>(null);
  const itemAudioRef = useRef<HTMLAudioElement | null>(null);
  const itemAudioUrlRef = useRef<string | null>(null);

  useEffect(() => {
    if (session) {
      dispatch({ type: 'SET_CURRENT_SESSION', payload: session });
      const rev = session.revision || [];
      setRevision(rev);
      setUserPrompt(session.userPrompt || '');
      const speakers = [...new Set(rev.map(r => r.speaker))];
      setSpeakerMappings(speakers.map((s, i) => ({
        speaker: s,
        voice: session.speakerMappings?.find(m => m.speaker === s)?.voice
          || (voiceList.length > 0 ? voiceList[i % voiceList.length].speaker_id : ttsVoices[i % ttsVoices.length]),
      })));
    }
  }, [session, dispatch, voiceList]);

  useEffect(() => {
    if (!id) return;
    const sessionId = id;
    let cancelled = false;

    async function loadRevision() {
      setNotFound(false);
      setError(null);
      try {
        const item = await getSession(sessionId);
        let nextSession = mapSessionItem(item);
        try {
          const revisionData = await getRevision(sessionId);
          nextSession = { ...nextSession, revision: mapRevision(revisionData), userPrompt: revisionData.user_prompt ?? undefined };
        } catch {
          // The user can create revision data from this page.
        }
        try {
          const settings = await getTtsSettings(sessionId);
          nextSession = applyTtsSettings(nextSession, settings);
          setFormat(settings.format);
          setEmotionScale([clampTtsParam(settings.emotion_scale, TTS_PARAM_RANGES.emotionScale)]);
          setSpeechRate([clampTtsParam(settings.speech_rate, TTS_PARAM_RANGES.speechRate)]);
          setLoudnessRate([clampTtsParam(settings.loudness_rate, TTS_PARAM_RANGES.loudnessRate)]);
        } catch {
          // Settings are optional until created.
        }
        if (!cancelled) {
          setLoadedSession(nextSession);
          dispatch({ type: 'UPDATE_SESSION', payload: nextSession });
        }
      } catch {
        if (!cancelled) setNotFound(true);
      }
    }

    async function loadVoices() {
      try {
        const data = await getTtsSpeakers();
        if (!cancelled && data.items.length > 0) {
          setVoiceList(data.items);
        }
      } catch {
        // Keep bundled voice list as fallback.
      }
    }

    void loadRevision();
    void loadVoices();
    return () => {
      cancelled = true;
    };
  }, [id, dispatch]);

  useEffect(() => {
    return () => {
      if (itemAudioRef.current) {
        itemAudioRef.current.pause();
      }
      if (itemAudioUrlRef.current) {
        URL.revokeObjectURL(itemAudioUrlRef.current);
      }
    };
  }, []);

  const handleUpdateRevision = useCallback((itemId: string, fullText: string) => {
    setRevision(prev => prev.map(item => item.id === itemId ? { ...item, fullText } : item));
    void updateRevisionItem(itemId, { draftText: fullText }).catch((err) => {
      setError(err instanceof Error ? err.message : 'Failed to save revision item');
    });
  }, []);

  const handleReviseByAI = useCallback(async () => {
    if (!id) return;
    setIsRevising(true);
    setError(null);
    try {
      const data = await createRevision({ sessionId: id, userPrompt, force: true });
      const nextRevision = mapRevision(data);
      setRevision(nextRevision);
      if (session) {
        dispatch({ type: 'UPDATE_SESSION', payload: { ...session, revision: nextRevision, userPrompt } });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to revise session');
    } finally {
      setIsRevising(false);
    }
  }, [id, userPrompt, session, dispatch]);

  // Ensure speaker mappings use valid speaker_ids after voices are loaded
  useEffect(() => {
    if (voiceList.length === 0) return;

    const validIds = new Set(voiceList.map(v => v.speaker_id));
    const nameToId = new Map(voiceList.map(v => [v.name, v.speaker_id]));

    setSpeakerMappings(prev => {
      let changed = false;
      const updated = prev.map(m => {
        if (validIds.has(m.voice)) return m;
        const idFromName = nameToId.get(m.voice);
        if (idFromName) {
          changed = true;
          return { ...m, voice: idFromName };
        }
        changed = true;
        return { ...m, voice: voiceList[0].speaker_id };
      });
      return changed ? updated : prev;
    });
  }, [voiceList]);

  const handleSynthesize = useCallback(async () => {
    if (!id) return;
    setIsSynthesizing(true);
    setError(null);
    try {
      await updateTtsSettings({
        sessionId: id,
        format,
        emotionScale: emotionScale[0],
        speechRate: speechRate[0],
        loudnessRate: loudnessRate[0],
        speakerMappings: speakerMappings.map((mapping) => ({
          conversation_speaker: mapping.speaker,
          provider_speaker_id: mapping.voice,
        })),
      });

      let synthesis = await createTtsSynthesis({ sessionId: id });

      for (let attempt = 0; attempt < 40 && isSynthesisRunning(synthesis); attempt += 1) {
        await wait(1500);
        synthesis = await getTtsSynthesis(id);
      }

      if (synthesis.status_name === 'failed') {
        throw new Error(synthesis.error_message || 'Failed to synthesize audio');
      }

      if (synthesis.full_asset_url && session) {
        const nextSession = applyTtsSynthesis(session, synthesis);
        setLoadedSession(nextSession);
        dispatch({ type: 'UPDATE_SESSION', payload: nextSession });
        navigate(`/session/${session.id}/listening`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to synthesize audio');
    } finally {
      setIsSynthesizing(false);
    }
  }, [id, format, emotionScale, speechRate, loudnessRate, speakerMappings, session, dispatch, navigate]);

  const stopItemAudio = useCallback(() => {
    if (itemAudioRef.current) {
      itemAudioRef.current.pause();
      itemAudioRef.current = null;
    }
    if (itemAudioUrlRef.current) {
      URL.revokeObjectURL(itemAudioUrlRef.current);
      itemAudioUrlRef.current = null;
    }
  }, []);

  const playAudio = useCallback((
    audio: HTMLAudioElement,
    options: {
      startTime?: number;
      endTime?: number;
      objectUrl?: string;
      onFinish?: () => void;
    } = {},
  ) => {
    stopItemAudio();

    itemAudioRef.current = audio;
    itemAudioUrlRef.current = options.objectUrl ?? null;

    const finish = () => {
      options.onFinish?.();
    };
    const stopAtEndTime = () => {
      if (options.endTime !== undefined && audio.currentTime >= options.endTime) {
        audio.pause();
        finish();
        audio.removeEventListener('timeupdate', stopAtEndTime);
      }
    };
    const startPlayback = () => {
      audio.currentTime = Math.max(0, options.startTime ?? 0);
      void audio.play().catch((err) => {
        finish();
        setError(err instanceof Error ? err.message : 'Failed to play audio');
      });
    };

    audio.addEventListener('timeupdate', stopAtEndTime);
    audio.addEventListener('ended', finish, { once: true });
    audio.addEventListener('error', finish, { once: true });

    if (audio.readyState >= HTMLMediaElement.HAVE_METADATA) {
      startPlayback();
    } else {
      audio.addEventListener('loadedmetadata', startPlayback, { once: true });
      audio.load();
    }
  }, [stopItemAudio]);

  const prepareItemTtsSettings = useCallback(async () => {
    if (!id) return;

    await updateTtsSettings({
      sessionId: id,
      format,
      emotionScale: emotionScale[0],
      speechRate: speechRate[0],
      loudnessRate: loudnessRate[0],
      speakerMappings: speakerMappings.map((mapping) => ({
        conversation_speaker: mapping.speaker,
        provider_speaker_id: mapping.voice,
      })),
    });
  }, [id, format, emotionScale, speechRate, loudnessRate, speakerMappings]);

  const handlePlayOriginal = useCallback(async (item: RevisionItem) => {
    if (!id) return;
    setError(null);
    setPlayingOriginalItemId(item.id);

    if (session?.audioUrl) {
      playAudio(new Audio(session.audioUrl), {
        startTime: item.startTime,
        endTime: item.endTime,
        onFinish: () => setPlayingOriginalItemId((current) => current === item.id ? null : current),
      });
      return;
    }

    try {
      await prepareItemTtsSettings();
      const audioBlob = await generateTtsItemAudio({
        itemId: item.id,
        sessionId: id,
        content: item.originalText,
      });
      const audioUrl = URL.createObjectURL(audioBlob);
      playAudio(new Audio(audioUrl), {
        objectUrl: audioUrl,
        onFinish: () => setPlayingOriginalItemId((current) => current === item.id ? null : current),
      });
    } catch (err) {
      setPlayingOriginalItemId(null);
      setError(err instanceof Error ? err.message : 'Failed to play original item');
    }
  }, [id, session?.audioUrl, playAudio, prepareItemTtsSettings]);

  const handleSynthesizeItem = useCallback(async (item: RevisionItem) => {
    if (!id) return;
    setSynthesizingItemId(item.id);
    setPlayingOriginalItemId(null);
    setError(null);
    try {
      await updateTtsSettings({
        sessionId: id,
        format,
        emotionScale: emotionScale[0],
        speechRate: speechRate[0],
        loudnessRate: loudnessRate[0],
        speakerMappings: speakerMappings.map((mapping) => ({
          conversation_speaker: mapping.speaker,
          provider_speaker_id: mapping.voice,
        })),
      });

      const audioBlob = await generateTtsItemAudio({
        itemId: item.id,
        sessionId: id,
        content: item.fullText,
      });

      const audioUrl = URL.createObjectURL(audioBlob);
      playAudio(new Audio(audioUrl), { objectUrl: audioUrl });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to synthesize item audio');
    } finally {
      setSynthesizingItemId(null);
    }
  }, [id, format, emotionScale, speechRate, loudnessRate, speakerMappings, playAudio]);

  const handleMappingChange = useCallback((speaker: string, voice: string) => {
    setSpeakerMappings(prev => prev.map(m => m.speaker === speaker ? { ...m, voice } : m));
  }, []);

  const speakers = useMemo(() => [...new Set(revision.map(r => r.speaker))], [revision]);

  if (!session && !notFound) {
    return <div className="text-[13px] text-slate-500">Loading revision...</div>;
  }

  if (!session) return <NotFound />;

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <div className="flex items-center justify-between">
        <Link to={`/session/${session.id}`} className="inline-flex items-center gap-1.5 text-[12px] text-slate-500 hover:text-indigo-600 transition-colors">
          <ArrowLeft className="w-3.5 h-3.5" />
          Session
        </Link>
        <Link to={`/session/${session.id}/listening`} className="inline-flex items-center gap-1.5 text-[12px] text-indigo-600 hover:text-indigo-700 transition-colors font-medium">
          Listening <ArrowRight className="w-3.5 h-3.5" />
        </Link>
      </div>

      {/* Header */}
      <div>
        <div className="flex items-center gap-2 mb-1">
          <span className="text-[10px] font-bold text-indigo-500 uppercase tracking-wider">Step 2</span>
        </div>
        <h1 className="text-[22px] font-bold text-slate-900 tracking-tight">Revise</h1>
        <p className="text-[13px] text-slate-500 mt-0.5">{revision.length} utterances ready for revision</p>
      </div>

      {/* AI Revise */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
        <div className="flex items-center gap-2 mb-3">
          <Wand2 className="w-4 h-4 text-indigo-500" />
          <h3 className="text-[13px] font-bold text-slate-800">AI Revise</h3>
        </div>
        <p className="text-[12px] text-slate-500 mb-3">Add a prompt to guide the AI in generating improved rewrites.</p>
        <div className="flex gap-3">
          <Textarea
            value={userPrompt}
            onChange={(e) => setUserPrompt(e.target.value)}
            placeholder="Optional prompt for AI..."
            className="flex-1 text-[13px] border-slate-200 resize-none"
            rows={2}
          />
          <Button
            onClick={handleReviseByAI}
            disabled={isRevising}
            className="bg-indigo-500 hover:bg-indigo-600 text-white h-auto px-5 disabled:opacity-60"
          >
            {isRevising ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
          </Button>
        </div>
      </div>

      {/* TTS Settings */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Volume2 className="w-4 h-4 text-indigo-500" />
            <h3 className="text-[13px] font-bold text-slate-800">TTS Settings</h3>
          </div>
          <span className="text-[10px] text-slate-400">{voiceList.length > 0 ? voiceList.length : ttsVoices.length} voices</span>
        </div>

        <Button
          onClick={handleSynthesize}
          disabled={isSynthesizing}
          className="w-full bg-indigo-500 hover:bg-indigo-600 text-white h-10 text-[12px] font-semibold mb-5 disabled:opacity-60"
        >
          {isSynthesizing ? (
            <span className="flex items-center gap-2"><Loader2 className="w-4 h-4 animate-spin" /> Synthesizing...</span>
          ) : (
            <span className="flex items-center gap-2"><Volume2 className="w-4 h-4" /> Synthesize All</span>
          )}
        </Button>

        <div className="grid grid-cols-2 gap-4 mb-5">
          <div>
            <Label className="text-[11px] font-semibold text-slate-600 mb-1.5 block">Format</Label>
            <Select value={format} onValueChange={setFormat}>
              <SelectTrigger className="h-9 text-[12px] border-slate-200"><SelectValue /></SelectTrigger>
              <SelectContent><SelectItem value="mp3">mp3</SelectItem><SelectItem value="wav">wav</SelectItem></SelectContent>
            </Select>
          </div>
          <div>
            <div className="flex justify-between mb-1"><Label className="text-[11px] font-semibold text-slate-600">Emotion</Label><span className="text-[10px] text-slate-400">{emotionScale[0].toFixed(1)}</span></div>
            <Slider value={emotionScale} onValueChange={setEmotionScale} min={TTS_PARAM_RANGES.emotionScale.min} max={TTS_PARAM_RANGES.emotionScale.max} step={TTS_PARAM_RANGES.emotionScale.step} />
          </div>
          <div>
            <div className="flex justify-between mb-1"><Label className="text-[11px] font-semibold text-slate-600">Speech Rate</Label><span className="text-[10px] text-slate-400">{speechRate[0]}</span></div>
            <Slider value={speechRate} onValueChange={setSpeechRate} min={TTS_PARAM_RANGES.speechRate.min} max={TTS_PARAM_RANGES.speechRate.max} step={TTS_PARAM_RANGES.speechRate.step} />
          </div>
          <div>
            <div className="flex justify-between mb-1"><Label className="text-[11px] font-semibold text-slate-600">Loudness</Label><span className="text-[10px] text-slate-400">{loudnessRate[0]}</span></div>
            <Slider value={loudnessRate} onValueChange={setLoudnessRate} min={TTS_PARAM_RANGES.loudnessRate.min} max={TTS_PARAM_RANGES.loudnessRate.max} step={TTS_PARAM_RANGES.loudnessRate.step} />
          </div>
        </div>

        <SpeakerSelect speakers={speakers} mappings={speakerMappings} onMappingChange={handleMappingChange} voices={voiceList} />
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-[13px] text-red-700">
          {error}
        </div>
      )}

      {/* Revision Cards */}
      <div>
        {revision.length > 0 ? revision.map(item => (
          <RevisionCard
            key={item.id}
            item={item}
            voice={getVoiceForSpeaker(item.speaker, speakerMappings, voiceList)}
            onUpdate={handleUpdateRevision}
            onPlayOriginal={handlePlayOriginal}
            onSynthesize={handleSynthesizeItem}
            isPlayingOriginal={playingOriginalItemId === item.id}
            isSynthesizing={synthesizingItemId === item.id}
          />
        )) : (
          <div className="bg-white rounded-xl border border-slate-200 p-12 text-center">
            <p className="text-[13px] text-slate-400">No revision data available.</p>
          </div>
        )}
      </div>
    </div>
  );
}

function wait(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function isSynthesisRunning(synthesis: TtsSynthesisResponse): boolean {
  return synthesis.status_name === 'pending' || synthesis.status_name === 'generating';
}
