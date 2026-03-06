import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { PageTitle } from '@/components/common/page-title'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { getListeningPath, getSessionPath, ROUTES } from '@/lib/constants/routes'
import { formatExpressionCue, inferExpressionCue, scoreRevisionIssues, type RevisionItem } from '@/lib/session/revision'
import { getSessionSummary, type SessionSummary } from '@/lib/session/sessions'
import { formatDuration } from '@/lib/utils/format'

function toggleById(value: Record<string, boolean>, id: string): Record<string, boolean> {
  return {
    ...value,
    [id]: !value[id],
  }
}

function splitDraftContent(value: string): { sentence: string; cue: string } {
  const trimmed = value.trim()
  if (!trimmed) {
    return { sentence: '', cue: '' }
  }

  const lines = trimmed.split('\n').map((line) => line.trim()).filter(Boolean)
  const lastLine = lines.at(-1) ?? ''

  if (lastLine.startsWith('[') && lastLine.endsWith(']')) {
    return {
      sentence: lines.slice(0, -1).join(' ').trim(),
      cue: lastLine,
    }
  }

  return {
    sentence: trimmed,
    cue: '',
  }
}

function buildEditableDraft(sentence: string, cue?: string): string {
  const resolvedCue = cue?.trim() || formatExpressionCue(inferExpressionCue(sentence))
  return `${sentence.trim()}\n${resolvedCue}`.trim()
}

const MOCK_REVISION_ITEMS: RevisionItem[] = [
  {
    id: 'mock-1',
    seq: 1,
    speaker: 'User 1',
    startTimeMs: 12000,
    endTimeMs: 15000,
    original: 'I go to to the park with my friends.',
    suggested: 'I went to the park with my friends last weekend.',
    cue: '[有点犹豫但友好的 / 回答问题的 / 周末聊天]',
    score: 52,
    issues: ['语法错误', '不够自然'],
    explanations: ['根据上下文对方问的是 "What did you do last weekend?"，这里应该用过去时来回答。', '原句里重复了 "to"，而且缺少时间信息，表达不够完整自然。'],
  },
  {
    id: 'mock-2',
    seq: 2,
    speaker: 'User 2',
    startTimeMs: 16000,
    endTimeMs: 19000,
    original: 'I very like this city because people is friendly.',
    suggested: 'I really like this city because the people are friendly.',
    cue: '[真诚的 / 描述感受的 / 城市话题]',
    score: 61,
    issues: ['语法错误', '不够自然'],
    explanations: ['"I very like" 不是自然表达，通常改成 "I really like"。', '"people is" 应改成 "people are"R,里有人称和谓语搭配问题。'],
  },
  {
    id: 'mock-3',
    seq: 3,
    speaker: 'User 1',
    startTimeMs: 20000,
    endTimeMs: 23000,
    original: 'I do not have much free time on weekdays.',
    suggested: 'I do not have much free time on weekdays.',
    cue: '[自然的 / 平稳的 / 日常对话]',
    score: 88,
    issues: ['表达基本自然'],
    explanations: ['这句话语法和表达都比较自然，基本可以直接通过。'],
  },
  {
    id: 'mock-4',
    seq: 4,
    speaker: 'User 2',
    startTimeMs: 24000,
    endTimeMs: 28000,
    original: 'Actually I want improve my spoken english more quickly',
    suggested: 'Actually, I want to improve my spoken English more quickly.',
    cue: '[认真的 / 表达目标的 / 学习计划]',
    score: 58,
    issues: ['语法错误', '大小写问题', '标点问题'],
    explanations: ['“want improve” 中间需要补上 “to”，否则语法不完整。', '“English” 需要大写。', '句子开头后的停顿和结尾标点需要补上，读起来会更自然。'],
  },
]

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
  const [expandedExplanation, setExpandedExplanation] = useState<Record<string, boolean>>({})
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [playbackMessage, setPlaybackMessage] = useState<string | null>(null)
  const [activeOriginalId, setActiveOriginalId] = useState<string | null>(null)
  const [activeSynthesisId, setActiveSynthesisId] = useState<string | null>(null)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const snippetEndRef = useRef<number | null>(null)

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
        setItems(MOCK_REVISION_ITEMS)
        setDrafts(Object.fromEntries(MOCK_REVISION_ITEMS.map((item) => [item.id, buildEditableDraft(item.suggested, item.cue)])))
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
    const draft = splitDraftContent(drafts[item.id] ?? buildEditableDraft(item.suggested, item.cue))
    if (!draft.sentence) {
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

    const utterance = new SpeechSynthesisUtterance(draft.sentence)
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
              <Link to={sessionId ? getSessionPath(sessionId) : ROUTES.dashboard}>Session</Link>
            </Button>
            <Button asChild variant="outline" size="sm">
              <Link to={sessionId ? getListeningPath(sessionId) : ROUTES.dashboard}>Listening</Link>
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
        <CardHeader className="gap-2">
          <CardTitle>{items.length > 0 ? `${items.length} Revision Cards` : 'Revision Cards'}</CardTitle>
          <CardDescription>
            Suggested text is directly editable. Click the score to inspect the original sentence and problem details.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3 pt-0 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex flex-wrap gap-2 text-xs text-slate-500">
            <span className="rounded-full bg-slate-100 px-2.5 py-1">{items.length} sentences</span>
            <span className="rounded-full bg-slate-100 px-2.5 py-1">expression cue visible</span>
            <span className="rounded-full bg-slate-100 px-2.5 py-1">large screens use multi-column cards</span>
          </div>
          {playbackMessage ? <p className="text-xs text-slate-500 sm:text-right">{playbackMessage}</p> : null}
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
        <div className="grid gap-4 xl:grid-cols-2 2xl:grid-cols-3">
          {items.map((item) => {
            const draftText = drafts[item.id] ?? buildEditableDraft(item.suggested, item.cue)
            const draft = splitDraftContent(draftText)
            const isExplanationOpen = expandedExplanation[item.id] ?? false
            const hasDraft = draft.sentence.length > 0
            const score = Number.isFinite(item.score) ? item.score : scoreRevisionIssues(item.issues)

            return (
              <Card key={item.id} className="border-slate-200/80 bg-white/95 shadow-sm">
                <CardContent className="space-y-4 p-5">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-slate-900">{item.speaker}</p>
                      <p className="text-xs text-slate-500">
                        {formatDuration(item.startTimeMs / 1000)}-{formatDuration(item.endTimeMs / 1000)}
                      </p>
                    </div>
                    <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-medium text-slate-500">
                      #{item.seq}
                    </span>
                  </div>

                  <div className="rounded-xl border border-slate-200 bg-white transition focus-within:border-slate-400 focus-within:ring-2 focus-within:ring-slate-200">
                    <textarea
                      value={draftText}
                      onChange={(event) => updateDraft(item.id, event.target.value)}
                      rows={4}
                      className="min-h-20 w-full resize-y border-0 bg-transparent px-3 py-3 text-sm leading-6 text-slate-900 outline-none"
                    />
                  </div>

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
