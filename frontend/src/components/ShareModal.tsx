import React, { useState } from 'react';
import {
  X,
  Share2,
  Mail,
  MessageCircle,
  Copy,
  Check,
  FileText,
  ExternalLink,
  Layers,
} from 'lucide-react';
import { DocumentFile } from '../types';

interface ShareModalProps {
  document: DocumentFile | null;
  onClose: () => void;
  activePageIdx?: number;
}

export const ShareModal: React.FC<ShareModalProps> = ({
  document: doc,
  onClose,
  activePageIdx = 0,
}) => {
  const [copiedType, setCopiedType] = useState<string | null>(null);
  const [isSharingFile, setIsSharingFile] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  if (!doc) return null;

  const currentImageUrl =
    (doc.pages && doc.pages[activePageIdx]?.url) || doc.previewUrl || '';

  const isImageDoc = doc.mimeType?.startsWith('image/');

  // Helper to fetch file object from preview URL
  const getShareableFile = async (): Promise<File | null> => {
    if (!currentImageUrl) return null;
    try {
      const res = await fetch(currentImageUrl, { credentials: 'include' });
      if (!res.ok) return null;
      const blob = await res.blob();
      const isPdf = doc.mimeType?.includes('pdf');
      const ext = isPdf ? 'pdf' : blob.type.includes('png') ? 'png' : 'jpg';
      const cleanName = doc.name.replace(/\.[^/.]+$/, '');
      const filename = `${cleanName}.${ext}`;
      return new File([blob], filename, {
        type: blob.type || (isPdf ? 'application/pdf' : 'image/jpeg'),
      });
    } catch (err) {
      console.warn('Could not prepare file for direct sharing:', err);
      return null;
    }
  };

  // 1. Direct System Share (Sends actual File/Image directly to WhatsApp, Mail, AirDrop, etc.)
  const handleSystemShare = async () => {
    setIsSharingFile(true);
    setStatusMessage(null);

    const shareData: ShareData = {
      title: doc.name,
      text: `${doc.name} (${doc.documentType || 'Vault Document'}) - Shared from Vault City`,
    };

    try {
      const file = await getShareableFile();
      if (file && navigator.canShare && navigator.canShare({ files: [file] })) {
        await navigator.share({
          ...shareData,
          files: [file],
        });
        setStatusMessage('File shared successfully!');
        return;
      }

      if (navigator.share) {
        await navigator.share(shareData);
        setStatusMessage('Shared successfully!');
        return;
      }

      // Fallback if Web Share API is unavailable
      await handleCopyDetails();
    } catch (err: any) {
      if (err.name !== 'AbortError') {
        setStatusMessage('System share not supported or cancelled.');
      }
    } finally {
      setIsSharingFile(false);
    }
  };

  // 2. Direct WhatsApp Share
  const handleWhatsAppShare = () => {
    const text = encodeURIComponent(
      `📄 *${doc.name}*\n` +
        `📂 Category: ${doc.category || 'Personal Vault'}\n` +
        `🔖 Type: ${doc.documentType || 'Document'}\n` +
        (doc.description ? `📝 ${doc.description}\n\n` : '\n') +
        `🔒 Shared securely via Vault City (@vault.city/${doc.category?.toLowerCase() || 'docs'})`
    );
    const waUrl = `https://api.whatsapp.com/send?text=${text}`;
    window.open(waUrl, '_blank', 'noopener,noreferrer');
  };

  // 3. Direct Email / Mail Share
  const handleMailShare = () => {
    const subject = encodeURIComponent(`[Vault City] ${doc.name}`);
    const body = encodeURIComponent(
      `Hello,\n\nSharing personal document:\n\n` +
        `Document Name: ${doc.name}\n` +
        `Category: ${doc.category || 'General'}\n` +
        `Document Type: ${doc.documentType || 'Document'}\n` +
        (doc.description ? `Description: ${doc.description}\n\n` : '\n') +
        `---\n` +
        `Vault City - Intelligent Personal Document Cloud\n` +
        `https://vault.city`
    );
    window.location.href = `mailto:?subject=${subject}&body=${body}`;
  };

  // 4. Copy Image Directly to Clipboard (So user can paste straight into WhatsApp Web or Mail)
  const handleCopyImage = async () => {
    if (!currentImageUrl) return;
    try {
      const res = await fetch(currentImageUrl, { credentials: 'include' });
      if (!res.ok) {
        await handleCopyDetails();
        return;
      }
      const blob = await res.blob();

      // Modern ClipboardItem supports image/png
      if (blob.type.includes('png') || blob.type.includes('jpeg') || blob.type.includes('image')) {
        // Convert to PNG if needed for maximum OS clipboard compatibility
        const objectUrl = URL.createObjectURL(blob);
        try {
          const canvas = document.createElement('canvas');
          const img = new Image();
          img.src = objectUrl;
          await new Promise((resolve, reject) => {
            img.onload = resolve;
            img.onerror = reject;
          });
          canvas.width = img.naturalWidth || 600;
          canvas.height = img.naturalHeight || 400;
          const ctx = canvas.getContext('2d');
          if (ctx) {
            ctx.drawImage(img, 0, 0);
            canvas.toBlob(async (pngBlob) => {
              if (pngBlob) {
                await navigator.clipboard.write([
                  new ClipboardItem({ 'image/png': pngBlob }),
                ]);
                setCopiedType('image');
                setTimeout(() => setCopiedType(null), 2500);
              }
            }, 'image/png');
          }
        } finally {
          URL.revokeObjectURL(objectUrl);
        }
      } else {
        await handleCopyDetails();
      }
    } catch (err) {
      console.warn('Image clipboard write error, copying summary text instead:', err);
      await handleCopyDetails();
    }
  };

  // 5. Copy Text Details to Clipboard
  const handleCopyDetails = async () => {
    const text =
      `📄 ${doc.name} (${doc.documentType || 'Document'})\n` +
      `Category: ${doc.category || 'General'}\n` +
      (doc.description ? `Description: ${doc.description}\n` : '') +
      `Vault Reference: @vault.city/${doc.category?.toLowerCase() || 'docs'}/${doc.id}`;

    await navigator.clipboard.writeText(text);
    setCopiedType('text');
    setTimeout(() => setCopiedType(null), 2500);
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/60 dark:bg-black/85 backdrop-blur-md flex items-center justify-center p-3 sm:p-4 animate-in fade-in duration-150">
      <div className="bg-white dark:bg-[#1C1510] border border-orange-200/80 dark:border-[#382A20] rounded-2xl max-w-md w-full p-5 space-y-4 shadow-2xl font-mono text-xs">
        {/* Header */}
        <div className="flex items-center justify-between pb-3 border-b border-stone-100 dark:border-stone-800">
          <div className="flex items-center space-x-2">
            <div className="p-1.5 bg-orange-500/10 dark:bg-orange-500/20 rounded-lg text-orange-600 dark:text-orange-400">
              <Share2 className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-stone-900 dark:text-white">Share Document</h3>
              <p className="text-[10px] text-stone-400 font-sans">
                Share directly without manual downloading
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-stone-400 hover:text-stone-900 dark:hover:text-white hover:bg-stone-100 dark:hover:bg-stone-800 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Document Card Preview */}
        <div className="flex items-center space-x-3 p-3 bg-stone-50 dark:bg-[#140E0A] rounded-xl border border-stone-200/60 dark:border-stone-800">
          {isImageDoc && currentImageUrl ? (
            <img
              src={currentImageUrl}
              alt={doc.name}
              className="w-12 h-12 object-cover rounded-lg border border-stone-200 dark:border-stone-800 shrink-0"
            />
          ) : (
            <div className="w-12 h-12 rounded-lg bg-orange-100 dark:bg-[#251A12] flex items-center justify-center text-orange-600 shrink-0">
              <FileText className="w-6 h-6" />
            </div>
          )}
          <div className="min-w-0 flex-1">
            <p className="font-bold text-stone-900 dark:text-white truncate text-xs">{doc.name}</p>
            <div className="flex items-center space-x-1.5 text-[10px] text-stone-400 mt-0.5">
              <span>{doc.category || 'Document'}</span>
              <span>•</span>
              <span>{(doc.size / (1024 * 1024)).toFixed(2)} MB</span>
              {doc.pages && doc.pages.length > 1 && (
                <>
                  <span>•</span>
                  <span className="flex items-center space-x-0.5 text-stone-500 dark:text-stone-300">
                    <Layers className="w-2.5 h-2.5" />
                    <span>Page {activePageIdx + 1}/{doc.pages.length}</span>
                  </span>
                </>
              )}
            </div>
          </div>
        </div>

        {/* Primary Action: Direct File Share (AirDrop, WhatsApp, Mail, System) */}
        <button
          onClick={handleSystemShare}
          disabled={isSharingFile}
          className="w-full py-2.5 px-4 bg-orange-600 hover:bg-orange-700 text-white rounded-xl font-semibold flex items-center justify-center space-x-2 shadow-xs transition-all active:scale-[0.99] cursor-pointer"
        >
          <Share2 className="w-4 h-4" />
          <span>{isSharingFile ? 'Preparing File...' : 'Direct Share File (AirDrop / Apps)'}</span>
        </button>

        {/* Social / App Direct Channels */}
        <div className="grid grid-cols-2 gap-2 pt-1">
          {/* WhatsApp Button */}
          <button
            onClick={handleWhatsAppShare}
            className="flex items-center justify-center space-x-2 py-2 px-3 bg-[#25D366]/10 hover:bg-[#25D366]/20 border border-[#25D366]/30 text-[#25D366] rounded-xl font-medium transition-colors cursor-pointer"
          >
            <MessageCircle className="w-4 h-4" />
            <span>WhatsApp</span>
          </button>

          {/* Email / Mail Button */}
          <button
            onClick={handleMailShare}
            className="flex items-center justify-center space-x-2 py-2 px-3 bg-blue-500/10 hover:bg-blue-500/20 border border-blue-500/30 text-blue-600 dark:text-blue-400 rounded-xl font-medium transition-colors cursor-pointer"
          >
            <Mail className="w-4 h-4" />
            <span>Mail</span>
          </button>
        </div>

        {/* Copy Options */}
        <div className="grid grid-cols-2 gap-2">
          {/* Copy Image directly to Clipboard for instant Paste */}
          <button
            onClick={handleCopyImage}
            className="flex items-center justify-center space-x-2 py-2 px-3 bg-stone-100 hover:bg-stone-200 dark:bg-stone-900 dark:hover:bg-stone-800 border border-stone-200 dark:border-stone-800 text-stone-700 dark:text-stone-300 rounded-xl font-medium transition-colors cursor-pointer"
          >
            {copiedType === 'image' ? (
              <>
                <Check className="w-3.5 h-3.5 text-emerald-500" />
                <span className="text-emerald-600 dark:text-emerald-400">Image Copied!</span>
              </>
            ) : (
              <>
                <Copy className="w-3.5 h-3.5 text-stone-400" />
                <span>Copy Image</span>
              </>
            )}
          </button>

          {/* Copy Details */}
          <button
            onClick={handleCopyDetails}
            className="flex items-center justify-center space-x-2 py-2 px-3 bg-stone-100 hover:bg-stone-200 dark:bg-stone-900 dark:hover:bg-stone-800 border border-stone-200 dark:border-stone-800 text-stone-700 dark:text-stone-300 rounded-xl font-medium transition-colors cursor-pointer"
          >
            {copiedType === 'text' ? (
              <>
                <Check className="w-3.5 h-3.5 text-emerald-500" />
                <span className="text-emerald-600 dark:text-emerald-400">Copied!</span>
              </>
            ) : (
              <>
                <ExternalLink className="w-3.5 h-3.5 text-stone-400" />
                <span>Copy Info</span>
              </>
            )}
          </button>
        </div>

        {/* Status Feedback */}
        {statusMessage && (
          <p className="text-[10px] text-center text-stone-400 dark:text-stone-500 pt-1 font-mono">
            {statusMessage}
          </p>
        )}
      </div>
    </div>
  );
};
