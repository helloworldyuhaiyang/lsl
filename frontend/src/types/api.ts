export interface UploadUrlRequest {
  category: string
  entityId: string
  filename: string
  contentType: string
}

export interface UploadUrlResponse {
  object_key: string
  upload_url: string
  asset_url: string
}

export interface CompleteUploadRequest {
  objectKey: string
  category?: string
  entityId?: string
  filename?: string
  contentType?: string
  fileSize?: number
  etag?: string
}

export interface CompleteUploadResponse {
  object_key: string
  asset_url: string
  status: string
}

export interface AssetListItem {
  object_key: string
  category: string
  entity_id: string
  filename?: string | null
  content_type?: string | null
  file_size?: number | null
  etag?: string | null
  upload_status: number
  created_at: string
  asset_url: string
}

export interface AssetListResponse {
  items: AssetListItem[]
}

export interface TaskItem {
  task_id: string
  object_key: string
  audio_url?: string | null
  duration_ms?: number | null
  duration_sec?: number | null
  status: number
  status_name: string
  language?: string | null
  provider?: string | null
  error_code?: string | null
  error_message?: string | null
  created_at: string
  updated_at: string
}

export interface CreateTaskRequest {
  objectKey: string
  audioUrl: string
  language?: string
}

export interface TaskListResponse {
  items: TaskItem[]
}

export interface SessionEntity {
  session_id: string
  title: string
  description?: string | null
  language?: string | null
  f_type: number
  asset_object_key?: string | null
  current_task_id?: string | null
  created_at: string
  updated_at: string
}

export interface SessionItem {
  session: SessionEntity
  asset?: AssetListItem | null
  task?: TaskItem | null
}

export interface SessionListResponse {
  items: SessionItem[]
}

export interface CreateSessionRequest {
  title: string
  description?: string
  language?: string
  fType?: 1 | 2
  assetObjectKey?: string
  currentTaskId?: string
}

export interface TaskTranscriptUtterance {
  seq: number
  text: string
  speaker?: string | null
  start_time: number
  end_time: number
  additions: Record<string, unknown>
}

export interface TaskTranscriptData {
  task_id: string
  duration_ms?: number | null
  full_text?: string | null
  utterances: TaskTranscriptUtterance[]
  raw_result?: Record<string, unknown> | null
}
