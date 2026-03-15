import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { PageTitle } from '@/components/common/page-title'
import { HighlightedTextarea } from '@/components/ui/highlighted-textarea'
import { ApiRequestError } from '@/lib/api/client'
import { createRevision, getRevision, updateRevisionItem } from '@/lib/api/revisions'
import { createTtsSynthesis, generateTtsItemAudio, getTtsSettings, getTtsSpeakers, getTtsSynthesis, updateTtsSettings } from '@/lib/api/tts'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { getListeningPath, getSessionPath, ROUTES } from '@/lib/constants/routes'
import { scoreRevisionIssues, type RevisionItem } from '@/lib/session/revision'
import { getSessionSummary, type SessionSummary } from '@/lib/session/sessions'
import { formatDuration } from '@/lib/utils/format'
import type { RevisionResponse, TtsSettingsResponse, TtsSpeakerItem, TtsSynthesisResponse } from '@/types/api'

function toggleById(value: Record<string, boolean>, id: string): Record<string, boolean> {
  return {
    ...value,
    [id]: !value[id],
  }
}

function splitCommaSeparated(value: string | null | undefined): string[] {
  return (value || '')
    .split(/[,，、]+/)
    .map((item) => item.trim())
    .filter(Boolean)
}

function splitExplanationText(value: string | null | undefined): string[] {
  return (value || '')
    .split(/[。.!?]\s*|\n+/)
    .map((item) => item.trim())
    .filter(Boolean)
}

const CUE_SEGMENT_PATTERN = /\[[^[\]]*]/g

