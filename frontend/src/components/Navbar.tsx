import { Link, useLocation } from 'react-router-dom';
import { cn } from '@/lib/utils';

export function Navbar() {
  const location = useLocation();
  const isDashboard = location.pathname === '/';

  return (
    <nav className="fixed top-0 left-0 right-0 h-16 bg-white border-b border-[#E7E5E4] z-50">
      <div className="max-w-[1200px] mx-auto h-full flex items-center justify-between px-6">
        {/* Brand */}
        <div className="flex flex-col">
          <span className="text-[15px] font-semibold text-[#1C1917] tracking-tight">LSL</span>
          <span className="text-[11px] text-[#A8A29E] leading-tight">Listening and speaking training workspace</span>
        </div>

        {/* Nav Links */}
        <div className="flex items-center gap-1">
          <Link
            to="/"
            className={cn(
              'px-3 py-1.5 rounded-md text-[15px] transition-colors duration-150',
              isDashboard
                ? 'text-[#1C1917] font-medium bg-[#F5F5F4]'
                : 'text-[#78716C] hover:text-[#1C1917] hover:bg-[#F5F5F4]'
            )}
          >
            Dashboard
          </Link>
          <Link
            to="/create"
            className={cn(
              'px-3 py-1.5 rounded-md text-[15px] transition-colors duration-150',
              location.pathname === '/create'
                ? 'text-[#1C1917] font-medium bg-[#F5F5F4]'
                : 'text-[#78716C] hover:text-[#1C1917] hover:bg-[#F5F5F4]'
            )}
          >
            Create Session
          </Link>
        </div>
      </div>
    </nav>
  );
}
