import { useEffect, useMemo, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, ArrowRight, Mic2, FileText, AudioWaveform } from 'lucide-react';
import { AudioPlayer } from '@/components/AudioPlayer';
import { StatusBadge } from '@/components/StatusBadge';
import { formatDateTime, formatTime } from '@/utils/formatTime';
import { speakerColors } from '@/data/mockData';
import { useApp } from '@/context/AppContext';
import { NotFound } from './NotFound';
import type { RevisionItem, TranscriptItem } from '@/types';
import { getSession } from '@/lib/api/sessions';
import { getTranscript } from '@/lib/api/transcripts';
import { getTtsSynthesis } from '@/lib/api/tts';
import { applyTtsSynthesis, mapSessionItem, mapTranscript } from '@/lib/domain';

export function SessionDetail() {
  const { id } = useParams<{ id: string }>();
  const { getSessionById, dispatch } = useApp();
  const [loadedSession, setLoadedSession] = useState<ReturnType<typeof getSessionById> | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [activeTranscriptIndex, setActiveTranscriptIndex] = useState<number | null>(null);
  const [seekRequest, setSeekRequest] = useState<{ time: number; requestId: number } | null>(null);

  const session = useMemo(() => loadedSession || (id ? getSessionById(id) : undefined), [id, getSessionById, loadedSession]);

  useEffect(() => {
    if (session) dispatch({ type: 'SET_CURRENT_SESSION', payload: session });
  }, [session, dispatch]);

  useEffect(() => {
    if (!id) return;
    const sessionId = id;
    let cancelled = false;
    let refreshTimer: ReturnType<typeof window.setTimeout> | null = null;

    async function loadSession(): Promise<boolean> {
      setNotFound(false);
      try {
        const item = await getSession(sessionId);
        let nextSession = mapSessionItem(item);

        if (item.session.current_transcript_id) {
          try {
            const transcript = await getTranscript(item.session.current_transcript_id);
            nextSession = { ...nextSession, transcript: mapTranscript(transcript) };
          } catch {
            // Transcript may not be ready while the source job is still processing.
          }
        }

        try {
          const synthesis = await getTtsSynthesis(sessionId);
          nextSession = applyTtsSynthesis(nextSession, synthesis);
        } catch {
          // TTS output is optional until step 3.
        }

        if (!cancelled) {
          setLoadedSession(nextSession);
          dispatch({ type: 'UPDATE_SESSION', payload: nextSession });
        }
        return nextSession.status === 'pending' || nextSession.status === 'processing';
      } catch {
        if (!cancelled) setNotFound(true);
        return false;
      }
    }

    async function loadAndSchedule() {
      const shouldKeepPolling = await loadSession();
      if (!cancelled && shouldKeepPolling) {
        refreshTimer = window.setTimeout(loadAndSchedule, 3000);
      }
    }

    void loadAndSchedule();
    return () => {
      cancelled = true;
      if (refreshTimer) window.clearTimeout(refreshTimer);
    };
  }, [id, dispatch]);

  if (!session && !notFound) {
    return <div className="text-[13px] text-slate-500">Loading session...</div>;
  }

  if (!session) return <NotFound />;

  const transcript = session.transcript || session.revision;
  const totalDuration = transcript && transcript.length > 0 ? transcript[transcript.length - 1].endTime : 0;
  const canOpenRevise = session.status === 'completed' || !!session.revision;
  const shouldShowAudioPlayer = session.type === 'audio' || !!session.synthesizedAudioUrl;

  const isRevision = (item: RevisionItem | TranscriptItem): item is RevisionItem => 'cue' in item;

  const handleTranscriptSelect = (index: number, item: RevisionItem | TranscriptItem) => {
    setActiveTranscriptIndex(index);
    setSeekRequest((current) => ({
      time: item.startTime,
      requestId: (current?.requestId ?? 0) + 1,
    }));
  };

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <Link to="/" className="inline-flex items-center gap-1.5 text-[12px] text-slate-500 hover:text-indigo-600 transition-colors">
        <ArrowLeft className="w-3.5 h-3.5" />
        Dashboard
      </Link>

      {/* Header Card */}
      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
        <div className="flex items-start justify-between">
          <div className="space-y-3">
            <div className="flex items-center gap-3">
              <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${
                session.type === 'audio' ? 'bg-violet-100 text-violet-600' : 'bg-sky-100 text-sky-600'
              }`}>
                {session.type === 'audio' ? <Mic2 className="w-5 h-5" /> : <FileText className="w-5 h-5" />}
              </div>
              <div>
                <h1 className="text-[20px] font-bold text-slate-900 tracking-tight">{session.title}</h1>
                <p className="text-[11px] text-slate-400 font-mono mt-0.5">ID: {session.id.slice(0, 16)}...</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <StatusBadge status={session.status} />
              <span className="text-[12px] text-slate-400">{formatDateTime(session.createdAt)}</span>
              {totalDuration > 0 && (
                <span className="text-[12px] text-slate-500 font-mono flex items-center gap-1">
                  <AudioWaveform className="w-3 h-3" />
                  {formatTime(totalDuration)}
                </span>
              )}
            </div>
          </div>
          {canOpenRevise ? (
            <Link
              to={`/session/${session.id}/revise`}
              className="inline-flex items-center gap-1.5 px-4 py-2 bg-indigo-500 hover:bg-indigo-600 text-white text-[12px] font-semibold rounded-lg transition-colors shadow-sm shadow-indigo-200"
            >
              Go to Revise <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          ) : (
            <span className="inline-flex items-center gap-1.5 px-4 py-2 bg-slate-100 text-slate-400 text-[12px] font-semibold rounded-lg">
              Go to Revise <ArrowRight className="w-3.5 h-3.5" />
            </span>
          )}
        </div>
      </div>

      {/* Step Progress */}
      <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
        <div className="flex items-center">
          {[
            { label: 'Session', path: `/session/${session.id}`, active: true },
            { label: 'Revise', path: `/session/${session.id}/revise`, active: canOpenRevise },
            { label: 'Listening', path: `/session/${session.id}/listening`, active: !!session.synthesizedAudioUrl },
          ].map((step, i, arr) => (
            <div key={step.label} className="flex items-center flex-1">
              <Link
                to={step.path}
                className={`flex items-center gap-2 text-[12px] font-medium transition-colors ${
                  step.active ? 'text-indigo-600' : 'text-slate-400 pointer-events-none'
                }`}
              >
                <span className={`w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold ${
                  i === 0 ? 'bg-indigo-500 text-white' : step.active ? 'bg-indigo-100 text-indigo-600' : 'bg-slate-100 text-slate-400'
                }`}>
                  {i + 1}
                </span>
                {step.label}
              </Link>
              {i < arr.length - 1 && (
                <div className={`flex-1 h-[2px] mx-3 rounded-full ${step.active ? 'bg-indigo-200' : 'bg-slate-100'}`} />
              )}
            </div>
          ))}
        </div>
      </div>

      {shouldShowAudioPlayer && (
        <AudioPlayer
          audioUrl={session.audioUrl}
          items={transcript}
          seekTo={seekRequest}
          onActiveIndexChange={(index) => setActiveTranscriptIndex(index === -1 ? null : index)}
        />
      )}

      {/* Transcript */}
      {(!transcript || transcript.length === 0) && session.status !== 'failed' && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-8 text-center">
          <p className="text-[13px] text-slate-500">
            {session.type === 'text' ? 'Generating script transcript...' : 'Transcription is still processing...'}
          </p>
        </div>
      )}

      {transcript && transcript.length > 0 && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
            <h3 className="text-[14px] font-bold text-slate-800">Transcript</h3>
            <span className="text-[11px] text-slate-400 font-mono">{transcript.length} utterances</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-slate-50 bg-slate-50/50">
                  <th className="text-left text-[10px] font-semibold text-slate-500 uppercase tracking-wider py-2.5 px-5 w-[15%]">Speaker</th>
                  <th className="text-left text-[10px] font-semibold text-slate-500 uppercase tracking-wider py-2.5 px-3 w-[10%]">Time</th>
                  <th className="text-left text-[10px] font-semibold text-slate-500 uppercase tracking-wider py-2.5 px-3">Content</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {transcript.map((item, index) => {
                  const isActive = activeTranscriptIndex === index;

                  return (
                    <tr
                      key={item.id}
                      role="button"
                      tabIndex={0}
                      aria-current={isActive ? 'true' : undefined}
                      onClick={() => handleTranscriptSelect(index, item)}
                      onKeyDown={(event) => {
                        if (event.key === 'Enter' || event.key === ' ') {
                          event.preventDefault();
                          handleTranscriptSelect(index, item);
                        }
                      }}
                      className={`cursor-pointer transition-colors ${
                        isActive
                          ? 'bg-indigo-50/80 ring-1 ring-inset ring-indigo-200'
                          : 'hover:bg-slate-50/50'
                      }`}
                    >
                      <td className="py-3 px-5">
                        <div className="flex items-center gap-2">
                          <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: speakerColors[item.speaker] || '#94A3B8' }} />
                          <span className={`text-[13px] font-medium ${isActive ? 'text-indigo-700' : 'text-slate-700'}`}>{item.speaker}</span>
                        </div>
                      </td>
                      <td className={`py-3 px-3 text-[12px] font-mono ${isActive ? 'text-indigo-600 font-semibold' : 'text-slate-400'}`}>{formatTime(item.startTime)}</td>
                      <td className={`py-3 px-3 text-[13px] leading-relaxed ${isActive ? 'text-slate-900 font-medium' : 'text-slate-700'}`}>
                        {isRevision(item) && item.cue ? (
                          <span>
                            <span className="font-mono text-[11px] bg-amber-50 text-amber-700 border border-amber-200 rounded-md px-1.5 py-0.5 mr-1.5 font-medium">
                              [{item.cue}]
                            </span>
                            {item.content}
                          </span>
                        ) : (
                          'text' in item ? item.text : item.content
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
