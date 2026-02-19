import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { PageTitle } from '@/components/common/page-title'
import { StatusBadge } from '@/components/common/status-badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { getUploadByTaskId } from '@/lib/storage/upload-history'
import { formatBytes, formatDateTime, formatDuration } from '@/lib/utils/format'
import type { TaskStatus } from '@/types/domain'

const STEP_ORDER: Exclude<TaskStatus, 'failed'>[] = ['uploaded', 'transcribing', 'analyzing', 'completed']

const STATUS_PRIORITY: Record<TaskStatus, number> = {
  uploaded: 1,
  transcribing: 2,
  analyzing: 3,
  completed: 4,
  failed: -1,
}

function inferTaskStatus(uploadedAt: string): TaskStatus {
  const elapsedSec = Math.floor((Date.now() - Date.parse(uploadedAt)) / 1000)

  if (elapsedSec < 12) {
    return 'uploaded'
  }

  if (elapsedSec < 45) {
    return 'transcribing'
  }

  if (elapsedSec < 80) {
    return 'analyzing'
  }

  return 'completed'
}

export function TaskPage() {
  const { taskId = 'unknown-task' } = useParams()
  const [, setTick] = useState(0)

  useEffect(() => {
    const timer = window.setInterval(() => {
      setTick((value) => value + 1)
    }, 1000)

    return () => window.clearInterval(timer)
  }, [])

  const uploadRecord = useMemo(() => getUploadByTaskId(taskId), [taskId])

  const currentStatus: TaskStatus = uploadRecord ? inferTaskStatus(uploadRecord.uploadedAt) : 'uploaded'

  const targetSummaryId = uploadRecord?.summaryId ?? `summary_${taskId.replace(/^task_/, '')}`

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
            <CardDescription>Simulated status flow until backend task APIs are available.</CardDescription>
          </CardHeader>
          <CardContent>
            <ol className="space-y-3">
              {STEP_ORDER.map((step, index) => {
                const isDone = STATUS_PRIORITY[step] <= STATUS_PRIORITY[currentStatus]

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
            {uploadRecord ? (
              <>
                <p>
                  <span className="font-medium">File:</span> {uploadRecord.fileName}
                </p>
                <p>
                  <span className="font-medium">Size:</span> {formatBytes(uploadRecord.fileSize)}
                </p>
                <p>
                  <span className="font-medium">Duration:</span> {formatDuration(uploadRecord.durationSec)}
                </p>
                <p>
                  <span className="font-medium">Uploaded:</span> {formatDateTime(uploadRecord.uploadedAt)}
                </p>
                <p className="break-all text-xs text-slate-600">
                  <span className="font-medium text-slate-700">object_key:</span> {uploadRecord.objectKey}
                </p>
              </>
            ) : (
              <p className="text-slate-600">
                No local upload record found for this task. You can still preview summary layout with demo data.
              </p>
            )}

            <div className="pt-2">
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
