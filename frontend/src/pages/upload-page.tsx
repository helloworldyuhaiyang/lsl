import { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { PageTitle } from '@/components/common/page-title'
import { FileDropzone } from '@/components/upload/file-dropzone'
import { UploadProgress } from '@/components/upload/upload-progress'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { getSessionPath, ROUTES } from '@/lib/constants/routes'
import { upsertSessionMetadata } from '@/lib/session/session-storage'
import { completeUploadedAsset, prepareUploadUrl, uploadToPresignedUrl } from '@/lib/api/upload'
import { createTask } from '@/lib/api/tasks'
import { formatBytes, formatDuration } from '@/lib/utils/format'
import type { UploadUrlResponse } from '@/types/api'

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

  return EXTENSION_CONTENT_TYPE[getExtension(file.name)] ?? 'application/octet-stream'
}

async function getAudioDuration(file: File): Promise<number | null> {
  const objectUrl = URL.createObjectURL(file)

  return new Promise<number | null>((resolve) => {
    const audio = new Audio()
    audio.preload = 'metadata'

    audio.onloadedmetadata = () => {
      URL.revokeObjectURL(objectUrl)
      resolve(Number.isFinite(audio.duration) ? audio.duration : null)
    }

    audio.onerror = () => {
      URL.revokeObjectURL(objectUrl)
      resolve(null)
    }

    audio.src = objectUrl
  })
}

