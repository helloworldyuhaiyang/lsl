import { requestJson } from '@/lib/api/client'
import type { CreateAsrRecognitionRequest, CreateAsrRecognitionResponse } from '@/types/api'

interface ApiResponse<T> {
  code: number
  message: string
  data: T
}

export async function createAsrRecognition(payload: CreateAsrRecognitionRequest): Promise<CreateAsrRecognitionResponse> {
  const response = await requestJson<ApiResponse<CreateAsrRecognitionResponse>>('/asr/recognitions', {
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
