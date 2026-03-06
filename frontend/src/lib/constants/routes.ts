export const ROUTES = {
  root: '/',
  dashboard: '/dashboard',
  upload: '/upload',
  session: '/sessions/:sessionId',
  revise: '/sessions/:sessionId/revise',
  listening: '/sessions/:sessionId/listening',
} as const

export const NAV_ITEMS = [
  { label: 'Dashboard', href: ROUTES.dashboard },
] as const

export function getSessionPath(sessionId: string): string {
  return `/sessions/${sessionId}`
}

export function getRevisePath(sessionId: string): string {
  return `/sessions/${sessionId}/revise`
}

export function getListeningPath(sessionId: string): string {
  return `/sessions/${sessionId}/listening`
}
