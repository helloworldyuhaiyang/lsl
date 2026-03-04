import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { PageTitle } from '@/components/common/page-title'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { getRevisePath, getSessionPath, ROUTES } from '@/lib/constants/routes'
import { getSessionSummary, getSessionTranscript, type SessionSummary } from '@/lib/session/sessions'
import { formatDuration } from '@/lib/utils/format'
import type { TaskTranscriptUtterance } from '@/types/api'

const SPEED_OPTIONS = [0.75, 1, 1.25] as const

type ListeningMode = 'full' | 'sentence' | 'shadowing'

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

export function ListeningPage() {
  const { sessionId = '' } = useParams()
  const [session, setSession] = useState<SessionSummary | null>(null)
  const [utterances, setUtterances] = useState<TaskTranscriptUtterance[]>([])
  const [mode, setMode] = useState<ListeningMode>('full')
  const [selectedIndex, setSelectedIndex] = useState(0)
  const [speed, setSpeed] = useState<(typeof SPEED_OPTIONS)[number]>(1)
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const stopAtSecondRef = useRef<number | null>(null)

  const selectedUtterance = utterances[selectedIndex] ?? null

  useEffect(() => {
    let cancelled = false

    async function load() {
      if (!sessionId) {
        setErrorMessage('Missing session id.')
        setIsLoading(false)
        return
      }

      try {
        setIsLoading(true)
        const detail = await getSessionSummary(sessionId)
        if (cancelled) {
          return
        }
        setSession(detail)

        if (detail.status !== 'completed') {
          setErrorMessage(`Session is ${detail.statusName}. Listening content is available after completion.`)
          setUtterances([])
          return
        }

        const transcript = await getSessionTranscript(sessionId)
        if (cancelled) {
          return
        }

        setUtterances(transcript.utterances)
        setSelectedIndex(0)
        setErrorMessage(null)
      } catch (error) {
        if (cancelled) {
          return
        }
        setErrorMessage(error instanceof Error ? error.message : 'Failed to load listening data.')
      } finally {
        if (!cancelled) {
          setIsLoading(false)
        }
      }
    }

    void load()

    return () => {
      cancelled = true
    }
  }, [sessionId])

  useEffect(() => {
    if (!audioRef.current) {
      return
    }

    audioRef.current.playbackRate = speed
  }, [speed])

  useEffect(() => {
    function handleSpace(event: KeyboardEvent) {
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

    window.addEventListener('keydown', handleSpace)
    return () => {
      window.removeEventListener('keydown', handleSpace)
    }
  }, [session?.audioUrl])

  function playFullConversation() {
    if (!audioRef.current) {
      return
    }

    stopAtSecondRef.current = null
    audioRef.current.currentTime = 0
    void audioRef.current.play().catch(() => {
      // Ignore autoplay restrictions.
    })
  }

  function playSelectedSentence() {
    if (!audioRef.current || !selectedUtterance) {
      return
    }

    const startSecond = selectedUtterance.start_time / 1000
    const endSecond = selectedUtterance.end_time / 1000

    stopAtSecondRef.current = endSecond
    audioRef.current.currentTime = startSecond
    void audioRef.current.play().catch(() => {
      // Ignore autoplay restrictions.
    })
  }

  function seekBy(delta: number) {
    if (!audioRef.current) {
      return
    }

    const next = Math.max(0, audioRef.current.currentTime + delta)
    audioRef.current.currentTime = next
  }

  const scriptText = useMemo(() => {
    if (utterances.length === 0) {
      return ''
    }

    return utterances
      .map((item) => `${(item.speaker || 'Speaker').replace('_', ' ')}: ${item.text}`)
      .join('\n\n')
  }, [utterances])

  return (
    <section className="space-y-6">
      <PageTitle
        eyebrow="Step 4"
        title="Listening Practice"
        description="Practice with full conversation, sentence repeat, or shadowing mode."
        actions={
          <>
            <Button asChild variant="outline" size="sm">
              <Link to={sessionId ? getSessionPath(sessionId) : ROUTES.dashboard}>Session</Link>
            </Button>
            <Button asChild variant="outline" size="sm">
              <Link to={sessionId ? getRevisePath(sessionId) : ROUTES.dashboard}>Revise</Link>
            </Button>
          </>
        }
      />

      <Card className="border-slate-200/80 bg-white/95 shadow-sm">
        <CardHeader>
          <CardTitle>Mode</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-slate-700">
          <label className="flex items-center gap-2">
            <input type="radio" name="mode" checked={mode === 'full'} onChange={() => setMode('full')} />
            Full conversation
          </label>
          <label className="flex items-center gap-2">
            <input type="radio" name="mode" checked={mode === 'sentence'} onChange={() => setMode('sentence')} />
            Sentence repeat
          </label>
          <label className="flex items-center gap-2">
            <input type="radio" name="mode" checked={mode === 'shadowing'} onChange={() => setMode('shadowing')} />
            Shadowing
          </label>
        </CardContent>
      </Card>

      <Card className="border-slate-200/80 bg-white/95 shadow-sm">
        <CardHeader>
          <CardTitle>Script</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {isLoading ? <p className="text-sm text-slate-600">Loading listening script...</p> : null}
          {errorMessage ? (
            <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">{errorMessage}</div>
          ) : null}

          {!isLoading && !errorMessage ? (
            mode === 'full' ? (
              <pre className="whitespace-pre-wrap rounded-md border border-slate-200 bg-slate-50 p-4 text-sm text-slate-800">
                {scriptText || 'No script available.'}
              </pre>
            ) : (
              <div className="space-y-2">
                {utterances.map((item, index) => (
                  <button
                    key={`${item.seq}-${item.start_time}`}
                    type="button"
                    onClick={() => setSelectedIndex(index)}
                    className={`w-full rounded-md border px-3 py-2 text-left text-sm transition ${
                      index === selectedIndex
                        ? 'border-cyan-300 bg-cyan-50 text-cyan-900'
                        : 'border-slate-200 bg-white text-slate-800 hover:border-slate-300'
                    }`}
                  >
                    <p className="text-xs uppercase tracking-wide text-slate-500">
                      {(item.speaker || 'Speaker').replace('_', ' ')} · {formatDuration(item.start_time / 1000)}
                    </p>
                    <p className="mt-1">{item.text}</p>
                  </button>
                ))}
              </div>
            )
          ) : null}
        </CardContent>
      </Card>

      <Card className="border-slate-200/80 bg-white/95 shadow-sm">
        <CardHeader>
          <CardTitle>Audio</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {session?.audioUrl ? (
            <>
              <div className="flex flex-wrap items-center gap-2">
                <Button type="button" variant="outline" size="sm" onClick={() => seekBy(-15)}>
                  |&lt;&lt;
                </Button>
                <Button type="button" variant="outline" size="sm" onClick={() => seekBy(-3)}>
                  &lt;
                </Button>
                <Button
                  type="button"
                  size="sm"
                  onClick={() => {
                    if (!audioRef.current) {
                      return
                    }
                    if (audioRef.current.paused) {
                      void audioRef.current.play().catch(() => {
                        // Ignore autoplay restrictions.
                      })
                    } else {
                      audioRef.current.pause()
                    }
                  }}
                >
                  Play / Pause
                </Button>
                <Button type="button" variant="outline" size="sm" onClick={() => seekBy(3)}>
                  &gt;
                </Button>
                <Button type="button" variant="outline" size="sm" onClick={() => seekBy(15)}>
                  &gt;&gt;|
                </Button>
              </div>

              {mode === 'full' ? (
                <Button type="button" variant="outline" size="sm" onClick={playFullConversation}>
                  Play Full Conversation
                </Button>
              ) : (
                <div className="flex flex-wrap items-center gap-2">
                  <Button type="button" variant="outline" size="sm" onClick={playSelectedSentence} disabled={!selectedUtterance}>
                    Play Selected Sentence
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => setSelectedIndex((value) => Math.max(0, value - 1))}
                    disabled={selectedIndex === 0}
                  >
                    Previous
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => setSelectedIndex((value) => Math.min(utterances.length - 1, value + 1))}
                    disabled={selectedIndex >= utterances.length - 1}
                  >
                    Next
                  </Button>
                </div>
              )}

              <audio
                ref={audioRef}
                className="w-full"
                controls
                src={session.audioUrl}
                onTimeUpdate={() => {
                  if (!audioRef.current || stopAtSecondRef.current === null) {
                    return
                  }

                  if (audioRef.current.currentTime >= stopAtSecondRef.current) {
                    audioRef.current.pause()
                    stopAtSecondRef.current = null

                    if (mode === 'shadowing') {
                      setSelectedIndex((value) => Math.min(utterances.length - 1, value + 1))
                    }
                  }
                }}
              >
                <track kind="captions" />
              </audio>

              <div className="space-y-2">
                <p className="text-sm font-medium text-slate-800">Speed</p>
                <div className="flex flex-wrap gap-2">
                  {SPEED_OPTIONS.map((value) => (
                    <Button
                      key={value}
                      type="button"
                      variant={speed === value ? 'default' : 'outline'}
                      size="sm"
                      onClick={() => setSpeed(value)}
                    >
                      {value}x
                    </Button>
                  ))}
                </div>
              </div>

              <p className="text-xs text-slate-500">Shortcut: press Space to toggle play/pause.</p>
            </>
          ) : (
            <p className="text-sm text-slate-600">No audio URL available for this session.</p>
          )}
        </CardContent>
      </Card>
    </section>
  )
}
