import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { PageTitle } from '@/components/common/page-title'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { getListeningPath, getSessionPath, ROUTES } from '@/lib/constants/routes'
import { buildRevisionItems, type RevisionItem } from '@/lib/session/revision'
import { getSessionSummary, getSessionTranscript, type SessionSummary } from '@/lib/session/sessions'
import { formatDuration } from '@/lib/utils/format'

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

export function RevisePage() {
  const { sessionId = '' } = useParams()
  const [session, setSession] = useState<SessionSummary | null>(null)
  const [items, setItems] = useState<RevisionItem[]>([])
  const [currentIndex, setCurrentIndex] = useState(0)
  const [isLoading, setIsLoading] = useState(true)
  const [isPlayingOriginal, setIsPlayingOriginal] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [speechMessage, setSpeechMessage] = useState<string | null>(null)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const snippetEndRef = useRef<number | null>(null)

  const currentItem = items[currentIndex] ?? null

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
          setItems([])
          setErrorMessage(`Session is ${detail.statusName}. Revise content is available after completion.`)
          return
        }

        const transcript = await getSessionTranscript(sessionId)
        if (cancelled) {
          return
        }

        const revisions = buildRevisionItems(transcript.utterances)
        setItems(revisions)
        setCurrentIndex(0)
        setErrorMessage(null)
      } catch (error) {
        if (cancelled) {
          return
        }
        setErrorMessage(error instanceof Error ? error.message : 'Failed to load revise content.')
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
    function onArrowKey(event: KeyboardEvent) {
      if (isEditableElement(event.target)) {
        return
      }

      if (event.key === 'ArrowLeft') {
        event.preventDefault()
        setCurrentIndex((value) => Math.max(0, value - 1))
      }

      if (event.key === 'ArrowRight') {
        event.preventDefault()
        setCurrentIndex((value) => Math.min(items.length - 1, value + 1))
      }
    }

    window.addEventListener('keydown', onArrowKey)
    return () => {
      window.removeEventListener('keydown', onArrowKey)
    }
  }, [items.length])

  useEffect(() => {
    return () => {
      if (typeof window !== 'undefined' && window.speechSynthesis) {
        window.speechSynthesis.cancel()
      }
    }
  }, [])

  function playOriginal() {
    if (!audioRef.current || !currentItem) {
      return
    }

    audioRef.current.currentTime = currentItem.startTimeMs / 1000
    snippetEndRef.current = currentItem.endTimeMs / 1000
    setIsPlayingOriginal(true)
    void audioRef.current.play().catch(() => {
      setIsPlayingOriginal(false)
    })
  }

  function playImproved() {
    if (!currentItem) {
      return
    }

    if (typeof window === 'undefined' || !window.speechSynthesis) {
      setSpeechMessage('Speech synthesis is not available in this browser.')
      return
    }

    window.speechSynthesis.cancel()

    const utterance = new SpeechSynthesisUtterance(currentItem.suggested)
    utterance.rate = 1
    utterance.onstart = () => setSpeechMessage('Playing improved sentence by browser TTS...')
    utterance.onend = () => setSpeechMessage('')
    utterance.onerror = () => setSpeechMessage('Failed to play improved sentence.')

    window.speechSynthesis.speak(utterance)
  }

  const positionLabel = useMemo(() => {
    if (items.length === 0) {
      return 'Sentence 0 / 0'
    }
    return `Sentence ${currentIndex + 1} / ${items.length}`
  }, [currentIndex, items.length])

  return (
    <section className="space-y-6">
      <PageTitle
        eyebrow="Step 3"
        title="Revise"
        description="Flashcard-style sentence revision for expression learning."
        actions={
          <>
            <Button asChild variant="outline" size="sm">
              <Link to={sessionId ? getSessionPath(sessionId) : ROUTES.dashboard}>Session</Link>
            </Button>
            <Button asChild variant="outline" size="sm">
              <Link to={sessionId ? getListeningPath(sessionId) : ROUTES.dashboard}>Listening</Link>
            </Button>
          </>
        }
      />

      <Card className="border-slate-200/80 bg-white/95 shadow-sm">
        <CardHeader>
          <CardTitle>{positionLabel}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          {isLoading ? <p className="text-sm text-slate-600">Loading revise content...</p> : null}
          {errorMessage ? (
            <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">{errorMessage}</div>
          ) : null}

          {!isLoading && !errorMessage && currentItem ? (
            <>
              <section className="rounded-md border border-slate-200 p-4">
                <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Original</h3>
                <p className="mt-2 text-base text-slate-900">{currentItem.original}</p>
                <p className="mt-2 text-xs text-slate-500">
                  {currentItem.speaker} · {formatDuration(currentItem.startTimeMs / 1000)}-{formatDuration(currentItem.endTimeMs / 1000)}
                </p>
              </section>

              <section className="rounded-md border border-slate-200 p-4">
                <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Suggested</h3>
                <p className="mt-2 text-base font-medium text-slate-900">{currentItem.suggested}</p>
              </section>

              <section className="rounded-md border border-slate-200 p-4">
                <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Diff</h3>
                <div className="mt-2 space-y-1 text-sm">
                  {currentItem.removedTokens.length > 0 ? (
                    currentItem.removedTokens.map((token, index) => (
                      <p key={`remove-${index}`} className="text-rose-700">
                        - {token}
                      </p>
                    ))
                  ) : (
                    <p className="text-slate-500">- No removal</p>
                  )}
                  {currentItem.addedTokens.length > 0 ? (
                    currentItem.addedTokens.map((token, index) => (
                      <p key={`add-${index}`} className="text-emerald-700">
                        + {token}
                      </p>
                    ))
                  ) : (
                    <p className="text-slate-500">+ No addition</p>
                  )}
                </div>
              </section>

              <section className="rounded-md border border-slate-200 p-4">
                <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Explanation</h3>
                <ul className="mt-2 space-y-1 text-sm text-slate-700">
                  {currentItem.explanations.map((line, index) => (
                    <li key={`${line}-${index}`}>- {line}</li>
                  ))}
                </ul>
              </section>

              <section className="rounded-md border border-slate-200 p-4">
                <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Audio</h3>
                {session?.audioUrl ? (
                  <audio
                    ref={audioRef}
                    className="mt-3 w-full"
                    controls
                    src={session.audioUrl}
                    onPause={() => setIsPlayingOriginal(false)}
                    onTimeUpdate={() => {
                      if (!audioRef.current || snippetEndRef.current === null) {
                        return
                      }

                      if (audioRef.current.currentTime >= snippetEndRef.current) {
                        audioRef.current.pause()
                        snippetEndRef.current = null
                        setIsPlayingOriginal(false)
                      }
                    }}
                  >
                    <track kind="captions" />
                  </audio>
                ) : (
                  <p className="mt-2 text-sm text-slate-500">No source audio URL available.</p>
                )}
                <div className="mt-3 flex flex-wrap gap-2">
                  <Button type="button" size="sm" variant="outline" onClick={playOriginal} disabled={!session?.audioUrl}>
                    {isPlayingOriginal ? 'Playing Original...' : 'Play Original'}
                  </Button>
                  <Button type="button" size="sm" variant="outline" onClick={playImproved}>
                    Play Improved
                  </Button>
                </div>
                {speechMessage ? <p className="mt-2 text-xs text-slate-500">{speechMessage}</p> : null}
              </section>

              <section className="flex items-center justify-between">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setCurrentIndex((value) => Math.max(0, value - 1))}
                  disabled={currentIndex === 0}
                >
                  Previous
                </Button>
                <Button
                  type="button"
                  onClick={() => setCurrentIndex((value) => Math.min(items.length - 1, value + 1))}
                  disabled={currentIndex >= items.length - 1}
                >
                  Next
                </Button>
              </section>
              <p className="text-xs text-slate-500">Shortcut: use Left / Right arrow for previous or next sentence.</p>
            </>
          ) : null}
        </CardContent>
      </Card>
    </section>
  )
}