function extractSpeechText(value: string): string {
  return value
    .replace(CUE_SEGMENT_PATTERN, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

function buildEditableDraft(script: string): string {
  return script.trim()
}

function buildDraftsByItem(items: RevisionItem[]): Record<string, string> {
  return Object.fromEntries(items.map((item) => [item.id, item.persistedDraft ?? buildEditableDraft(item.suggested)]))
}

function formatSeqLabel(item: RevisionItem): string {
  return item.seqStart === item.seqEnd ? `#${item.seqStart}` : `#${item.seqStart}-${item.seqEnd}`
}

function normalizeDraftValue(value: string | null | undefined): string {
  return value?.trim() || ''
}

function buildPersistedDraft(draftText: string | null | undefined): string | null {
  const normalizedDraftText = draftText?.trim() || ''
  if (normalizedDraftText) {
    return normalizedDraftText
  }
  return null
}

interface TtsSettingsForm {
  format: string
  emotionScale: number
  speechRate: number
  loudnessRate: number
  speakerMappings: Record<string, string>
}

function buildDefaultTtsSettingsForm(): TtsSettingsForm {
  return {
    format: 'mp3',
    emotionScale: 1,
    speechRate: 1,
    loudnessRate: 1,
    speakerMappings: {},
  }
}

function mapTtsSettingsResponseToForm(settings: TtsSettingsResponse): TtsSettingsForm {
  return {
    format: settings.format,
    emotionScale: settings.emotion_scale,
    speechRate: settings.speech_rate,
    loudnessRate: settings.loudness_rate,
    speakerMappings: Object.fromEntries(
      settings.speaker_mappings.map((item) => [item.conversation_speaker, item.provider_speaker_id]),
    ),
  }
}

function serializeTtsSettingsForm(value: TtsSettingsForm | null): string {
  if (!value) {
    return ''
  }
  const speakerMappings = Object.entries(value.speakerMappings).sort(([left], [right]) => left.localeCompare(right))
  return JSON.stringify({
    format: value.format,
    emotionScale: value.emotionScale,
    speechRate: value.speechRate,
    loudnessRate: value.loudnessRate,
    speakerMappings,
  })
}

function listConversationSpeakers(items: RevisionItem[]): string[] {
  const result: string[] = []
  const seen = new Set<string>()
  items.forEach((item) => {
    const speaker = item.speaker.trim() || 'Speaker'
    if (seen.has(speaker)) {
      return
    }
    seen.add(speaker)
    result.push(speaker)
  })
  return result
}

function normalizeTtsSettingsForm(
  value: TtsSettingsForm | null,
  conversationSpeakers: string[],
  defaultProviderSpeakerId: string,
): TtsSettingsForm | null {
  if (!value) {
    return null
  }

  const speakerMappings: Record<string, string> = {}
  conversationSpeakers.forEach((speaker) => {
    speakerMappings[speaker] = value.speakerMappings[speaker] || defaultProviderSpeakerId
  })

  return {
    ...value,
    speakerMappings,
  }
}

function mapRevisionResponseToItems(revision: RevisionResponse): RevisionItem[] {
  return revision.items.map((item) => ({
    id: item.item_id,
    seqStart: item.source_seq_start,
    seqEnd: item.source_seq_end,
    sourceSeqCount: item.source_seq_count,
    sourceSeqs: item.source_seqs,
    speaker: item.speaker?.trim() || 'Speaker',
    startTimeMs: item.start_time,
    endTimeMs: item.end_time,
    original: item.original_text,
    suggested: item.suggested_text,
    score: item.score,
    issues: splitCommaSeparated(item.issue_tags),
    explanations: splitExplanationText(item.explanations),
    persistedDraft: buildPersistedDraft(item.draft_text),
  }))
}

function getScoreButtonClassName(score: number): string {
  if (score >= 80) {
    return 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200 hover:bg-emerald-100'
  }

  if (score >= 60) {
    return 'bg-amber-50 text-amber-700 ring-1 ring-amber-200 hover:bg-amber-100'
  }

  return 'bg-rose-50 text-rose-700 ring-1 ring-rose-200 hover:bg-rose-100'
}

function getErrorMessage(error: unknown, fallbackMessage: string): string {
  return error instanceof Error ? error.message : fallbackMessage
}

function formatTtsActionError(error: unknown, fallbackMessage: string): string {
  const message = getErrorMessage(error, fallbackMessage)
  if (/requested resource not granted|resource is not granted/i.test(message)) {
    return [
      message,
      '请检查 .env 里的 TTS_VOLC_APP_ID、TTS_VOLC_ACCESS_KEY、TTS_VOLC_RESOURCE_ID。',
      '不要复用只开通了 ASR 的火山凭证。',
      '如果只是本地联调，可以先把 TTS_PROVIDER 改成 fake。',
    ].join('\n\n')
  }
  return message
}

function showPopupMessage(message: string) {
  if (typeof window !== 'undefined') {
    window.alert(message)
  }
}

export function RevisePage() {
  const { sessionId = '' } = useParams()
  const navigate = useNavigate()
  const [session, setSession] = useState<SessionSummary | null>(null)
  const [items, setItems] = useState<RevisionItem[]>([])
  const [drafts, setDrafts] = useState<Record<string, string>>({})
  const [persistedDrafts, setPersistedDrafts] = useState<Record<string, string>>({})
  const [editingItemIds, setEditingItemIds] = useState<Record<string, boolean>>({})
  const [savingItemIds, setSavingItemIds] = useState<Record<string, boolean>>({})
  const [revisionStatusName, setRevisionStatusName] = useState<string | null>(null)
  const [userPrompt, setUserPrompt] = useState('')
  const [expandedExplanation, setExpandedExplanation] = useState<Record<string, boolean>>({})
  const [isLoading, setIsLoading] = useState(true)
  const [isSubmittingRevision, setIsSubmittingRevision] = useState(false)
  const [isSubmittingTtsBatch, setIsSubmittingTtsBatch] = useState(false)
  const [isSavingTtsSettings, setIsSavingTtsSettings] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [playbackMessage, setPlaybackMessage] = useState<string | null>(null)
  const [activeOriginalId, setActiveOriginalId] = useState<string | null>(null)
  const [activeSynthesisId, setActiveSynthesisId] = useState<string | null>(null)
  const [ttsSettings, setTtsSettings] = useState<TtsSettingsForm | null>(null)
  const [persistedTtsSettings, setPersistedTtsSettings] = useState<TtsSettingsForm | null>(null)
  const [ttsSpeakers, setTtsSpeakers] = useState<TtsSpeakerItem[]>([])
  const [ttsStatusName, setTtsStatusName] = useState<string | null>(null)
  const [ttsFullAssetUrl, setTtsFullAssetUrl] = useState<string | null>(null)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const snippetEndRef = useRef<number | null>(null)
  const synthAudioRef = useRef<HTMLAudioElement | null>(null)
  const synthAudioUrlRef = useRef<string | null>(null)
  const resolvedSessionId = session?.sessionId || sessionId
  const isRevisionGenerating = revisionStatusName === 'generating'
  const isTtsGenerating = ttsStatusName === 'generating'
  const isAnyGenerating = isSubmittingRevision || isRevisionGenerating || isSubmittingTtsBatch || isTtsGenerating
  const hasActiveDraftMutation =
    Object.keys(editingItemIds).length > 0 || Object.keys(savingItemIds).length > 0
  const conversationSpeakers = listConversationSpeakers(items)
  const defaultProviderSpeakerId = ttsSpeakers[0]?.speaker_id ?? ''
  const resolvedTtsSettings = normalizeTtsSettingsForm(ttsSettings, conversationSpeakers, defaultProviderSpeakerId)
  const resolvedPersistedTtsSettings = normalizeTtsSettingsForm(
    persistedTtsSettings,
    conversationSpeakers,
    defaultProviderSpeakerId,
  )
  const hasPendingTtsSettings =
    serializeTtsSettingsForm(resolvedTtsSettings) !== serializeTtsSettingsForm(resolvedPersistedTtsSettings)
  const canUseTts = Boolean(resolvedSessionId) && Boolean(resolvedTtsSettings) && ttsSpeakers.length > 0
  const canRevise = Boolean(resolvedSessionId) && !isLoading && !isAnyGenerating && session?.status === 'completed'

  function applyRevision(revision: RevisionResponse) {
    const nextItems = mapRevisionResponseToItems(revision)
    const nextDrafts = buildDraftsByItem(nextItems)
    setRevisionStatusName(revision.status_name)
    setItems(nextItems)
    setDrafts(nextDrafts)
    setPersistedDrafts(nextDrafts)
    setUserPrompt(revision.user_prompt?.trim() || '')
  }

  function applyTtsSynthesis(synthesis: TtsSynthesisResponse) {
    setTtsStatusName(synthesis.status_name)
    setTtsFullAssetUrl(synthesis.full_asset_url ?? null)
  }

  function stopSynthesisPreview(clearMessage = true) {
    const synthAudio = synthAudioRef.current
    if (synthAudio) {
      synthAudio.pause()
      synthAudio.currentTime = 0
      synthAudio.onended = null
      synthAudio.onerror = null
    }
    if (synthAudioUrlRef.current) {
      URL.revokeObjectURL(synthAudioUrlRef.current)
      synthAudioUrlRef.current = null
    }
    setActiveSynthesisId(null)
    if (clearMessage) {
      setPlaybackMessage(null)
    }
  }

  function stopOriginalPreview() {
    audioRef.current?.pause()
    snippetEndRef.current = null
    setActiveOriginalId(null)
  }

  useEffect(() => {
    let cancelled = false

    async function load() {
      if (!sessionId) {
        setErrorMessage('Missing session id.')
        setIsLoading(false)
        return
      }

      try {
        setIsLoading(true)
        setPlaybackMessage(null)
        setActiveOriginalId(null)
        setActiveSynthesisId(null)

        const detail = await getSessionSummary(sessionId)
        if (cancelled) {
          return
        }
        setSession(detail)

        try {
          const revision = await getRevision(sessionId)
          if (cancelled) {
            return
          }

          applyRevision(revision)
        } catch (error) {
          if (cancelled) {
            return
          }

          if (error instanceof ApiRequestError && error.status === 404) {
            setRevisionStatusName(null)
            setItems([])
            setDrafts({})
            setPersistedDrafts({})
            setEditingItemIds({})
            setSavingItemIds({})
            setUserPrompt('')
          } else {
            throw error
          }
        }

        const [settings, speakers] = await Promise.all([
          getTtsSettings(sessionId),
          getTtsSpeakers('active'),
        ])
        if (cancelled) {
          return
        }
        const mappedSettings = mapTtsSettingsResponseToForm(settings)
        setTtsSettings(mappedSettings)
        setPersistedTtsSettings(mappedSettings)
        setTtsSpeakers(speakers.items)

        try {
          const synthesis = await getTtsSynthesis(sessionId)
          if (cancelled) {
            return
          }
          applyTtsSynthesis(synthesis)
        } catch (error) {
          if (cancelled) {
            return
          }
          if (error instanceof ApiRequestError && error.status === 404) {
            setTtsStatusName(null)
            setTtsFullAssetUrl(null)
          } else {
            throw error
          }
        }

        setExpandedExplanation({})
        setErrorMessage(null)
      } catch (error) {
        if (cancelled) {
          return
        }
        setErrorMessage(error instanceof Error ? error.message : 'Failed to load revise content.')
      } finally {
        if (!cancelled) {
          setIsLoading(false)
        }
      }
    }

    void load()

    return () => {
      cancelled = true
    }
  }, [sessionId])

  useEffect(() => {
    if (!resolvedSessionId || !isRevisionGenerating || hasActiveDraftMutation) {
      return
    }

    let cancelled = false
    const timerId = window.setInterval(() => {
      void (async () => {
        try {
          const revision = await getRevision(resolvedSessionId)
          if (cancelled) {
            return
          }
          applyRevision(revision)
        } catch (error) {
          if (cancelled) {
            return
          }
          setErrorMessage(error instanceof Error ? error.message : 'Failed to refresh revise status.')
        }
      })()
    }, 2000)

    return () => {
      cancelled = true
      window.clearInterval(timerId)
    }
  }, [resolvedSessionId, isRevisionGenerating, hasActiveDraftMutation])

  useEffect(() => {
    const audio = audioRef.current

    return () => {
      audio?.pause()
      snippetEndRef.current = null
      const synthAudio = synthAudioRef.current
      if (synthAudio) {
        synthAudio.pause()
        synthAudio.currentTime = 0
        synthAudio.onended = null
        synthAudio.onerror = null
      }
      if (synthAudioUrlRef.current) {
        URL.revokeObjectURL(synthAudioUrlRef.current)
        synthAudioUrlRef.current = null
      }
    }
  }, [session?.audioUrl])

  useEffect(() => {
    if (!resolvedSessionId || ttsStatusName !== 'generating') {
      return
    }

    let cancelled = false
    const timerId = window.setInterval(() => {
      void (async () => {
        try {
          const synthesis = await getTtsSynthesis(resolvedSessionId)
          if (cancelled) {
            return
          }
          applyTtsSynthesis(synthesis)
        } catch (error) {
          if (cancelled) {
            return
          }
          if (error instanceof ApiRequestError && error.status === 404) {
            setTtsStatusName(null)
            setTtsFullAssetUrl(null)
            return
          }
          setErrorMessage(error instanceof Error ? error.message : 'Failed to refresh TTS status.')
        }
      })()
    }, 2000)

    return () => {
      cancelled = true
      window.clearInterval(timerId)
    }
  }, [resolvedSessionId, ttsStatusName])

  function getEditableTtsSettingsBase(): TtsSettingsForm {
    return (
      resolvedTtsSettings ??
      resolvedPersistedTtsSettings ??
      buildDefaultTtsSettingsForm()
    )
  }

  function updateDraft(itemId: string, nextValue: string) {
    setDrafts((value) => ({
      ...value,
      [itemId]: nextValue,
    }))
  }

  function markItemEditing(itemId: string, isEditing: boolean) {
    setEditingItemIds((value) => {
      if (isEditing) {
        return {
          ...value,
          [itemId]: true,
        }
      }
      if (!value[itemId]) {
        return value
      }
      const nextValue = { ...value }
      delete nextValue[itemId]
      return nextValue
    })
  }

  function updateTtsSettingsForm(nextValue: Partial<TtsSettingsForm>) {
    const current = getEditableTtsSettingsBase()
    setTtsSettings({
      format: nextValue.format ?? current.format,
      emotionScale: nextValue.emotionScale ?? current.emotionScale,
      speechRate: nextValue.speechRate ?? current.speechRate,
      loudnessRate: nextValue.loudnessRate ?? current.loudnessRate,
      speakerMappings: nextValue.speakerMappings ?? current.speakerMappings,
    })
  }

  function markItemSaving(itemId: string, isSaving: boolean) {
    setSavingItemIds((value) => {
      if (isSaving) {
        return {
          ...value,
          [itemId]: true,
        }
      }
      if (!value[itemId]) {
        return value
      }
      const nextValue = { ...value }
      delete nextValue[itemId]
      return nextValue
    })
  }

  async function handleDraftBlur(item: RevisionItem) {
    markItemEditing(item.id, false)
    const nextDraftValue = normalizeDraftValue(drafts[item.id])
    const persistedDraftValue = normalizeDraftValue(persistedDrafts[item.id])
    if (nextDraftValue === persistedDraftValue) {
      return
    }

    try {
      markItemSaving(item.id, true)
      setErrorMessage(null)
      await updateRevisionItem(item.id, {
        draftText: nextDraftValue || null,
      })
      setPersistedDrafts((value) => ({
        ...value,
        [item.id]: nextDraftValue,
      }))
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Failed to save revise draft.')
    } finally {
      markItemSaving(item.id, false)
    }
  }

  async function persistDraftChanges() {
    const pendingItems = items.filter((item) => {
      const draftValue = normalizeDraftValue(drafts[item.id])
      const persistedDraftValue = normalizeDraftValue(persistedDrafts[item.id])
      return draftValue !== persistedDraftValue
    })

    if (pendingItems.length === 0) {
      setEditingItemIds({})
      return
    }

    setEditingItemIds({})
    await Promise.all(
      pendingItems.map(async (item) => {
        markItemSaving(item.id, true)
        try {
          const nextDraftValue = normalizeDraftValue(drafts[item.id])
          await updateRevisionItem(item.id, {
            draftText: nextDraftValue || null,
          })
          setPersistedDrafts((value) => ({
            ...value,
            [item.id]: nextDraftValue,
          }))
        } finally {
          markItemSaving(item.id, false)
        }
      }),
    )
  }

  async function persistTtsSettingsIfNeeded() {
    if (!resolvedSessionId) {
      throw new Error('Missing session id.')
    }

    const nextSettings = resolvedTtsSettings
    if (!nextSettings) {
      throw new Error('TTS settings are not ready.')
    }
    if (!hasPendingTtsSettings) {
      return nextSettings
    }

    setIsSavingTtsSettings(true)
    try {
      const saved = await updateTtsSettings({
        sessionId: resolvedSessionId,
        format: nextSettings.format,
        emotionScale: nextSettings.emotionScale,
        speechRate: nextSettings.speechRate,
        loudnessRate: nextSettings.loudnessRate,
        speakerMappings: conversationSpeakers
          .filter((speaker) => nextSettings.speakerMappings[speaker])
          .map((speaker) => ({
            conversation_speaker: speaker,
            provider_speaker_id: nextSettings.speakerMappings[speaker],
          })),
      })
      const mapped = mapTtsSettingsResponseToForm(saved)
      setTtsSettings(mapped)
      setPersistedTtsSettings(mapped)
      return normalizeTtsSettingsForm(mapped, conversationSpeakers, defaultProviderSpeakerId) ?? mapped
    } finally {
      setIsSavingTtsSettings(false)
    }
  }

  async function handleSaveTtsSettings() {
    try {
      setErrorMessage(null)
      await persistTtsSettingsIfNeeded()
    } catch (error) {
      showPopupMessage(formatTtsActionError(error, 'Failed to save TTS settings.'))
    }
  }

  function handleTtsSettingsBlur() {
    if (!hasPendingTtsSettings || isSavingTtsSettings) {
      return
    }
    void handleSaveTtsSettings()
  }

  async function handleRevise() {
    if (!resolvedSessionId) {
      setErrorMessage('Missing session id.')
      return
    }

    try {
      setIsSubmittingRevision(true)
      setErrorMessage(null)
      setPlaybackMessage(null)

      const revision = await createRevision({
        sessionId: resolvedSessionId,
        userPrompt: userPrompt.trim() || undefined,
        force: true,
      })

      applyRevision(revision)
      setTtsStatusName(null)
      setTtsFullAssetUrl(null)
      setExpandedExplanation({})
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Failed to create revise content.')
    } finally {
      setIsSubmittingRevision(false)
    }
  }

  function playOriginal(item: RevisionItem) {
    if (!audioRef.current || !session?.audioUrl) {
      return
    }

    if (activeOriginalId === item.id && !audioRef.current.paused) {
      audioRef.current.pause()
      snippetEndRef.current = null
      setActiveOriginalId(null)
      return
    }

    stopSynthesisPreview(false)
    setActiveSynthesisId(null)
    setPlaybackMessage(null)
    audioRef.current.currentTime = item.startTimeMs / 1000
    snippetEndRef.current = item.endTimeMs / 1000
    setActiveOriginalId(item.id)

    void audioRef.current.play().catch(() => {
      snippetEndRef.current = null
      setActiveOriginalId(null)
      setPlaybackMessage('Failed to preview original audio snippet.')
    })
  }

  async function synthesizeItem(item: RevisionItem) {
    const content = normalizeDraftValue(drafts[item.id] ?? buildEditableDraft(item.suggested))
    if (!content) {
      return
    }
    if (!resolvedSessionId) {
      setErrorMessage('Missing session id.')
      return
    }

    if (activeSynthesisId === item.id) {
      stopSynthesisPreview()
      return
    }

    try {
      setErrorMessage(null)
      setPlaybackMessage(`Generating synth preview: ${item.speaker}`)
      stopOriginalPreview()
      stopSynthesisPreview(false)
      setActiveSynthesisId(item.id)
      await persistTtsSettingsIfNeeded()

      const audioBlob = await generateTtsItemAudio({
        itemId: item.id,
        sessionId: resolvedSessionId,
        content,
      })
      const audioUrl = URL.createObjectURL(audioBlob)
      synthAudioUrlRef.current = audioUrl

      const synthAudio = synthAudioRef.current ?? new Audio()
      synthAudioRef.current = synthAudio
      synthAudio.src = audioUrl
      synthAudio.currentTime = 0
      synthAudio.onended = () => {
        setActiveSynthesisId(null)
        setPlaybackMessage(null)
      }
      synthAudio.onerror = () => {
        stopSynthesisPreview(false)
        setPlaybackMessage('Failed to play synthesized preview.')
      }

      await synthAudio.play()
      setActiveSynthesisId(item.id)
      setPlaybackMessage(`Synthesize preview: ${item.speaker}`)
    } catch (error) {
      stopSynthesisPreview(false)
      setActiveSynthesisId(null)
      setPlaybackMessage('Failed to synthesize preview.')
      showPopupMessage(formatTtsActionError(error, 'Failed to synthesize preview.'))
    }
  }

  async function handleSynthesizeAll() {
    if (!resolvedSessionId) {
      setErrorMessage('Missing session id.')
      return
    }
    if (!canUseTts) {
      setErrorMessage('TTS speakers are not available.')
      return
    }

    try {
      setIsSubmittingTtsBatch(true)
      setErrorMessage(null)
      setPlaybackMessage(null)
      stopOriginalPreview()
      stopSynthesisPreview()
      await persistDraftChanges()
      await persistTtsSettingsIfNeeded()
      const synthesis = await createTtsSynthesis({
        sessionId: resolvedSessionId,
      })
      applyTtsSynthesis(synthesis)
      navigate(getListeningPath(resolvedSessionId))
    } catch (error) {
      showPopupMessage(formatTtsActionError(error, 'Failed to synthesize all items.'))
    } finally {
      setIsSubmittingTtsBatch(false)
    }
  }

  return (
    <section className="space-y-6">
      <PageTitle
        eyebrow="Step 3"
        title="Revise"
        actions={
          <>
            <Button asChild variant="outline" size="sm">
              <Link to={resolvedSessionId ? getSessionPath(resolvedSessionId) : ROUTES.dashboard}>Session</Link>
            </Button>
            <Button asChild variant="outline" size="sm">
              <Link to={resolvedSessionId ? getListeningPath(resolvedSessionId) : ROUTES.dashboard}>Listening</Link>
            </Button>
          </>
        }
      />

      {session?.audioUrl ? (
        <audio
          ref={audioRef}
          className="hidden"
          preload="metadata"
          src={session.audioUrl}
          onPause={() => setActiveOriginalId(null)}
          onTimeUpdate={() => {
            if (!audioRef.current || snippetEndRef.current === null) {
              return
            }

            if (audioRef.current.currentTime >= snippetEndRef.current) {
              audioRef.current.pause()
              snippetEndRef.current = null
              setActiveOriginalId(null)
            }
          }}
        >
          <track kind="captions" />
        </audio>
      ) : null}

      <Card className="border-slate-200/80 bg-white/95 shadow-sm">
        <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="space-y-2">
            <CardTitle>{items.length > 0 ? `${items.length} Revision Cards` : 'Revision Cards'}</CardTitle>
            <CardDescription>
              Add an optional prompt, then click `Revise by AI` to generate a perfect rewrite.
            </CardDescription>
          </div>
          <div className="flex items-center gap-2 self-start">
            {revisionStatusName ? (
              <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-medium uppercase tracking-wide text-slate-600">
                {revisionStatusName}
              </span>
            ) : null}
            <Button type="button" size="sm" onClick={() => void handleRevise()} disabled={!canRevise}>
              {isAnyGenerating ? 'Generating' : 'Revise by AI'}
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-3 pt-0">
          <div className="space-y-1.5">
            <label htmlFor="revision-user-prompt" className="text-xs font-medium uppercase tracking-wide text-slate-500">
              User Prompt
            </label>
            <textarea
              id="revision-user-prompt"
              value={userPrompt}
              onChange={(event) => setUserPrompt(event.target.value)}
              rows={2}
              placeholder="Optional. For example: make the rewrite more natural and conversational."
              className="min-h-20 w-full resize-y rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm leading-6 text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-slate-400 focus:ring-2 focus:ring-slate-200"
            />
          </div>

          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex flex-wrap gap-2 text-xs text-slate-500">
              <span className="rounded-full bg-slate-100 px-2.5 py-1">{items.length} span items</span>
              <span className="rounded-full bg-slate-100 px-2.5 py-1">expression cue visible</span>
              <span className="rounded-full bg-slate-100 px-2.5 py-1">input height adapts to content</span>
            </div>
            {playbackMessage ? <p className="text-xs text-slate-500 sm:text-right">{playbackMessage}</p> : null}
          </div>
        </CardContent>
      </Card>

      <Card className="border-slate-200/80 bg-white/95 shadow-sm">
        <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="space-y-2">
            <CardTitle>TTS Settings</CardTitle>
            <CardDescription>Configure provider voice mapping and synthesize the full revised script.</CardDescription>
          </div>
          <div className="flex items-center gap-2 self-start">
            {ttsStatusName ? (
              <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-medium uppercase tracking-wide text-slate-600">
                {ttsStatusName}
              </span>
            ) : null}
            <Button
              type="button"
              size="sm"
              onClick={() => void handleSynthesizeAll()}
              disabled={!canUseTts || isAnyGenerating || items.length === 0}
            >
              {isAnyGenerating ? 'Generating' : 'Synthesize All'}
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4 pt-0">
          {resolvedTtsSettings ? (
            <>
              <div className="grid gap-3 md:grid-cols-4">
                <label className="space-y-1.5 text-sm text-slate-700">
                  <span className="text-xs font-medium uppercase tracking-wide text-slate-500">Format</span>
                  <select
                    value={resolvedTtsSettings.format}
                    onChange={(event) => updateTtsSettingsForm({ format: event.target.value })}
                    onBlur={handleTtsSettingsBlur}
                    className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-200"
                  >
                    <option value="mp3">mp3</option>
                    <option value="wav">wav</option>
                  </select>
                </label>
                <label className="space-y-1.5 text-sm text-slate-700">
                  <span className="text-xs font-medium uppercase tracking-wide text-slate-500">Emotion Scale</span>
                  <input
                    type="number"
                    min="0.1"
                    max="4"
                    step="0.1"
                    value={resolvedTtsSettings.emotionScale}
                    onChange={(event) => updateTtsSettingsForm({ emotionScale: Number(event.target.value) || 1 })}
                    onBlur={handleTtsSettingsBlur}
                    className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-200"
                  />
                </label>
                <label className="space-y-1.5 text-sm text-slate-700">
                  <span className="text-xs font-medium uppercase tracking-wide text-slate-500">Speech Rate</span>
                  <input
                    type="number"
                    min="0.1"
                    max="4"
                    step="0.1"
                    value={resolvedTtsSettings.speechRate}
                    onChange={(event) => updateTtsSettingsForm({ speechRate: Number(event.target.value) || 1 })}
                    onBlur={handleTtsSettingsBlur}
                    className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-200"
                  />
                </label>
                <label className="space-y-1.5 text-sm text-slate-700">
                  <span className="text-xs font-medium uppercase tracking-wide text-slate-500">Loudness Rate</span>
                  <input
                    type="number"
                    min="0.1"
                    max="4"
                    step="0.1"
                    value={resolvedTtsSettings.loudnessRate}
                    onChange={(event) => updateTtsSettingsForm({ loudnessRate: Number(event.target.value) || 1 })}
                    onBlur={handleTtsSettingsBlur}
                    className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-200"
                  />
                </label>
              </div>

              <div className="space-y-3 rounded-xl border border-slate-200 bg-slate-50/70 p-4">
                <div className="space-y-1">
                  <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Speaker Mapping</p>
                  <p className="text-sm text-slate-600">Map each conversation speaker to one provider speaker.</p>
                </div>
                {conversationSpeakers.length > 0 ? (
                  <div className="grid gap-3 md:grid-cols-2">
                    {conversationSpeakers.map((speaker) => (
                      <label key={speaker} className="space-y-1.5 text-sm text-slate-700">
                        <span className="text-xs font-medium uppercase tracking-wide text-slate-500">{speaker}</span>
                        <select
                          value={resolvedTtsSettings.speakerMappings[speaker] || defaultProviderSpeakerId}
                          onChange={(event) =>
                            updateTtsSettingsForm({
                              speakerMappings: {
                                ...resolvedTtsSettings.speakerMappings,
                                [speaker]: event.target.value,
                              },
                            })
                          }
                          onBlur={handleTtsSettingsBlur}
                          className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-200"
                          disabled={ttsSpeakers.length === 0}
                        >
                          {ttsSpeakers.map((ttsSpeaker) => (
                            <option key={ttsSpeaker.speaker_id} value={ttsSpeaker.speaker_id}>
                              {ttsSpeaker.name}
                            </option>
                          ))}
                        </select>
                      </label>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-slate-500">Speaker mapping is available after revise items are generated.</p>
                )}
              </div>

              <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
                <span className="rounded-full bg-slate-100 px-2.5 py-1">{ttsSpeakers.length} provider speakers</span>
                {hasPendingTtsSettings ? (
                  <span className="rounded-full bg-amber-50 px-2.5 py-1 text-amber-800 ring-1 ring-amber-200/80">
                    unsaved settings
                  </span>
                ) : null}
                {ttsFullAssetUrl ? (
                  <a
                    href={ttsFullAssetUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="rounded-full bg-emerald-50 px-2.5 py-1 font-medium text-emerald-700 ring-1 ring-emerald-200/80"
                  >
                    Open Full Audio
                  </a>
                ) : null}
              </div>
            </>
          ) : (
            <p className="text-sm text-slate-500">Loading TTS settings...</p>
          )}
        </CardContent>
      </Card>

      {isLoading ? (
        <Card className="border-slate-200/80 bg-white/95 shadow-sm">
          <CardContent className="p-4 text-sm text-slate-600">Loading revise content...</CardContent>
        </Card>
      ) : null}

      {errorMessage ? (
        <Card className="border-slate-200/80 bg-white/95 shadow-sm">
          <CardContent className="p-4">
            <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
              {errorMessage}
            </div>
          </CardContent>
        </Card>
      ) : null}

      {!isLoading && !errorMessage && items.length === 0 ? (
        <Card className="border-slate-200/80 bg-white/95 shadow-sm">
          <CardContent className="p-4 text-sm text-slate-600">Revise content is empty.</CardContent>
        </Card>
      ) : null}

      {!isLoading && items.length > 0 ? (
        <div className="space-y-4">
          {items.map((item) => {
            const draftText = drafts[item.id] ?? buildEditableDraft(item.suggested)
            const isExplanationOpen = expandedExplanation[item.id] ?? false
            const hasDraft = extractSpeechText(draftText).length > 0
            const score = Number.isFinite(item.score) ? item.score : scoreRevisionIssues(item.issues)

            return (
              <Card key={item.id} className="w-full border-slate-200/80 bg-white/95 shadow-sm">
                <CardContent className="space-y-4 p-5">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-slate-900">{item.speaker}</p>
                      <p className="text-xs text-slate-500">
                        {formatDuration(item.startTimeMs / 1000)}-{formatDuration(item.endTimeMs / 1000)}
                      </p>
                    </div>
                    <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-medium text-slate-500">
                      {formatSeqLabel(item)}
                    </span>
                  </div>

                  {item.sourceSeqCount > 1 ? (
                    <div className="flex flex-wrap gap-2 text-xs text-slate-500">
                      <span className="rounded-full bg-amber-50 px-2.5 py-1 text-amber-800 ring-1 ring-amber-200/80">
                        {`Merged ${item.sourceSeqCount} utterances`}
                      </span>
                    </div>
                  ) : null}

                  <HighlightedTextarea
                    value={draftText}
                    onChange={(nextValue) => updateDraft(item.id, nextValue)}
                    onFocus={() => markItemEditing(item.id, true)}
                    onBlur={() => void handleDraftBlur(item)}
                  />

                  <div className="flex flex-wrap gap-2">
                    <Button
                      type="button"
                      size="xs"
                      variant="ghost"
                      className={`font-semibold ${getScoreButtonClassName(score)}`}
                      onClick={() => setExpandedExplanation((value) => toggleById(value, item.id))}
                    >
                      {`Score ${score}`}
                    </Button>
                    <Button
                      type="button"
                      size="xs"
                      variant="outline"
                      onClick={() => playOriginal(item)}
                      disabled={!session?.audioUrl}
                    >
                      {activeOriginalId === item.id ? 'Stop Original' : 'Original'}
                    </Button>
                    <Button
                      type="button"
                      size="xs"
                      variant="outline"
                      onClick={() => void synthesizeItem(item)}
                      disabled={!hasDraft || !canUseTts}
                    >
                      {activeSynthesisId === item.id ? 'Stop Synthesize' : 'Synthesize'}
                    </Button>
                  </div>

                  {isExplanationOpen ? (
                    <section className="rounded-xl border border-slate-200 bg-white p-4">
                      <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Score Detail</p>
                      <p className="mt-2 text-sm font-medium text-slate-900">{`Score ${score}`}</p>
                      <p className="mt-3 text-[11px] font-semibold uppercase tracking-wide text-slate-500">Original</p>
                      <p className="mt-2 text-sm leading-6 text-slate-700">{item.original}</p>
                      <p className="mt-4 text-[11px] font-semibold uppercase tracking-wide text-slate-500">Problems</p>
                      <div className="mt-2 flex flex-wrap gap-2">
                        {item.issues.map((issue) => (
                          <span
                            key={`${item.id}-${issue}`}
                            className="rounded-full bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-800 ring-1 ring-amber-200/80"
                          >
                            {issue}
                          </span>
                        ))}
                      </div>
                      <p className="mt-4 text-[11px] font-semibold uppercase tracking-wide text-slate-500">Notes</p>
                      <ul className="mt-2 space-y-2 text-sm leading-6 text-slate-700">
                        {item.explanations.map((line, index) => (
                          <li key={`${item.id}-explanation-${index}`}>{line}</li>
                        ))}
                      </ul>
                    </section>
                  ) : null}
                </CardContent>
              </Card>
            )
          })}
        </div>
      ) : null}
    </section>
  )
}
