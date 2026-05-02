import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Play, Pause, SkipBack, SkipForward, ArrowLeft, ChevronDown } from 'lucide-react';
import { formatTime } from '@/utils/formatTime';
import { useApp } from '@/context/AppContext';
import type { RevisionItem, SpeakerMapping } from '@/types';
import type { TtsSpeakerItem } from '@/types/api';
import { VoiceAvatar } from '@/components/VoiceAvatar';
import { NotFound } from './NotFound';
import { parseCueText } from '@/utils/cueParser';
import { cn } from '@/lib/utils';
import { getSession } from '@/lib/api/sessions';
import { getRevision } from '@/lib/api/revisions';
import { getTtsSettings, getTtsSpeakers, getTtsSynthesis } from '@/lib/api/tts';
import { applyTtsSynthesis, mapRevision, mapSessionItem } from '@/lib/domain';
import { getVoiceForSpeaker } from '@/lib/voice';

function MobileSubtitleCard({
  item, index, isActive, voice, onClick,
}: {
  item: RevisionItem;
  index: number;
  isActive: boolean;
  voice?: TtsSpeakerItem;
  onClick: (time: number) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const parsed = parseCueText(item.fullText);
  const cardRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isActive && cardRef.current) {
      cardRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }, [isActive]);

  return (
    <div
      ref={cardRef}
      onClick={() => { onClick(item.startTime); setExpanded(!expanded); }}
      className={cn(
        'bg-white rounded-xl border p-3.5 cursor-pointer transition-all duration-300 select-none',
        isActive
          ? 'border-indigo-300 ring-1 ring-indigo-200 shadow-md shadow-indigo-100'
          : 'border-slate-200'
      )}
    >
      <div className="flex items-center gap-2">
        <span className="text-[11px] font-bold text-slate-500">{index + 1}</span>
        <VoiceAvatar voice={voice} fallbackLabel={item.speaker} className="h-6 w-6 text-[9px]" />
        <span className="text-[10px] text-slate-400 font-mono ml-auto">
          {formatTime(item.startTime)}
        </span>
        <ChevronDown className={cn('w-3 h-3 text-slate-400 transition-transform', expanded && 'rotate-180')} />
      </div>

      {expanded && (
        <div className="mt-2 pt-2 border-t border-slate-100 animate-in fade-in slide-in-from-top-1 duration-200">
          {parsed.cue && (
            <span className="inline-block font-mono text-[11px] bg-amber-50 text-amber-700 border border-amber-200 rounded-md px-1.5 py-0.5 font-medium mb-1">
              [{parsed.cue}]
            </span>
          )}
          <p className="text-[14px] text-slate-700 leading-relaxed">{parsed.content}</p>
        </div>
      )}

      {!expanded && isActive && (
        <p className="text-[12px] text-indigo-500 mt-1 font-medium truncate">
          {parsed.content}
        </p>
      )}
    </div>
  );
}

