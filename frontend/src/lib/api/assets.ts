import { requestJson } from '@/lib/api/client'
import type { UploadUrlRequest, UploadUrlResponse } from '@/types/api'

interface ApiResponse<T> {
  code: number
  message: string
  data: T
}

export async function createUploadUrl(payload: UploadUrlRequest): Promise<UploadUrlResponse> {
  const response = await requestJson<ApiResponse<UploadUrlResponse>>('/assets/upload-url', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      category: payload.category,
      entity_id: payload.entityId,
      filename: payload.filename,
      content_type: payload.contentType,
    }),
  })
  return response.data
}
