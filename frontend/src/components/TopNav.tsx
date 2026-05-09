import { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Languages, LayoutDashboard, LogIn, LogOut, Menu, PlusCircle, UserCircle, X } from 'lucide-react';
import { BrandWordmark } from '@/components/BrandLogo';
import { useAuth } from '@/context/AuthContext';
import { cn } from '@/lib/utils';
import { useI18n } from '@/i18n';

const navItems = [
  { icon: LayoutDashboard, labelKey: 'common.dashboard' as const, path: '/dashboard' },
  { icon: PlusCircle, labelKey: 'common.newSession' as const, path: '/create' },
];

export function TopNav() {
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);
  const { language, setLanguage, t } = useI18n();
  const { user, loading: authLoading, login, logout } = useAuth();

  const userLabel = user?.display_name || user?.username || user?.email || t('common.user');
  const visibleNavItems = user ? navItems : [];

  const handleLogout = async () => {
    await logout();
    setMobileOpen(false);
  };

  return (
    <header className="sticky top-0 z-50 bg-white/80 backdrop-blur-md border-b border-slate-200">
      <div className="max-w-[1100px] mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-14">
          {/* Logo */}
          <Link to="/" className="group" aria-label="LSL">
            <BrandWordmark
              markClassName="transition-transform duration-150 group-hover:-translate-y-0.5"
              textClassName="text-slate-800"
            />
          </Link>

          {/* Desktop Nav */}
          <nav className="hidden sm:flex items-center gap-1">
            {visibleNavItems.map(item => {
              const isActive = location.pathname === item.path;
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className={cn(
                    'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[13px] font-medium transition-all duration-150',
                    isActive
                      ? 'bg-indigo-50 text-indigo-600'
                      : 'text-slate-500 hover:text-slate-700 hover:bg-slate-50'
                  )}
                >
                  <item.icon className="w-4 h-4" />
                  {t(item.labelKey)}
                </Link>
              );
            })}
          </nav>

          <div className="hidden sm:flex items-center gap-2">
            <div className="flex items-center gap-1 rounded-lg border border-slate-200 bg-white p-1">
              <Languages className="ml-1.5 h-3.5 w-3.5 text-slate-400" />
              {(['en', 'zh-CN'] as const).map((item) => (
                <button
                  key={item}
                  type="button"
                  onClick={() => setLanguage(item)}
                  className={cn(
                    'h-7 rounded-md px-2 text-[11px] font-semibold transition-colors',
                    language === item
                      ? 'bg-indigo-50 text-indigo-700'
                      : 'text-slate-500 hover:text-slate-700'
                  )}
                >
                  {item === 'en' ? t('app.language.english') : t('app.language.chinese')}
                </button>
              ))}
            </div>
            {user ? (
              <>
                <div className="flex items-center gap-2 min-w-0 max-w-[220px]">
                  {user.avatar_url ? (
                    <img
                      src={user.avatar_url}
                      alt=""
                      className="w-7 h-7 rounded-full border border-slate-200 object-cover"
                    />
                  ) : (
                    <UserCircle className="w-7 h-7 text-slate-400" />
                  )}
                  <span className="text-[12px] font-medium text-slate-600 truncate">{userLabel}</span>
                </div>
                <button
                  type="button"
                  onClick={handleLogout}
                  disabled={authLoading}
                  className="inline-flex items-center justify-center w-8 h-8 rounded-lg text-slate-500 hover:bg-slate-100 hover:text-slate-700 disabled:opacity-50 transition-colors"
                  title={t('common.logout')}
                >
                  <LogOut className="w-4 h-4" />
                </button>
              </>
            ) : (
              <button
                type="button"
                onClick={login}
                disabled={authLoading}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[13px] font-medium text-white bg-indigo-500 hover:bg-indigo-600 disabled:opacity-50 transition-colors"
              >
                <LogIn className="w-4 h-4" />
                {t('common.login')}
              </button>
            )}
          </div>

          {/* Mobile menu button */}
          <button
            onClick={() => setMobileOpen(!mobileOpen)}
            className="sm:hidden p-2 rounded-lg text-slate-500 hover:bg-slate-100 transition-colors"
          >
            {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
        </div>
      </div>

      {/* Mobile Nav */}
      {mobileOpen && (
        <div className="sm:hidden border-t border-slate-100 bg-white px-4 py-2">
          <nav className="space-y-1">
            {visibleNavItems.map(item => {
              const isActive = location.pathname === item.path;
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  onClick={() => setMobileOpen(false)}
                  className={cn(
                    'flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-[14px] font-medium transition-all',
                    isActive
                      ? 'bg-indigo-50 text-indigo-600'
                      : 'text-slate-600 hover:bg-slate-50'
                  )}
                >
                  <item.icon className="w-4.5 h-4.5" />
                  {t(item.labelKey)}
                </Link>
              );
            })}
            <div className="flex items-center gap-1 px-3 py-2">
              <Languages className="h-3.5 w-3.5 text-slate-400" />
              {(['en', 'zh-CN'] as const).map((item) => (
                <button
                  key={item}
                  type="button"
                  onClick={() => {
                    setLanguage(item);
                    setMobileOpen(false);
                  }}
                  className={cn(
                    'h-7 rounded-md px-2 text-[11px] font-semibold transition-colors',
                    language === item
                      ? 'bg-indigo-50 text-indigo-700'
                      : 'text-slate-500 hover:text-slate-700'
                  )}
                >
                  {item === 'en' ? t('app.language.english') : t('app.language.chinese')}
                </button>
              ))}
            </div>
            <div className="border-t border-slate-100 mt-2 pt-2">
              {user ? (
                <div className="flex items-center justify-between gap-3 px-3 py-2">
                  <div className="flex items-center gap-2 min-w-0">
                    {user.avatar_url ? (
                      <img
                        src={user.avatar_url}
                        alt=""
                        className="w-7 h-7 rounded-full border border-slate-200 object-cover"
                      />
                    ) : (
                      <UserCircle className="w-7 h-7 text-slate-400" />
                    )}
                    <span className="text-[13px] font-medium text-slate-600 truncate">{userLabel}</span>
                  </div>
                  <button
                    type="button"
                    onClick={handleLogout}
                    disabled={authLoading}
                    className="inline-flex items-center justify-center w-8 h-8 rounded-lg text-slate-500 hover:bg-slate-100 disabled:opacity-50"
                    title={t('common.logout')}
                  >
                    <LogOut className="w-4 h-4" />
                  </button>
                </div>
              ) : (
                <button
                  type="button"
                  onClick={() => {
                    setMobileOpen(false);
                    login();
                  }}
                  disabled={authLoading}
                  className="flex items-center gap-2.5 w-full px-3 py-2.5 rounded-lg text-[14px] font-medium text-indigo-600 hover:bg-indigo-50 disabled:opacity-50"
                >
                  <LogIn className="w-4 h-4" />
                  {t('common.login')}
                </button>
              )}
            </div>
          </nav>
        </div>
      )}
    </header>
  );
}
