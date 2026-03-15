import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { PageTitle } from '@/components/common/page-title'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ApiRequestError } from '@/lib/api/client'
import { getTtsSynthesis } from '@/lib/api/tts'
import { getRevisePath, getSessionPath, ROUTES } from '@/lib/constants/routes'
import { getSessionSummary, type SessionSummary } from '@/lib/session/sessions'
import { formatDuration } from '@/lib/utils/format'
import type { TtsSynthesisItemResponse, TtsSynthesisResponse } from '@/types/api'

const SPEED_OPTIONS = [0.75, 1, 1.25] as const

interface TtsTimelineItem {
  item: TtsSynthesisItemResponse
  startSecond: number
  endSecond: number
}

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

function normalizeSpeakerLabel(value: string | null | undefined): string {
  return value?.trim() || 'Speaker'
}

function estimateItemWeight(item: TtsSynthesisItemResponse): number {
  if (typeof item.duration_ms === 'number' && item.duration_ms > 0) {
    return item.duration_ms / 1000
  }

  const plainText = item.plain_text.trim()
  const wordCount = plainText.split(/\s+/).filter(Boolean).length
  const charCount = plainText.length
  return Math.max(1.2, wordCount * 0.35, charCount * 0.08)
}

function buildTimeline(
  items: TtsSynthesisItemResponse[],
  totalDurationSecond: number | null,
): TtsTimelineItem[] {
  if (items.length === 0) {
    return []
  }

  const hasExactTimeline = items.every(
    (item) => typeof item.start_time_ms === 'number' && typeof item.end_time_ms === 'number',
  )
  if (hasExactTimeline) {
    return items.map((item) => ({
      item,
      startSecond: (item.start_time_ms ?? 0) / 1000,
      endSecond: (item.end_time_ms ?? 0) / 1000,
    }))
  }

  const weights = items.map(estimateItemWeight)
  const weightSum = weights.reduce((sum, value) => sum + value, 0)
  const fallbackDurationSecond = totalDurationSecond && totalDurationSecond > 0 ? totalDurationSecond : weightSum
  const resolvedDurationSecond = fallbackDurationSecond > 0 ? fallbackDurationSecond : items.length

  let cursor = 0
  return items.map((item, index) => {
    const segmentLength = resolvedDurationSecond * (weights[index] / weightSum)
    const startSecond = cursor
    const endSecond = index === items.length - 1 ? resolvedDurationSecond : cursor + segmentLength
    cursor = endSecond
    return {
      item,
      startSecond,
      endSecond,
    }
  })
}

function findActiveTimelineItem(
  timeline: TtsTimelineItem[],
  currentTimeSecond: number,
): TtsTimelineItem | null {
  if (timeline.length === 0) {
    return null
  }

  for (const entry of timeline) {
    if (currentTimeSecond < entry.endSecond) {
      return entry
    }
  }

  return timeline[timeline.length - 1]
}

