const DEFAULT_API_BASE_URL = '/api'

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? DEFAULT_API_BASE_URL).replace(/\/$/, '')

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

export async function requestJson<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const response = await fetch(buildUrl(path, options.query), {
    method: options.method ?? 'GET',
    headers: options.headers,
    body: options.body,
  })

  if (!response.ok) {
    const text = await response.text()
    throw new Error(text || `Request failed with status ${response.status}`)
  }

  return (await response.json()) as T
}

export { API_BASE_URL }
