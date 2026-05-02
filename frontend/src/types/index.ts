export type SessionStatus = 'pending' | 'processing' | 'completed' | 'failed';
export type SessionType = 'audio' | 'text';
export type Difficulty = 'Beginner' | 'Intermediate' | 'Advanced';

export interface TranscriptItem {
  id: string;
  speaker: string;
  startTime: number;
  endTime: number;
  text: string;
}

export interface RevisionItem {
  id: string;
  speaker: string;
  startTime: number;
  endTime: number;
  cue: string;
  content: string;
  fullText: string;
  score: number;
  originalText: string;
}

export interface SpeakerMapping {
  speaker: string;
  voice: string;
}

export interface Session {
  id: string;
  title: string;
  description?: string;
  duration?: number;
  status: SessionStatus;
  type: SessionType;
  createdAt: string;
  audioUrl?: string;
  transcript?: TranscriptItem[];
  revision?: RevisionItem[];
  speakerMappings?: SpeakerMapping[];
  synthesizedAudioUrl?: string;
  userPrompt?: string;
}

export interface AppState {
  sessions: Session[];
  currentSession: Session | null;
  loading: boolean;
  error: string | null;
}

export type AppAction =
  | { type: 'SET_SESSIONS'; payload: Session[] }
  | { type: 'SET_CURRENT_SESSION'; payload: Session | null }
  | { type: 'ADD_SESSION'; payload: Session }
  | { type: 'UPDATE_SESSION'; payload: Session }
  | { type: 'DELETE_SESSION'; payload: string }
  | { type: 'UPDATE_REVISION'; payload: { sessionId: string; revision: RevisionItem[] } }
  | { type: 'SET_LOADING'; payload: boolean }
  | { type: 'SET_ERROR'; payload: string | null };

export interface CueParseResult {
  cue: string;
  content: string;
  fullText: string;
}
