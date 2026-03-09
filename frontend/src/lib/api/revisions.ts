import { requestJson } from '@/lib/api/client'
import type { CreateRevisionRequest, RevisionResponse } from '@/types/api'

interface ApiResponse<T> {
  code: number
  message: string
  data: T
}

export async function getRevision(sessionId: string): Promise<RevisionResponse> {
  const response = await requestJson<ApiResponse<RevisionResponse>>('/revisions', {
    query: {
      session_id: sessionId,
    },
  })

  return response.data
}

export async function createRevision(payload: CreateRevisionRequest): Promise<RevisionResponse> {
  const response = await requestJson<ApiResponse<RevisionResponse>>('/revisions', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      session_id: payload.sessionId,
      user_prompt: payload.userPrompt,
      force: payload.force ?? true,
    }),
  })

  return response.data
}
