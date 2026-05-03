import { requestBlob, requestJson } from '@/lib/api/client'
import type {
  CreateTtsSynthesisRequest,
  CreateTtsSynthesisResponse,
  TtsSettingsResponse,
  TtsSpeakerListResponse,
  TtsSynthesisResponse,
  UpdateTtsSettingsRequest,
} from '@/types/api'

interface ApiResponse<T> {
  code: number
  message: string
  data: T
}

export async function getTtsSpeakers(provider = 'active'): Promise<TtsSpeakerListResponse> {
  const response = await requestJson<ApiResponse<TtsSpeakerListResponse>>(`/tts/providers/${provider}/speakers`)
  return response.data
}

export async function getTtsSettings(sessionId: string): Promise<TtsSettingsResponse> {
  const response = await requestJson<ApiResponse<TtsSettingsResponse>>('/tts/settings', {
    query: {
      session_id: sessionId,
    },
  })
  return response.data
}

export async function updateTtsSettings(payload: UpdateTtsSettingsRequest): Promise<TtsSettingsResponse> {
  const response = await requestJson<ApiResponse<TtsSettingsResponse>>('/tts/settings', {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      session_id: payload.sessionId,
      format: payload.format,
      emotion_scale: payload.emotionScale,
      speech_rate: payload.speechRate,
      loudness_rate: payload.loudnessRate,
      speaker_mappings: payload.speakerMappings,
    }),
  })
  return response.data
}

export async function generateTtsItemAudio(params: {
  itemId: string
  sessionId: string
  content: string
  force?: boolean
}): Promise<Blob> {
  return await requestBlob(`/tts/items/${params.itemId}/generate`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      session_id: params.sessionId,
      content: params.content,
      force: params.force ?? false,
    }),
  })
}

export async function createTtsSynthesis(payload: CreateTtsSynthesisRequest): Promise<TtsSynthesisResponse> {
  const response = await requestJson<ApiResponse<CreateTtsSynthesisResponse>>('/tts', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      session_id: payload.sessionId,
      force: payload.force ?? false,
    }),
  })
  return response.data.synthesis
}

export async function getTtsSynthesis(sessionId: string): Promise<TtsSynthesisResponse> {
  const response = await requestJson<ApiResponse<TtsSynthesisResponse>>('/tts', {
    query: {
      session_id: sessionId,
    },
  })
  return response.data
}
