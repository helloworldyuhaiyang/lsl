import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { PageTitle } from '@/components/common/page-title'
import { HighlightedTextarea } from '@/components/ui/highlighted-textarea'
import { ApiRequestError } from '@/lib/api/client'
import { createRevision, getRevision, updateRevisionItem } from '@/lib/api/revisions'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { getListeningPath, getSessionPath, ROUTES } from '@/lib/constants/routes'
import { formatCueText, formatExpressionCue, inferExpressionCue, scoreRevisionIssues, type RevisionItem } from '@/lib/session/revision'
import { getSessionSummary, type SessionSummary } from '@/lib/session/sessions'
import { formatDuration } from '@/lib/utils/format'
import type { RevisionResponse } from '@/types/api'

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

function extractSpeechText(value: string): string {
  return value
    .replace(/\[[^[\]]*]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

function buildEditableDraft(sentence: string, cue?: string): string {
  const resolvedCue = cue?.trim() || formatExpressionCue(inferExpressionCue(sentence))
  return `${resolvedCue} ${sentence.trim()}`.trim()
}

function buildDraftsByItem(items: RevisionItem[]): Record<string, string> {
  return Object.fromEntries(items.map((item) => [item.id, item.persistedDraft ?? buildEditableDraft(item.suggested, item.cue)]))
}

function formatSeqLabel(item: RevisionItem): string {
  return item.seqStart === item.seqEnd ? `#${item.seqStart}` : `#${item.seqStart}-${item.seqEnd}`
}

function normalizeDraftValue(value: string | null | undefined): string {
  return value?.trim() || ''
}

function buildPersistedDraft(draftText: string | null | undefined, draftCue: string | null | undefined): string | null {
  const normalizedDraftText = draftText?.trim() || ''
  const normalizedDraftCue = draftCue?.trim() || ''
  if (normalizedDraftText) {
    return normalizedDraftText
  }
  if (normalizedDraftCue) {
    return formatCueText(normalizedDraftCue)
  }
  return null
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
    suggested: extractSpeechText(item.draft_text?.trim() || item.suggested_text),
    cue: formatCueText(item.draft_cue?.trim() || item.suggested_cue?.trim() || formatExpressionCue(inferExpressionCue(item.suggested_text))),
    score: item.score,
    issues: splitCommaSeparated(item.issue_tags),
    explanations: splitExplanationText(item.explanations),
    persistedDraft: buildPersistedDraft(item.draft_text, item.draft_cue),
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

export function RevisePage() {
  const { sessionId = '' } = useParams()
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
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [playbackMessage, setPlaybackMessage] = useState<string | null>(null)
  const [activeOriginalId, setActiveOriginalId] = useState<string | null>(null)
  const [activeSynthesisId, setActiveSynthesisId] = useState<string | null>(null)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const snippetEndRef = useRef<number | null>(null)
  const resolvedSessionId = session?.sessionId || sessionId
  const isRevisionGenerating = revisionStatusName === 'generating'
  const hasActiveDraftMutation =
    Object.keys(editingItemIds).length > 0 || Object.keys(savingItemIds).length > 0
  const canRevise = Boolean(resolvedSessionId) && !isLoading && !isSubmittingRevision && !isRevisionGenerating && session?.status === 'completed'

  function applyRevision(revision: RevisionResponse) {
    const nextItems = mapRevisionResponseToItems(revision)
    const nextDrafts = buildDraftsByItem(nextItems)
    setRevisionStatusName(revision.status_name)
    setItems(nextItems)
    setDrafts(nextDrafts)
    setPersistedDrafts(nextDrafts)
    setUserPrompt(revision.user_prompt?.trim() || '')
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

      if (typeof window !== 'undefined' && window.speechSynthesis) {
        window.speechSynthesis.cancel()
      }
    }
  }, [session?.audioUrl])

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
        draftCue: null,
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

    if (typeof window !== 'undefined' && window.speechSynthesis) {
      window.speechSynthesis.cancel()
    }

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

  function synthesizeItem(item: RevisionItem) {
    const sentence = extractSpeechText(drafts[item.id] ?? buildEditableDraft(item.suggested, item.cue))
    if (!sentence) {
      return
    }

    if (typeof window === 'undefined' || !window.speechSynthesis) {
      setPlaybackMessage('Speech synthesis is not available in this browser.')
      return
    }

    if (activeSynthesisId === item.id) {
      window.speechSynthesis.cancel()
      setActiveSynthesisId(null)
      setPlaybackMessage(null)
      return
    }

    audioRef.current?.pause()
    snippetEndRef.current = null
    setActiveOriginalId(null)
    window.speechSynthesis.cancel()

    const utterance = new SpeechSynthesisUtterance(sentence)
    utterance.lang = 'en-US'
    utterance.rate = 1
    utterance.onstart = () => {
      setActiveSynthesisId(item.id)
      setPlaybackMessage(`Synthesize preview: ${item.speaker}`)
    }
    utterance.onend = () => {
      setActiveSynthesisId(null)
      setPlaybackMessage(null)
    }
    utterance.onerror = () => {
      setActiveSynthesisId(null)
      setPlaybackMessage('Failed to synthesize preview.')
    }

    window.speechSynthesis.speak(utterance)
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
              Add an optional prompt, then click `Revise by AI` to call `POST /revisions`.
            </CardDescription>
          </div>
          <div className="flex items-center gap-2 self-start">
            {revisionStatusName ? (
              <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-medium uppercase tracking-wide text-slate-600">
                {revisionStatusName}
              </span>
            ) : null}
            <Button type="button" size="sm" onClick={() => void handleRevise()} disabled={!canRevise}>
              {isSubmittingRevision ? 'Submitting...' : isRevisionGenerating ? 'Generating' : 'Revise by AI'}
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

      {!isLoading && !errorMessage && items.length > 0 ? (
        <div className="space-y-4">
          {items.map((item) => {
            const draftText = drafts[item.id] ?? buildEditableDraft(item.suggested, item.cue)
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
                      onClick={() => synthesizeItem(item)}
                      disabled={!hasDraft}
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
