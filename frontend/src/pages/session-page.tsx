import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { PageTitle } from '@/components/common/page-title'
import { StatusBadge } from '@/components/common/status-badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { getListeningPath, getRevisePath, ROUTES } from '@/lib/constants/routes'
import { getSessionSummary, getSessionTranscript, type SessionSummary } from '@/lib/session/sessions'
import { formatClock, formatDateTime, formatDuration } from '@/lib/utils/format'
import type { TaskTranscriptData } from '@/types/api'

function isEditableElement(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) {
    return false
  }

  const tag = target.tagName
  return (
    target.isContentEditable ||
    tag === 'INPUT' ||
    tag === 'TEXTAREA' ||
    tag === 'SELECT' ||
    target.closest('[contenteditable="true"]') !== null
  )
}

export function SessionPage() {
  const { sessionId = '' } = useParams()
  const [session, setSession] = useState<SessionSummary | null>(null)
  const [transcript, setTranscript] = useState<TaskTranscriptData | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [activeSeq, setActiveSeq] = useState<number | null>(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [audioCurrentSec, setAudioCurrentSec] = useState(0)
  const [audioDurationSec, setAudioDurationSec] = useState<number | null>(null)
  const audioRef = useRef<HTMLAudioElement | null>(null)

  const isCompleted = session?.status === 'completed'

  const loadSession = useCallback(
    async (options: { refresh?: boolean; showLoading?: boolean; showRefreshing?: boolean } = {}) => {
      if (!sessionId) {
        setErrorMessage('Missing session id.')
        setIsLoading(false)
        return
      }

      const { refresh = true, showLoading = true, showRefreshing = false } = options

      if (showLoading) {
        setIsLoading(true)
      }
      if (showRefreshing) {
        setIsRefreshing(true)
      }

      try {
        const detail = await getSessionSummary(sessionId, refresh)
        setSession(detail)
        setErrorMessage(null)

        if (detail.status === 'completed') {
          const transcriptData = await getSessionTranscript(sessionId)
          setTranscript(transcriptData)
        } else {
          setTranscript(null)
        }
      } catch (error) {
        setErrorMessage(error instanceof Error ? error.message : 'Failed to load session.')
      } finally {
        setIsLoading(false)
        setIsRefreshing(false)
      }
    },
    [sessionId],
  )

  useEffect(() => {
    void loadSession({ refresh: true, showLoading: true })
  }, [loadSession])

  useEffect(() => {
    if (!session || session.status === 'completed' || session.status === 'failed') {
      return
    }

    const timer = window.setInterval(() => {
      void loadSession({ refresh: true, showLoading: false })
    }, 3000)

    return () => window.clearInterval(timer)
  }, [loadSession, session])

  useEffect(() => {
    const audio = audioRef.current
    if (!audio) {
      return
    }

    const handlePlay = () => setIsPlaying(true)
    const handlePause = () => setIsPlaying(false)

    audio.addEventListener('play', handlePlay)
    audio.addEventListener('pause', handlePause)

    return () => {
      audio.removeEventListener('play', handlePlay)
      audio.removeEventListener('pause', handlePause)
    }
  }, [session?.audioUrl])

  useEffect(() => {
    function onGlobalSpace(event: KeyboardEvent) {
      if (event.code !== 'Space' || event.defaultPrevented) {
        return
      }
      if (isEditableElement(event.target) || !audioRef.current || !session?.audioUrl) {
        return
      }

      event.preventDefault()
      if (audioRef.current.paused) {
        void audioRef.current.play().catch(() => {
          // Ignore autoplay restrictions.
        })
      } else {
        audioRef.current.pause()
      }
    }

    window.addEventListener('keydown', onGlobalSpace)
    return () => {
      window.removeEventListener('keydown', onGlobalSpace)
    }
  }, [session?.audioUrl])

  function seekBy(delta: number) {
    if (!audioRef.current) {
      return
    }

    const next = Math.max(0, audioRef.current.currentTime + delta)
    audioRef.current.currentTime = next
    setAudioCurrentSec(next)
  }

  function togglePlayPause() {
    if (!audioRef.current) {
      return
    }

    if (audioRef.current.paused) {
      void audioRef.current.play().catch(() => {
        // Ignore autoplay restrictions.
      })
      return
    }

    audioRef.current.pause()
  }

  function playFromUtterance(startMs: number, seq: number) {
    if (!audioRef.current) {
      return
    }

    audioRef.current.currentTime = startMs / 1000
    setActiveSeq(seq)
    setAudioCurrentSec(startMs / 1000)
    void audioRef.current.play().catch(() => {
      // Ignore autoplay restrictions.
    })
  }

  const transcriptRows = useMemo(() => transcript?.utterances ?? [], [transcript])

  return (
    <section className="space-y-6">
      <PageTitle
        eyebrow="Session"
        title={session?.title ?? 'Session'}
        description={session?.description || `Session ID: ${sessionId || '--'}`}
        actions={
          <>
            <Button asChild variant="outline" size="sm">
              <Link to={ROUTES.dashboard}>Dashboard</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link to={sessionId ? getRevisePath(sessionId) : ROUTES.dashboard}>Revise</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link to={sessionId ? getListeningPath(sessionId) : ROUTES.dashboard}>Listening</Link>
            </Button>
          </>
        }
      />

      <Card className="border-slate-200/80 bg-white/95 shadow-sm">
        <CardHeader className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <CardTitle>Audio Player</CardTitle>
            {session ? (
              <CardDescription>
                Status: {session.statusName} · Created: {formatDateTime(session.createdAt)}
              </CardDescription>
            ) : null}
          </div>
          {session ? <StatusBadge status={session.status} /> : null}
        </CardHeader>

        <CardContent className="space-y-3">
          {session?.audioUrl ? (
            <>
              <div className="flex flex-wrap items-center gap-2">
                <Button type="button" variant="outline" size="sm" onClick={() => seekBy(-15)}>
                  |&lt;&lt;
                </Button>
                <Button type="button" variant="outline" size="sm" onClick={() => seekBy(-3)}>
                  &lt;
                </Button>
                <Button type="button" size="sm" onClick={togglePlayPause}>
                  {isPlaying ? 'Pause' : 'Play'}
                </Button>
                <Button type="button" variant="outline" size="sm" onClick={() => seekBy(3)}>
                  &gt;
                </Button>
                <Button type="button" variant="outline" size="sm" onClick={() => seekBy(15)}>
                  &gt;&gt;|
                </Button>
                <p className="ml-2 text-xs text-slate-600">
                  {formatClock(audioCurrentSec)} / {formatClock(audioDurationSec)}
                </p>
              </div>
              <audio
                ref={audioRef}
                className="w-full"
                controls
                src={session.audioUrl}
                onLoadedMetadata={() => {
                  if (!audioRef.current) {
                    setAudioDurationSec(null)
                    return
                  }
                  setAudioDurationSec(Number.isFinite(audioRef.current.duration) ? audioRef.current.duration : null)
                }}
                onTimeUpdate={() => {
                  if (!audioRef.current) {
                    return
                  }
                  const currentSec = audioRef.current.currentTime
                  setAudioCurrentSec(currentSec)

                  if (!transcript) {
                    return
                  }

                  const currentMs = currentSec * 1000
                  const active = transcript.utterances.find(
                    (item) => currentMs >= item.start_time && currentMs <= item.end_time + 120,
                  )
                  setActiveSeq(active?.seq ?? null)
                }}
              >
                <track kind="captions" />
              </audio>
              <p className="text-xs text-slate-500">Tip: Press Space to toggle play/pause.</p>
            </>
          ) : (
            <p className="text-sm text-slate-600">Audio URL is not available for this session yet.</p>
          )}

          {isRefreshing ? <p className="text-xs text-slate-500">Refreshing status...</p> : null}
          {errorMessage ? (
            <div className="rounded-md border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">{errorMessage}</div>
          ) : null}

          <div>
            <Button type="button" variant="outline" size="sm" onClick={() => void loadSession({ showRefreshing: true })}>
              Refresh Session
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card className="border-slate-200/80 bg-white/95 shadow-sm">
        <CardHeader>
          <CardTitle>Transcript</CardTitle>
          <CardDescription>
            {isCompleted
              ? `Total duration: ${formatDuration((transcript?.duration_ms ?? 0) / 1000)}`
              : 'Transcript will appear after processing completes.'}
          </CardDescription>
        </CardHeader>

        <CardContent>
          {isLoading ? <p className="text-sm text-slate-600">Loading session...</p> : null}

          {!isLoading && session && session.status !== 'completed' ? (
            <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
              This session is <span className="font-medium">{session.statusName}</span>. Transcript is available after
              completion.
            </div>
          ) : null}

          {!isLoading && isCompleted ? (
            transcriptRows.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full border-collapse text-left text-sm">
                  <thead>
                    <tr className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
                      <th className="w-36 py-3 pr-3 font-medium">Speaker</th>
                      <th className="py-3 pr-3 font-medium">Conversation</th>
                    </tr>
                  </thead>
                  <tbody>
                    {transcriptRows.map((row) => (
                      <tr
                        key={`${row.seq}-${row.start_time}`}
                        className={`border-b border-slate-100 align-top last:border-none ${
                          activeSeq === row.seq ? 'bg-cyan-50/80' : 'hover:bg-slate-50'
                        } ${session.audioUrl ? 'cursor-pointer' : ''}`}
                        onClick={() => {
                          if (session.audioUrl) {
                            playFromUtterance(row.start_time, row.seq)
                          }
                        }}
                        onKeyDown={(event) => {
                          if (event.key === 'Enter' && session.audioUrl) {
                            event.preventDefault()
                            playFromUtterance(row.start_time, row.seq)
                          }
                        }}
                        tabIndex={0}
                        role="button"
                      >
                        <td className="py-3 pr-3 text-xs uppercase tracking-wide text-slate-500">
                          {(row.speaker || 'speaker').replace('_', ' ')}
                          <p className="mt-1 text-[11px] text-slate-400">{formatDuration(row.start_time / 1000)}</p>
                        </td>
                        <td className="py-3 pr-3 text-slate-800">{row.text}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-sm text-slate-600">Transcript is empty.</p>
            )
          ) : null}
        </CardContent>
      </Card>
    </section>
  )
}
