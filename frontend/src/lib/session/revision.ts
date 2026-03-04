import type { TaskTranscriptUtterance } from '@/types/api'

export interface RevisionItem {
  id: string
  seq: number
  speaker: string
  startTimeMs: number
  endTimeMs: number
  original: string
  suggested: string
  removedTokens: string[]
  addedTokens: string[]
  explanations: string[]
}

function ensureSentencePunctuation(text: string): string {
  if (!text.trim()) {
    return text
  }
  if (/[.!?]$/.test(text.trim())) {
    return text.trim()
  }
  return `${text.trim()}.`
}

function capitalizeFirst(text: string): string {
  const trimmed = text.trim()
  if (!trimmed) {
    return trimmed
  }
  return `${trimmed[0].toUpperCase()}${trimmed.slice(1)}`
}

function suggestSentence(original: string): { suggested: string; explanations: string[] } {
  let next = original.trim()
  const explanations: string[] = []

  const replacements: Array<{ pattern: RegExp; replacement: string; note: string }> = [
    { pattern: /\bI go to\b/gi, replacement: 'I went to', note: 'Adjusted present tense to past tense in context.' },
    { pattern: /\bgo to park\b/gi, replacement: 'go to the park', note: 'Inserted article for natural phrasing.' },
    { pattern: /\ba bit mess\b/gi, replacement: 'a bit messy', note: 'Corrected adjective form.' },
    { pattern: /\bsoonly\b/gi, replacement: 'soon', note: 'Replaced non-standard word.' },
    { pattern: /\bthis talking\b/gi, replacement: 'this discussion', note: 'Improved expression clarity.' },
  ]

  replacements.forEach((rule) => {
    if (rule.pattern.test(next)) {
      next = next.replace(rule.pattern, rule.replacement)
      explanations.push(rule.note)
    }
  })

  const capitalized = capitalizeFirst(next)
  if (capitalized !== next) {
    next = capitalized
    explanations.push('Capitalized sentence start.')
  }

  const punctuated = ensureSentencePunctuation(next)
  if (punctuated !== next) {
    next = punctuated
    explanations.push('Added ending punctuation.')
  }

  return {
    suggested: next,
    explanations: explanations.length > 0 ? explanations : ['No strong rewrite needed; kept sentence natural and clear.'],
  }
}

function tokenize(text: string): string[] {
  return text
    .trim()
    .split(/\s+/)
    .filter((token) => token.length > 0)
}

function computeDiff(originalText: string, suggestedText: string): { removedTokens: string[]; addedTokens: string[] } {
  const original = tokenize(originalText)
  const suggested = tokenize(suggestedText)

  const m = original.length
  const n = suggested.length
  const dp: number[][] = Array.from({ length: m + 1 }, () => Array.from({ length: n + 1 }, () => 0))

  for (let i = m - 1; i >= 0; i -= 1) {
    for (let j = n - 1; j >= 0; j -= 1) {
      if (original[i] === suggested[j]) {
        dp[i][j] = dp[i + 1][j + 1] + 1
      } else {
        dp[i][j] = Math.max(dp[i + 1][j], dp[i][j + 1])
      }
    }
  }

  const removedTokens: string[] = []
  const addedTokens: string[] = []

  let i = 0
  let j = 0

  while (i < m && j < n) {
    if (original[i] === suggested[j]) {
      i += 1
      j += 1
      continue
    }

    if (dp[i + 1][j] >= dp[i][j + 1]) {
      removedTokens.push(original[i])
      i += 1
    } else {
      addedTokens.push(suggested[j])
      j += 1
    }
  }

  while (i < m) {
    removedTokens.push(original[i])
    i += 1
  }

  while (j < n) {
    addedTokens.push(suggested[j])
    j += 1
  }

  return { removedTokens, addedTokens }
}

export function buildRevisionItems(utterances: TaskTranscriptUtterance[]): RevisionItem[] {
  return utterances.map((item) => {
    const suggestion = suggestSentence(item.text)
    const diff = computeDiff(item.text, suggestion.suggested)

    return {
      id: `${item.seq}-${item.start_time}`,
      seq: item.seq,
      speaker: (item.speaker || 'Speaker').replace('_', ' '),
      startTimeMs: item.start_time,
      endTimeMs: item.end_time,
      original: item.text,
      suggested: suggestion.suggested,
      removedTokens: diff.removedTokens,
      addedTokens: diff.addedTokens,
      explanations: suggestion.explanations,
    }
  })
}
