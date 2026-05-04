import { useCallback, useEffect, useMemo, useState } from 'react'
import { createTranslation, getTranslation, isMissingTranslationError } from '@/lib/api/translations'
import type { TranslationItemResponse, TranslationResponse } from '@/types/api'

type SourceType = 'transcript' | 'revision'

interface UseTranslationParams {
  sourceType?: SourceType
  sourceEntityId?: string | null
  sessionId?: string | null
  targetLanguage?: string
  enabled?: boolean
}

export function useTranslation({
  sourceType,
  sourceEntityId,
  sessionId,
  targetLanguage = 'zh-CN',
  enabled = true,
}: UseTranslationParams) {
  const [translation, setTranslation] = useState<TranslationResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  const canLoad = enabled && !!sourceType && !!sourceEntityId

  const load = useCallback(async () => {
    if (!canLoad || !sourceType || !sourceEntityId) return null
    setError(null)
    try {
      const data = await getTranslation({ sourceType, sourceEntityId, targetLanguage })
      setTranslation(data)
      return data
    } catch (err) {
      if (isMissingTranslationError(err)) {
        const created = await createTranslation({
          sourceType,
          sourceEntityId,
          sessionId: sessionId ?? undefined,
          targetLanguage,
        })
        setTranslation(created)
        return created
      }
      setError(err instanceof Error ? err.message : 'Failed to load translation')
      return null
    }
  }, [canLoad, sourceType, sourceEntityId, sessionId, targetLanguage])

  const retry = useCallback(async () => {
    if (!canLoad || !sourceType || !sourceEntityId) return null
    setError(null)
    try {
      const data = await createTranslation({
        sourceType,
        sourceEntityId,
        sessionId: sessionId ?? undefined,
        targetLanguage,
        force: true,
      })
      setTranslation(data)
      return data
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start translation')
      return null
    }
  }, [canLoad, sourceType, sourceEntityId, sessionId, targetLanguage])

  useEffect(() => {
    if (!canLoad) {
      setTranslation(null)
      setError(null)
      return
    }
    let cancelled = false
    let timer: ReturnType<typeof window.setTimeout> | null = null

    async function loadAndSchedule() {
      const data = await load()
      const status = data?.status_name
      if (!cancelled && (status === 'pending' || status === 'generating')) {
        timer = window.setTimeout(loadAndSchedule, 2000)
      }
    }

    void loadAndSchedule()
    return () => {
      cancelled = true
      if (timer) window.clearTimeout(timer)
    }
  }, [canLoad, load])

  const itemsByKey = useMemo(() => {
    const map = new Map<string, TranslationItemResponse>()
    for (const item of translation?.items ?? []) {
      map.set(item.source_item_key, item)
    }
    return map
  }, [translation])

  const isTranslating = translation?.status_name === 'pending' || translation?.status_name === 'generating'
  const hasStuckItems = !!translation
    && !isTranslating
    && translation.items.some((item) => item.status_name === 'pending' || item.status_name === 'generating')
  const needsUpdate = !!translation && translation.stale_count > 0

  return {
    translation,
    itemsByKey,
    isTranslating,
    hasStuckItems,
    needsUpdate,
    error,
    reload: load,
    retry,
  }
}
