import { requestJson } from '@/lib/api/client'
import type { TranscriptData } from '@/types/api'

interface ApiResponse<T> {
  code: number
  message: string
  data: T
}

export async function getTranscript(transcriptId: string, includeRaw = false): Promise<TranscriptData> {
  const response = await requestJson<ApiResponse<TranscriptData>>(`/transcripts/${transcriptId}`, {
    method: 'GET',
    query: {
      include_raw: String(includeRaw),
    },
  })
  return response.data
}
