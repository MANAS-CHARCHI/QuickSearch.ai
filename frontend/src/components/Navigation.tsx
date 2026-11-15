import React from 'react';
import { Files, UploadCloud, MessageSquareCode, Activity, Settings, Sun, Moon, ShieldCheck, LogOut } from 'lucide-react';
import { TabType, UserProfile } from '../types';

interface NavigationProps {
  currentTab: TabType;
  onSelectTab: (tab: TabType) => void;
  systemStatus: {
    postgres: string;
    chromadb: string;
  };
  isDark: boolean;
  onToggleTheme: () => void;
  currentUser?: UserProfile | null;
  onLogout?: () => void;
}

export const Navigation: React.FC<NavigationProps> = ({
  currentTab,
  onSelectTab,
  isDark,
  onToggleTheme,
  currentUser,
  onLogout,
}) => {
  const tabs: { id: TabType; label: string; icon: React.ElementType }[] = [
    { id: 'chat', label: 'Assistant', icon: MessageSquareCode },
    { id: 'vault', label: 'Vault', icon: Files },
    { id: 'upload', label: 'Upload', icon: UploadCloud },
    { id: 'activity', label: 'Activity', icon: Activity },
    { id: 'settings', label: 'Settings', icon: Settings },
  ];

  return (
    <>
      {/* Top Vault City Navbar */}
      <header className="sticky top-0 z-40 bg-[#FAFAF9]/85 dark:bg-[#090A0D]/85 backdrop-blur-md border-b border-stone-200/90 dark:border-stone-800/90 transition-colors">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between">
          {/* Vault City Brand (Val Town Bold Lowercase Style) */}
          <div className="flex items-center space-x-2">
            <span className="font-extrabold text-base tracking-tight text-stone-950 dark:text-white font-sans">
              vault city
            </span>
            <span className="text-[10px] text-stone-400 font-mono">/</span>
            <span className="text-[11px] text-stone-500 dark:text-stone-400 font-mono">personal</span>
            <span className="hidden sm:inline-block text-[9px] px-1.5 py-0.2 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 rounded font-mono border border-emerald-500/20">
              v1.0
            </span>
          </div>

          {/* Desktop Navigation Tabs (No numbers) */}
          <nav className="hidden md:flex items-center space-x-1 bg-stone-200/50 dark:bg-stone-900/80 p-0.5 rounded-lg border border-stone-200 dark:border-stone-800">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              const isActive = currentTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => onSelectTab(tab.id)}
                  className={`flex items-center space-x-1.5 px-3 py-1 rounded-md text-xs font-mono transition-all ${
                    isActive
                      ? 'bg-white dark:bg-stone-800 text-stone-950 dark:text-white shadow-sm font-semibold border border-stone-200/60 dark:border-stone-700/60'
                      : 'text-stone-500 dark:text-stone-400 hover:text-stone-900 dark:hover:text-stone-200'
                  }`}
                >
                  <Icon className="w-3.5 h-3.5" />
                  <span>{tab.label}</span>
                </button>
              );
            })}
          </nav>

          {/* Right Status & Controls (Clean, Non-AI) */}
          <div className="flex items-center space-x-2">
            <div className="hidden sm:flex items-center space-x-1.5 px-2.5 py-1 rounded-md text-xs font-sans text-stone-500 dark:text-stone-400 bg-stone-100 dark:bg-stone-900 border border-stone-200 dark:border-stone-800">
              <ShieldCheck className="w-3.5 h-3.5 text-stone-500 dark:text-stone-400" />
              <span>Encrypted</span>
            </div>

            {/* Theme Toggle */}
            <button
              onClick={onToggleTheme}
              title={isDark ? 'Switch to Day (Light)' : 'Switch to Night (Dark)'}
              className="p-1.5 rounded-md bg-stone-100 dark:bg-stone-900 border border-stone-200 dark:border-stone-800 text-stone-600 dark:text-stone-300 hover:text-stone-900 dark:hover:text-white transition-all cursor-pointer font-mono"
            >
              {isDark ? <Sun className="w-3.5 h-3.5 text-amber-400" /> : <Moon className="w-3.5 h-3.5" />}
            </button>

            {/* Sign Out Button */}
            {onLogout && (
              <button
                onClick={onLogout}
                title="Sign Out"
                className="flex items-center space-x-1 px-2.5 py-1 rounded-md text-xs font-mono text-stone-500 hover:text-stone-900 dark:text-stone-400 dark:hover:text-white bg-stone-100 dark:bg-stone-900 border border-stone-200 dark:border-stone-800 transition-colors cursor-pointer"
              >
                <LogOut className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">Sign Out</span>
              </button>
            )}
          </div>
        </div>
      </header>

      {/* Mobile Floating Bottom Dock (Val Town style) */}
      <nav className="md:hidden fixed bottom-3 left-4 right-4 z-40 bg-white/95 dark:bg-stone-900/95 backdrop-blur-xl border border-stone-200 dark:border-stone-800 rounded-xl px-2 py-1.5 flex items-center justify-around shadow-xl">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = currentTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => onSelectTab(tab.id)}
              className={`flex flex-col items-center justify-center py-1 px-3 rounded-lg text-[10px] font-mono transition-all ${
                isActive
                  ? 'text-indigo-600 dark:text-indigo-400 font-bold bg-indigo-50/80 dark:bg-indigo-950/40'
                  : 'text-stone-400 hover:text-stone-900 dark:hover:text-stone-200'
              }`}
            >
              <Icon className="w-4 h-4 mb-0.5" />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </nav>
    </>
  );
};
