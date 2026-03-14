const DEFAULT_API_BASE_URL = '/api'

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? DEFAULT_API_BASE_URL).replace(/\/$/, '')

export class ApiRequestError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiRequestError'
    this.status = status
  }
}

function buildUrl(path: string, query?: Record<string, string>): string {
  const url = new URL(`${API_BASE_URL}${path}`, window.location.origin)
  if (query) {
    Object.entries(query).forEach(([key, value]) => {
      url.searchParams.set(key, value)
    })
  }
  return url.toString()
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  query?: Record<string, string>
  headers?: Record<string, string>
  body?: BodyInit
}

async function assertOk(response: Response): Promise<void> {
  if (response.ok) {
    return
  }

  const text = await response.text()
  const fallbackMessage = `Request failed with status ${response.status}`
  if (text) {
    let message: string | null = null
    try {
      const parsed = JSON.parse(text) as { detail?: string; message?: string }
      if (typeof parsed.detail === 'string' && parsed.detail.trim()) {
        message = parsed.detail
      } else if (typeof parsed.message === 'string' && parsed.message.trim()) {
        message = parsed.message
      }
    } catch {
      message = text
    }

    throw new ApiRequestError(response.status, message || text || fallbackMessage)
  }

  throw new ApiRequestError(response.status, fallbackMessage)
}

export async function requestJson<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const response = await fetch(buildUrl(path, options.query), {
    method: options.method ?? 'GET',
    headers: options.headers,
    body: options.body,
  })

  await assertOk(response)

  return (await response.json()) as T
}

export async function requestBlob(path: string, options: RequestOptions = {}): Promise<Blob> {
  const response = await fetch(buildUrl(path, options.query), {
    method: options.method ?? 'GET',
    headers: options.headers,
    body: options.body,
  })

  await assertOk(response)
  return await response.blob()
}

export { API_BASE_URL }
