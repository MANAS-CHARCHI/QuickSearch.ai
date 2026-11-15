import React from 'react';
import { Terminal } from 'lucide-react';
import { ActivityItem } from '../types';

interface ActivityViewProps {
  activities: ActivityItem[];
}

export const ActivityView: React.FC<ActivityViewProps> = ({ activities }) => {
  return (
    <div className="max-w-2xl mx-auto space-y-3 font-mono">
      <div className="flex items-center justify-between pb-1.5 border-b border-stone-200 dark:border-stone-800">
        <div>
          <h2 className="text-xs font-semibold text-stone-900 dark:text-white flex items-center">
            <Terminal className="w-3.5 h-3.5 mr-1.5 text-stone-500" />
            vault/audit_trail
          </h2>
          <p className="text-[10px] text-stone-500 dark:text-stone-400">
            immutable execution logs • zero sensitive content recorded
          </p>
        </div>
        <span className="text-[10px] text-emerald-700 dark:text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded font-mono">
          verified log
        </span>
      </div>

      <div className="divide-y divide-stone-100 dark:divide-stone-800 bg-white dark:bg-[#121216] border border-stone-200 dark:border-stone-800 rounded-xl overflow-hidden shadow-val font-mono">
        {activities.map((item) => (
          <div
            key={item.id}
            className="p-2.5 sm:px-3 flex items-center justify-between hover:bg-stone-50 dark:hover:bg-stone-900/40 transition-colors text-xs"
          >
            <div className="flex items-center space-x-2.5 min-w-0">
              <span className="text-stone-400 text-[10px] font-bold">&gt;</span>

              <div className="min-w-0">
                <p className="text-xs font-medium text-stone-800 dark:text-stone-200 truncate">
                  <span className="font-semibold text-stone-950 dark:text-white">{item.action}</span>
                  <span className="text-stone-400 mx-1.5">•</span>
                  <span className="text-stone-500 dark:text-stone-400">{item.target}</span>
                </p>
                <p className="text-[10px] text-stone-400">
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
        ))}
      </div>
    </div>
  );
};
