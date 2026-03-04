import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { PageTitle } from '@/components/common/page-title'
import { StatusBadge } from '@/components/common/status-badge'
import { getTask, refreshTask } from '@/lib/api/tasks'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { formatDateTime } from '@/lib/utils/format'
import type { TaskStatus } from '@/types/domain'
import type { TaskItem } from '@/types/api'

const STEP_ORDER: Exclude<TaskStatus, 'failed'>[] = ['uploaded', 'transcribing', 'analyzing', 'completed']

const STATUS_PRIORITY: Record<TaskStatus, number> = {
  uploaded: 1,
  transcribing: 2,
  analyzing: 3,
  completed: 4,
  failed: -1,
}

function parseTaskStatus(statusName: string | undefined): TaskStatus {
  if (statusName === 'uploaded') return 'uploaded'
  if (statusName === 'transcribing') return 'transcribing'
  if (statusName === 'analyzing') return 'analyzing'
  if (statusName === 'completed') return 'completed'
  if (statusName === 'failed') return 'failed'
  return 'uploaded'
}

export function TaskPage() {
  const { taskId = 'unknown-task' } = useParams()
  const [task, setTask] = useState<TaskItem | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  const fetchTask = useCallback(
    async (refresh = true) => {
      try {
        const result = await getTask(taskId, { refresh })
        setTask(result)
        setErrorMessage(null)
      } catch (error) {
        setErrorMessage(error instanceof Error ? error.message : 'Failed to load task details.')
      } finally {
        setIsLoading(false)
      }
    },
    [taskId],
  )

  useEffect(() => {
    setIsLoading(true)
    void fetchTask(true)
  }, [fetchTask])

  useEffect(() => {
    if (!task) {
      return
    }
    const status = parseTaskStatus(task.status_name)
    if (status === 'completed' || status === 'failed') {
      return
    }

    const timer = window.setInterval(() => {
      void fetchTask(true)
    }, 3000)

    return () => window.clearInterval(timer)
  }, [fetchTask, task])

  const currentStatus: TaskStatus = parseTaskStatus(task?.status_name)
  const targetSummaryId = `summary_${taskId}`

  return (
    <section className="space-y-6">
      <PageTitle
        eyebrow="Step 2"
        title="Processing Task"
        description={`Track progress from upload to transcript + summary generation. Task ID: ${taskId}`}
        actions={<StatusBadge status={currentStatus} />}
      />

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="bg-white/90 shadow-sm lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-lg">Pipeline Timeline</CardTitle>
            <CardDescription>Realtime task status from backend APIs.</CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? <p className="pb-3 text-sm text-slate-600">Loading task...</p> : null}
            {errorMessage ? (
              <div className="mb-3 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">
                {errorMessage}
              </div>
            ) : null}
            <ol className="space-y-3">
              {STEP_ORDER.map((step, index) => {
                const isDone = currentStatus !== 'failed' && STATUS_PRIORITY[step] <= STATUS_PRIORITY[currentStatus]

                return (
                  <li
                    key={step}
                    className="flex items-center justify-between rounded-lg border border-slate-200 bg-slate-50/70 px-4 py-3"
                  >
                    <span className="text-sm font-medium text-slate-700">
                      {index + 1}. {step}
                    </span>
                    <StatusBadge status={isDone ? step : 'uploaded'} />
                  </li>
                )
              })}
            </ol>
          </CardContent>
        </Card>

        <Card className="bg-white/90 shadow-sm">
          <CardHeader>
            <CardTitle className="text-lg">Task Context</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm text-slate-700">
            {task ? (
              <>
                <p>
                  <span className="font-medium">Backend Task ID:</span> {task.task_id}
                </p>
                <p>
                  <span className="font-medium">Status:</span> {task.status_name} ({task.status})
                </p>
                <p className="break-all text-xs text-slate-600">
                  <span className="font-medium text-slate-700">object_key:</span> {task.object_key}
                </p>
                {task.audio_url ? (
                  <p className="break-all text-xs text-slate-600">
                    <span className="font-medium text-slate-700">audio_url:</span> {task.audio_url}
                  </p>
                ) : null}
                {task.provider ? (
                  <p>
                    <span className="font-medium">Provider:</span> {task.provider}
                  </p>
                ) : null}
                <p>
                  <span className="font-medium">Created:</span> {formatDateTime(task.created_at)}
                </p>
                <p>
                  <span className="font-medium">Updated:</span> {formatDateTime(task.updated_at)}
                </p>
                {task.error_message ? (
                  <p className="rounded border border-rose-200 bg-rose-50 p-2 text-rose-700">
                    <span className="font-medium">Error:</span> {task.error_message}
                  </p>
                ) : null}
              </>
            ) : !task ? (
              <p className="text-slate-600">
                No task data available yet.
              </p>
            ) : (
              <p className="text-slate-600">
                No extra task context available.
              </p>
            )}

            <div className="flex flex-wrap gap-2 pt-2">
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={isRefreshing || isLoading}
                onClick={async () => {
                  try {
                    setIsRefreshing(true)
                    const result = await refreshTask(taskId)
                    setTask(result)
                    setErrorMessage(null)
                  } catch (error) {
                    setErrorMessage(error instanceof Error ? error.message : 'Failed to refresh task status.')
                  } finally {
                    setIsRefreshing(false)
                  }
                }}
              >
                {isRefreshing ? 'Refreshing...' : 'Refresh Now'}
              </Button>
              <Button asChild size="sm" disabled={currentStatus !== 'completed'}>
                <Link to={`/summaries/${targetSummaryId}`}>Open Summary</Link>
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </section>
  )
}
