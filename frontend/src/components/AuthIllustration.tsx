import React, { useState } from 'react';
import { ShieldCheck, Lock, Code2, MapPin } from 'lucide-react';

export const AuthIllustration: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'illustration' | 'code'>('illustration');

  return (
    <div className="flex flex-col space-y-3.5 w-full">
      {/* Val Town Hand-drawn Illustration / Code Card */}
      <div className="rounded-2xl overflow-hidden border border-stone-200 dark:border-stone-800 bg-[#FCFAF6] dark:bg-[#0D1017] shadow-val transition-all">
        {/* Card Header with Val Town Style Tabs */}
        <div className="px-4 py-2.5 bg-stone-100/70 dark:bg-stone-900/80 border-b border-stone-200 dark:border-stone-800 flex items-center justify-between font-mono text-xs">
          <div className="flex items-center space-x-1.5">
            <button
              type="button"
              onClick={() => setActiveTab('illustration')}
              className={`flex items-center space-x-1.5 px-2.5 py-1 rounded-md transition-all text-xs ${
                activeTab === 'illustration'
                  ? 'bg-white dark:bg-stone-800 text-stone-900 dark:text-white font-semibold shadow-xs border border-stone-200 dark:border-stone-700'
                  : 'text-stone-500 hover:text-stone-800 dark:hover:text-stone-300'
              }`}
            >
              <MapPin className="w-3.5 h-3.5" />
              <span>vault.city/view</span>
            </button>

            <button
              type="button"
              onClick={() => setActiveTab('code')}
              className={`flex items-center space-x-1.5 px-2.5 py-1 rounded-md transition-all text-xs ${
                activeTab === 'code'
                  ? 'bg-white dark:bg-stone-800 text-stone-900 dark:text-white font-semibold shadow-xs border border-stone-200 dark:border-stone-700'
                  : 'text-stone-500 hover:text-stone-800 dark:hover:text-stone-300'
              }`}
            >
              <Code2 className="w-3.5 h-3.5" />
              <span>client.ts</span>
            </button>
          </div>

          <div className="flex items-center space-x-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-[10px] text-stone-500 dark:text-stone-400 font-sans">Zero-Knowledge</span>
          </div>
        </div>

        {/* Tab 1: Hand-Drawn Isometric Vault City Artwork (Val Town style) */}
        {activeTab === 'illustration' ? (
          <div className="relative p-2 bg-[#FCFAF6] dark:bg-[#0D1017] flex items-center justify-center overflow-hidden">
            <img
              src="/samples/vault_city_valtown.svg"
              alt="Vault City Hand-Drawn Isometric Town"
              className="w-full h-auto max-h-72 object-contain rounded-xl select-none"
              onError={(e) => {
                // Fallback to raster generated hero if SVG fails
                e.currentTarget.src = '/samples/vault_city_hero.png';
              }}
            />
          </div>
        ) : (
          /* Tab 2: Val Town Code Editor */
          <div className="p-4 sm:p-5 font-mono text-xs bg-[#090A0E] text-stone-200 space-y-1.5 leading-relaxed">
            <p>
              <span className="text-purple-400">import</span>{' '}
              <span className="text-stone-100">{'{ vault }'}</span>{' '}
              <span className="text-purple-400">from</span>{' '}
              <span className="text-emerald-400">&quot;@vault.city&quot;</span>
              <span className="text-stone-500">;</span>
            </p>

            <p className="text-stone-500 italic pt-1">
              // Zero-knowledge personal document store
            </p>

            <p>
              <span className="text-purple-400">const</span>{' '}
              <span className="text-blue-400">doc</span>{' '}
              <span className="text-stone-200">=</span>{' '}
              <span className="text-purple-400">await</span>{' '}
              <span className="text-stone-200">vault.</span>
              <span className="text-sky-400">get</span>
              <span className="text-stone-200">({'{'}</span>
            </p>

            <p className="pl-4">
              <span className="text-stone-300">type:</span>{' '}
              <span className="text-emerald-400">&quot;Passport&quot;</span>
              <span className="text-stone-500">,</span>
            </p>
            <p className="pl-4">
              <span className="text-stone-300">decrypt:</span>{' '}
              <span className="text-pink-400">true</span>
            </p>

            <p className="text-stone-200">{'}'});</p>

            <p className="pt-2">
              <span className="text-purple-400">console</span>
              <span className="text-stone-200">.</span>
              <span className="text-sky-400">log</span>
              <span className="text-stone-200">(doc.expiryDate);</span>
            </p>

            <p className="text-emerald-400 font-semibold pt-1">
              <span className="text-stone-500">// =&gt; </span>
              <span>&quot;2032-10-24&quot; (Valid)</span>
            </p>
          </div>
        )}

        {/* Val Town Signature Announcement Pill (Light Pastel Blue) */}
        <div className="p-3 bg-[#F0F9FF] dark:bg-[#072439] border-t border-sky-200 dark:border-sky-900/60 flex items-center justify-between text-xs font-sans">
          <div className="flex items-center space-x-2">
            <Lock className="w-3.5 h-3.5 text-sky-600 dark:text-sky-400 flex-shrink-0" />
            <span className="text-sky-900 dark:text-sky-200 font-medium text-[11px] sm:text-xs">
              Client-side AES-256-GCM encryption is active.
            </span>
          </div>
          <span className="text-[10px] text-sky-700 dark:text-sky-300 underline font-semibold flex-shrink-0">
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
        <div className="flex items-center space-x-2 text-xs text-stone-600 dark:text-stone-400 font-sans">
          <ShieldCheck className="w-4 h-4 text-emerald-500 flex-shrink-0" />
          <span>Biometric &amp; ID masking</span>
        </div>
      </div>
    </div>
  );
};
