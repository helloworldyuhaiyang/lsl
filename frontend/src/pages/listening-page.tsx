import { useEffect, useMemo, useRef, useState } from 'react'
import { ListRestart, Pause, Play, Repeat, Repeat1, SkipBack, SkipForward, Volume2 } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'

import { PageTitle } from '@/components/common/page-title'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Slider } from '@/components/ui/slider'
import { ApiRequestError } from '@/lib/api/client'
import { getTtsSynthesis } from '@/lib/api/tts'
import { getRevisePath, getSessionPath, ROUTES } from '@/lib/constants/routes'
import { getSessionSummary, type SessionSummary } from '@/lib/session/sessions'
import { formatDuration } from '@/lib/utils/format'
import type { TtsSynthesisItemResponse, TtsSynthesisResponse } from '@/types/api'

const SPEED_OPTIONS = [0.7, 0.8, 0.9, 1, 1.1, 1.2, 1.3, 1.4, 1.5] as const
const PLAY_MODE_OPTIONS = [
  { value: 'sequence', label: 'Sequence', icon: ListRestart },
  { value: 'article-loop', label: 'Full Audio Loop', icon: Repeat },
  { value: 'sentence-loop', label: 'Sentence Loop', icon: Repeat1 },
] as const

type PlayMode = (typeof PLAY_MODE_OPTIONS)[number]['value']

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

function getPlayModeLabel(playMode: PlayMode): string {
  return PLAY_MODE_OPTIONS.find((option) => option.value === playMode)?.label ?? 'Sequence'
}

function isSpeedOption(value: number): value is (typeof SPEED_OPTIONS)[number] {
  return SPEED_OPTIONS.some((option) => option === value)
}

