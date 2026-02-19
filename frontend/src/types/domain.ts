export type TaskStatus = 'uploaded' | 'transcribing' | 'analyzing' | 'completed' | 'failed'

export interface UploadRecord {
  taskId: string
  summaryId: string
  fileName: string
  fileSize: number
  durationSec: number | null
  objectKey: string
  assetUrl: string
  uploadedAt: string
}

export interface SummaryLine {
  id: string
  timestampLabel: string
  speaker: 'speaker_a' | 'speaker_b'
  original: string
  optimized: string
  note: string
}
