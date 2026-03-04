const STORAGE_KEY = 'lsl.session-metadata.v1'

export interface SessionMetadata {
  title?: string
  description?: string
  fileName?: string
  fileSize?: number
  durationSec?: number | null
}

type SessionMetadataMap = Record<string, SessionMetadata>

function canUseStorage(): boolean {
  return typeof window !== 'undefined' && typeof window.localStorage !== 'undefined'
}

function readStorageMap(): SessionMetadataMap {
  if (!canUseStorage()) {
    return {}
  }

  const raw = window.localStorage.getItem(STORAGE_KEY)
  if (!raw) {
    return {}
  }

  try {
    const parsed = JSON.parse(raw) as SessionMetadataMap
    if (!parsed || typeof parsed !== 'object') {
      return {}
    }
    return parsed
  } catch {
    return {}
  }
}

function writeStorageMap(map: SessionMetadataMap): void {
  if (!canUseStorage()) {
    return
  }
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(map))
}

export function listSessionMetadata(): SessionMetadataMap {
  return readStorageMap()
}

export function getSessionMetadata(sessionId: string): SessionMetadata | null {
  const all = readStorageMap()
  return all[sessionId] ?? null
}

export function upsertSessionMetadata(sessionId: string, metadata: SessionMetadata): void {
  const all = readStorageMap()
  all[sessionId] = {
    ...(all[sessionId] ?? {}),
    ...metadata,
  }
  writeStorageMap(all)
}
