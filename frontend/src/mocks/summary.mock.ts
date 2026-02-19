import type { SummaryLine } from '@/types/domain'

export function buildSummaryLines(): SummaryLine[] {
  return [
    {
      id: 'line-1',
      timestampLabel: '00:08',
      speaker: 'speaker_a',
      original: 'I want discuss yesterday client call, it was a bit mess.',
      optimized: 'I want to discuss yesterday\'s client call. It was a bit messy.',
      note: 'Added missing infinitive and article; corrected adjective form.',
    },
    {
      id: 'line-2',
      timestampLabel: '00:15',
      speaker: 'speaker_b',
      original: 'Yes, we should align on next step and timeline soonly.',
      optimized: 'Yes, we should align on the next steps and timeline soon.',
      note: 'Corrected plural form and replaced non-standard adverb.',
    },
    {
      id: 'line-3',
      timestampLabel: '00:27',
      speaker: 'speaker_a',
      original: 'Can you send me the summary after this talking?',
      optimized: 'Could you send me the summary after this discussion?',
      note: 'Improved tone and replaced unnatural noun phrase.',
    },
  ]
}
