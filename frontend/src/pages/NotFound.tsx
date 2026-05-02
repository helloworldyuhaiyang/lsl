import { Link } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { Button } from '@/components/ui/button';

export function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center py-24">
      <div className="w-16 h-16 rounded-2xl bg-slate-100 flex items-center justify-center mb-5">
        <span className="text-[24px] font-bold text-slate-400">?</span>
      </div>
      <h1 className="text-[20px] font-bold text-slate-800 mb-2">Page not found</h1>
      <p className="text-[13px] text-slate-500 mb-6">The page you're looking for doesn't exist.</p>
      <Link to="/">
        <Button className="bg-indigo-500 hover:bg-indigo-600 text-white h-9 px-4 text-[12px] font-semibold gap-1.5">
          <ArrowLeft className="w-3.5 h-3.5" />
          Back to Dashboard
        </Button>
      </Link>
    </div>
  );
}
