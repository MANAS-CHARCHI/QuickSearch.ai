import React, { useState, useEffect } from "react";
import {
  User,
  Check,
  Database,
  Lock,
  Download,
  Trash2,
  KeyRound,
  Terminal,
  Laptop,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { UserProfile, UserTokenSummary } from "../types";
import { DevicesModal } from "./DevicesModal";
import { PasswordModal } from "./PasswordModal";
import { apiGetTokenUsage } from "../services/api";

interface SettingsViewProps {
  currentUser?: UserProfile | null;
  onUpdateFullName?: (newName: string) => void;
  onLogout?: () => void;
  usedBytes?: number;
  quotaBytes?: number;
}

export const SettingsView: React.FC<SettingsViewProps> = ({
  currentUser,
  onUpdateFullName,
  onLogout,
  usedBytes = 0,
  quotaBytes = 100 * 1024 * 1024,
}) => {
  const usedMb = (usedBytes / (1024 * 1024)).toFixed(2);
  const quotaMb = Math.round(quotaBytes / (1024 * 1024));
  const usedPercent = Math.min(100, Math.max(usedBytes > 0 ? 1 : 0, Math.round((usedBytes / Math.max(1, quotaBytes)) * 100)));
  const [fullName, setFullName] = useState(
    currentUser?.fullName || currentUser?.name || "",
  );
  const [saved, setSaved] = useState(false);
  const [showDevicesModal, setShowDevicesModal] = useState(false);
  const [showPasswordModal, setShowPasswordModal] = useState(false);
  const [tokenSummary, setTokenSummary] = useState<UserTokenSummary | null>(null);

  useEffect(() => {
    async function loadTokens() {
      try {
        const data = await apiGetTokenUsage();
        if (data) setTokenSummary(data);
      } catch (e) {
        // Ignore token fetch errors
      }
    }
    loadTokens();
  }, []);

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    if (onUpdateFullName) {
      onUpdateFullName(fullName.trim());
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    }
  };

  return (
    <div className="max-w-2xl mx-auto space-y-3 font-mono pb-20">
      

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
        {/* S3 Storage Quota */}
        <div className="bg-white dark:bg-[#1C1510] border border-orange-200/80 dark:border-[#2D2118] rounded-xl p-3 space-y-2 shadow-val">
          <div className="flex items-center justify-between text-xs">
            <span className="flex items-center font-medium text-stone-800 dark:text-stone-200">
              <Database className="w-3.5 h-3.5 text-stone-400 mr-1.5" />storage
            </span>
            <span className="text-[10px] text-stone-500 font-mono">{usedMb} MB / {quotaMb} MB</span>
          </div>
          <div className="w-full bg-orange-100/50 dark:bg-[#251A12] rounded-full h-1 overflow-hidden">
            <div className="bg-emerald-500 h-1 rounded-full transition-all" style={{ width: `${usedPercent}%` }} />
          </div>
          <p className="text-[9px] text-stone-400">
            100 MB free storage limit • AWS SSE-KMS prefix isolation
          </p>
        </div>

        {/* AI Token Usage (Calculated from dedicated SQLite database) */}
        <div className="bg-white dark:bg-[#1C1510] border border-orange-200/80 dark:border-[#2D2118] rounded-xl p-3 space-y-2 shadow-val">
          <div className="flex items-center justify-between text-xs">
            <span className="flex items-center font-medium text-stone-800 dark:text-stone-200">
              <Sparkles className="w-3.5 h-3.5 text-amber-500 mr-1.5" /> ai
              tokens
            </span>
            <span className="text-[10px] text-stone-500 font-bold font-mono">
              {tokenSummary ? tokenSummary.total_tokens.toLocaleString() : '0'} tokens
            </span>
          </div>

          <div className="grid grid-cols-2 gap-2 text-[10px] bg-orange-50/50 dark:bg-[#251A12] p-1.5 rounded-lg border border-orange-200/50 dark:border-[#382A20]">
            <div>
              <span className="text-stone-400 block text-[9px]">Input Tokens</span>
              <span className="font-semibold text-stone-800 dark:text-stone-200 font-mono">
                {tokenSummary ? tokenSummary.total_input_tokens.toLocaleString() : '0'}
              </span>
            </div>
            <div>
              <span className="text-stone-400 block text-[9px]">Output Tokens</span>
              <span className="font-semibold text-stone-800 dark:text-stone-200 font-mono">
                {tokenSummary ? tokenSummary.total_output_tokens.toLocaleString() : '0'}
              </span>
            </div>
          </div>

          <div className="flex items-center justify-between text-[9px] text-stone-400 pt-0.5">
            <span>
              Requests:{" "}
              <span className="text-stone-600 dark:text-stone-300 font-semibold font-mono">
                {tokenSummary?.total_requests || 0}
              </span>
            </span>
            <span>
              AI Spend:{" "}
              <span className="text-emerald-600 dark:text-emerald-400 font-semibold font-mono">
                ${(tokenSummary?.total_cost_usd || 0).toFixed(5)} (₹{((tokenSummary?.total_cost_inr !== undefined ? tokenSummary.total_cost_inr : (tokenSummary?.total_cost_usd || 0) * 86.0)).toFixed(3)})
              </span>
            </span>
          </div>
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
            {currentUser?.hasGoogle ? (
              <span className="text-[10px] text-emerald-700 dark:text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded font-mono flex items-center gap-1">
                <Check className="w-3 h-3" />
                connected
              </span>
            ) : (
              <span className="text-[10px] text-stone-500 dark:text-stone-400 bg-stone-100 dark:bg-[#251A12] border border-stone-200 dark:border-stone-800 px-2 py-0.5 rounded font-mono">
                not connected
              </span>
            )}
          </div>

          <div className="pt-2 border-t border-orange-100 dark:border-[#2D2118]/80 flex items-center justify-between text-xs">
            <div>
              <p className="font-medium text-stone-800 dark:text-stone-200">
                master password
              </p>
            </div>
            <button
              type="button"
              onClick={() => setShowPasswordModal(true)}
              className="flex items-center space-x-1.5 text-xs text-stone-700 dark:text-stone-300 hover:text-stone-950 dark:hover:text-white bg-orange-50/70 dark:bg-[#251A12] border border-orange-200/80 dark:border-[#382A20] hover:border-orange-300 dark:hover:border-orange-500/50 px-2.5 py-1 rounded-lg transition-colors font-mono cursor-pointer"
            >
              <KeyRound className="w-3.5 h-3.5 text-orange-500" />
              <span>
                {currentUser?.hasPassword === false ? "set password" : "reset"}
              </span>
            </button>
          </div>

          {/* Active Devices Row */}
          <div className="pt-2 border-t border-orange-100 dark:border-[#2D2118]/80 flex items-center justify-between text-xs">
            <div>
              <p className="font-medium text-stone-800 dark:text-stone-200 flex items-center space-x-1.5">
                <Laptop className="w-3.5 h-3.5 text-stone-500" />
                <span>active devices & sessions</span>
              </p>
              <p className="text-[10px] text-stone-400">
                view & manage devices logged into your vault
              </p>
            </div>
            <button
              type="button"
              onClick={() => setShowDevicesModal(true)}
              className="flex items-center space-x-1.5 text-xs text-stone-700 dark:text-stone-300 hover:text-stone-950 dark:hover:text-white bg-orange-50/70 dark:bg-[#251A12] border border-orange-200/80 dark:border-[#382A20] hover:border-orange-300 dark:hover:border-orange-500/50 px-2.5 py-1 rounded-lg transition-colors font-mono cursor-pointer"
            >
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-500" />
              <span>manage</span>
            </button>
          </div>
        </div>
      </div>

      {/* Profile Card */}
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
          <button
            type="button"
            className="flex items-center justify-center space-x-1.5 px-3 py-1 bg-stone-100 dark:bg-stone-800 hover:bg-stone-200 dark:hover:bg-stone-700 text-stone-700 dark:text-stone-200 rounded text-xs font-medium transition-colors"
          >
            <Download className="w-3 h-3 text-stone-500" />
            <span>export all files (.zip)</span>
          </button>
          <button
            type="button"
            className="flex items-center justify-center space-x-1.5 px-3 py-1 bg-rose-500/10 hover:bg-rose-500/20 text-rose-700 dark:text-rose-400 border border-rose-500/20 rounded text-xs font-medium transition-colors"
          >
            <Trash2 className="w-3 h-3" />
            <span>purge all data & vectors</span>
          </button>
        </div>
      </div>

      {/* Active Devices Pop-up Modal */}
      <DevicesModal
        isOpen={showDevicesModal}
        onClose={() => setShowDevicesModal(false)}
        onLogout={onLogout}
      />

      {/* Master Password Change & Reset Modal */}
      <PasswordModal
        isOpen={showPasswordModal}
        onClose={() => setShowPasswordModal(false)}
        hasPassword={currentUser?.hasPassword}
      />
    </div>
  );
};
