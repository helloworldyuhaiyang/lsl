import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { PageTitle } from '@/components/common/page-title'
import { getTask, getTaskTranscript } from '@/lib/api/tasks'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { formatDuration } from '@/lib/utils/format'
import type { TaskItem, TaskTranscriptData } from '@/types/api'

const SECTIONS = ['transcript', 'improvements', 'listening'] as const

type Section = (typeof SECTIONS)[number]

function extractTaskId(summaryId: string): string | null {
  if (summaryId.startsWith('summary_')) {
    return summaryId.slice('summary_'.length)
  }
  return null
}

function formatTimeFromMs(milliseconds: number): string {
  return formatDuration(milliseconds / 1000)
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

export function SummaryPage() {
  const { summaryId = 'unknown-summary' } = useParams()
  const [section, setSection] = useState<Section>('transcript')
  const [transcript, setTranscript] = useState<TaskTranscriptData | null>(null)
  const [isLoadingTranscript, setIsLoadingTranscript] = useState(false)
  const [transcriptError, setTranscriptError] = useState<string | null>(null)
  const [taskStatusName, setTaskStatusName] = useState<string | null>(null)
  const [task, setTask] = useState<TaskItem | null>(null)
  const [activeUtteranceSeq, setActiveUtteranceSeq] = useState<number | null>(null)
  const audioRef = useRef<HTMLAudioElement | null>(null)

  const taskId = useMemo(() => extractTaskId(summaryId), [summaryId])

  function playFromUtterance(startTimeMs: number, seq: number) {
    if (!audioRef.current || !task?.audio_url) {
      return
    }
    audioRef.current.currentTime = startTimeMs / 1000
    setActiveUtteranceSeq(seq)
    void audioRef.current.play().catch(() => {
      // Ignore autoplay rejection; user can press play manually after seeking.
    })
  }

  function handleAudioTimeUpdate() {
    if (!audioRef.current || !transcript) {
      return
    }
    const positionMs = audioRef.current.currentTime * 1000
    const current = transcript.utterances.find(
      (item) => positionMs >= item.start_time && positionMs <= item.end_time + 120,
    )
    setActiveUtteranceSeq(current?.seq ?? null)
  }

  useEffect(() => {
    function handleGlobalSpaceToggle(event: KeyboardEvent) {
      if (event.code !== 'Space' || event.defaultPrevented) {
        return
      }
      if (isEditableElement(event.target) || !audioRef.current || !task?.audio_url) {
        return
      }

      event.preventDefault()
      if (audioRef.current.paused) {
        void audioRef.current.play().catch(() => {
          // Ignore autoplay rejection; user can press play manually after interaction.
        })
        return
      }
      audioRef.current.pause()
    }

    window.addEventListener('keydown', handleGlobalSpaceToggle)
    return () => {
      window.removeEventListener('keydown', handleGlobalSpaceToggle)
    }
  }, [task?.audio_url])

  useEffect(() => {
    if (!taskId) {
      setTranscript(null)
      setTaskStatusName(null)
      setTranscriptError('Unable to resolve task id from summary id.')
      return
    }
    const resolvedTaskId = taskId

    let cancelled = false

    async function loadTranscript() {
      setIsLoadingTranscript(true)
      try {
        const task = await getTask(resolvedTaskId, { refresh: true })
        if (cancelled) {
          return
        }
        setTask(task)
        setTaskStatusName(task.status_name)

        if (task.status_name !== 'completed') {
          setTranscript(null)
          setTranscriptError(`Task is ${task.status_name}. Transcript is available after task completed.`)
          return
        }

        const data = await getTaskTranscript(resolvedTaskId)
        if (cancelled) {
          return
        }
        setTranscript(data)
        setTranscriptError(null)
      } catch (error) {
        if (cancelled) {
          return
        }
        setTranscript(null)
        setTranscriptError(error instanceof Error ? error.message : 'Failed to fetch transcript.')
      } finally {
        if (!cancelled) {
          setIsLoadingTranscript(false)
        }
      }
    }

    void loadTranscript()

    return () => {
      cancelled = true
    }
  }, [taskId])

  return (
    <section className="space-y-6">
      <PageTitle
        eyebrow="Step 3"
        title="Conversation Summary"
        description={`Review transcript, expression refinements, and listening loop material. Summary ID: ${summaryId}`}
        actions={
          <Button asChild variant="outline" size="sm">
            <Link to={taskId ? `/tasks/${taskId}` : '/upload'}>Back to Task</Link>
          </Button>
        }
      />

      <Card className="bg-white/90 shadow-sm">
        <CardHeader>
          <CardTitle className="text-lg">Section Switcher</CardTitle>
          <CardDescription>Transcript section is connected to backend task transcript API.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          {SECTIONS.map((item) => (
            <Button
              key={item}
              type="button"
              size="sm"
              variant={section === item ? 'default' : 'outline'}
              onClick={() => setSection(item)}
            >
              {item}
            </Button>
          ))}
        </CardContent>
      </Card>

      {section === 'transcript' ? (
        <Card className="bg-white/90 shadow-sm">
          <CardHeader>
            <CardTitle className="text-lg">Transcript</CardTitle>
            {transcript?.duration_ms ? (
              <CardDescription>Total Duration: {formatTimeFromMs(transcript.duration_ms)}</CardDescription>
            ) : null}
          </CardHeader>
          <CardContent className="space-y-3">
            {task?.audio_url ? (
              <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                <audio ref={audioRef} className="w-full" controls src={task.audio_url} onTimeUpdate={handleAudioTimeUpdate}>
                  <track kind="captions" />
                </audio>
              </div>
            ) : null}
            {isLoadingTranscript ? <p className="text-sm text-slate-600">Loading transcript...</p> : null}
            {transcriptError ? (
              <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
                {transcriptError}
              </div>
            ) : null}

            {!isLoadingTranscript && !transcriptError && transcript ? (
              transcript.utterances.length > 0 ? (
                <ul className="space-y-3">
                  {transcript.utterances.map((item) => (
                    <li
                      key={`${item.seq}-${item.start_time}`}
                      role="button"
                      tabIndex={0}
                      onClick={() => playFromUtterance(item.start_time, item.seq)}
                      onKeyDown={(event) => {
                        if (event.key === 'Enter') {
                          event.preventDefault()
                          playFromUtterance(item.start_time, item.seq)
                        }
                      }}
                      className={`rounded-lg border p-4 transition ${activeUtteranceSeq === item.seq
                          ? 'border-cyan-300 bg-cyan-50/80'
                          : 'border-slate-200 bg-slate-50/70'
                        } ${task?.audio_url ? 'cursor-pointer hover:border-cyan-200' : 'cursor-default'}`}
                    >
                      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
                        {formatTimeFromMs(item.start_time)}-{formatTimeFromMs(item.end_time)} ·{' '}
                        {(item.speaker || 'speaker').replace('_', ' ')}
                      </p>
                      <p className="mt-2 text-sm text-slate-800">{item.text}</p>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-slate-600">Transcript is empty.</p>
              )
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      {section === 'improvements' ? (
        <Card className="bg-white/90 shadow-sm">
          <CardHeader>
            <CardTitle className="text-lg">Expression Improvements</CardTitle>
            <CardDescription>LLM refinement output is not connected yet.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {transcript?.utterances?.slice(0, 5).map((item) => (
              <article key={`${item.seq}-${item.start_time}`} className="rounded-lg border border-slate-200 p-4">
                <p className="text-xs text-slate-500">
                  {formatTimeFromMs(item.start_time)}-{formatTimeFromMs(item.end_time)}
                </p>
                <p className="mt-2 text-sm text-slate-600">Original: {item.text}</p>
                <p className="mt-1 text-sm font-medium text-slate-900">Optimized: Pending</p>
                <p className="mt-1 text-xs text-slate-500">Reason: Pending LLM analysis.</p>
              </article>
            ))}
            {!transcript?.utterances?.length ? <p className="text-sm text-slate-600">No transcript lines yet.</p> : null}
          </CardContent>
        </Card>
      ) : null}

      {section === 'listening' ? (
        <Card className="bg-white/90 shadow-sm">
          <CardHeader>
            <CardTitle className="text-lg">Listening Replay</CardTitle>
            <CardDescription>
              TTS output is not integrated yet. The player below uses original uploaded audio when available.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {task?.audio_url ? (
              <>
                <p className="text-sm text-slate-700">
                  Source file: {task?.object_key?.split('/').at(-1) ?? 'task audio'}
                </p>
                <audio ref={audioRef} className="w-full" controls src={task?.audio_url ?? undefined} onTimeUpdate={handleAudioTimeUpdate}>
                  <track kind="captions" />
                </audio>
                <Button asChild size="sm" variant="outline">
                  <a href={task?.audio_url ?? '#'} target="_blank" rel="noreferrer">
                    Open Source Audio URL
                  </a>
                </Button>
              </>
            ) : (
              <p className="text-sm text-slate-600">
                No audio URL found for this task.
              </p>
            )}
            {taskStatusName ? (
              <p className="text-xs text-slate-500">Current task status: {taskStatusName}</p>
            ) : null}
          </CardContent>
        </Card>
      ) : null}
    </section>
  )
}
