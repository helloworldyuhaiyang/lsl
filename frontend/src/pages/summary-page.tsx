import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { PageTitle } from '@/components/common/page-title'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { buildSummaryLines } from '@/mocks/summary.mock'
import { getUploadBySummaryId } from '@/lib/storage/upload-history'

const SECTIONS = ['transcript', 'improvements', 'listening'] as const

type Section = (typeof SECTIONS)[number]

export function SummaryPage() {
  const { summaryId = 'unknown-summary' } = useParams()
  const [section, setSection] = useState<Section>('transcript')

  const record = useMemo(() => getUploadBySummaryId(summaryId), [summaryId])
  const lines = useMemo(() => buildSummaryLines(), [])

  return (
    <section className="space-y-6">
      <PageTitle
        eyebrow="Step 3"
        title="Conversation Summary"
        description={`Review transcript, expression refinements, and listening loop material. Summary ID: ${summaryId}`}
        actions={
          <Button asChild variant="outline" size="sm">
            <Link to={record ? `/tasks/${record.taskId}` : '/upload'}>Back to Task</Link>
          </Button>
        }
      />

      <Card className="bg-white/90 shadow-sm">
        <CardHeader>
          <CardTitle className="text-lg">Section Switcher</CardTitle>
          <CardDescription>Current summary data is mocked and will be replaced by real backend payload later.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          {SECTIONS.map((item) => (
            <Button
              key={item}
              type="button"
              size="sm"
              variant={section === item ? 'default' : 'outline'}
              onClick={() => setSection(item)}
            >
              {item}
            </Button>
          ))}
        </CardContent>
      </Card>

      {section === 'transcript' ? (
        <Card className="bg-white/90 shadow-sm">
          <CardHeader>
            <CardTitle className="text-lg">Transcript Timeline</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-3">
              {lines.map((line) => (
                <li key={line.id} className="rounded-lg border border-slate-200 bg-slate-50/70 p-4">
                  <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
                    {line.timestampLabel} · {line.speaker.replace('_', ' ')}
                  </p>
                  <p className="mt-2 text-sm text-slate-800">{line.original}</p>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      ) : null}

      {section === 'improvements' ? (
        <Card className="bg-white/90 shadow-sm">
          <CardHeader>
            <CardTitle className="text-lg">Expression Improvements</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {lines.map((line) => (
              <article key={line.id} className="rounded-lg border border-slate-200 p-4">
                <p className="text-xs text-slate-500">{line.timestampLabel}</p>
                <p className="mt-2 text-sm text-slate-600">Original: {line.original}</p>
                <p className="mt-1 text-sm font-medium text-slate-900">Optimized: {line.optimized}</p>
                <p className="mt-1 text-xs text-slate-500">Reason: {line.note}</p>
              </article>
            ))}
          </CardContent>
        </Card>
      ) : null}

      {section === 'listening' ? (
        <Card className="bg-white/90 shadow-sm">
          <CardHeader>
            <CardTitle className="text-lg">Listening Replay</CardTitle>
            <CardDescription>
              TTS output is not integrated yet. The player below uses original uploaded audio when available.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {record ? (
              <>
                <p className="text-sm text-slate-700">Source file: {record.fileName}</p>
                <audio className="w-full" controls src={record.assetUrl}>
                  <track kind="captions" />
                </audio>
                <Button asChild size="sm" variant="outline">
                  <a href={record.assetUrl} target="_blank" rel="noreferrer">
                    Open Source Audio URL
                  </a>
                </Button>
              </>
            ) : (
              <p className="text-sm text-slate-600">
                No matching upload record in localStorage. Upload a file first to preview listening replay.
              </p>
            )}
          </CardContent>
        </Card>
      ) : null}
    </section>
  )
}
