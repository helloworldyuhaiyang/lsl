import { requestJson } from '@/lib/api/client'
import type { UploadUrlRequest, UploadUrlResponse } from '@/types/api'

export async function createUploadUrl(payload: UploadUrlRequest): Promise<UploadUrlResponse> {
  return requestJson<UploadUrlResponse>('/assets/upload-url', {
    method: 'POST',
    query: {
      category: payload.category,
      entity_id: payload.entityId,
      filename: payload.filename,
      content_type: payload.contentType,
    },
  })
}
