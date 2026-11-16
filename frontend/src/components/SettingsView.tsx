import React, { useState } from "react";
import {
  User,
  Check,
  Database,
  Cpu,
  Lock,
  Download,
  Trash2,
  KeyRound,
  Terminal,
} from "lucide-react";
import { UserProfile } from "../types";

interface SettingsViewProps {
  currentUser?: UserProfile | null;
  onUpdateFullName?: (newName: string) => void;
  onLogout?: () => void;
}

export const SettingsView: React.FC<SettingsViewProps> = ({
  currentUser,
  onUpdateFullName,
  onLogout,
}) => {
  const [fullName, setFullName] = useState(
    currentUser?.fullName || currentUser?.name || ""
  );
  const [saved, setSaved] = useState(false);

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    if (onUpdateFullName) {
      onUpdateFullName(fullName.trim());
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    }
  };

  return (
    <div className="max-w-2xl mx-auto space-y-3 font-mono">
      <div className="pb-1.5 border-b border-stone-200 dark:border-stone-800">
        <h2 className="text-xs font-semibold text-stone-900 dark:text-white flex items-center">
          <Terminal className="w-3.5 h-3.5 mr-1.5 text-stone-500" />
          vault/config
        </h2>
        <p className="text-[10px] text-stone-500 dark:text-stone-400">
          infrastructure limits, credentials, and compliance parameters
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
        {/* S3 Storage Quota */}
        <div className="bg-white dark:bg-[#1C1510] border border-orange-200/80 dark:border-[#2D2118] rounded-xl p-3 space-y-2 shadow-val">
          <div className="flex items-center justify-between text-xs">
            <span className="flex items-center font-medium text-stone-800 dark:text-stone-200">
              <Database className="w-3.5 h-3.5 text-stone-400 mr-1.5" /> s3
              storage
            </span>
            <span className="text-[10px] text-stone-500">3.5 MB / 500 MB</span>
          </div>
          <div className="w-full bg-orange-100/50 dark:bg-[#251A12] rounded-full h-1 overflow-hidden">
            <div className="bg-emerald-500 h-1 rounded-full w-[2%]" />
          </div>
          <p className="text-[9px] text-stone-400">
            AWS SSE-KMS per-user prefix isolation
          </p>
        </div>

        {/* AI Token Budget */}
        <div className="bg-white dark:bg-[#1C1510] border border-orange-200/80 dark:border-[#2D2118] rounded-xl p-3 space-y-2 shadow-val">
          <div className="flex items-center justify-between text-xs">
            <span className="flex items-center font-medium text-stone-800 dark:text-stone-200">
              <Cpu className="w-3.5 h-3.5 text-stone-400 mr-1.5" /> monthly
              tokens
            </span>
            <span className="text-[10px] text-stone-500">1,240 / 50,000</span>
          </div>
          <div className="w-full bg-orange-100/50 dark:bg-[#251A12] rounded-full h-1 overflow-hidden">
            <div className="bg-orange-500 h-1 rounded-full w-[5%]" />
          </div>
          <p className="text-[9px] text-stone-400">
            resets on 1st of every month
          </p>
        </div>
      </div>

      {/* Security Credentials Card */}
      <div className="bg-white dark:bg-[#1C1510] border border-orange-200/80 dark:border-[#2D2118] rounded-xl p-3 space-y-2.5 shadow-val">
        <h3 className="text-xs font-semibold text-stone-900 dark:text-white flex items-center">
          <Lock className="w-3.5 h-3.5 text-stone-500 mr-1.5" /> authentication
          & secrets
        </h3>

        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs">
            <div>
              <p className="font-medium text-stone-800 dark:text-stone-200">
                google oauth2
              </p>
              <p className="text-[10px] text-stone-400">
                social single sign-on
              </p>
            </div>
            <span className="text-[10px] text-emerald-700 dark:text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded font-mono">
              connected
            </span>
          </div>

          <div className="pt-2 border-t border-orange-100 dark:border-[#2D2118]/80 flex items-center justify-between text-xs">
            <div>
              <p className="font-medium text-stone-800 dark:text-stone-200">
                master password
              </p>
              <p className="text-[10px] text-stone-400">
                bcrypt hash • 3-attempt lockout
              </p>
            </div>
            <button className="flex items-center space-x-1 text-xs text-stone-700 dark:text-stone-300 hover:text-stone-950 dark:hover:text-white bg-orange-50/60 dark:bg-[#251A12] border border-orange-200/60 dark:border-[#382A20] px-2 py-0.5 rounded transition-colors font-mono">
              <KeyRound className="w-3 h-3" />
              <span>change</span>
            </button>
          </div>

          {onLogout && (
            <div className="pt-2 border-t border-orange-100 dark:border-[#2D2118]/80 flex items-center justify-between text-xs">
              <div>
                <p className="font-medium text-stone-800 dark:text-stone-200">
                  session management
                </p>
                <p className="text-[10px] text-stone-400">
                  active encrypted session
                </p>
              </div>
              <button
                onClick={onLogout}
                className="flex items-center space-x-1 text-xs text-rose-600 dark:text-rose-400 hover:text-rose-700 bg-rose-500/10 border border-rose-500/20 px-2.5 py-0.5 rounded transition-colors font-mono cursor-pointer"
              >
                <span>sign out</span>
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Profile Card (between Auth and Data Management) */}
      <div className="bg-white dark:bg-[#1C1510] border border-orange-200/80 dark:border-[#2D2118] rounded-xl p-3.5 space-y-2.5 shadow-val">
        <div className="flex items-center justify-between pb-1 border-b border-orange-100 dark:border-[#281D15]">
          <h3 className="text-xs font-semibold text-stone-900 dark:text-white flex items-center">
            <User className="w-3.5 h-3.5 mr-1.5 text-stone-500" /> profile
          </h3>
          <span className="text-[10px] text-stone-400 font-mono">
            {currentUser?.email}
          </span>
        </div>

        <form onSubmit={handleSave} className="space-y-2">
          <div className="flex flex-col sm:flex-row sm:items-center gap-2">
            <div className="flex-1">
              <label className="block text-[10px] text-stone-500 dark:text-stone-400 mb-1 font-mono">
                full name
              </label>
              <input
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Enter your full name..."
                className="w-full bg-[#FFFCF9] dark:bg-[#251A12] border border-orange-200/80 dark:border-[#382A20] rounded-lg px-3 py-1.5 text-xs text-stone-900 dark:text-white placeholder-stone-400 focus:outline-none focus:border-orange-500 focus:ring-1 focus:ring-orange-500/20 font-sans"
              />
            </div>
            <div className="sm:self-end">
              <button
                type="submit"
                className="w-full sm:w-auto px-3.5 py-1.5 bg-orange-600 hover:bg-orange-700 text-white dark:bg-orange-500 dark:hover:bg-orange-400 dark:text-stone-950 rounded-lg text-xs font-mono font-semibold transition-all cursor-pointer flex items-center justify-center space-x-1 shadow-xs"
              >
                {saved ? (
                  <>
                    <Check className="w-3 h-3" />
                    <span>saved</span>
                  </>
                ) : (
                  <span>update</span>
                )}
              </button>
            </div>
          </div>
          {saved && (
            <p className="text-[10px] text-emerald-600 dark:text-emerald-400 flex items-center space-x-1 font-sans">
              <Check className="w-3 h-3" />
              <span>Full name updated successfully</span>
            </p>
          )}
        </form>
      </div>

      {/* GDPR Data Export & Purge */}
      <div className="bg-white dark:bg-[#1C1510] border border-orange-200/80 dark:border-[#2D2118] rounded-xl p-3 space-y-2 shadow-val">
        <h3 className="text-xs font-semibold text-stone-900 dark:text-white">
          data management
        </h3>
        <div className="flex flex-col sm:flex-row gap-2 pt-0.5 font-mono">
          <button className="flex items-center justify-center space-x-1.5 px-3 py-1 bg-stone-100 dark:bg-stone-800 hover:bg-stone-200 dark:hover:bg-stone-700 text-stone-700 dark:text-stone-200 rounded text-xs font-medium transition-colors">
            <Download className="w-3 h-3 text-stone-500" />
            <span>export all files (.zip)</span>
          </button>
          <button className="flex items-center justify-center space-x-1.5 px-3 py-1 bg-rose-500/10 hover:bg-rose-500/20 text-rose-700 dark:text-rose-400 border border-rose-500/20 rounded text-xs font-medium transition-colors">
            <Trash2 className="w-3 h-3" />
            <span>purge all data & vectors</span>
          </button>
        </div>
      </div>
    </div>
  );
};
