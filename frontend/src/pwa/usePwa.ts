import { useState, useEffect, useCallback } from 'react';

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed'; platform: string }>;
}

let globalDeferredPrompt: BeforeInstallPromptEvent | null = null;
const promptListeners = new Set<(prompt: BeforeInstallPromptEvent | null) => void>();

// Register global listener once
if (typeof window !== 'undefined') {
  window.addEventListener('beforeinstallprompt', (e: Event) => {
    e.preventDefault();
    globalDeferredPrompt = e as BeforeInstallPromptEvent;
    promptListeners.forEach((fn) => fn(globalDeferredPrompt));
  });

  window.addEventListener('appinstalled', () => {
    globalDeferredPrompt = null;
    promptListeners.forEach((fn) => fn(null));
  });
}

export function usePwa() {
  const [deferredPrompt, setDeferredPrompt] = useState<BeforeInstallPromptEvent | null>(
    () => globalDeferredPrompt
  );
  const [isInstalled, setIsInstalled] = useState<boolean>(() => {
    if (typeof window === 'undefined') return false;
    return (
      window.matchMedia('(display-mode: standalone)').matches ||
      (navigator as any).standalone === true ||
      document.referrer.includes('android-app://')
    );
  });
  const [isOffline, setIsOffline] = useState<boolean>(() => {
    if (typeof navigator === 'undefined') return false;
    return !navigator.onLine;
  });
  const [hasUpdate, setHasUpdate] = useState<boolean>(false);

  useEffect(() => {
    const handlePromptChange = (prompt: BeforeInstallPromptEvent | null) => {
      setDeferredPrompt(prompt);
    };
    promptListeners.add(handlePromptChange);

    const checkDisplayMode = (e: MediaQueryListEvent) => {
      setIsInstalled(e.matches);
    };
    const mql = window.matchMedia('(display-mode: standalone)');
    mql.addEventListener('change', checkDisplayMode);

    const handleOnline = () => setIsOffline(false);
    const handleOffline = () => setIsOffline(true);
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    // Listen for custom SW update event
    const handleSwUpdate = () => setHasUpdate(true);
    window.addEventListener('vault-sw-update', handleSwUpdate);

    return () => {
      promptListeners.delete(handlePromptChange);
      mql.removeEventListener('change', checkDisplayMode);
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
      window.removeEventListener('vault-sw-update', handleSwUpdate);
    };
  }, []);

  const installApp = useCallback(async () => {
    if (!deferredPrompt) return false;
    try {
      await deferredPrompt.prompt();
      const choice = await deferredPrompt.userChoice;
      if (choice.outcome === 'accepted') {
        globalDeferredPrompt = null;
        setDeferredPrompt(null);
        setIsInstalled(true);
        return true;
      }
      return false;
    } catch (err) {
      console.warn('[PWA] Prompt error:', err);
      return false;
    }
  }, [deferredPrompt]);

  const updateApp = useCallback(() => {
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.getRegistration().then((reg) => {
        if (reg?.waiting) {
          reg.waiting.postMessage({ type: 'SKIP_WAITING' });
          window.location.reload();
        }
      });
    }
  }, []);

  return {
    isInstallable: Boolean(deferredPrompt && !isInstalled),
    isInstalled,
    isOffline,
    hasUpdate,
    installApp,
    updateApp,
  };
}
