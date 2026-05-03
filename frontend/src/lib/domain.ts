import type {
  RevisionItemResponse,
  RevisionResponse,
  SessionItem,
  TaskTranscriptData,
  TtsSettingsResponse,
  TtsSynthesisResponse,
} from '@/types/api';
import type { RevisionItem, Session, SessionStatus, TranscriptItem } from '@/types';
import { parseCueText } from '@/utils/cueParser';

function normalizeStatus(statusName?: string | null): SessionStatus {
  const status = statusName?.toLowerCase();
  if (status === 'completed' || status === 'processing' || status === 'failed' || status === 'pending') {
    return status;
  }
  return status ? 'processing' : 'completed';
}

function normalizeSeconds(value: number): number {
  return value > 300 ? value / 1000 : value;
}

export function mapSessionItem(item: SessionItem): Session {
  const entity = item.session;
  return {
    id: entity.session_id,
    title: entity.title,
    description: entity.description ?? item.asset?.filename ?? undefined,
    duration: item.task?.duration_sec ?? undefined,
    status: normalizeStatus(item.task?.status_name),
    type: entity.f_type === 2 ? 'text' : 'audio',
    createdAt: entity.created_at,
    audioUrl: item.asset?.asset_url ?? item.task?.audio_url ?? undefined,
  };
}

export function mapTranscript(data: TaskTranscriptData): TranscriptItem[] {
  return data.utterances.map((utterance) => ({
    id: String(utterance.seq),
    speaker: utterance.speaker || `user-${(utterance.seq % 2) + 1}`,
    startTime: normalizeSeconds(utterance.start_time),
    endTime: normalizeSeconds(utterance.end_time),
    text: utterance.text,
  }));
}

function mapRevisionItem(item: RevisionItemResponse): RevisionItem {
  const fullText = item.draft_text || item.suggested_text || item.original_text;
  const parsed = parseCueText(fullText);
  const issueTags = item.issue_tags
    .split(/[,，]/)
    .map((tag) => tag.trim())
    .filter(Boolean);

  return {
    id: item.item_id,
    speaker: item.speaker || 'speaker',
    startTime: normalizeSeconds(item.start_time),
    endTime: normalizeSeconds(item.end_time),
    cue: parsed.cue,
    content: parsed.content,
    fullText,
    score: item.score,
    issueTags,
    explanations: item.explanations,
    originalText: item.original_text,
  };
}

export function mapRevision(data: RevisionResponse): RevisionItem[] {
  return data.items.map(mapRevisionItem);
}

export function applyTtsSettings(session: Session, settings?: TtsSettingsResponse | null): Session {
  if (!settings) return session;
  return {
    ...session,
    speakerMappings: settings.speaker_mappings.map((mapping) => ({
      speaker: mapping.conversation_speaker,
      voice: mapping.provider_speaker_id,
    })),
  };
}

export function applyTtsSynthesis(session: Session, synthesis?: TtsSynthesisResponse | null): Session {
  if (!synthesis?.full_asset_url) return session;
  return {
    ...session,
    synthesizedAudioUrl: synthesis.full_asset_url,
    duration: synthesis.full_duration_ms ? synthesis.full_duration_ms / 1000 : session.duration,
  };
}
