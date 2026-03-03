import { requestJson } from '@/lib/api/client'
import type { CreateTaskRequest, TaskItem, TaskListResponse, TaskTranscriptData } from '@/types/api'

interface ApiResponse<T> {
  code: number
  message: string
  data: T
}

interface GetTaskParams {
  refresh?: boolean
}

interface ListTasksParams {
  limit?: number
  status?: number
  category?: string
  entityId?: string
}

export async function createTask(payload: CreateTaskRequest): Promise<TaskItem> {
  const response = await requestJson<ApiResponse<TaskItem>>('/tasks', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      object_key: payload.objectKey,
      audio_url: payload.audioUrl,
      language: payload.language,
    }),
  })
  return response.data
}

export async function getTask(taskId: string, { refresh = true }: GetTaskParams = {}): Promise<TaskItem> {
  const response = await requestJson<ApiResponse<TaskItem>>(`/tasks/${taskId}`, {
    method: 'GET',
    query: {
      refresh: String(refresh),
    },
  })
  return response.data
}

export async function refreshTask(taskId: string): Promise<TaskItem> {
  const response = await requestJson<ApiResponse<TaskItem>>(`/tasks/${taskId}/refresh`, {
    method: 'POST',
  })
  return response.data
}

export async function listTasks({
  limit = 20,
  status,
  category,
  entityId,
}: ListTasksParams = {}): Promise<TaskItem[]> {
  const query: Record<string, string> = {
    limit: String(limit),
  }
  if (typeof status === 'number') {
    query.status = String(status)
  }
  if (category) {
    query.category = category
  }
  if (entityId) {
    query.entity_id = entityId
  }

  const response = await requestJson<ApiResponse<TaskListResponse>>('/tasks', {
    method: 'GET',
    query,
  })
  return response.data.items
}

export async function getTaskTranscript(taskId: string, includeRaw = false): Promise<TaskTranscriptData> {
  const response = await requestJson<ApiResponse<TaskTranscriptData>>(`/tasks/${taskId}/transcript`, {
    method: 'GET',
    query: {
      include_raw: String(includeRaw),
    },
  })
  return response.data
}
