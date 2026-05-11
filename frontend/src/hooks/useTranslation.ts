import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { createTranslation, getTranslation, isMissingTranslationError, translateTranslationItem } from '@/lib/api/translations'
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
  targetLanguage,
  enabled = true,
}: UseTranslationParams) {
  const [translation, setTranslation] = useState<TranslationResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const requestSeqRef = useRef(0)

  const canLoad = enabled && !!sourceType && !!sourceEntityId

  const load = useCallback(async () => {
    if (!canLoad || !sourceType || !sourceEntityId) return null
    const seq = requestSeqRef.current + 1
    requestSeqRef.current = seq
    setError(null)
    try {
      const data = await getTranslation({ sourceType, sourceEntityId, targetLanguage })
      if (requestSeqRef.current === seq) {
        setTranslation(data)
      }
      return data
    } catch (err) {
      if (isMissingTranslationError(err)) {
        const created = await createTranslation({
          sourceType,
          sourceEntityId,
          sessionId: sessionId ?? undefined,
          targetLanguage,
        })
        if (requestSeqRef.current === seq) {
          setTranslation(created)
        }
        return created
      }
      if (requestSeqRef.current === seq) {
        setError(err instanceof Error ? err.message : 'Failed to load translation')
      }
      return null
    }
  }, [canLoad, sourceType, sourceEntityId, sessionId, targetLanguage])

  const retry = useCallback(async () => {
    if (!canLoad || !sourceType || !sourceEntityId) return null
    const seq = requestSeqRef.current + 1
    requestSeqRef.current = seq
    setError(null)
    try {
      const data = await createTranslation({
        sourceType,
        sourceEntityId,
        sessionId: sessionId ?? undefined,
        targetLanguage,
        force: true,
      })
      if (requestSeqRef.current === seq) {
        setTranslation(data)
      }
      return data
    } catch (err) {
      if (requestSeqRef.current === seq) {
        setError(err instanceof Error ? err.message : 'Failed to start translation')
      }
      return null
    }
  }, [canLoad, sourceType, sourceEntityId, sessionId, targetLanguage])

  const translateItem = useCallback(async (sourceItemKey: string) => {
    if (!canLoad || !sourceType || !sourceEntityId) return null
    const seq = requestSeqRef.current + 1
    requestSeqRef.current = seq
    setError(null)
    try {
      const data = await translateTranslationItem({
        sourceType,
        sourceEntityId,
        sourceItemKey,
        sessionId: sessionId ?? undefined,
        targetLanguage,
      })
      if (requestSeqRef.current === seq) {
        setTranslation(data)
      }
      return data
    } catch (err) {
      if (requestSeqRef.current === seq) {
        setError(err instanceof Error ? err.message : 'Failed to translate item')
      }
      return null
    }
  }, [canLoad, sourceType, sourceEntityId, sessionId, targetLanguage])

  useEffect(() => {
    if (!canLoad) {
      requestSeqRef.current += 1
      setTranslation(null)
      setError(null)
      return
    }

    void load()
  }, [canLoad, load])

  useEffect(() => {
    if (!canLoad) return
    const status = translation?.status_name
    if (status !== 'pending' && status !== 'generating') return

    const timer = window.setTimeout(() => {
      void load()
    }, 2000)

    return () => window.clearTimeout(timer)
  }, [canLoad, load, translation])

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
    translateItem,
  }
}
