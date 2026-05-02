import { useMemo } from 'react';
import type { Session } from '@/types';

export function useSessionFilter(sessions: Session[], searchQuery: string): Session[] {
  return useMemo(() => {
    if (!searchQuery.trim()) return sessions;
    const query = searchQuery.toLowerCase().trim();
    return sessions.filter(session =>
      session.title.toLowerCase().includes(query) ||
      session.description?.toLowerCase().includes(query) ||
      session.id.toLowerCase().includes(query)
    );
  }, [sessions, searchQuery]);
}
