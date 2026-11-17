import React, { useState, useEffect } from "react";
import {
  X,
  Laptop,
  Smartphone,
  Tablet,
  ShieldCheck,
  LogOut,
  RefreshCw,
  Check,
  AlertCircle,
} from "lucide-react";
import { UserSession } from "../types";
import {
  apiGetSessions,
  apiRevokeSession,
  apiRevokeAllSessions,
  triggerForcedLogout,
} from "../services/api";

interface DevicesModalProps {
  isOpen: boolean;
  onClose: () => void;
  onLogout?: () => void;
}

export const DevicesModal: React.FC<DevicesModalProps> = ({
  isOpen,
  onClose,
  onLogout,
}) => {
  const [sessions, setSessions] = useState<UserSession[]>([]);
  const [loading, setLoading] = useState(false);
  const [actionLoadingId, setActionLoadingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const fetchSessions = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiGetSessions();
      setSessions(data);
    } catch (err: any) {
      console.warn("Failed to fetch sessions:", err);
      setError("Unable to load active sessions.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchSessions();
      setError(null);
      setSuccess(null);
    }
  }, [isOpen]);

  // Close on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const handleRevokeSingle = async (sess: UserSession) => {
    setActionLoadingId(sess.id);
    setError(null);
    setSuccess(null);

    try {
      await apiRevokeSession(sess.id);

      if (sess.isCurrent) {
        // If current device was revoked, force immediate logout everywhere
        triggerForcedLogout("Session terminated by user");
        if (onLogout) onLogout();
        onClose();
        return;
      }

      setSuccess(`Logged out "${sess.deviceName}" successfully.`);
      setTimeout(() => setSuccess(null), 3500);
      await fetchSessions();
    } catch (err: any) {
      setError(err.message || "Failed to log out device.");
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleRevokeAll = async (keepCurrent: boolean) => {
    setActionLoadingId(keepCurrent ? "all_others" : "all");
    setError(null);
    setSuccess(null);

    try {
      await apiRevokeAllSessions(keepCurrent);

      if (!keepCurrent) {
        // Logged out of all devices including current
        triggerForcedLogout("All sessions terminated by user");
        if (onLogout) onLogout();
        onClose();
        return;
      }

      setSuccess("All other devices have been logged out.");
      setTimeout(() => setSuccess(null), 3500);
      await fetchSessions();
    } catch (err: any) {
      setError(err.message || "Failed to log out sessions.");
    } finally {
      setActionLoadingId(null);
    }
  };

  const renderDeviceIcon = (type: string) => {
    if (type === "mobile") return <Smartphone className="w-4 h-4 text-orange-500" />;
    if (type === "tablet") return <Tablet className="w-4 h-4 text-amber-500" />;
    return <Laptop className="w-4 h-4 text-stone-700 dark:text-stone-300" />;
  };

  const formatDate = (isoString: string) => {
    try {
      const d = new Date(isoString);
      return d.toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return isoString;
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-black/60 backdrop-blur-xs font-mono"
      onClick={onClose}
    >
      <div
        className="w-full max-w-lg bg-white dark:bg-[#1C1510] border border-orange-200/90 dark:border-[#382A20] rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[88vh]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="p-4 border-b border-orange-100 dark:border-[#281D15] flex items-center justify-between shrink-0 bg-orange-50/30 dark:bg-[#201712]">
          <div className="flex items-center space-x-2.5">
            <div className="p-1.5 rounded-lg bg-emerald-500/10 dark:bg-emerald-500/20 text-emerald-600 dark:text-emerald-400">
              <ShieldCheck className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-xs sm:text-sm font-semibold text-stone-900 dark:text-white">
                active devices & logged-in sessions
              </h3>
              <p className="text-[10px] text-stone-500 dark:text-stone-400">
                manage devices currently authorized to access your vault
              </p>
            </div>
          </div>
          <div className="flex items-center space-x-1.5">
            <button
              onClick={fetchSessions}
              disabled={loading}
              title="Refresh sessions"
              className="p-1.5 rounded-lg text-stone-400 hover:text-stone-700 dark:hover:text-stone-200 hover:bg-orange-100/50 dark:hover:bg-[#281D15] transition-colors cursor-pointer"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
            </button>
            <button
              onClick={onClose}
              title="Close modal"
              className="p-1.5 rounded-lg text-stone-400 hover:text-stone-700 dark:hover:text-stone-200 hover:bg-orange-100/50 dark:hover:bg-[#281D15] transition-colors cursor-pointer"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Status Alerts */}
        {success && (
          <div className="mx-4 mt-3 p-2.5 bg-emerald-500/10 border border-emerald-500/20 rounded-xl text-xs text-emerald-700 dark:text-emerald-300 flex items-center space-x-2 font-sans shrink-0">
            <Check className="w-4 h-4 text-emerald-500 shrink-0" />
            <span>{success}</span>
          </div>
        )}

        {error && (
          <div className="mx-4 mt-3 p-2.5 bg-rose-500/10 border border-rose-500/20 rounded-xl text-xs text-rose-700 dark:text-rose-300 flex items-center space-x-2 font-sans shrink-0">
            <AlertCircle className="w-4 h-4 text-rose-500 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Sessions Scrollable Body */}
        <div className="p-4 overflow-y-auto space-y-2.5 flex-1">
          {loading && sessions.length === 0 ? (
            <div className="py-8 text-center text-xs text-stone-400 flex flex-col items-center justify-center space-y-2">
              <RefreshCw className="w-5 h-5 animate-spin text-orange-500" />
              <span>Scanning active devices...</span>
            </div>
          ) : sessions.length === 0 ? (
            <div className="py-8 text-center text-xs text-stone-400">
              No active sessions found.
            </div>
          ) : (
            sessions.map((sess) => {
              const isProcessing = actionLoadingId === sess.id;
              return (
                <div
                  key={sess.id}
                  className={`p-3 rounded-xl border transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-3 ${
                    sess.isCurrent
                      ? "bg-orange-50/50 dark:bg-[#251A12] border-orange-200/90 dark:border-[#382A20]"
                      : "bg-white dark:bg-[#18110D] border-stone-200/80 dark:border-stone-800/80 hover:border-orange-200 dark:hover:border-[#33251B]"
                  }`}
                >
                  <div className="flex items-start space-x-3 min-w-0">
                    <div className="p-2 rounded-lg bg-orange-100/50 dark:bg-[#281D15] border border-orange-200/60 dark:border-[#382A20] shrink-0 mt-0.5">
                      {renderDeviceIcon(sess.deviceType)}
                    </div>
                    <div className="min-w-0">
                      <div className="flex items-center space-x-2 flex-wrap">
                        <p className="text-xs font-semibold text-stone-900 dark:text-white truncate">
                          {sess.deviceName}
                        </p>
                        {sess.isCurrent && (
                          <span className="text-[9px] font-bold px-1.5 py-0.5 bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border border-emerald-500/30 rounded font-mono">
                            THIS DEVICE
                          </span>
                        )}
                      </div>
                      <p className="text-[10px] text-stone-500 dark:text-stone-400 font-mono mt-0.5">
                        IP: {sess.ipAddress} • Signed in {formatDate(sess.createdAt)}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center sm:self-center self-end shrink-0">
                    <button
                      onClick={() => handleRevokeSingle(sess)}
                      disabled={isProcessing}
                      className={`text-xs font-mono font-medium px-3 py-1.5 rounded-lg transition-all flex items-center space-x-1.5 cursor-pointer ${
                        sess.isCurrent
                          ? "text-rose-600 dark:text-rose-400 hover:text-rose-700 bg-rose-500/10 border border-rose-500/20 hover:bg-rose-500/20"
                          : "text-stone-600 dark:text-stone-300 hover:text-rose-600 dark:hover:text-rose-400 bg-stone-100 dark:bg-[#251A12] border border-stone-200 dark:border-stone-700 hover:border-rose-400"
                      } ${isProcessing ? "opacity-50 pointer-events-none" : ""}`}
                      title={sess.isCurrent ? "Log out this device" : "Revoke device session"}
                    >
                      <LogOut className="w-3 h-3" />
                      <span>{sess.isCurrent ? "sign out" : "revoke"}</span>
                    </button>
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Footer with Bulk Actions */}
        <div className="p-3 sm:p-4 border-t border-orange-100 dark:border-[#281D15] bg-orange-50/20 dark:bg-[#18110D] flex flex-wrap items-center justify-between gap-2 shrink-0">
          <div className="text-[10px] text-stone-400 font-mono">
            {sessions.length} {sessions.length === 1 ? "session active" : "sessions active"}
          </div>

          <div className="flex items-center space-x-2 text-[10px] font-mono">
            {sessions.length > 1 && (
              <button
                onClick={() => handleRevokeAll(true)}
                disabled={actionLoadingId !== null}
                className="px-2.5 py-1.5 text-stone-700 dark:text-stone-300 hover:text-stone-900 dark:hover:text-white bg-white dark:bg-[#251A12] border border-orange-200/80 dark:border-[#382A20] rounded-lg cursor-pointer transition-colors"
              >
                log out other devices
              </button>
            )}

            <button
              onClick={() => handleRevokeAll(false)}
              disabled={actionLoadingId !== null}
              className="px-2.5 py-1.5 text-rose-600 dark:text-rose-400 hover:text-rose-700 bg-rose-500/10 border border-rose-500/20 rounded-lg cursor-pointer transition-colors"
            >
              log out all devices
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