export function UploadPage() {
  const navigate = useNavigate()
  const [sessionName, setSessionName] = useState('')
  const [sessionDescription, setSessionDescription] = useState('')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [preparedUpload, setPreparedUpload] = useState<UploadUrlResponse | null>(null)
  const [durationSec, setDurationSec] = useState<number | null>(null)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [isPreparingUpload, setIsPreparingUpload] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [uploadedSessionId, setUploadedSessionId] = useState<string | null>(null)

  const canUpload =
    sessionName.trim().length > 0 &&
    Boolean(selectedFile) &&
    Boolean(preparedUpload) &&
    !isUploading &&
    !isPreparingUpload

  const extension = useMemo(() => (selectedFile ? getExtension(selectedFile.name).toUpperCase() : ''), [selectedFile])

  async function handleFileSelected(file: File) {
    const fileExtension = getExtension(file.name)
    if (!ALLOWED_EXTENSIONS.has(fileExtension)) {
      setErrorMessage('Only mp3, wav, and m4a files are supported.')
      setSelectedFile(null)
      setPreparedUpload(null)
      setDurationSec(null)
      return
    }

    setErrorMessage(null)
    setUploadedSessionId(null)
    setIsPreparingUpload(true)
    setSelectedFile(null)
    setPreparedUpload(null)
    setDurationSec(null)
    setUploadProgress(0)

    try {
      const [duration, uploadInfo] = await Promise.all([
        getAudioDuration(file),
        prepareUploadUrl({
          category: 'conversation',
          entityId: 'web_user',
          filename: file.name,
          contentType: resolveContentType(file),
        }),
      ])

      setSelectedFile(file)
      setPreparedUpload(uploadInfo)
      setDurationSec(duration)
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Failed to prepare upload.')
    } finally {
      setIsPreparingUpload(false)
    }
  }

  async function handleUploadSession() {
    if (!selectedFile || !preparedUpload || sessionName.trim().length === 0 || isUploading || isPreparingUpload) {
      return
    }

    setIsUploading(true)
    setErrorMessage(null)
    setUploadedSessionId(null)

    try {
      const contentType = resolveContentType(selectedFile)
      const { etag } = await uploadToPresignedUrl({
        uploadUrl: preparedUpload.upload_url,
        file: selectedFile,
        contentType,
        onProgress: (progress) => setUploadProgress(progress),
      })

      const uploaded = await completeUploadedAsset({
        uploadInfo: preparedUpload,
        upload: {
          category: 'conversation',
          entityId: 'web_user',
          filename: selectedFile.name,
          contentType,
        },
        file: selectedFile,
        etag,
      })

      const task = await createTask({
        objectKey: uploaded.object_key,
        audioUrl: uploaded.asset_url,
        language: 'en-US',
      })

      upsertSessionMetadata(task.task_id, {
        title: sessionName.trim(),
        description: sessionDescription.trim(),
        fileName: selectedFile.name,
        fileSize: selectedFile.size,
        durationSec,
      })

      setUploadedSessionId(task.task_id)
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
        title="Upload Session"
        description="Create a session with name/description, then upload an audio file for transcript and learning workflow."
        actions={
          <Button asChild variant="outline" size="sm">
            <Link to={ROUTES.dashboard}>Back to Dashboard</Link>
          </Button>
        }
      />

      <Card className="border-slate-200/80 bg-white/95 shadow-sm">
        <CardHeader>
          <CardTitle>Upload Session</CardTitle>
        </CardHeader>

        <CardContent className="space-y-6">
          <div className="space-y-4">
            <div className="space-y-1.5">
              <label htmlFor="session-name" className="text-sm font-medium text-slate-800">
                Session Name
              </label>
              <input
                id="session-name"
                value={sessionName}
                onChange={(event) => setSessionName(event.target.value)}
                placeholder="Client Meeting"
                className="h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm outline-none placeholder:text-slate-400 focus:border-slate-900"
              />
            </div>

            <div className="space-y-1.5">
              <label htmlFor="session-description" className="text-sm font-medium text-slate-800">
                Session Description (optional)
              </label>
              <textarea
                id="session-description"
                value={sessionDescription}
                onChange={(event) => setSessionDescription(event.target.value)}
                placeholder="Short context for this conversation"
                className="min-h-24 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none placeholder:text-slate-400 focus:border-slate-900"
              />
            </div>
          </div>

          <div className="h-px bg-slate-200" />

          <div className="space-y-3">
            <div>
              <h3 className="text-sm font-semibold text-slate-900">Audio File</h3>
              <p className="text-xs text-slate-500">Supported format: mp3 / wav / m4a</p>
            </div>
            <FileDropzone disabled={isUploading || isPreparingUpload} onFileSelected={handleFileSelected} />
          </div>

          {isPreparingUpload ? <p className="text-sm text-slate-600">Preparing upload URL...</p> : null}

          <div className="h-px bg-slate-200" />

          <div className="space-y-2 rounded-md border border-slate-200 bg-slate-50 p-4">
            <h3 className="text-sm font-semibold text-slate-900">File Info</h3>
            {selectedFile ? (
              <div className="space-y-1 text-sm text-slate-700">
                <p>
                  <span className="font-medium text-slate-900">Name:</span> {selectedFile.name}
                </p>
                <p>
                  <span className="font-medium text-slate-900">Duration:</span> {formatDuration(durationSec)}
                </p>
                <p>
                  <span className="font-medium text-slate-900">Size:</span> {formatBytes(selectedFile.size)}
                </p>
                <p>
                  <span className="font-medium text-slate-900">Format:</span> {extension || '--'}
                </p>
              </div>
            ) : (
              <p className="text-sm text-slate-500">No file selected yet.</p>
            )}
          </div>

          {isUploading || uploadProgress > 0 ? <UploadProgress value={uploadProgress} /> : null}

          {errorMessage ? (
            <div className="rounded-md border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">{errorMessage}</div>
          ) : null}

          {uploadedSessionId ? (
            <div className="rounded-md border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">
              <p className="font-medium">Session uploaded successfully.</p>
              <div className="mt-3 flex flex-wrap gap-2">
                <Button asChild size="sm">
                  <Link to={getSessionPath(uploadedSessionId)}>Open Session</Link>
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    setSessionName('')
                    setSessionDescription('')
                    setSelectedFile(null)
                    setPreparedUpload(null)
                    setDurationSec(null)
                    setUploadProgress(0)
                    setErrorMessage(null)
                    setUploadedSessionId(null)
                  }}
                >
                  Upload Another
                </Button>
              </div>
            </div>
          ) : null}

          <div className="flex justify-center sm:justify-end">
            <Button type="button" onClick={handleUploadSession} disabled={!canUpload}>
              {isUploading ? 'Uploading...' : 'Upload Session'}
            </Button>
          </div>

          {uploadedSessionId ? (
            <div className="flex justify-center sm:justify-end">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => {
                  navigate(getSessionPath(uploadedSessionId))
                }}
              >
                Continue to Session
              </Button>
            </div>
          ) : null}
        </CardContent>
      </Card>
    </section>
  )
}
