import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { PageTitle } from '@/components/common/page-title'
import { FileDropzone } from '@/components/upload/file-dropzone'
import { UploadProgress } from '@/components/upload/upload-progress'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { uploadAssetWithConfirmation } from '@/lib/api/upload'
import { getUploadHistory, saveUploadRecord } from '@/lib/storage/upload-history'
import { formatBytes, formatDateTime, formatDuration } from '@/lib/utils/format'
import type { UploadRecord } from '@/types/domain'

const ALLOWED_EXTENSIONS = new Set(['mp3', 'wav', 'm4a'])

const EXTENSION_CONTENT_TYPE: Record<string, string> = {
  mp3: 'audio/mpeg',
  wav: 'audio/wav',
  m4a: 'audio/mp4',
}

function getExtension(filename: string): string {
  const parts = filename.toLowerCase().split('.')
  return parts.length > 1 ? parts[parts.length - 1] : ''
}

function resolveContentType(file: File): string {
  if (file.type) {
    return file.type
  }

  const extension = getExtension(file.name)
  return EXTENSION_CONTENT_TYPE[extension] ?? 'application/octet-stream'
}

async function getAudioDuration(file: File): Promise<number | null> {
  const objectUrl = URL.createObjectURL(file)

  return new Promise<number | null>((resolve) => {
    const audio = new Audio()

    audio.preload = 'metadata'

    audio.onloadedmetadata = () => {
      URL.revokeObjectURL(objectUrl)
      const duration = Number.isFinite(audio.duration) ? audio.duration : null
      resolve(duration)
    }

    audio.onerror = () => {
      URL.revokeObjectURL(objectUrl)
      resolve(null)
    }

    audio.src = objectUrl
  })
}

function createJobIds(objectKey: string): { taskId: string; summaryId: string } {
  const fileSegment = objectKey.split('/').at(-1) ?? crypto.randomUUID()
  const base = fileSegment.split('.')[0]
  return {
    taskId: `task_${base}`,
    summaryId: `summary_${base}`,
  }
}

