export const ROUTES = {
  root: '/',
  upload: '/upload',
  task: '/tasks/:taskId',
  summary: '/summaries/:summaryId',
} as const

export const NAV_ITEMS = [
  { label: 'Upload', href: ROUTES.upload },
  { label: 'Task', href: '/tasks/demo-task' },
  { label: 'Summary', href: '/summaries/demo-summary' },
] as const
