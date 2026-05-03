import type {
  RevisionItemResponse,
  RevisionResponse,
  SessionItem,
  TranscriptData,
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

function inferSessionStatus(item: SessionItem): SessionStatus {
  if (item.transcript?.status_name) {
    return normalizeStatus(item.transcript.status_name);
  }
  if (item.session.current_transcript_id) {
    return 'processing';
  }
  return 'pending';
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
    duration: item.transcript?.duration_sec ?? undefined,
    status: inferSessionStatus(item),
    type: entity.f_type === 2 ? 'text' : 'audio',
    createdAt: entity.created_at,
    audioUrl: item.asset?.asset_url ?? undefined,
  };
}

export function mapTranscript(data: TranscriptData): TranscriptItem[] {
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

export function applyTtsTimelineToRevision(
  revision: RevisionItem[],
  synthesis?: TtsSynthesisResponse | null,
): RevisionItem[] {
  if (!synthesis?.full_asset_url) return revision;

  const timelineByItemId = new Map(
    synthesis.items
      .filter((item) => item.start_time_ms != null && item.end_time_ms != null && item.end_time_ms > item.start_time_ms)
      .map((item) => [
        item.item_id,
        {
          startTime: item.start_time_ms! / 1000,
          endTime: item.end_time_ms! / 1000,
        },
      ])
  );

  if (timelineByItemId.size === 0) return revision;

  return revision.map((item) => {
    const timeline = timelineByItemId.get(item.id);
    return timeline ? { ...item, ...timeline } : item;
  });
}

export function fitRevisionTimelineToAudioDuration(
  revision: RevisionItem[],
  audioDurationSeconds: number,
): RevisionItem[] {
  if (revision.length === 0 || !Number.isFinite(audioDurationSeconds) || audioDurationSeconds <= 0) {
    return revision;
  }

  const timelineDuration = revision[revision.length - 1].endTime;
  const drift = audioDurationSeconds - timelineDuration;
  if (timelineDuration <= 0 || Math.abs(drift) < 0.25) {
    return revision;
  }

  const perItemDrift = drift / revision.length;
  return revision.map((item, index) => ({
    ...item,
    startTime: Math.max(0, item.startTime + perItemDrift * index),
    endTime: Math.max(0, item.endTime + perItemDrift * (index + 1)),
  }));
}
