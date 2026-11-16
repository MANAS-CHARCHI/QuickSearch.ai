import React from "react";
import { ShieldCheck, Lock, Sparkles } from "lucide-react";

export const AuthIllustration: React.FC = () => {
  return (
    <div className="flex flex-col space-y-3.5 w-full">
      {/* Val Town Live Hand-drawn Isometric Scene Card */}
      <div className="rounded-2xl overflow-hidden border border-orange-200/80 dark:border-[#2D2118] bg-[#FFFBF7] dark:bg-[#1A130E] shadow-val transition-all">
        {/* Card Header (Clean & Minimalist, No client.ts tab) */}
        <div className="px-4 py-2.5 bg-orange-50/70 dark:bg-[#1C1510] border-b border-orange-200/60 dark:border-[#2D2118] flex items-center justify-between font-mono text-xs">
          <div className="flex items-center space-x-2">
            <span className="font-semibold text-stone-900 dark:text-white">
              vault.city
            </span>
            <span className="text-stone-400">•</span>
            <span className="text-stone-500 text-[11px] flex items-center gap-1 font-sans">
              <Sparkles className="w-3 h-3 text-amber-500 animate-pulse" />
              Live City View
            </span>
          </div>

          <div className="flex items-center space-x-1.5">
            <span className="text-[10px] text-stone-500 dark:text-stone-400 font-sans">
              Zero-Knowledge
            </span>
          </div>
        </div>

        {/* Live Animated Isometric Town with Hovering User Character (Prominent & Bigger) */}
        <div className="relative p-2 sm:p-3 bg-[#FFFBF7] dark:bg-[#1A130E] flex items-center justify-center overflow-hidden min-h-[320px] sm:min-h-[380px]">
          <img
            src="/samples/vault_city_valtown.svg"
            alt="Vault City Live Hand-Drawn Animated Scene with Hovering User"
            className="w-full h-auto min-h-[300px] max-h-[440px] object-contain rounded-xl select-none"
            onError={(e) => {
              // Fallback to raster generated hero if SVG fails
              e.currentTarget.src = "/samples/vault_city_hero.png";
            }}
          />
        </div>

        {/* Val Town Signature Announcement Pill (Warm Orange Tint) */}
        <div className="p-3 bg-[#FFF7ED] dark:bg-[#251A12] border-t border-orange-200/70 dark:border-orange-950/60 flex items-center justify-between text-xs font-sans">
          <div className="flex items-center space-x-2">
            <Lock className="w-3.5 h-3.5 text-orange-600 dark:text-orange-400 flex-shrink-0" />
            <span className="text-orange-900 dark:text-orange-200 font-medium text-[11px] sm:text-xs">
              Client-side AES-256-GCM encryption is active.
            </span>
          </div>
          <span className="text-[10px] text-orange-700 dark:text-orange-300 underline font-semibold flex-shrink-0">
            Read docs &rarr;
          </span>
        </div>
      </div>

      {/* Feature Badges */}
      <div className="grid grid-cols-2 gap-2 px-1">
        <div className="flex items-center space-x-2 text-xs text-stone-600 dark:text-stone-400 font-sans">
          <ShieldCheck className="w-4 h-4 text-emerald-500 flex-shrink-0" />
          <span>Zero-knowledge storage</span>
        </div>
      </div>
    </div>
  );
};