export function Listening() {
  const { id } = useParams<{ id: string }>();
  const { getSessionById, dispatch } = useApp();
  const [loadedSession, setLoadedSession] = useState<ReturnType<typeof getSessionById> | null>(null);
  const [notFound, setNotFound] = useState(false);

  const session = useMemo(() => loadedSession || (id ? getSessionById(id) : undefined), [id, getSessionById, loadedSession]);

  const [revision, setRevision] = useState<RevisionItem[]>([]);
  const [currentTime, setCurrentTime] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackRate, setPlaybackRate] = useState(1);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [speakerMappings, setSpeakerMappings] = useState<SpeakerMapping[]>([]);
  const [voiceList, setVoiceList] = useState<TtsSpeakerItem[]>([]);

  const audioRef = useRef<HTMLAudioElement | null>(null);

  const duration = useMemo(() => {
    if (audioRef.current && audioRef.current.duration && Number.isFinite(audioRef.current.duration)) {
      return audioRef.current.duration;
    }
    return revision.length > 0 ? revision[revision.length - 1].endTime : 0;
  }, [revision, currentTime]);

  const audioUrl = session?.synthesizedAudioUrl || session?.audioUrl;

  useEffect(() => {
    if (session) {
      dispatch({ type: 'SET_CURRENT_SESSION', payload: session });
      setRevision(session.revision || []);
    }
  }, [session, dispatch]);

  useEffect(() => {
    if (!id) return;
    const sessionId = id;
    let cancelled = false;

    async function loadListeningData() {
      setNotFound(false);
      try {
        const item = await getSession(sessionId);
        let nextSession = mapSessionItem(item);
        let nextSpeakerMappings: SpeakerMapping[] = [];
        let nextVoiceList: TtsSpeakerItem[] = [];
        try {
          const revisionData = await getRevision(sessionId);
          nextSession = { ...nextSession, revision: mapRevision(revisionData), userPrompt: revisionData.user_prompt ?? undefined };
        } catch {
          // Revision must exist before listening practice has subtitles.
        }
        try {
          const synthesis = await getTtsSynthesis(sessionId);
          nextSession = applyTtsSynthesis(nextSession, synthesis);
        } catch {
          // Audio synthesis is optional; the page can still show timed subtitles.
        }
        try {
          const settings = await getTtsSettings(sessionId);
          nextSpeakerMappings = settings.speaker_mappings.map((mapping) => ({
            speaker: mapping.conversation_speaker,
            voice: mapping.provider_speaker_id,
          }));
        } catch {
          // Speaker mapping is optional for sessions without TTS settings.
        }
        try {
          const speakers = await getTtsSpeakers();
          nextVoiceList = speakers.items;
        } catch {
          // Keep subtitles usable even if provider metadata is unavailable.
        }
        if (!cancelled) {
          setLoadedSession(nextSession);
          setSpeakerMappings(nextSpeakerMappings);
          setVoiceList(nextVoiceList);
          dispatch({ type: 'UPDATE_SESSION', payload: nextSession });
        }
      } catch {
        if (!cancelled) setNotFound(true);
      }
    }

    void loadListeningData();
    return () => {
      cancelled = true;
    };
  }, [id, dispatch]);

  // Sync audio source when URL changes
  useEffect(() => {
    const audio = audioRef.current;
    if (audio && audioUrl) {
      audio.src = audioUrl;
      audio.load();
      setCurrentTime(0);
      setIsPlaying(false);
    }
  }, [audioUrl]);

  // Sync playback rate
  useEffect(() => {
    if (audioRef.current) {
      audioRef.current.playbackRate = playbackRate;
    }
  }, [playbackRate]);

  const togglePlay = useCallback(() => {
    const audio = audioRef.current;
    if (!audio) return;

    if (isPlaying) {
      audio.pause();
      setIsPlaying(false);
    } else {
      if (audio.ended || audio.currentTime >= audio.duration) {
        audio.currentTime = 0;
      }
      audio.play().catch(() => {
        // Ignore autoplay restrictions
      });
      setIsPlaying(true);
    }
  }, [isPlaying]);

  const handleSeek = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const time = Number(e.target.value);
    if (audioRef.current) {
      audioRef.current.currentTime = time;
    }
    setCurrentTime(time);
  }, []);

  const skip = useCallback((delta: number) => {
    if (audioRef.current) {
      const next = Math.min(Math.max(audioRef.current.currentTime + delta, 0), audioRef.current.duration || duration);
      audioRef.current.currentTime = next;
      setCurrentTime(next);
    }
  }, [duration]);

  const handleSentenceClick = useCallback((time: number) => {
    if (audioRef.current) {
      audioRef.current.currentTime = time;
      setCurrentTime(time);
      audioRef.current.play().catch(() => {
        // Ignore autoplay restrictions
      });
      setIsPlaying(true);
    }
  }, []);

  // Keep UI currentTime and active index in sync with audio
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    const onTimeUpdate = () => {
      setCurrentTime(audio.currentTime);
      const idx = revision.findIndex(item => audio.currentTime >= item.startTime && audio.currentTime < item.endTime);
      if (idx !== -1) setActiveIndex(idx);
    };

    const onEnded = () => {
      setIsPlaying(false);
    };

    const onPlay = () => setIsPlaying(true);
    const onPause = () => setIsPlaying(false);

    audio.addEventListener('timeupdate', onTimeUpdate);
    audio.addEventListener('ended', onEnded);
    audio.addEventListener('play', onPlay);
    audio.addEventListener('pause', onPause);

    return () => {
      audio.removeEventListener('timeupdate', onTimeUpdate);
      audio.removeEventListener('ended', onEnded);
      audio.removeEventListener('play', onPlay);
      audio.removeEventListener('pause', onPause);
    };
  }, [revision]);

  if (!session && !notFound) {
    return <div className="text-[13px] text-slate-500">Loading listening practice...</div>;
  }

  if (!session) return <NotFound />;

  return (
    <div className="sm:space-y-6 space-y-4 pb-28 sm:pb-0">
      {/* Hidden audio element */}
      <audio ref={audioRef} preload="metadata" />

      {/* Breadcrumb */}
      <Link to={`/session/${session.id}/revise`} className="inline-flex items-center gap-1.5 text-[12px] text-slate-500 hover:text-indigo-600 transition-colors">
        <ArrowLeft className="w-3.5 h-3.5" />
        Revise
      </Link>

      {/* Header - hidden on mobile to save space */}
      <div className="hidden sm:block">
        <span className="text-[10px] font-bold text-indigo-500 uppercase tracking-wider">Step 3</span>
        <h1 className="text-[22px] font-bold text-slate-900 tracking-tight mt-1">Listening Practice</h1>
        <p className="text-[13px] text-slate-500 mt-0.5">Follow along with the audio and review each sentence</p>
      </div>

      {/* Mobile mini header */}
      <div className="sm:hidden flex items-center justify-between">
        <h1 className="text-[16px] font-bold text-slate-800">Listening</h1>
        <span className="text-[11px] text-slate-400">{revision.length} sentences</span>
      </div>

      {/* Subtitle Cards */}
      <div className="space-y-2">
        {revision.map((item, index) => (
          <MobileSubtitleCard
            key={item.id}
            item={item}
            index={index}
            isActive={activeIndex === index}
            voice={getVoiceForSpeaker(item.speaker, speakerMappings, voiceList)}
            onClick={handleSentenceClick}
          />
        ))}
      </div>

      {/* Desktop Player - normal flow */}
      <div className="hidden sm:block bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
        <DesktopPlayer
          currentTime={currentTime}
          duration={duration}
          isPlaying={isPlaying}
          playbackRate={playbackRate}
          onTogglePlay={togglePlay}
          onSeek={handleSeek}
          onSkip={skip}
          onRateChange={setPlaybackRate}
        />
      </div>

      {/* Mobile Player - fixed bottom */}
      <div className="sm:hidden fixed bottom-0 left-0 right-0 bg-white/95 backdrop-blur-lg border-t border-slate-200 px-4 py-3 z-50 safe-area-pb">
        <MobilePlayer
          currentTime={currentTime}
          duration={duration}
          isPlaying={isPlaying}
          playbackRate={playbackRate}
          onTogglePlay={togglePlay}
          onSeek={handleSeek}
          onSkip={skip}
          onRateChange={setPlaybackRate}
        />
      </div>
    </div>
  );
}

