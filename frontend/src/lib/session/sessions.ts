import { getTask, getTaskTranscript, listTasks } from '@/lib/api/tasks'
import { listAssets } from '@/lib/api/upload'
import { getSessionMetadata, listSessionMetadata } from '@/lib/session/session-storage'
import type { AssetListItem, TaskItem, TaskTranscriptData } from '@/types/api'
import type { TaskStatus } from '@/types/domain'

export interface SessionSummary {
  sessionId: string
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

function getBaseName(value: string): string {
  const lastSegment = value.split('/').at(-1) ?? value
  const dotIndex = lastSegment.lastIndexOf('.')
  return dotIndex > 0 ? lastSegment.slice(0, dotIndex) : lastSegment
}

function toTitleCase(input: string): string {
  return input
    .replace(/[-_]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/\b\w/g, (char) => char.toUpperCase())
}

function normalizeTaskStatus(statusName: string | undefined): TaskStatus {
  if (statusName === 'uploaded') return 'uploaded'
  if (statusName === 'transcribing') return 'transcribing'
  if (statusName === 'analyzing') return 'analyzing'
  if (statusName === 'completed') return 'completed'
  if (statusName === 'failed') return 'failed'
  return 'uploaded'
}

function resolveTitle(task: TaskItem, asset?: AssetListItem, localTitle?: string): string {
  if (localTitle && localTitle.trim().length > 0) {
    return localTitle.trim()
  }

  const fileName = asset?.filename ?? task.object_key.split('/').at(-1) ?? task.task_id
  return toTitleCase(getBaseName(fileName))
}

function mapTaskToSessionSummary(task: TaskItem, assetsByObjectKey: Map<string, AssetListItem>): SessionSummary {
  const asset = assetsByObjectKey.get(task.object_key)
  const local = getSessionMetadata(task.task_id)

  return {
    sessionId: task.task_id,
    title: resolveTitle(task, asset, local?.title),
    description: local?.description?.trim() ?? '',
    fileName: local?.fileName ?? asset?.filename ?? task.object_key.split('/').at(-1) ?? task.task_id,
    fileSize: typeof local?.fileSize === 'number' ? local.fileSize : (asset?.file_size ?? null),
    durationSec: typeof local?.durationSec === 'number' ? local.durationSec : (local?.durationSec ?? null),
    status: normalizeTaskStatus(task.status_name),
    statusName: task.status_name,
    createdAt: task.created_at,
    updatedAt: task.updated_at,
    objectKey: task.object_key,
    audioUrl: task.audio_url ?? asset?.asset_url ?? null,
  }
}

export async function listSessionSummaries({ query = '', limit = 50 }: ListSessionSummariesParams = {}): Promise<SessionSummary[]> {
  const [tasks, assets] = await Promise.all([
    listTasks({
      limit: Math.max(limit, 50),
      category: 'conversation',
      entityId: 'web_user',
    }),
    listAssets({
      limit: Math.max(limit, 50),
      category: 'conversation',
      entityId: 'web_user',
    }),
  ])

  const assetsByObjectKey = assets.reduce((acc, item) => {
    acc.set(item.object_key, item)
    return acc
  }, new Map<string, AssetListItem>())

  const sessions = tasks
    .map((task) => mapTaskToSessionSummary(task, assetsByObjectKey))
    .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())

  const normalizedQuery = query.trim().toLowerCase()
  if (!normalizedQuery) {
    return sessions.slice(0, limit)
  }

  return sessions
    .filter((item) => {
      const target = [item.title, item.description, item.fileName, item.objectKey].join(' ').toLowerCase()
      return target.includes(normalizedQuery)
    })
    .slice(0, limit)
}

export async function getSessionSummary(sessionId: string, refresh = true): Promise<SessionSummary> {
  const task = await getTask(sessionId, { refresh })

  const localMap = listSessionMetadata()
  const local = localMap[sessionId]

  return {
    sessionId: task.task_id,
    title: resolveTitle(task, undefined, local?.title),
    description: local?.description?.trim() ?? '',
    fileName: local?.fileName ?? task.object_key.split('/').at(-1) ?? task.task_id,
    fileSize: typeof local?.fileSize === 'number' ? local.fileSize : null,
    durationSec: typeof local?.durationSec === 'number' ? local.durationSec : (local?.durationSec ?? null),
    status: normalizeTaskStatus(task.status_name),
    statusName: task.status_name,
    createdAt: task.created_at,
    updatedAt: task.updated_at,
    objectKey: task.object_key,
    audioUrl: task.audio_url ?? null,
  }
}

export async function getSessionTranscript(sessionId: string): Promise<TaskTranscriptData> {
  return getTaskTranscript(sessionId)
}
