import React, { useState } from 'react';
import { Download, X, Smartphone, Laptop } from 'lucide-react';
import { usePwa } from '../pwa/usePwa';

interface PwaInstallButtonProps {
  variant?: 'floating' | 'nav' | 'inline';
  className?: string;
}

export const PwaInstallButton: React.FC<PwaInstallButtonProps> = ({
  variant = 'floating',
  className = '',
}) => {
  const { isInstallable, isInstalled, installApp } = usePwa();
  const [showInstructions, setShowInstructions] = useState(false);
  const [isDismissed, setIsDismissed] = useState(false);

  // STRICT REQUIREMENT: Only render on browser screens (hide when already installed or dismissed)
  if (isInstalled || (variant === 'floating' && isDismissed)) {
    return null;
  }

  const handleInstallClick = async () => {
    if (isInstallable) {
      const installed = await installApp();
      if (!installed) {
        setShowInstructions(true);
      }
    } else {
      setShowInstructions(true);
    }
  };

  const isIOS =
    typeof navigator !== 'undefined' &&
    /iPad|iPhone|iPod/.test(navigator.userAgent) &&
    !(window as any).MSStream;

  // Instructions Modal (rendered when native install prompt isn't directly triggered)
  const renderInstructionsModal = () => (
    showInstructions && (
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-in fade-in duration-150">
        <div className="bg-white dark:bg-[#1C1510] border border-orange-200/80 dark:border-[#2D2118] rounded-2xl max-w-sm w-full p-5 shadow-2xl space-y-4 font-mono text-stone-900 dark:text-white">
          <div className="flex items-center justify-between pb-2 border-b border-orange-100 dark:border-[#2D2118]">
            <div className="flex items-center space-x-2">
              <span className="w-6 h-6 rounded-lg bg-orange-600 flex items-center justify-center text-white">
                <Download className="w-3.5 h-3.5" />
              </span>
              <h3 className="text-sm font-bold tracking-tight">Install Vault City PWA</h3>
            </div>
            <button
              type="button"
              onClick={() => setShowInstructions(false)}
              className="p-1 rounded-md text-stone-400 hover:text-stone-700 dark:hover:text-stone-200 cursor-pointer"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <p className="text-xs text-stone-600 dark:text-stone-300">
            Install Vault City as a native application on your device for instant offline access and dedicated window mode:
          </p>

          {isIOS ? (
            <div className="space-y-2 text-xs bg-orange-50/50 dark:bg-[#251A12] p-3 rounded-xl border border-orange-200/60 dark:border-[#382A20]">
              <div className="flex items-start space-x-2">
                <span className="text-orange-600 font-bold">1.</span>
                <span>Tap the <strong>Share</strong> button at the bottom of Safari.</span>
              </div>
              <div className="flex items-start space-x-2">
                <span className="text-orange-600 font-bold">2.</span>
                <span>Scroll down and tap <strong>'Add to Home Screen'</strong>.</span>
              </div>
            </div>
          ) : (
            <div className="space-y-2 text-xs bg-orange-50/50 dark:bg-[#251A12] p-3 rounded-xl border border-orange-200/60 dark:border-[#382A20]">
              <div className="flex items-start space-x-2">
                <Smartphone className="w-4 h-4 text-orange-500 shrink-0 mt-0.5" />
                <span><strong>Mobile Chrome/Edge:</strong> Tap menu (⋮) &gt; <strong>Install app</strong> or <strong>Add to Home screen</strong>.</span>
              </div>
              <div className="flex items-start space-x-2">
                <Laptop className="w-4 h-4 text-orange-500 shrink-0 mt-0.5" />
                <span><strong>Desktop Chrome/Edge:</strong> Click the <strong>Install</strong> icon in the address bar (top right) or menu (⋮) &gt; <strong>Install Vault City</strong>.</span>
              </div>
            </div>
          )}

          <div className="flex justify-end pt-1">
            <button
              type="button"
              onClick={() => setShowInstructions(false)}
              className="w-full py-2 bg-orange-600 hover:bg-orange-700 text-white rounded-lg text-xs font-bold transition-colors cursor-pointer"
            >
              Got it
            </button>
          </div>
        </div>
      </div>
    )
  );

  // Floating variant: small, beautiful floating pill in bottom-right corner of browser screen
  if (variant === 'floating') {
    return (
      <>
        <div
          className={`fixed bottom-20 md:bottom-6 right-3 sm:right-6 z-40 flex items-center shadow-lg rounded-full bg-stone-900/90 dark:bg-[#1E1611]/95 text-white backdrop-blur-md border border-orange-500/30 p-1 sm:p-1.5 transition-all hover:scale-[1.02] active:scale-[0.98] ${className}`}
        >
          <button
            type="button"
            onClick={handleInstallClick}
            title="Download & Install Vault City PWA"
            className="flex items-center space-x-2 pl-1.5 pr-2.5 py-1 text-xs font-mono font-medium cursor-pointer focus:outline-none"
          >
            <span className="flex items-center justify-center w-6 h-6 rounded-full bg-orange-600 text-white shrink-0 shadow-sm animate-pulse">
              <Download className="w-3.5 h-3.5" />
            </span>
            <span className="font-semibold text-white tracking-tight">
              Download PWA
            </span>
          </button>

          <button
            type="button"
            onClick={() => setIsDismissed(true)}
            title="Dismiss"
            className="p-1 rounded-full text-stone-400 hover:text-white hover:bg-stone-800 dark:hover:bg-stone-700/50 transition-colors cursor-pointer mr-0.5"
          >
            <X className="w-3 h-3" />
          </button>
        </div>

        {renderInstructionsModal()}
      </>
    );
  }

  // Nav / Header variant: small download symbol ONLY (matches icon buttons like theme toggle)
  return (
    <>
      <button
        type="button"
        onClick={handleInstallClick}
        title="Download Vault City PWA"
        className={`p-1.5 rounded-md bg-orange-50/60 dark:bg-[#1C1510] border border-orange-200/60 dark:border-[#2D2118] text-orange-600 dark:text-orange-400 hover:text-orange-700 dark:hover:text-orange-300 transition-all cursor-pointer font-mono flex items-center justify-center ${className}`}
      >
        <Download className="w-3.5 h-3.5" />
      </button>

      {renderInstructionsModal()}
    </>
  );
};