/* ---------- Desktop Player ---------- */
function DesktopPlayer({
  currentTime, duration, isPlaying, playbackRate,
  onTogglePlay, onSeek, onSkip, onRateChange,
}: {
  currentTime: number; duration: number; isPlaying: boolean; playbackRate: number;
  onTogglePlay: () => void; onSeek: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onSkip: (d: number) => void; onRateChange: (r: number) => void;
}) {
  return (
    <div className="flex items-center gap-4">
      <button onClick={() => onSkip(-5)} className="p-2 hover:bg-slate-100 rounded-full transition-colors">
        <SkipBack className="w-5 h-5 text-slate-600" />
      </button>

      <button
        onClick={onTogglePlay}
        className="w-12 h-12 bg-indigo-500 hover:bg-indigo-600 rounded-full flex items-center justify-center transition-colors shadow-lg shadow-indigo-200"
      >
        {isPlaying ? <Pause className="w-5 h-5 text-white" /> : <Play className="w-5 h-5 text-white ml-0.5" />}
      </button>

      <button onClick={() => onSkip(5)} className="p-2 hover:bg-slate-100 rounded-full transition-colors">
        <SkipForward className="w-5 h-5 text-slate-600" />
      </button>

      <div className="flex-1 mx-2">
        <input type="range" min={0} max={duration || 0} value={currentTime} onChange={onSeek} className="w-full" />
      </div>

      <span className="text-[11px] text-slate-500 font-mono tabular-nums">
        {formatTime(currentTime)} / {formatTime(duration)}
      </span>

      <select
        value={playbackRate}
        onChange={(e) => onRateChange(Number(e.target.value))}
        className="text-[11px] text-slate-600 bg-slate-100 border border-slate-200 rounded-lg px-2 py-1.5 cursor-pointer font-medium"
      >
        {[0.7, 0.8, 0.9, 1, 1.1, 1.2, 1.3, 1.4, 1.5].map(r => <option key={r} value={r}>{r}x</option>)}
      </select>
    </div>
  );
}

