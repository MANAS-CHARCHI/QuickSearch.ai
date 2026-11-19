import React from 'react';
import { Terminal, ChevronDown, CheckCircle2 } from 'lucide-react';
import { ActivityItem } from '../types';

interface ActivityViewProps {
  activities: ActivityItem[];
  hasMore?: boolean;
  totalCount?: number;
  isLoadingMore?: boolean;
  onLoadMore?: () => void;
}

export const ActivityView: React.FC<ActivityViewProps> = ({
  activities,
  hasMore = false,
  totalCount = 0,
  isLoadingMore = false,
  onLoadMore,
}) => {
  const displayTotal = totalCount || activities.length;

  return (
    <div className="max-w-2xl mx-auto space-y-3 font-mono pb-20 md:pb-0">
      <div className="flex items-center justify-between pb-1.5 border-b border-orange-200/80 dark:border-[#2D2118]">
        <div>
          <h2 className="text-xs font-semibold text-stone-900 dark:text-white flex items-center">
            <Terminal className="w-3.5 h-3.5 mr-1.5 text-stone-500 shrink-0" />
            vault/audit_trail
          </h2>
          <p className="text-[10px] text-stone-500 dark:text-stone-400">
            immutable execution logs
          </p>
        </div>
        <div className="flex items-center gap-1.5 shrink-0 ml-2">
          <span className="text-[10px] text-stone-500 dark:text-stone-400 font-mono">
            {activities.length} of {displayTotal}
          </span>
          <span className="text-[10px] text-emerald-700 dark:text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded font-mono">
            verified log
          </span>
        </div>
      </div>

      <div className="divide-y divide-orange-100 dark:divide-[#2D2118] bg-white dark:bg-[#1C1510] border border-orange-200/80 dark:border-[#2D2118] rounded-xl overflow-hidden shadow-val font-mono">
        {activities.length === 0 ? (
          <div className="p-8 text-center text-xs text-stone-400">
            No activity logs found.
          </div>
        ) : (
          activities.map((item) => (
            <div
              key={item.id}
              className="p-2.5 sm:px-3 flex items-center justify-between hover:bg-orange-50/40 dark:hover:bg-[#281D16]/40 transition-colors text-xs gap-2"
            >
              <div className="flex items-start sm:items-center space-x-2.5 min-w-0 flex-1">
                <span className="text-stone-400 text-[10px] font-bold mt-0.5 sm:mt-0 shrink-0">&gt;</span>

                <div className="min-w-0 flex-1">
                  <p className="text-xs font-medium text-stone-800 dark:text-stone-200 truncate">
                    <span className="font-semibold text-stone-950 dark:text-white">{item.action}</span>
                    <span className="text-stone-400 mx-1.5">•</span>
                    <span className="text-stone-500 dark:text-stone-400">{item.target}</span>
                  </p>
                  <p className="text-[10px] text-stone-400 truncate mt-0.5">
                    {new Date(item.timestamp).toISOString().replace('T', ' ').slice(0, 19)} UTC
                  </p>
                </div>
              </div>

              <div className="flex-shrink-0 ml-2">
                {item.status === 'success' && (
                  <span className="text-[9px] text-emerald-700 dark:text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded font-bold">
                    PASS
                  </span>
                )}
                {item.status === 'warning' && (
                  <span className="text-[9px] text-amber-700 dark:text-amber-400 bg-amber-500/10 px-1.5 py-0.5 rounded font-bold">
                    FLAG
                  </span>
                )}
                {item.status === 'info' && (
                  <span className="text-[9px] text-stone-500 bg-stone-100 dark:bg-stone-800 px-1.5 py-0.5 rounded">
                    LOG
                  </span>
                )}
              </div>
            </div>
          ))
        )}
      </div>

      {/* Pagination Controls */}
      {hasMore && onLoadMore && (
        <div className="pt-1 text-center">
          <button
            type="button"
            onClick={onLoadMore}
            disabled={isLoadingMore}
            className="w-full py-2 px-3 bg-white dark:bg-[#1C1510] hover:bg-orange-50 dark:hover:bg-[#281D16] border border-orange-200/80 dark:border-[#2D2118] text-stone-700 dark:text-stone-300 hover:text-stone-950 dark:hover:text-white rounded-xl text-xs font-semibold shadow-xs transition-all cursor-pointer flex items-center justify-center space-x-1.5 disabled:opacity-50"
          >
            <ChevronDown className={`w-3.5 h-3.5 text-orange-500 ${isLoadingMore ? 'animate-bounce' : ''}`} />
            <span>
              {isLoadingMore
                ? 'Fetching older logs from database...'
                : `Load More Activities (${Math.max(0, displayTotal - activities.length)} remaining)`}
            </span>
          </button>
        </div>
      )}

      {!hasMore && activities.length > 0 && (
        <div className="text-center py-1.5 text-[10px] text-stone-400 flex items-center justify-center space-x-1 font-mono">
          <CheckCircle2 className="w-3 h-3 text-emerald-500" />
          <span>All recorded activities loaded ({activities.length})</span>
        </div>
      )}
    </div>
  );
};
