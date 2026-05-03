import { requestJson } from '@/lib/api/client'
import type { JobItem } from '@/types/api'

interface ApiResponse<T> {
  code: number
  message: string
  data: T
}

export async function getJob(jobId: string): Promise<JobItem> {
  const response = await requestJson<ApiResponse<JobItem>>(`/jobs/${jobId}`)
  return response.data
}