export function UploadPage() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [durationSec, setDurationSec] = useState<number | null>(null)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [isUploading, setIsUploading] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [successRecord, setSuccessRecord] = useState<UploadRecord | null>(null)
  const [history, setHistory] = useState<UploadRecord[]>(() => getUploadHistory())

  const selectedExtension = useMemo(() => {
    if (!selectedFile) {
      return ''
    }
    return getExtension(selectedFile.name)
  }, [selectedFile])

  async function handleFileSelected(file: File) {
    const extension = getExtension(file.name)

    if (!ALLOWED_EXTENSIONS.has(extension)) {
      setErrorMessage('Only mp3, wav, and m4a files are supported.')
      setSelectedFile(null)
      setDurationSec(null)
      return
    }

    const duration = await getAudioDuration(file)
    setSelectedFile(file)
    setDurationSec(duration)
    setUploadProgress(0)
    setSuccessRecord(null)
    setErrorMessage(null)
  }

  async function handleUpload() {
    if (!selectedFile || isUploading) {
      return
    }

    setIsUploading(true)
    setErrorMessage(null)
    setSuccessRecord(null)
    setUploadProgress(0)

    try {
      const contentType = resolveContentType(selectedFile)

      const { completed } = await uploadAssetWithConfirmation({
        upload: {
          category: 'conversation',
          entityId: 'web_user',
          filename: selectedFile.name,
          contentType,
        },
        file: selectedFile,
        onProgress: (progress) => setUploadProgress(progress),
      })

      const { taskId, summaryId } = createJobIds(completed.object_key)

      const record: UploadRecord = {
        taskId,
        summaryId,
        fileName: selectedFile.name,
        fileSize: selectedFile.size,
        durationSec,
        objectKey: completed.object_key,
        assetUrl: completed.asset_url,
        uploadedAt: new Date().toISOString(),
      }

      saveUploadRecord(record)
      setHistory(getUploadHistory())
      setSuccessRecord(record)
      setUploadProgress(100)
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Upload failed. Please retry.')
    } finally {
      setIsUploading(false)
    }
  }

  return (
    <section className="space-y-6">
      <PageTitle
        eyebrow="Step 1"
        title="Upload Conversation Recording"
        description="Upload mp3, wav, or m4a from meetings, interviews, calls, or casual chats. We will turn it into a structured summary workflow."
      />

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="border-slate-200/80 bg-white/90 shadow-sm lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-lg">Audio Input</CardTitle>
            <CardDescription>Client uploads directly to object storage using presigned PUT URL.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <FileDropzone disabled={isUploading} onFileSelected={handleFileSelected} />

            {selectedFile ? (
              <div className="rounded-lg border border-slate-200 bg-slate-50/80 p-4">
                <p className="text-sm font-medium text-slate-800">{selectedFile.name}</p>
                <p className="mt-1 text-xs text-slate-600">
                  {selectedExtension.toUpperCase()} · {formatBytes(selectedFile.size)} · {formatDuration(durationSec)}
                </p>
              </div>
            ) : null}

            {isUploading || uploadProgress > 0 ? <UploadProgress value={uploadProgress} /> : null}

            {errorMessage ? (
              <div className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">{errorMessage}</div>
            ) : null}

            {successRecord ? (
              <div className="space-y-3 rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">
                <p className="font-medium">Upload completed successfully.</p>
                <p className="text-xs break-all">object_key: {successRecord.objectKey}</p>
                <div className="flex flex-wrap gap-2">
                  <Button asChild size="sm">
                    <Link to={`/tasks/${successRecord.taskId}`}>View Task</Link>
                  </Button>
                  <Button asChild size="sm" variant="outline">
                    <Link to={`/summaries/${successRecord.summaryId}`}>Open Summary</Link>
                  </Button>
                  <Button asChild size="sm" variant="ghost">
                    <a href={successRecord.assetUrl} target="_blank" rel="noreferrer">
                      Open Asset URL
                    </a>
                  </Button>
                </div>
              </div>
            ) : null}

            <div className="flex flex-wrap gap-3">
              <Button type="button" onClick={handleUpload} disabled={!selectedFile || isUploading}>
                {isUploading ? 'Uploading...' : 'Upload to Storage'}
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  setSelectedFile(null)
                  setDurationSec(null)
                  setUploadProgress(0)
                  setErrorMessage(null)
                  setSuccessRecord(null)
                }}
                disabled={isUploading}
              >
                Clear
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card className="border-slate-200/80 bg-white/90 shadow-sm">
          <CardHeader>
            <CardTitle className="text-lg">Recent Uploads</CardTitle>
            <CardDescription>Latest 20 records stored in localStorage.</CardDescription>
          </CardHeader>
          <CardContent>
            {history.length === 0 ? (
              <p className="text-sm text-slate-600">No upload history yet.</p>
            ) : (
              <ul className="space-y-3">
                {history.slice(0, 5).map((item) => (
                  <li key={item.taskId} className="rounded-lg border border-slate-200 p-3">
                    <p className="truncate text-sm font-medium text-slate-800">{item.fileName}</p>
                    <p className="mt-1 text-xs text-slate-600">{formatDateTime(item.uploadedAt)}</p>
                    <div className="mt-2 flex flex-wrap gap-2">
                      <Button asChild size="xs" variant="outline">
                        <Link to={`/tasks/${item.taskId}`}>Task</Link>
                      </Button>
                      <Button asChild size="xs" variant="outline">
                        <Link to={`/summaries/${item.summaryId}`}>Summary</Link>
                      </Button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>

      <p className="text-xs text-slate-500">
        API base URL: <code>{import.meta.env.VITE_API_BASE_URL ?? '/api'}</code>
      </p>
    </section>
  )
}
