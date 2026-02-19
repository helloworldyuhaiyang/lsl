import type { UploadRecord } from '@/types/domain'

const STORAGE_KEY = 'lsl.upload.history.v1'

function safeParse(value: string | null): UploadRecord[] {
  if (!value) {
    return []
  }

  try {
    const parsed = JSON.parse(value) as UploadRecord[]
    if (!Array.isArray(parsed)) {
      return []
    }
    return parsed
  } catch {
    return []
  }
}

export function getUploadHistory(): UploadRecord[] {
  if (typeof window === 'undefined') {
    return []
  }

  const list = safeParse(window.localStorage.getItem(STORAGE_KEY))
  return list.sort((a, b) => Date.parse(b.uploadedAt) - Date.parse(a.uploadedAt))
}

export function saveUploadRecord(record: UploadRecord): void {
  if (typeof window === 'undefined') {
    return
  }

  const history = getUploadHistory()
  const deduped = history.filter((item) => item.taskId !== record.taskId)
  const next = [record, ...deduped].slice(0, 20)
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
}

export function getUploadByTaskId(taskId: string): UploadRecord | null {
  const history = getUploadHistory()
  return history.find((item) => item.taskId === taskId) ?? null
}

export function getUploadBySummaryId(summaryId: string): UploadRecord | null {
  const history = getUploadHistory()
  return history.find((item) => item.summaryId === summaryId) ?? null
}
