import React, { useEffect, useRef, useState } from 'react';
import { ShieldCheck, AlertCircle } from 'lucide-react';

interface TurnstileWidgetProps {
  isDark: boolean;
  onVerify: (token: string) => void;
  onExpire?: () => void;
  action?: string;
}

// Global declaration for Cloudflare Turnstile API
declare global {
  interface Window {
    turnstile?: {
      render: (
        container: string | HTMLElement,
        options: {
          sitekey: string;
          theme?: 'light' | 'dark' | 'auto';
          action?: string;
          callback?: (token: string) => void;
          'error-callback'?: (error: any) => void;
          'expired-callback'?: () => void;
          appearance?: 'always' | 'execute' | 'interaction-only';
        }
      ) => string;
      reset: (widgetId?: string) => void;
      remove: (widgetId?: string) => void;
    };
  }
}

const DEFAULT_SITE_KEY = '0x4AAAAAAGDGaHDA7lQB_a7O';

export const TurnstileWidget: React.FC<TurnstileWidgetProps> = ({
  isDark,
  onVerify,
  onExpire,
  action = 'auth',
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const widgetIdRef = useRef<string | null>(null);
  const [hasError, setHasError] = useState(false);
  const [isVerified, setIsVerified] = useState(false);

  useEffect(() => {
    let checkInterval: any = null;
    let attempts = 0;
    const maxAttempts = 30; // 3 seconds timeout for script load

    const tryRender = () => {
      attempts++;
      if (window.turnstile && containerRef.current) {
        clearInterval(checkInterval);
        setHasError(false);

        // Clear existing widget if re-rendering (e.g. theme change)
        if (widgetIdRef.current) {
          try {
            window.turnstile.remove(widgetIdRef.current);
          } catch {
            // ignore
          }
        }

        try {
          const widgetId = window.turnstile.render(containerRef.current, {
            sitekey: DEFAULT_SITE_KEY,
            theme: isDark ? 'dark' : 'light',
            action,
            callback: (token: string) => {
              setIsVerified(true);
              setHasError(false);
              onVerify(token);
            },
            'expired-callback': () => {
              setIsVerified(false);
              if (onExpire) onExpire();
            },
            'error-callback': (err: any) => {
              console.warn('Cloudflare Turnstile error:', err);
              setHasError(true);
            },
          });
          widgetIdRef.current = widgetId;
        } catch (e) {
          console.warn('Turnstile render exception:', e);
          setHasError(true);
        }
      } else if (attempts >= maxAttempts) {
        clearInterval(checkInterval);
        setHasError(true);
      }
    };

    checkInterval = setInterval(tryRender, 100);
    tryRender();

    return () => {
      if (checkInterval) clearInterval(checkInterval);
      if (widgetIdRef.current && window.turnstile) {
        try {
          window.turnstile.remove(widgetIdRef.current);
        } catch {
          // ignore
        }
      }
    };
  }, [isDark, action]);

  const handleSimulateLocalVerify = () => {
    // Cloudflare standard development test token that always passes
    const devToken = '1x00000000000000000000AA';
    setIsVerified(true);
    setHasError(false);
    onVerify(devToken);
  };

  return (
    <div className="w-full my-2.5 flex flex-col items-center justify-center">
      {/* Official Cloudflare Turnstile Render Mount */}
      <div
        ref={containerRef}
        className="min-h-[65px] flex items-center justify-center transition-opacity"
      />

      {/* Verified Status Pill */}
      {isVerified && (
        <div className="mt-1 flex items-center space-x-1 text-[11px] text-emerald-600 dark:text-emerald-400 font-mono">
          <ShieldCheck className="w-3.5 h-3.5" />
          <span>Cloudflare Human Verification Passed</span>
        </div>
      )}

      {/* Fallback & Adblock Notice */}
      {hasError && !isVerified && (
        <div className="w-full p-2.5 rounded-lg border border-amber-200 dark:border-amber-900/60 bg-amber-50/70 dark:bg-amber-950/20 text-stone-700 dark:text-stone-300 text-[11px] font-mono flex flex-col sm:flex-row items-center justify-between gap-2">
          <div className="flex items-center space-x-1.5 text-amber-700 dark:text-amber-400">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>Turnstile script blocked or offline</span>
          </div>
          <button
            type="button"
            onClick={handleSimulateLocalVerify}
            className="px-2 py-1 rounded bg-stone-900 dark:bg-white text-white dark:text-stone-900 font-semibold text-[10px] hover:opacity-90 transition-opacity cursor-pointer whitespace-nowrap"
          >
            Use Dev Test Token
          </button>
        </div>
      )}
    </div>
  );
};
