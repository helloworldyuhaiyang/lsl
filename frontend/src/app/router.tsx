import { Navigate, createBrowserRouter, useParams } from 'react-router-dom'

import { AppShell } from '@/app/layout/app-shell'
import { ROUTES } from '@/lib/constants/routes'
import { DashboardPage } from '@/pages/dashboard-page'
import { ListeningPage } from '@/pages/listening-page'
import { NotFoundPage } from '@/pages/not-found-page'
import { RevisePage } from '@/pages/revise-page'
import { SessionPage } from '@/pages/session-page'
import { UploadPage } from '@/pages/upload-page'

function resolveTaskSummaryToSessionId(summaryId: string): string {
  if (summaryId.startsWith('summary_')) {
    return summaryId.slice('summary_'.length)
  }
  return summaryId
}

export const router = createBrowserRouter([
  {
    path: ROUTES.root,
    element: <AppShell />,
    children: [
      {
        index: true,
        element: <Navigate replace to={ROUTES.dashboard} />,
      },
      {
        path: ROUTES.dashboard,
        element: <DashboardPage />,
      },
      {
        path: ROUTES.upload,
        element: <UploadPage />,
      },
      {
        path: ROUTES.session,
        element: <SessionPage />,
      },
      {
        path: ROUTES.revise,
        element: <RevisePage />,
      },
      {
        path: ROUTES.listening,
        element: <ListeningPage />,
      },
      {
        path: '/tasks/:taskId',
        element: <LegacyTaskRedirect />,
      },
      {
        path: '/summaries/:summaryId',
        element: <LegacySummaryRedirect />,
      },
      {
        path: '*',
        element: <NotFoundPage />,
      },
    ],
  },
])

function LegacyTaskRedirect() {
  const { taskId = '' } = useParams()
  return <Navigate replace to={`/sessions/${taskId}`} />
}

function LegacySummaryRedirect() {
  const { summaryId = '' } = useParams()
  const sessionId = resolveTaskSummaryToSessionId(summaryId)
  return <Navigate replace to={`/sessions/${sessionId}`} />
}
