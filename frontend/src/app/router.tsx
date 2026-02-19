import { Navigate, createBrowserRouter } from 'react-router-dom'

import { AppShell } from '@/app/layout/app-shell'
import { ROUTES } from '@/lib/constants/routes'
import { NotFoundPage } from '@/pages/not-found-page'
import { SummaryPage } from '@/pages/summary-page'
import { TaskPage } from '@/pages/task-page'
import { UploadPage } from '@/pages/upload-page'

export const router = createBrowserRouter([
  {
    path: ROUTES.root,
    element: <AppShell />,
    children: [
      {
        index: true,
        element: <Navigate replace to={ROUTES.upload} />,
      },
      {
        path: ROUTES.upload,
        element: <UploadPage />,
      },
      {
        path: ROUTES.task,
        element: <TaskPage />,
      },
      {
        path: ROUTES.summary,
        element: <SummaryPage />,
      },
      {
        path: '*',
        element: <NotFoundPage />,
      },
    ],
  },
])
