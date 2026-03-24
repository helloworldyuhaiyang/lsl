import { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { PageTitle } from '@/components/common/page-title'
import { FileDropzone } from '@/components/upload/file-dropzone'
import { UploadProgress } from '@/components/upload/upload-progress'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { getRevisePath, getSessionPath, ROUTES } from '@/lib/constants/routes'
import { generateScriptSession } from '@/lib/api/scripts'
import { upsertSessionMetadata } from '@/lib/session/session-storage'
import { completeUploadedAsset, prepareUploadUrl, uploadToPresignedUrl } from '@/lib/api/upload'
import { createTask } from '@/lib/api/tasks'
import { createSession } from '@/lib/api/sessions'
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
  const [createMode, setCreateMode] = useState<'audio' | 'script'>('audio')
  const [sessionName, setSessionName] = useState('')
  const [sessionDescription, setSessionDescription] = useState('')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [preparedUpload, setPreparedUpload] = useState<UploadUrlResponse | null>(null)
  const [durationSec, setDurationSec] = useState<number | null>(null)
  const [scriptPrompt, setScriptPrompt] = useState('')
  const [scriptTurnCount, setScriptTurnCount] = useState(8)
  const [scriptSpeakerCount, setScriptSpeakerCount] = useState(2)
  const [scriptDifficulty, setScriptDifficulty] = useState('intermediate')
  const [scriptCueStyle, setScriptCueStyle] = useState('自然口语、便于 TTS 演绎')
  const [scriptMustInclude, setScriptMustInclude] = useState('')
  const [uploadProgress, setUploadProgress] = useState(0)
  const [isPreparingUpload, setIsPreparingUpload] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [isGeneratingScript, setIsGeneratingScript] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [uploadedSessionId, setUploadedSessionId] = useState<string | null>(null)

  const isBusy = isUploading || isPreparingUpload || isGeneratingScript
  const canUpload =
    sessionName.trim().length > 0 &&
    Boolean(selectedFile) &&
    Boolean(preparedUpload) &&
    !isBusy
  const canGenerateScript = sessionName.trim().length > 0 && scriptPrompt.trim().length > 0 && !isBusy

  const extension = useMemo(() => (selectedFile ? getExtension(selectedFile.name).toUpperCase() : ''), [selectedFile])

  function parseMustInclude(value: string): string[] {
    return value
      .split(/[\n,，、]+/)
      .map((item) => item.trim())
      .filter(Boolean)
  }

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
    if (!selectedFile || !preparedUpload || sessionName.trim().length === 0 || isBusy) {
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

      const createdSession = await createSession({
        title: sessionName.trim(),
        description: sessionDescription.trim() || undefined,
        language: 'en-US',
        fType: 1,
        assetObjectKey: uploaded.object_key,
        currentTaskId: task.task_id,
      })

      upsertSessionMetadata(createdSession.session.session_id, {
        title: sessionName.trim(),
        description: sessionDescription.trim(),
        fileName: selectedFile.name,
        fileSize: selectedFile.size,
        durationSec,
      })

      setUploadedSessionId(createdSession.session.session_id)
      setUploadProgress(100)
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Upload failed. Please retry.')
    } finally {
      setIsUploading(false)
    }
  }

  async function handleGenerateScriptSession() {
    if (!canGenerateScript) {
      return
    }

    setIsGeneratingScript(true)
    setErrorMessage(null)
    setUploadedSessionId(null)

    try {
      const generated = await generateScriptSession({
        title: sessionName.trim(),
        description: sessionDescription.trim() || undefined,
        language: 'en-US',
        prompt: scriptPrompt.trim(),
        turnCount: scriptTurnCount,
        speakerCount: scriptSpeakerCount,
        difficulty: scriptDifficulty,
        cueStyle: scriptCueStyle.trim() || undefined,
        mustInclude: parseMustInclude(scriptMustInclude),
      })

      upsertSessionMetadata(generated.session.session.session_id, {
        title: sessionName.trim(),
        description: sessionDescription.trim(),
      })

      navigate(getRevisePath(generated.session.session.session_id))
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Failed to generate cue script.')
    } finally {
      setIsGeneratingScript(false)
    }
  }

  return (
    <section className="space-y-6">
      <PageTitle
        eyebrow="Create"
        title="Create Session"
        description="Upload an audio session or generate a cue-first script session for revise and TTS workflow."
        actions={
          <Button asChild variant="outline" size="sm">
            <Link to={ROUTES.dashboard}>Back to Dashboard</Link>
          </Button>
        }
      />

      <Card className="border-slate-200/80 bg-white/95 shadow-sm">
        <CardHeader>
          <CardTitle>Create Session</CardTitle>
        </CardHeader>

        <CardContent className="space-y-6">
          <div className="space-y-2">
            <div className="inline-flex rounded-xl border border-slate-200 bg-slate-50 p-1">
              <button
                type="button"
                onClick={() => {
                  setCreateMode('audio')
                  setErrorMessage(null)
                }}
                className={`rounded-lg px-3 py-1.5 text-sm font-medium transition ${createMode === 'audio' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-600 hover:text-slate-900'
                  }`}
              >
                Audio Upload
              </button>
              <button
                type="button"
                onClick={() => {
                  setCreateMode('script')
                  setErrorMessage(null)
                  setUploadedSessionId(null)
                }}
                className={`rounded-lg px-3 py-1.5 text-sm font-medium transition ${createMode === 'script' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-600 hover:text-slate-900'
                  }`}
              >
                AI Script
              </button>
            </div>
            <p className="text-xs text-slate-500">
              {createMode === 'audio'
                ? 'Upload an existing audio conversation for transcript and revise.'
                : 'Generate a cue-first dialogue script. Every line will include a highlighted [...] cue by default.'}
            </p>
          </div>

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

          {createMode === 'audio' ? (
            <>
              <div className="space-y-3">
                <div>
                  <h3 className="text-sm font-semibold text-slate-900">Audio File</h3>
                  <p className="text-xs text-slate-500">Supported format: mp3 / wav / m4a</p>
                </div>
                <FileDropzone disabled={isBusy} onFileSelected={handleFileSelected} />
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
            </>
          ) : (
            <div className="space-y-5">
              <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
                AI will generate a dialogue where every line already contains a cue, for example
                {' '}
                <span className="font-medium">[语气平淡地回应] Interesting, innit?</span>
              </div>

              <div className="space-y-1.5">
                <label htmlFor="script-prompt" className="text-sm font-medium text-slate-800">
                  Scenario Prompt
                </label>
                <textarea
                  id="script-prompt"
                  value={scriptPrompt}
                  onChange={(event) => setScriptPrompt(event.target.value)}
                  placeholder="Describe the situation you want to practice, who is speaking, and what tension or goal the dialogue should have."
                  className="min-h-28 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none placeholder:text-slate-400 focus:border-slate-900"
                />
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <label htmlFor="script-turn-count" className="text-sm font-medium text-slate-800">
                    Turn Count
                  </label>
                  <select
                    id="script-turn-count"
                    value={scriptTurnCount}
                    onChange={(event) => setScriptTurnCount(Number(event.target.value))}
                    className="h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm outline-none focus:border-slate-900"
                  >
                    {[8, 12, 16, 20, 24].map((value) => (
                      <option key={value} value={value}>
                        {value}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="space-y-1.5">
                  <label htmlFor="script-speaker-count" className="text-sm font-medium text-slate-800">
                    Speaker Count
                  </label>
                  <select
                    id="script-speaker-count"
                    value={scriptSpeakerCount}
                    onChange={(event) => setScriptSpeakerCount(Number(event.target.value))}
                    className="h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm outline-none focus:border-slate-900"
                  >
                    {[2, 3, 4].map((value) => (
                      <option key={value} value={value}>
                        {value}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="space-y-1.5">
                  <label htmlFor="script-difficulty" className="text-sm font-medium text-slate-800">
                    Difficulty
                  </label>
                  <select
                    id="script-difficulty"
                    value={scriptDifficulty}
                    onChange={(event) => setScriptDifficulty(event.target.value)}
                    className="h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm outline-none focus:border-slate-900"
                  >
                    <option value="beginner">Beginner</option>
                    <option value="intermediate">Intermediate</option>
                    <option value="advanced">Advanced</option>
                  </select>
                </div>

                <div className="space-y-1.5">
                  <label htmlFor="script-cue-style" className="text-sm font-medium text-slate-800">
                    Cue Style
                  </label>
                  <input
                    id="script-cue-style"
                    value={scriptCueStyle}
                    onChange={(event) => setScriptCueStyle(event.target.value)}
                    placeholder="自然口语、便于 TTS 演绎"
                    className="h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm outline-none placeholder:text-slate-400 focus:border-slate-900"
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <label htmlFor="script-must-include" className="text-sm font-medium text-slate-800">
                  Must-Include Expressions (optional)
                </label>
                <textarea
                  id="script-must-include"
                  value={scriptMustInclude}
                  onChange={(event) => setScriptMustInclude(event.target.value)}
                  placeholder="One per line, or separate with commas."
                  className="min-h-24 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none placeholder:text-slate-400 focus:border-slate-900"
                />
              </div>
            </div>
          )}

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
            {createMode === 'audio' ? (
              <Button type="button" onClick={handleUploadSession} disabled={!canUpload}>
                {isUploading ? 'Uploading...' : 'Create Audio Session'}
              </Button>
            ) : (
              <Button type="button" onClick={() => void handleGenerateScriptSession()} disabled={!canGenerateScript}>
                {isGeneratingScript ? 'Generating...' : 'Generate Cue Script'}
              </Button>
            )}
          </div>

          {createMode === 'audio' && uploadedSessionId ? (
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
