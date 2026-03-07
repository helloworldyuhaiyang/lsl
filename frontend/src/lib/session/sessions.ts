import { getSession, listSessions } from '@/lib/api/sessions'
import { getTaskTranscript } from '@/lib/api/tasks'
import { getSessionMetadata } from '@/lib/session/session-storage'
import type { SessionItem, TaskTranscriptData } from '@/types/api'
import type { TaskStatus } from '@/types/domain'

export interface SessionSummary {
  sessionId: string
  taskId: string | null
  title: string
  description: string
  fileName: string
  fileSize: number | null
  durationSec: number | null
  status: TaskStatus
  statusName: string
  createdAt: string
  updatedAt: string
  objectKey: string
  audioUrl: string | null
}

interface ListSessionSummariesParams {
  query?: string
  limit?: number
}

function normalizeTaskStatus(statusName: string | undefined): TaskStatus {
  if (statusName === 'uploaded') return 'uploaded'
  if (statusName === 'transcribing') return 'transcribing'
  if (statusName === 'analyzing') return 'analyzing'
  if (statusName === 'completed') return 'completed'
  if (statusName === 'failed') return 'failed'
  return 'uploaded'
}

function getObjectFileName(objectKey: string | null | undefined, fallback: string): string {
  const lastSegment = objectKey?.split('/').at(-1)?.trim()
  return lastSegment || fallback
}

function getSessionLocalMetadata(item: SessionItem) {
  return getSessionMetadata(item.session.session_id) ?? (
    item.session.current_task_id ? getSessionMetadata(item.session.current_task_id) : null
  )
}

function mapSessionItemToSummary(item: SessionItem): SessionSummary {
  const local = getSessionLocalMetadata(item)
  const taskId = item.task?.task_id ?? item.session.current_task_id ?? null
  const objectKey = item.asset?.object_key ?? item.task?.object_key ?? item.session.asset_object_key ?? ''

  let durationSec: number | null = null
  if (typeof item.task?.duration_sec === 'number') {
    durationSec = item.task.duration_sec
  } else if (typeof item.task?.duration_ms === 'number') {
    durationSec = item.task.duration_ms / 1000
  } else if (typeof local?.durationSec === 'number') {
    durationSec = local.durationSec
  }

  return {
    sessionId: item.session.session_id,
    taskId,
    title: local?.title?.trim() || item.session.title,
    description: local?.description?.trim() || item.session.description?.trim() || '',
    fileName: local?.fileName || item.asset?.filename || getObjectFileName(objectKey, item.session.session_id),
    fileSize: typeof local?.fileSize === 'number' ? local.fileSize : (item.asset?.file_size ?? null),
    durationSec,
    status: normalizeTaskStatus(item.task?.status_name),
    statusName: item.task?.status_name ?? 'uploaded',
    createdAt: item.session.created_at,
    updatedAt: item.session.updated_at,
    objectKey,
    audioUrl: item.task?.audio_url ?? item.asset?.asset_url ?? null,
  }
}

function isSessionNotFoundError(error: unknown): boolean {
  return error instanceof Error && /session not found/i.test(error.message)
}

async function resolveSessionItem(sessionIdOrTaskId: string): Promise<SessionItem> {
  try {
    return await getSession(sessionIdOrTaskId)
  } catch (error) {
    if (!isSessionNotFoundError(error)) {
      throw error
    }
  }

  const sessions = await listSessions({ limit: 100 })
  const matched = sessions.find(
    (item) => item.session.current_task_id === sessionIdOrTaskId || item.task?.task_id === sessionIdOrTaskId,
  )

  if (!matched) {
    throw new Error('session not found')
  }

  return matched
}

export async function listSessionSummaries({ query = '', limit = 50 }: ListSessionSummariesParams = {}): Promise<SessionSummary[]> {
  const sessions = await listSessions({
    limit: Math.min(Math.max(limit, 1), 100),
    query: query.trim() || undefined,
  })

  return sessions.map(mapSessionItemToSummary)
}

export async function getSessionSummary(sessionId: string): Promise<SessionSummary> {
  const item = await resolveSessionItem(sessionId)
  return mapSessionItemToSummary(item)
}

export async function getSessionTranscript(sessionId: string): Promise<TaskTranscriptData> {
  const item = await resolveSessionItem(sessionId)
  const taskId = item.task?.task_id ?? item.session.current_task_id

  if (!taskId) {
    throw new Error('session current_task_id is missing')
  }

  return getTaskTranscript(taskId)
}
