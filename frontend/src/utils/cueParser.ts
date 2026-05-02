import type { CueParseResult } from '@/types';

/**
 * Parse a text string that may contain CUE markers like [some cue] content
 * Returns the cue, the content without cue, and the full text
 */
export function parseCueText(text: string): CueParseResult {
  const cueRegex = /^\s*\[([^\]]+)\]\s*(.*)$/s;
  const match = text.match(cueRegex);

  if (match) {
    return {
      cue: match[1].trim(),
      content: match[2].trim(),
      fullText: text.trim(),
    };
  }

  return {
    cue: '',
    content: text.trim(),
    fullText: text.trim(),
  };
}

/**
 * Check if text contains a CUE marker
 */
export function hasCue(text: string): boolean {
  return /^\s*\[[^\]]+\]/.test(text);
}

/**
 * Extract CUE part from text for display
 */
export function extractCue(text: string): string {
  const result = parseCueText(text);
  return result.cue;
}

/**
 * Extract content part (without CUE) from text
 */
export function extractContent(text: string): string {
  const result = parseCueText(text);
  return result.content;
}

/**
 * Render text with CUE highlighted - splits into cue and content segments
 */
export function renderCueHtml(text: string): { cue: string | null; content: string } {
  const result = parseCueText(text);
  return {
    cue: result.cue || null,
    content: result.content,
  };
}
