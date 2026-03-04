import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { PageTitle } from '@/components/common/page-title'
import { StatusBadge } from '@/components/common/status-badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { getSessionPath, ROUTES } from '@/lib/constants/routes'
import { listSessionSummaries, type SessionSummary } from '@/lib/session/sessions'
import { formatMonthDay } from '@/lib/utils/format'

function formatDurationMinutes(durationSec: number | null): string {
  if (durationSec === null || durationSec <= 0) {
    return '--'
  }

  const minutes = Math.max(1, Math.round(durationSec / 60))
  return `${minutes} min`
}

export function DashboardPage() {
  const [sessions, setSessions] = useState<SessionSummary[]>([])
  const [search, setSearch] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  async function loadSessions(showRefreshing = false) {
    try {
      if (showRefreshing) {
        setIsRefreshing(true)
      } else {
        setIsLoading(true)
      }

      const next = await listSessionSummaries({ limit: 200 })
      setSessions(next)
      setErrorMessage(null)
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Failed to load sessions.')
    } finally {
      setIsLoading(false)
      setIsRefreshing(false)
    }
  }

  useEffect(() => {
    void loadSessions(false)
  }, [])

  const filtered = useMemo(() => {
    const normalized = search.trim().toLowerCase()
    if (!normalized) {
      return sessions
    }

    return sessions.filter((session) => {
      const target = [session.title, session.description, session.fileName, session.objectKey].join(' ').toLowerCase()
      return target.includes(normalized)
    })
  }, [search, sessions])

  return (
    <section className="space-y-6">
      <PageTitle
        eyebrow="Workspace"
        title="Dashboard"
        description="Manage your sessions and track processing status in one place."
        actions={
          <Button asChild>
            <Link to={ROUTES.upload}>Upload Session</Link>
          </Button>
        }
      />

      <Card className="border-slate-200/80 bg-white/95 shadow-sm">
        <CardHeader className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <CardTitle>Sessions</CardTitle>
          <div className="flex w-full gap-2 sm:w-auto">
            <input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search session"
              className="h-9 w-full rounded-md border border-slate-300 bg-white px-3 text-sm outline-none ring-0 placeholder:text-slate-400 focus:border-slate-900 sm:w-64"
            />
            <Button type="button" variant="outline" onClick={() => void loadSessions(true)} disabled={isRefreshing}>
              {isRefreshing ? 'Refreshing...' : 'Refresh'}
            </Button>
          </div>
        </CardHeader>

        <CardContent>
          {isLoading ? <p className="text-sm text-slate-600">Loading sessions...</p> : null}
          {errorMessage ? (
            <p className="rounded-md border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">{errorMessage}</p>
          ) : null}

          {!isLoading && !errorMessage ? (
            filtered.length > 0 ? (
              <>
                <div className="hidden overflow-x-auto md:block">
                  <table className="w-full border-collapse text-left text-sm">
                    <thead>
                      <tr className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
                        <th className="py-3 pr-3 font-medium">Title</th>
                        <th className="py-3 pr-3 font-medium">Duration</th>
                        <th className="py-3 pr-3 font-medium">Status</th>
                        <th className="py-3 pr-3 font-medium">Created</th>
                        <th className="py-3 font-medium text-right">Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filtered.map((session) => (
                        <tr key={session.sessionId} className="border-b border-slate-100 align-middle last:border-none">
                          <td className="py-3 pr-3">
                            <p className="font-medium text-slate-900">{session.title}</p>
                            <p className="truncate text-xs text-slate-500">{session.fileName}</p>
                          </td>
                          <td className="py-3 pr-3 text-slate-700">{formatDurationMinutes(session.durationSec)}</td>
                          <td className="py-3 pr-3">
                            <StatusBadge status={session.status} />
                          </td>
                          <td className="py-3 pr-3 text-slate-700">{formatMonthDay(session.createdAt)}</td>
                          <td className="py-3 text-right">
                            <Button asChild size="sm" variant="outline">
                              <Link to={getSessionPath(session.sessionId)}>Open</Link>
                            </Button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <ul className="space-y-3 md:hidden">
                  {filtered.map((session) => (
                    <li key={session.sessionId} className="rounded-lg border border-slate-200 p-3">
                      <p className="text-sm font-medium text-slate-900">{session.title}</p>
                      <p className="mt-1 text-xs text-slate-500">
                        {formatDurationMinutes(session.durationSec)} · {formatMonthDay(session.createdAt)}
                      </p>
                      <div className="mt-3 flex items-center justify-between">
                        <StatusBadge status={session.status} />
                        <Button asChild size="sm" variant="outline">
                          <Link to={getSessionPath(session.sessionId)}>Open</Link>
                        </Button>
                      </div>
                    </li>
                  ))}
                </ul>
              </>
            ) : (
              <div className="rounded-md border border-dashed border-slate-300 bg-slate-50 p-6 text-center">
                <p className="text-sm text-slate-600">No session found.</p>
                <Button asChild className="mt-3" size="sm">
                  <Link to={ROUTES.upload}>Upload your first session</Link>
                </Button>
              </div>
            )
          ) : null}
        </CardContent>
      </Card>
    </section>
  )
}
