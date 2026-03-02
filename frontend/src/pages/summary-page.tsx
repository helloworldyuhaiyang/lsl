import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { PageTitle } from '@/components/common/page-title'
import { getTask, getTaskTranscript } from '@/lib/api/tasks'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { getUploadBySummaryId } from '@/lib/storage/upload-history'
import { formatDuration } from '@/lib/utils/format'
import type { TaskTranscriptData } from '@/types/api'

const SECTIONS = ['transcript', 'improvements', 'listening'] as const

type Section = (typeof SECTIONS)[number]

function extractTaskId(summaryId: string, recordTaskId?: string): string | null {
  if (recordTaskId) {
    return recordTaskId
  }
  if (summaryId.startsWith('summary_')) {
    return summaryId.slice('summary_'.length)
  }
  return null
}

function formatTimeFromMs(milliseconds: number): string {
  return formatDuration(milliseconds / 1000)
}

export function SummaryPage() {
  const { summaryId = 'unknown-summary' } = useParams()
  const [section, setSection] = useState<Section>('transcript')
  const [transcript, setTranscript] = useState<TaskTranscriptData | null>(null)
  const [isLoadingTranscript, setIsLoadingTranscript] = useState(false)
  const [transcriptError, setTranscriptError] = useState<string | null>(null)
  const [taskStatusName, setTaskStatusName] = useState<string | null>(null)

  const record = useMemo(() => getUploadBySummaryId(summaryId), [summaryId])
  const taskId = useMemo(() => extractTaskId(summaryId, record?.taskId), [record?.taskId, summaryId])

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
            <CardTitle className="text-lg">Transcript Timeline</CardTitle>
            {transcript?.duration_ms ? (
              <CardDescription>Total Duration: {formatTimeFromMs(transcript.duration_ms)}</CardDescription>
            ) : null}
          </CardHeader>
          <CardContent>
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
                    <li key={`${item.seq}-${item.start_time}`} className="rounded-lg border border-slate-200 bg-slate-50/70 p-4">
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
            {record ? (
              <>
                <p className="text-sm text-slate-700">Source file: {record.fileName}</p>
                <audio className="w-full" controls src={record.assetUrl}>
                  <track kind="captions" />
                </audio>
                <Button asChild size="sm" variant="outline">
                  <a href={record.assetUrl} target="_blank" rel="noreferrer">
                    Open Source Audio URL
                  </a>
                </Button>
              </>
            ) : (
              <p className="text-sm text-slate-600">
                No matching upload record in localStorage. Upload a file first to preview listening replay.
              </p>
            )}
            {!record && taskStatusName ? (
              <p className="text-xs text-slate-500">Current task status: {taskStatusName}</p>
            ) : null}
          </CardContent>
        </Card>
      ) : null}
    </section>
  )
}