/* ---------- Mobile Player ---------- */
function MobilePlayer({
  currentTime, duration, isPlaying, playbackRate,
  onTogglePlay, onSeek, onSkip, onRateChange,
}: {
  currentTime: number; duration: number; isPlaying: boolean; playbackRate: number;
  onTogglePlay: () => void; onSeek: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onSkip: (d: number) => void; onRateChange: (r: number) => void;
}) {
  return (
    <div className="space-y-2">
      {/* Progress */}
      <div className="flex items-center gap-2.5">
        <span className="text-[10px] text-slate-500 font-mono w-8 text-right">{formatTime(currentTime)}</span>
        <input
          type="range"
          min={0}
          max={duration || 0}
          value={currentTime}
          onChange={onSeek}
          className="flex-1"
        />
        <span className="text-[10px] text-slate-500 font-mono w-8">{formatTime(duration)}</span>
      </div>

      {/* Controls */}
      <div className="flex items-center justify-center gap-6">
        <button onClick={() => onSkip(-5)} className="p-2 active:bg-slate-100 rounded-full transition-colors">
          <SkipBack className="w-5 h-5 text-slate-600" />
        </button>

        <button
          onClick={onTogglePlay}
          className="w-11 h-11 bg-indigo-500 active:bg-indigo-600 rounded-full flex items-center justify-center transition-colors shadow-md shadow-indigo-200"
        >
          {isPlaying
            ? <Pause className="w-5 h-5 text-white" />
            : <Play className="w-5 h-5 text-white ml-0.5" />}
        </button>

        <button onClick={() => onSkip(5)} className="p-2 active:bg-slate-100 rounded-full transition-colors">
          <SkipForward className="w-5 h-5 text-slate-600" />
        </button>

        <select
          value={playbackRate}
          onChange={(e) => onRateChange(Number(e.target.value))}
          className="text-[10px] text-slate-600 bg-slate-100 border border-slate-200 rounded-md px-1.5 py-1 cursor-pointer font-semibold"
        >
          {[0.7, 0.8, 0.9, 1, 1.1, 1.2, 1.3, 1.4, 1.5].map(r => <option key={r} value={r}>{r}x</option>)}
        </select>
      </div>
    </div>
  );
}