export function ListeningPage() {
  const { sessionId = '' } = useParams()
  const [session, setSession] = useState<SessionSummary | null>(null)
  const [synthesis, setSynthesis] = useState<TtsSynthesisResponse | null>(null)
  const [speed, setSpeed] = useState<(typeof SPEED_OPTIONS)[number]>(1)
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [currentTimeSecond, setCurrentTimeSecond] = useState(0)
  const [durationSecond, setDurationSecond] = useState(0)
  const audioRef = useRef<HTMLAudioElement | null>(null)

  const resolvedSessionId = session?.sessionId || sessionId
  const audioUrl = synthesis?.full_asset_url ?? null
  const playableItems = useMemo(
    () => (synthesis?.items ?? []).filter((item) => item.status_name !== 'failed'),
    [synthesis],
  )
  const resolvedDurationSecond =
    durationSecond > 0
      ? durationSecond
      : typeof synthesis?.full_duration_ms === 'number' && synthesis.full_duration_ms > 0
        ? synthesis.full_duration_ms / 1000
        : null
  const timeline = useMemo(
    () => buildTimeline(playableItems, resolvedDurationSecond),
    [playableItems, resolvedDurationSecond],
  )
  const activeTimelineItem = useMemo(
    () => findActiveTimelineItem(timeline, currentTimeSecond),
    [timeline, currentTimeSecond],
  )
  const activeIndex = activeTimelineItem ? timeline.findIndex((entry) => entry.item.item_id === activeTimelineItem.item.item_id) : -1

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

        const nextSynthesis = await getTtsSynthesis(sessionId)
        if (cancelled) {
          return
        }

        setSynthesis(nextSynthesis)
        setCurrentTimeSecond(0)
        setDurationSecond(0)
        setErrorMessage(null)
      } catch (error) {
        if (cancelled) {
          return
        }
        if (error instanceof ApiRequestError && error.status === 404) {
          setSynthesis(null)
          setErrorMessage('No synthesized audio yet. Go back to Revise and run `Synthesize All` first.')
        } else {
          setErrorMessage(error instanceof Error ? error.message : 'Failed to load listening data.')
        }
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
    if (!resolvedSessionId || synthesis?.status_name !== 'generating') {
      return
    }

    let cancelled = false
    const timerId = window.setInterval(() => {
      void (async () => {
        try {
          const nextSynthesis = await getTtsSynthesis(resolvedSessionId)
          if (cancelled) {
            return
          }
          setSynthesis(nextSynthesis)
          setErrorMessage(null)
        } catch (error) {
          if (cancelled) {
            return
          }
          setErrorMessage(error instanceof Error ? error.message : 'Failed to refresh TTS listening data.')
        }
      })()
    }, 2000)

    return () => {
      cancelled = true
      window.clearInterval(timerId)
    }
  }, [resolvedSessionId, synthesis?.status_name])

  useEffect(() => {
    if (!audioRef.current) {
      return
    }

    audioRef.current.playbackRate = speed
  }, [speed, audioUrl])

  useEffect(() => {
    function handleSpace(event: KeyboardEvent) {
      if (event.code !== 'Space' || event.defaultPrevented) {
        return
      }
      if (isEditableElement(event.target) || !audioRef.current || !audioUrl) {
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
  }, [audioUrl])

  function handleSeek(nextSecond: number) {
    if (!audioRef.current || !Number.isFinite(nextSecond)) {
      return
    }

    audioRef.current.currentTime = nextSecond
    setCurrentTimeSecond(nextSecond)
  }

  function handleJumpToTimelineIndex(nextIndex: number) {
    if (nextIndex < 0 || nextIndex >= timeline.length) {
      return
    }

    handleSeek(Math.max(0, timeline[nextIndex].startSecond))
  }

  const canJumpToPrevious = activeIndex > 0
  const canJumpToNext = activeIndex >= 0 && activeIndex < timeline.length - 1

  return (
    <section className="space-y-6">
      <PageTitle
        eyebrow="Step 4"
        title="Listening Practice"
        description="Listen to the synthesized revision audio and follow the current sentence."
        actions={
          <>
            <Button asChild variant="outline" size="sm">
              <Link to={resolvedSessionId ? getSessionPath(resolvedSessionId) : ROUTES.dashboard}>Session</Link>
            </Button>
            <Button asChild variant="outline" size="sm">
              <Link to={resolvedSessionId ? getRevisePath(resolvedSessionId) : ROUTES.dashboard}>Revise</Link>
            </Button>
          </>
        }
      />

      <Card className="border-slate-200/80 bg-white/95 shadow-sm">
        <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="space-y-1">
            <CardTitle>Generated Audio</CardTitle>
            {synthesis?.status_name ? (
              <p className="text-sm text-slate-500">{`Status: ${synthesis.status_name}`}</p>
            ) : null}
          </div>
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
        </CardHeader>
        <CardContent className="space-y-4">
          {isLoading ? <p className="text-sm text-slate-600">Loading synthesized audio...</p> : null}

          {!isLoading && errorMessage && !synthesis ? (
            <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">{errorMessage}</div>
          ) : null}

          {audioUrl ? (
            <>
              <audio
                ref={audioRef}
                className="w-full"
                controls
                src={audioUrl}
                onLoadedMetadata={() => {
                  if (!audioRef.current) {
                    return
                  }
                  const nextDuration = Number.isFinite(audioRef.current.duration) ? audioRef.current.duration : 0
                  setDurationSecond(nextDuration)
                }}
                onDurationChange={() => {
                  if (!audioRef.current) {
                    return
                  }
                  const nextDuration = Number.isFinite(audioRef.current.duration) ? audioRef.current.duration : 0
                  setDurationSecond(nextDuration)
                }}
                onTimeUpdate={() => {
                  if (!audioRef.current) {
                    return
                  }
                  setCurrentTimeSecond(audioRef.current.currentTime)
                }}
              >
                <track kind="captions" />
              </audio>

              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm text-slate-600">
                  <span>{formatDuration(currentTimeSecond)}</span>
                  <span>{formatDuration(resolvedDurationSecond ?? 0)}</span>
                </div>
                <input
                  type="range"
                  min={0}
                  max={resolvedDurationSecond ?? 0}
                  step={0.01}
                  value={Math.min(currentTimeSecond, resolvedDurationSecond ?? 0)}
                  onChange={(event) => handleSeek(Number(event.target.value))}
                  disabled={!resolvedDurationSecond || resolvedDurationSecond <= 0}
                  className="w-full accent-slate-900"
                />
              </div>

              <p className="text-xs text-slate-500">Shortcut: press Space to toggle play/pause.</p>
            </>
          ) : !isLoading && synthesis?.status_name === 'generating' ? (
            <p className="text-sm text-slate-600">Synthesized audio is generating. This page will refresh automatically.</p>
          ) : !isLoading && synthesis ? (
            <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
              {synthesis.error_message || 'Synthesized audio is not ready yet.'}
            </div>
          ) : null}
        </CardContent>
      </Card>

      <Card className="border-slate-200/80 bg-white/95 shadow-sm">
        <CardHeader>
          <CardTitle>Current Sentence</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {activeTimelineItem ? (
            <>
              <div className="flex flex-wrap gap-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => handleJumpToTimelineIndex(activeIndex - 1)}
                  disabled={!canJumpToPrevious}
                >
                  Previous
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => handleJumpToTimelineIndex(activeIndex + 1)}
                  disabled={!canJumpToNext}
                >
                  Next
                </Button>
              </div>
              <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
                <span className="rounded-full bg-slate-100 px-2.5 py-1">
                  {`${activeIndex + 1} / ${timeline.length}`}
                </span>
                <span className="rounded-full bg-slate-100 px-2.5 py-1">
                  {normalizeSpeakerLabel(activeTimelineItem.item.conversation_speaker)}
                </span>
              </div>
              <p className="text-2xl font-semibold leading-10 text-slate-900">{activeTimelineItem.item.plain_text}</p>
            </>
          ) : isLoading ? (
            <p className="text-sm text-slate-600">Preparing current sentence...</p>
          ) : (
            <p className="text-sm text-slate-600">No synthesized sentence available yet.</p>
          )}
        </CardContent>
      </Card>
    </section>
  )
}
