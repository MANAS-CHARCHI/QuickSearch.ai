import React from 'react';
import { Files, UploadCloud, MessageSquareCode, Activity, Settings, Sun, Moon, ShieldCheck, LogOut, WifiOff, RefreshCw } from 'lucide-react';
import { usePwa } from '../pwa/usePwa';
import { PwaInstallButton } from './PwaInstallButton';
import { TabType, UserProfile } from '../types';

interface NavigationProps {
  currentTab: TabType;
  onSelectTab: (tab: TabType) => void;
  systemStatus: {
    postgres: string;
    pgvector: string;
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
  const { isOffline, hasUpdate, updateApp } = usePwa();
  const tabs: { id: TabType; label: string; icon: React.ElementType }[] = [
    { id: 'chat', label: 'Assistant', icon: MessageSquareCode },
    { id: 'vault', label: 'Vault', icon: Files },
    { id: 'upload', label: 'Upload', icon: UploadCloud },
    { id: 'activity', label: 'Activity', icon: Activity },
    { id: 'settings', label: 'Settings', icon: Settings },
  ];

  return (
    <>
      {/* Top Vault City Navbar (Fixed) */}
      <header className="fixed top-0 left-0 right-0 z-40 h-14 bg-[#FFFCF9]/90 dark:bg-[#140E0A]/90 backdrop-blur-md border-b border-orange-200/50 dark:border-[#2D2118] transition-colors">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between">
          {/* Vault City Brand (Val Town Bold Lowercase Style) */}
          <div className="flex items-center space-x-2.5">
            <img src="/favicon.svg" alt="Vault City" className="w-5 h-5 rounded-md shrink-0" />
            <span className="font-extrabold text-base tracking-tight text-stone-950 dark:text-white font-sans">
              vault city
            </span>
            <span className="text-[10px] text-stone-400 font-mono">/</span>
            <span className="text-[11px] text-stone-600 dark:text-stone-300 font-mono font-medium truncate max-w-[120px] sm:max-w-[200px]">
              {currentUser?.name || (currentUser?.email ? currentUser.email.split('@')[0] : 'user')}
            </span>
          </div>

          {/* Desktop Navigation Tabs (No numbers) */}
          <nav className="hidden md:flex items-center space-x-1 bg-orange-100/50 dark:bg-[#1C1510] p-0.5 rounded-lg border border-orange-200/60 dark:border-[#2D2118]">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              const isActive = currentTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => onSelectTab(tab.id)}
                  className={`flex items-center space-x-1.5 px-3 py-1 rounded-md text-xs font-mono transition-all duration-150 cursor-pointer ${
                    isActive
                      ? 'bg-white dark:bg-[#281D16] text-stone-950 dark:text-[#FAF5F0] shadow-sm font-semibold border border-orange-200/60 dark:border-[#3E2C1F]'
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
            {/* Offline Indicator */}
            {isOffline && (
              <div className="flex items-center space-x-1 px-2 py-0.5 rounded-md text-[10px] font-mono text-amber-700 dark:text-amber-300 bg-amber-500/10 border border-amber-500/30">
                <WifiOff className="w-3 h-3 text-amber-500" />
                <span>Offline</span>
              </div>
            )}

            {/* PWA Update Banner */}
            {hasUpdate && (
              <button
                type="button"
                onClick={updateApp}
                title="A new version of Vault City is available. Click to reload."
                className="flex items-center space-x-1 px-2 py-1 rounded-md text-xs font-mono bg-orange-500 hover:bg-orange-600 text-white font-semibold shadow-xs transition-colors cursor-pointer"
              >
                <RefreshCw className="w-3 h-3 animate-spin" />
                <span>Update</span>
              </button>
            )}

            {/* PWA Download / Install Button (Browser Screen Only) */}
            <PwaInstallButton variant="nav" className="hidden sm:flex" />

            <div className="hidden sm:flex items-center space-x-1.5 px-2.5 py-1 rounded-md text-xs font-sans text-stone-500 dark:text-stone-400 bg-orange-50/60 dark:bg-[#1C1510] border border-orange-200/60 dark:border-[#2D2118]">
              <ShieldCheck className="w-3.5 h-3.5 text-stone-500 dark:text-stone-400" />
              <span>Encrypted</span>
            </div>

            {/* Theme Toggle */}
            <button
              onClick={onToggleTheme}
              title={isDark ? 'Switch to Day (Light)' : 'Switch to Night (Dark)'}
              className="p-1.5 rounded-md bg-orange-50/60 dark:bg-[#1C1510] border border-orange-200/60 dark:border-[#2D2118] text-stone-600 dark:text-stone-300 hover:text-stone-900 dark:hover:text-white transition-all cursor-pointer font-mono"
            >
              {isDark ? <Sun className="w-3.5 h-3.5 text-amber-400" /> : <Moon className="w-3.5 h-3.5" />}
            </button>

            {/* Sign Out Button */}
            {onLogout && (
              <button
                onClick={onLogout}
                title="Sign Out"
                className="flex items-center space-x-1 px-2.5 py-1 rounded-md text-xs font-mono text-stone-500 hover:text-stone-900 dark:text-stone-400 dark:hover:text-white bg-orange-50/60 dark:bg-[#1C1510] border border-orange-200/60 dark:border-[#2D2118] transition-colors cursor-pointer"
              >
                <LogOut className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">Sign Out</span>
              </button>
            )}
          </div>
        </div>
      </header>

      {/* Mobile Bottom Navigation Bar (Standard Mobile Type) */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 z-40 bg-[#FFFCF9]/95 dark:bg-[#140E0A]/95 backdrop-blur-xl border-t border-orange-200/80 dark:border-[#2D2118] shadow-lg pb-[env(safe-area-inset-bottom,0px)]">
        <div className="grid grid-cols-5 h-14 w-full max-w-md mx-auto">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = currentTab === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => onSelectTab(tab.id)}
                className={`flex flex-col items-center justify-center h-full w-full py-1 px-0.5 transition-colors cursor-pointer select-none relative group ${
                  isActive
                    ? 'text-orange-600 dark:text-orange-400 font-semibold'
                    : 'text-stone-400 dark:text-stone-500 hover:text-stone-700 dark:hover:text-stone-300 font-medium'
                }`}
              >
                {isActive && (
                  <span className="absolute top-0 inset-x-2 sm:inset-x-3 h-0.5 bg-orange-500 dark:bg-orange-400 rounded-full" />
                )}
                <Icon
                  className={`w-4 h-4 sm:w-5 sm:h-5 transition-transform ${
                    isActive ? 'scale-110 text-orange-600 dark:text-orange-400' : 'group-hover:scale-105'
                  }`}
                />
                <span className="text-[10px] tracking-tight font-sans truncate max-w-full mt-1 leading-none">
                  {tab.label}
                </span>
              </button>
            );
          })}
        </div>
      </nav>
    </>
  );
};
