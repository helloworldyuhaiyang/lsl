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

export interface JobItem {
  job_id: string
  job_type: string
  status: number
  status_name: string
  entity_type?: string | null
  entity_id?: string | null
  progress: number
  attempts: number
  error_code?: string | null
  error_message?: string | null
  created_at?: string | null
  updated_at?: string | null
}

export interface TranscriptItemResponse {
  transcript_id: string
  source_type: string
  source_entity_id?: string | null
  duration_ms?: number | null
  duration_sec?: number | null
  status: number
  status_name: string
  language?: string | null
  error_code?: string | null
  error_message?: string | null
  created_at: string
  updated_at: string
}

export interface CreateAsrRecognitionRequest {
  objectKey: string
  audioUrl: string
  language?: string
}

export interface AsrRecognitionResponse {
  recognition_id: string
  transcript_id: string
  job_id?: string | null
  object_key: string
  audio_url?: string | null
  language?: string | null
  provider?: string | null
  status: number
  status_name: string
  error_code?: string | null
  error_message?: string | null
  created_at: string
  updated_at: string
}

export interface CreateAsrRecognitionResponse {
  recognition: AsrRecognitionResponse
  transcript: TranscriptItemResponse
  job: JobItem
}

export interface SessionEntity {
  session_id: string
  title: string
  description?: string | null
  language?: string | null
  f_type: number
  asset_object_key?: string | null
  current_transcript_id?: string | null
  created_at: string
  updated_at: string
}

export interface SessionItem {
  session: SessionEntity
  asset?: AssetListItem | null
  transcript?: TranscriptItemResponse | null
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
  currentTranscriptId?: string
}

export interface GenerateScriptSessionRequest {
  title: string
  description?: string
  language?: string
  prompt: string
  turnCount?: number
  speakerCount?: number
  difficulty?: string
  cueStyle?: string
  mustInclude?: string[]
}

export interface GenerateScriptSessionResponse {
  session: SessionItem
  generation: ScriptGenerationResponse
  job: JobItem
  revision?: RevisionResponse | null
}

export interface ScriptGenerationResponse {
  generation_id: string
  session_id: string
  transcript_id?: string | null
  job_id?: string | null
  provider: string
  title: string
  prompt: string
  status: number
  status_name: string
  error_code?: string | null
  error_message?: string | null
  created_at: string
  updated_at: string
}

export interface ScriptGenerationPreviewItemResponse {
  seq: number
  speaker: string
  cue: string
  text: string
}

export interface ScriptGenerationPreviewResponse {
  generation: ScriptGenerationResponse
  items: ScriptGenerationPreviewItemResponse[]
}

export interface CreateRevisionRequest {
  sessionId: string
  userPrompt?: string
  force?: boolean
}

export interface UpdateRevisionItemRequest {
  draftText?: string | null
}

export interface RevisionItemResponse {
  item_id: string
  revision_id: string
  transcript_id: string
  source_seq_start: number
  source_seq_end: number
  source_seq_count: number
  source_seqs: number[]
  speaker?: string | null
  start_time: number
  end_time: number
  original_text: string
  suggested_text: string
  draft_text?: string | null
  score: number
  issue_tags: string
  explanations: string
  created_at: string
  updated_at: string
}

export interface RevisionResponse {
  revision_id: string
  session_id: string
  transcript_id: string
  job_id?: string | null
  user_prompt?: string | null
  status: number
  status_name: string
  error_code?: string | null
  error_message?: string | null
  item_count: number
  created_at: string
  updated_at: string
  items: RevisionItemResponse[]
}

export interface TranscriptUtteranceResponse {
  seq: number
  text: string
  speaker?: string | null
  start_time: number
  end_time: number
  additions: Record<string, unknown>
}

export interface TranscriptData {
  transcript_id: string
  source_type: string
  source_entity_id?: string | null
  status: number
  status_name: string
  duration_ms?: number | null
  duration_sec?: number | null
  full_text?: string | null
  utterances: TranscriptUtteranceResponse[]
  raw_result?: Record<string, unknown> | null
}

export interface TtsSpeakerMapping {
  conversation_speaker: string
  provider_speaker_id: string
}

export interface TtsSpeakerItem {
  speaker_id: string
  name: string
  provider_name?: string | null
  display_name?: string | null
  language?: string | null
  gender?: string | null
  style?: string | null
  description?: string | null
  i18n?: Record<string, {
    name?: string
    language?: string
    style?: string
    description?: string
  }>
  avatar?: {
    type?: string
    key?: string
    color?: string
    initials?: string
    url?: string | null
  }
  traits?: Record<string, unknown>
}

export interface TtsSpeakerListResponse {
  items: TtsSpeakerItem[]
}

export interface TtsSettingsResponse {
  session_id: string
  format: string
  emotion_scale: number
  speech_rate: number
  loudness_rate: number
  speaker_mappings: TtsSpeakerMapping[]
}

export interface UpdateTtsSettingsRequest {
  sessionId: string
  format: string
  emotionScale: number
  speechRate: number
  loudnessRate: number
  speakerMappings: TtsSpeakerMapping[]
}

export interface CreateTtsSynthesisRequest {
  sessionId: string
  force?: boolean
}

export interface TtsSynthesisItemResponse {
  item_id: string
  conversation_speaker?: string | null
  provider_speaker_id: string
  content: string
  plain_text: string
  cue_texts: string[]
  content_hash: string
  start_time_ms?: number | null
  end_time_ms?: number | null
  duration_ms?: number | null
  status: number
  status_name: string
}

export interface TtsSynthesisResponse {
  synthesis_id: string
  session_id: string
  provider: string
  full_asset_url?: string | null
  full_duration_ms?: number | null
  item_count: number
  completed_item_count: number
  failed_item_count: number
  status: number
  status_name: string
  error_code?: string | null
  error_message?: string | null
  created_at: string
  updated_at: string
  items: TtsSynthesisItemResponse[]
}

export interface CreateTtsSynthesisResponse {
  synthesis: TtsSynthesisResponse
  job?: JobItem | null
}
