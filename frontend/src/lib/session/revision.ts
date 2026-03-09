import type { TaskTranscriptUtterance } from '@/types/api'

export interface RevisionItem {
  id: string
  seq: number
  speaker: string
  startTimeMs: number
  endTimeMs: number
  original: string
  suggested: string
  cue: string
  score: number
  issues: string[]
  explanations: string[]
}

export interface ExpressionCue {
  emoji: string
  emotion: string
  tone: string
  scene: string
}

function normalizeCueText(value: string): string {
  return value.trim().replace(/^\[/, '').replace(/\]$/, '').replace(/\s+/g, ' ')
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

function normalizeSpeaker(speaker: string | null | undefined): string {
  const normalized = (speaker || 'Speaker').replace(/_/g, ' ').trim()

  if (/^\d+$/.test(normalized)) {
    return `User ${normalized}`
  }

  return normalized
    .split(/\s+/)
    .map((part) => `${part[0]?.toUpperCase() ?? ''}${part.slice(1)}`)
    .join(' ')
}

function inferIssues(explanations: string[]): string[] {
  const issues = new Set<string>()

  explanations.forEach((line) => {
    if (/past tense|adjective form/i.test(line)) {
      issues.add('语法错误')
    }

    if (/natural phrasing|expression clarity/i.test(line)) {
      issues.add('不够自然')
    }

    if (/non-standard word/i.test(line)) {
      issues.add('用词错误')
    }

    if (/Capitalized sentence start/i.test(line)) {
      issues.add('大小写问题')
    }

    if (/ending punctuation/i.test(line)) {
      issues.add('标点问题')
    }
  })

  if (issues.size === 0) {
    issues.add('表达基本自然')
  }

  return Array.from(issues)
}

export function scoreRevisionIssues(issues: string[]): number {
  let score = 96

  issues.forEach((issue) => {
    if (issue === '语法错误') {
      score -= 24
    } else if (issue === '用词错误') {
      score -= 18
    } else if (issue === '不够自然') {
      score -= 14
    } else if (issue === '标点问题') {
      score -= 8
    } else if (issue === '大小写问题') {
      score -= 6
    }
  })

  if (issues.includes('表达基本自然')) {
    score = Math.max(score, 92)
  }

  return Math.max(35, Math.min(score, 99))
}

function suggestSentence(original: string): { suggested: string; explanations: string[]; issues: string[] } {
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
    issues: inferIssues(explanations),
  }
}

export function inferExpressionCue(text: string): ExpressionCue {
  const normalized = text.trim().toLowerCase()
  const hasQuestion = /[?？]/.test(text)
  const hasExcitement = /[!！]/.test(text)

  if (!normalized) {
    return {
      emoji: '🙂',
      emotion: '自然的',
      tone: '平稳的',
      scene: '日常对话',
    }
  }

  if (/\b(thank|thanks|appreciate)\b/.test(normalized)) {
    return {
      emoji: '🙏',
      emotion: '真诚的',
      tone: '礼貌的',
      scene: '表达感谢',
    }
  }

  if (/\b(sorry|apologize|excuse me)\b/.test(normalized)) {
    return {
      emoji: '😅',
      emotion: '抱歉的',
      tone: '柔和的',
      scene: '修复关系',
    }
  }

  if (/\b(hello|hi|good morning|good afternoon|good evening)\b/.test(normalized)) {
    return {
      emoji: '🙂',
      emotion: '友好的',
      tone: '轻松的',
      scene: '打招呼',
    }
  }

  if (/\b(weekend|friends?|park|beach|trip|travel|party|holiday|vacation)\b/.test(normalized)) {
    return {
      emoji: '😄',
      emotion: '有点兴奋的',
      tone: '肯定的',
      scene: '分享经历',
    }
  }

  if (hasQuestion) {
    return {
      emoji: '🤔',
      emotion: '关心的',
      tone: '好奇的',
      scene: '日常对话',
    }
  }

  if (/\b(think|believe|guess|probably|maybe)\b/.test(normalized)) {
    return {
      emoji: '🧐',
      emotion: '思考中的',
      tone: '解释性的',
      scene: '表达观点',
    }
  }

  if (hasExcitement) {
    return {
      emoji: '😄',
      emotion: '积极的',
      tone: '强调的',
      scene: '情绪表达',
    }
  }

  return {
    emoji: '🙂',
    emotion: '自然的',
    tone: '平稳的',
    scene: '日常对话',
  }
}

export function formatExpressionCue(cue: ExpressionCue): string {
  return `[用${cue.emotion}、${cue.tone}的语气读这句，带出${cue.scene}的感觉。]`
}

export function formatCueText(cue: string): string {
  const normalized = normalizeCueText(cue)
  if (!normalized) {
    return ''
  }
  return `[${normalized}]`
}

export function buildRevisionItems(utterances: TaskTranscriptUtterance[]): RevisionItem[] {
  return utterances.map((item) => {
    const suggestion = suggestSentence(item.text)
    const cue = formatExpressionCue(inferExpressionCue(suggestion.suggested))

    return {
      id: `${item.seq}-${item.start_time}`,
      seq: item.seq,
      speaker: normalizeSpeaker(item.speaker),
      startTimeMs: item.start_time,
      endTimeMs: item.end_time,
      original: item.text,
      suggested: suggestion.suggested,
      cue,
      score: scoreRevisionIssues(suggestion.issues),
      issues: suggestion.issues,
      explanations: suggestion.explanations,
    }
  })
}