export function ListeningPage() {
  const { sessionId = '' } = useParams()
  const [session, setSession] = useState<SessionSummary | null>(null)
  const [synthesis, setSynthesis] = useState<TtsSynthesisResponse | null>(null)
  const [speed, setSpeed] = useState<(typeof SPEED_OPTIONS)[number]>(1)
  const [playMode, setPlayMode] = useState<PlayMode>('sequence')
  const [isLoopMenuOpen, setIsLoopMenuOpen] = useState(false)
  const [isPlaying, setIsPlaying] = useState(false)
  const [volume, setVolume] = useState(1)
  const [revealedItemIds, setRevealedItemIds] = useState<Set<string>>(() => new Set())
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [currentTimeSecond, setCurrentTimeSecond] = useState(0)
  const [durationSecond, setDurationSecond] = useState(0)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const loopMenuRef = useRef<HTMLDivElement | null>(null)
  const activeSubtitleRef = useRef<HTMLButtonElement | null>(null)

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
        setIsPlaying(false)
        setRevealedItemIds(new Set())
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
    if (!audioRef.current) {
      return
    }

    audioRef.current.volume = volume
  }, [volume, audioUrl])

  useEffect(() => {
    if (!audioRef.current) {
      return
    }

    audioRef.current.loop = playMode === 'article-loop'
  }, [playMode, audioUrl])

  useEffect(() => {
    if (!isLoopMenuOpen) {
      return
    }

    function handlePointerDown(event: PointerEvent) {
      if (loopMenuRef.current?.contains(event.target as Node)) {
        return
      }
      setIsLoopMenuOpen(false)
    }

    function handleEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        setIsLoopMenuOpen(false)
      }
    }

    window.addEventListener('pointerdown', handlePointerDown)
    window.addEventListener('keydown', handleEscape)
    return () => {
      window.removeEventListener('pointerdown', handlePointerDown)
      window.removeEventListener('keydown', handleEscape)
    }
  }, [isLoopMenuOpen])

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

    const upperBound = resolvedDurationSecond ?? durationSecond
    const clampedSecond = upperBound && upperBound > 0 ? Math.min(Math.max(0, nextSecond), upperBound) : Math.max(0, nextSecond)
    audioRef.current.currentTime = clampedSecond
    setCurrentTimeSecond(clampedSecond)
  }

  function handleJumpToTimelineIndex(nextIndex: number) {
    if (nextIndex < 0 || nextIndex >= timeline.length) {
      return
    }

    handleSeek(Math.max(0, timeline[nextIndex].startSecond))
  }

  function handleTimeUpdate() {
    if (!audioRef.current) {
      return
    }

    const currentSecond = audioRef.current.currentTime
    if (playMode === 'sentence-loop') {
      const loopingEntry = timeline[activeIndex] ?? findActiveTimelineItem(timeline, currentSecond)
      if (loopingEntry && currentSecond >= loopingEntry.endSecond - 0.05) {
        audioRef.current.currentTime = loopingEntry.startSecond
        setCurrentTimeSecond(loopingEntry.startSecond)
        return
      }
    }

    setCurrentTimeSecond(currentSecond)
  }

  function togglePlayPause() {
    if (!audioRef.current) {
      return
    }

    if (audioRef.current.paused) {
      if (durationSecond > 0 && audioRef.current.currentTime >= durationSecond - 0.1) {
        audioRef.current.currentTime = 0
        setCurrentTimeSecond(0)
      }
      void audioRef.current.play().catch(() => {
        // Ignore autoplay restrictions.
      })
      return
    }

    audioRef.current.pause()
  }

  function toggleItemReveal(itemId: string) {
    setRevealedItemIds((current) => {
      const next = new Set(current)
      if (next.has(itemId)) {
        next.delete(itemId)
      } else {
        next.add(itemId)
      }
      return next
    })
  }

  const canJumpToPrevious = activeIndex > 0
  const canJumpToNext = activeIndex >= 0 && activeIndex < timeline.length - 1
  const progressDurationSecond = resolvedDurationSecond ?? durationSecond
  const playbackSliderMax = Math.max(progressDurationSecond ?? 0, 0.01)
  const playbackSliderValue = Math.min(currentTimeSecond, playbackSliderMax)
  const CurrentPlayModeIcon = playMode === 'sentence-loop' ? Repeat1 : playMode === 'article-loop' ? Repeat : ListRestart

  useEffect(() => {
    activeSubtitleRef.current?.scrollIntoView({
      block: 'nearest',
    })
  }, [activeTimelineItem?.item.item_id])

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
        <CardHeader className="py-4">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <CardTitle>Generated Audio</CardTitle>
            {synthesis?.status_name ? (
              <p className="text-sm text-slate-500">{`Status: ${synthesis.status_name}`}</p>
            ) : null}
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
                className="hidden"
                loop={playMode === 'article-loop'}
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
                onPlay={() => setIsPlaying(true)}
                onPause={() => setIsPlaying(false)}
                onEnded={() => setIsPlaying(false)}
                onTimeUpdate={handleTimeUpdate}
              >
                <track kind="captions" />
              </audio>

              <div className="rounded-lg border border-slate-200 bg-slate-50/80 px-4 py-3 text-slate-800 shadow-sm">
                <div className="flex flex-col gap-3 md:flex-row md:items-center">
                  <div className="flex items-center justify-center gap-2 md:justify-start">
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon-sm"
                      className="text-slate-600 hover:bg-white hover:text-slate-950 disabled:text-slate-300"
                      onClick={() => handleJumpToTimelineIndex(activeIndex - 1)}
                      disabled={!canJumpToPrevious}
                      aria-label="Previous sentence"
                      title="Previous sentence"
                    >
                      <SkipBack className="size-5" />
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon-lg"
                      className="rounded-full border border-slate-200 bg-white text-slate-700 shadow-xs hover:bg-slate-100 hover:text-slate-900"
                      onClick={togglePlayPause}
                      aria-label={isPlaying ? 'Pause' : 'Play'}
                      title={isPlaying ? 'Pause' : 'Play'}
                    >
                      {isPlaying ? <Pause className="size-6" /> : <Play className="size-6 fill-current" />}
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon-sm"
                      className="text-slate-600 hover:bg-white hover:text-slate-950 disabled:text-slate-300"
                      onClick={() => handleJumpToTimelineIndex(activeIndex + 1)}
                      disabled={!canJumpToNext}
                      aria-label="Next sentence"
                      title="Next sentence"
                    >
                      <SkipForward className="size-5" />
                    </Button>

                    <div ref={loopMenuRef} className="relative">
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon-sm"
                        className={`text-slate-600 hover:bg-white hover:text-slate-950 ${playMode === 'sequence' ? '' : 'bg-white text-slate-700 shadow-xs'
                          }`}
                        onClick={() => setIsLoopMenuOpen((value) => !value)}
                        aria-expanded={isLoopMenuOpen}
                        aria-label={getPlayModeLabel(playMode)}
                        title={getPlayModeLabel(playMode)}
                      >
                        <CurrentPlayModeIcon className="size-5" />
                      </Button>

                      {isLoopMenuOpen ? (
                        <div className="absolute bottom-11 left-1/2 z-20 w-14 -translate-x-1/2 rounded-md border border-slate-200 bg-white py-1 shadow-lg">
                          {PLAY_MODE_OPTIONS.map((option) => {
                            const Icon = option.icon
                            const isSelected = playMode === option.value
                            return (
                              <button
                                key={option.value}
                                type="button"
                                className={`group relative flex h-12 w-full items-center justify-center transition ${isSelected ? 'bg-slate-100 text-slate-800' : 'text-slate-500 hover:bg-slate-50 hover:text-slate-900'
                                  }`}
                                onClick={() => {
                                  setPlayMode(option.value)
                                  setIsLoopMenuOpen(false)
                                }}
                                aria-label={option.label}
                              >
                                <Icon className="size-5" />
                                <span className="pointer-events-none absolute right-full top-1/2 mr-2 hidden -translate-y-1/2 whitespace-nowrap rounded bg-slate-900 px-2.5 py-1.5 text-sm font-medium text-white shadow-sm group-hover:block">
                                  {option.label}
                                </span>
                              </button>
                            )
                          })}
                        </div>
                      ) : null}
                    </div>

                    <div className="flex items-center gap-2">
                      <Volume2 className="size-5 text-slate-500" aria-hidden="true" />
                      <Slider
                        className="w-16"
                        max={1}
                        min={0}
                        onValueChange={(nextValue) => setVolume(nextValue[0] ?? 0)}
                        step={0.01}
                        thumbLabel="Volume"
                        value={[volume]}
                      />
                    </div>
                  </div>

                  <div className="flex min-w-0 flex-1 items-center gap-3">
                    <span className="w-11 text-right text-xs tabular-nums text-slate-500">{formatDuration(currentTimeSecond)}</span>
                    <Slider
                      className="min-w-0 flex-1"
                      min={0}
                      max={playbackSliderMax}
                      onValueChange={(nextValue) => handleSeek(nextValue[0] ?? 0)}
                      step={0.01}
                      thumbLabel="Playback progress"
                      value={[playbackSliderValue]}
                    />
                    <span className="w-11 text-xs tabular-nums text-slate-500">{formatDuration(progressDurationSecond ?? null)}</span>
                  </div>

                  <div className="flex items-center justify-center md:justify-end">
                    <select
                      className="h-8 rounded-md border border-slate-200 bg-white px-2 text-sm font-medium text-slate-600 shadow-xs outline-none transition hover:text-slate-900 focus:border-slate-300 focus:ring-2 focus:ring-slate-200"
                      value={speed}
                      onChange={(event) => {
                        const nextSpeed = Number(event.target.value)
                        if (isSpeedOption(nextSpeed)) {
                          setSpeed(nextSpeed)
                        }
                      }}
                      aria-label="Playback speed"
                    >
                      {SPEED_OPTIONS.map((value) => (
                        <option key={value} value={value}>
                          {value}x
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              </div>
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
          <CardTitle>Subtitles</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {timeline.length > 0 ? (
            <div className="max-h-[28rem] space-y-2 overflow-y-auto pr-1">
              {timeline.map((entry, index) => {
                const isActive = entry.item.item_id === activeTimelineItem?.item.item_id
                const isRevealed = revealedItemIds.has(entry.item.item_id)
                return (
                  <button
                    key={entry.item.item_id}
                    ref={isActive ? activeSubtitleRef : null}
                    type="button"
                    onClick={() => {
                      handleJumpToTimelineIndex(index)
                      toggleItemReveal(entry.item.item_id)
                    }}
                    className={`w-full rounded-lg border px-4 py-3 text-left transition ${isActive
                      ? 'border-slate-300 bg-slate-100 shadow-sm'
                      : 'border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50'
                      }`}
                  >
                    <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
                      <span className={`rounded-full px-2.5 py-1 ${isActive ? 'bg-slate-200 text-slate-700' : 'bg-slate-100'}`}>
                        {`Sentence ${index + 1}`}
                      </span>
                      <span className={`rounded-full px-2.5 py-1 ${isActive ? 'bg-slate-200 text-slate-700' : 'bg-slate-100'}`}>
                        {normalizeSpeakerLabel(entry.item.conversation_speaker)}
                      </span>
                      <span>{`${formatDuration(entry.startSecond)}-${formatDuration(entry.endSecond)}`}</span>
                      {isActive && isPlaying ? (
                        <span className="inline-flex size-6 items-center justify-center rounded-full bg-white text-slate-800 shadow-sm">
                          <Play className="size-3 animate-spin fill-current" />
                        </span>
                      ) : null}
                    </div>
                    {isRevealed ? (
                      <p className={`mt-3 leading-7 ${isActive ? 'font-semibold text-slate-950' : 'text-slate-700'}`}>
                        {entry.item.plain_text}
                      </p>
                    ) : (
                      <div
                        className={`mt-3 flex min-h-20 items-center justify-center rounded-md text-sm font-medium ${
                          isActive ? 'bg-slate-200/70 text-slate-700' : 'bg-slate-50 text-slate-500'
                        }`}
                      >
                        Click to show original text
                      </div>
                    )}
                  </button>
                )
              })}
            </div>
          ) : isLoading ? (
            <p className="text-sm text-slate-600">Preparing subtitles...</p>
          ) : (
            <p className="text-sm text-slate-600">No synthesized sentence available yet.</p>
          )}
        </CardContent>
      </Card>
    </section>
  )
}
