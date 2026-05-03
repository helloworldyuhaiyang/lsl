import { requestJson } from '@/lib/api/client'
import type {
  GenerateScriptSessionRequest,
  GenerateScriptSessionResponse,
  ScriptGenerationPreviewResponse,
} from '@/types/api'

interface ApiResponse<T> {
  code: number
  message: string
  data: T
}

export async function generateScriptSession(payload: GenerateScriptSessionRequest): Promise<GenerateScriptSessionResponse> {
  const response = await requestJson<ApiResponse<GenerateScriptSessionResponse>>('/scripts/generate-session', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      title: payload.title,
      description: payload.description,
      language: payload.language,
      prompt: payload.prompt,
      turn_count: payload.turnCount,
      speaker_count: payload.speakerCount,
      difficulty: payload.difficulty,
      cue_style: payload.cueStyle,
      must_include: payload.mustInclude,
    }),
  })

  return response.data
}

export async function getScriptGenerationPreview(generationId: string): Promise<ScriptGenerationPreviewResponse> {
  const response = await requestJson<ApiResponse<ScriptGenerationPreviewResponse>>(`/scripts/generations/${generationId}/preview`)
  return response.data
}
