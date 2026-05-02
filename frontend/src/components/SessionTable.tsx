import { useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { Search, RefreshCw, FileAudio, FileText } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { StatusBadge } from './StatusBadge';
import { useSessionFilter } from '@/hooks/useSessionFilter';
import { formatDuration, formatDate } from '@/utils/formatTime';
import type { Session } from '@/types';
import { useApp } from '@/context/AppContext';

interface SessionTableProps {
  sessions: Session[];
}

export function SessionTable({ sessions }: SessionTableProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [isRefreshing, setIsRefreshing] = useState(false);
  const { refreshSessions } = useApp();

  const filteredSessions = useSessionFilter(sessions, searchQuery);

  const handleRefresh = useCallback(async () => {
    setIsRefreshing(true);
    await refreshSessions();
    setIsRefreshing(false);
  }, [refreshSessions]);

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex items-center justify-between gap-4">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <Input
            placeholder="Search sessions..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-10 bg-white border-slate-200 focus:border-indigo-300 focus:ring-indigo-200 text-[13px] h-10"
          />
        </div>
        <button
          onClick={handleRefresh}
          className="p-2.5 rounded-lg border border-slate-200 bg-white text-slate-500 hover:text-slate-700 hover:border-slate-300 transition-all"
        >
          <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-sm">
        <table className="w-full">
          <thead>
            <tr className="border-b border-slate-100 bg-slate-50/50">
              <th className="text-left text-[10px] font-semibold text-slate-500 uppercase tracking-wider py-3 px-5">Session</th>
              <th className="text-left text-[10px] font-semibold text-slate-500 uppercase tracking-wider py-3 px-4 w-[100px]">Type</th>
              <th className="text-left text-[10px] font-semibold text-slate-500 uppercase tracking-wider py-3 px-4 w-[100px]">Duration</th>
              <th className="text-left text-[10px] font-semibold text-slate-500 uppercase tracking-wider py-3 px-4 w-[120px]">Status</th>
              <th className="text-left text-[10px] font-semibold text-slate-500 uppercase tracking-wider py-3 px-4 w-[100px]">Created</th>
              <th className="py-3 px-4 w-[60px]"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-50">
            {filteredSessions.map((session) => (
              <tr
                key={session.id}
                className="group hover:bg-slate-50/80 transition-colors duration-150 cursor-pointer"
              >
                <td className="py-3.5 px-5">
                  <Link to={`/session/${session.id}`} className="flex items-center gap-3">
                    <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${
                      session.type === 'audio' ? 'bg-violet-50 text-violet-500' : 'bg-sky-50 text-sky-500'
                    }`}>
                      {session.type === 'audio' ? <FileAudio className="w-4 h-4" /> : <FileText className="w-4 h-4" />}
                    </div>
                    <div className="min-w-0">
                      <p className="text-[13px] font-medium text-slate-800 truncate group-hover:text-indigo-600 transition-colors">{session.title}</p>
                      {session.description && (
                        <p className="text-[11px] text-slate-400 truncate">{session.description}</p>
                      )}
                    </div>
                  </Link>
                </td>
                <td className="py-3.5 px-4">
                  <Link to={`/session/${session.id}`}>
                    <span className={`text-[11px] font-medium px-2 py-0.5 rounded-md ${
                      session.type === 'audio'
                        ? 'bg-violet-50 text-violet-600'
                        : 'bg-sky-50 text-sky-600'
                    }`}>
                      {session.type === 'audio' ? 'Audio' : 'Script'}
                    </span>
                  </Link>
                </td>
                <td className="py-3.5 px-4 text-[13px] text-slate-500 tabular-nums">
                  <Link to={`/session/${session.id}`}>{formatDuration(session.duration)}</Link>
                </td>
                <td className="py-3.5 px-4">
                  <Link to={`/session/${session.id}`}><StatusBadge status={session.status} /></Link>
                </td>
                <td className="py-3.5 px-4 text-[12px] text-slate-500">
                  <Link to={`/session/${session.id}`}>{formatDate(session.createdAt)}</Link>
                </td>
                <td className="py-3.5 px-4">
                  <Link
                    to={`/session/${session.id}`}
                    className="p-1.5 rounded-md text-slate-300 hover:text-indigo-600 hover:bg-indigo-50 transition-all duration-150 block"
                  >
                    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 18l6-6-6-6"/></svg>
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {filteredSessions.length === 0 && (
          <div className="py-16 text-center">
            <p className="text-[14px] text-slate-400">No sessions found.</p>
          </div>
        )}
      </div>
    </div>
  );
}
