import { ApiRequestError, requestJson } from '@/lib/api/client'
import type { TranslationResponse } from '@/types/api'

interface ApiResponse<T> {
  code: number
  message: string
  data: T
}

export interface TranslationSourceParams {
  sourceType: 'transcript' | 'revision'
  sourceEntityId: string
  sessionId?: string
  targetLanguage?: string
}

export async function getTranslation(params: TranslationSourceParams): Promise<TranslationResponse> {
  const query: Record<string, string> = {
    source_type: params.sourceType,
    source_entity_id: params.sourceEntityId,
  }
  if (params.targetLanguage) {
    query.target_language = params.targetLanguage
  }
  const response = await requestJson<ApiResponse<TranslationResponse>>('/translations', {
    method: 'GET',
    query,
  })
  return response.data
}

export async function createTranslation(params: TranslationSourceParams & { force?: boolean }): Promise<TranslationResponse> {
  const response = await requestJson<ApiResponse<TranslationResponse>>('/translations', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      source_type: params.sourceType,
      source_entity_id: params.sourceEntityId,
      session_id: params.sessionId,
      target_language: params.targetLanguage,
      force: params.force ?? false,
    }),
  })
  return response.data
}

export async function translateTranslationItem(params: TranslationSourceParams & { sourceItemKey: string }): Promise<TranslationResponse> {
  const response = await requestJson<ApiResponse<TranslationResponse>>('/translations/items/translate', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      source_type: params.sourceType,
      source_entity_id: params.sourceEntityId,
      source_item_key: params.sourceItemKey,
      session_id: params.sessionId,
      target_language: params.targetLanguage,
    }),
  })
  return response.data
}

export function isMissingTranslationError(error: unknown): boolean {
  return error instanceof ApiRequestError && error.status === 404
}
