import { Link } from 'react-router-dom';
import { Plus, TrendingUp, CheckCircle2, Clock, AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { SessionTable } from '@/components/SessionTable';
import { useApp } from '@/context/AppContext';

export function Dashboard() {
  const { state } = useApp();

  const stats = [
    { label: 'Total Sessions', value: state.sessions.length, icon: TrendingUp, color: 'text-indigo-600', bg: 'bg-indigo-50' },
    { label: 'Completed', value: state.sessions.filter(s => s.status === 'completed').length, icon: CheckCircle2, color: 'text-emerald-600', bg: 'bg-emerald-50' },
    { label: 'Processing', value: state.sessions.filter(s => s.status === 'processing' || s.status === 'pending').length, icon: Clock, color: 'text-amber-600', bg: 'bg-amber-50' },
    { label: 'Failed', value: state.sessions.filter(s => s.status === 'failed').length, icon: AlertCircle, color: 'text-red-500', bg: 'bg-red-50' },
  ];

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-[22px] font-bold text-slate-900 tracking-tight">Dashboard</h1>
          <p className="text-[13px] text-slate-500 mt-0.5">Manage your sessions and track processing status</p>
        </div>
        <Link to="/create">
          <Button className="bg-indigo-500 hover:bg-indigo-600 text-white h-9 px-4 text-[12px] font-semibold gap-1.5 shadow-sm shadow-indigo-200">
            <Plus className="w-3.5 h-3.5" />
            New Session
          </Button>
        </Link>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4">
        {stats.map(stat => (
          <div key={stat.label} className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
            <div className="flex items-center gap-2.5">
              <div className={`w-9 h-9 rounded-lg ${stat.bg} flex items-center justify-center`}>
                <stat.icon className={`w-4.5 h-4.5 ${stat.color}`} />
              </div>
              <div>
                <p className="text-[20px] font-bold text-slate-800 leading-tight">{stat.value}</p>
                <p className="text-[11px] text-slate-500">{stat.label}</p>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Sessions Table */}
      {state.error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-[13px] text-red-700">
          {state.error}
        </div>
      )}
      <SessionTable sessions={state.sessions} />
    </div>
  );
}
