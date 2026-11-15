import React, { useState, useRef } from 'react';
import { UploadCloud, Camera, FileCode2, CheckCircle, Shield, X, Edit3 } from 'lucide-react';
import { StagedFile } from '../types';

interface UploadViewProps {
  onConfirmUpload: (files: { file: File; finalName: string; category: StagedFile['category'] }[]) => void;
}

export const UploadView: React.FC<UploadViewProps> = ({ onConfirmUpload }) => {
  const [isDragging, setIsDragging] = useState(false);
  const [stagedFiles, setStagedFiles] = useState<StagedFile[]>([]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const cameraInputRef = useRef<HTMLInputElement>(null);

  const handleFilesSelected = (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setErrorMessage(null);

    const validFiles: StagedFile[] = [];
    for (let i = 0; i < files.length; i++) {
      const file = files[i];

      // 10MB limit
      if (file.size > 10 * 1024 * 1024) {
        setErrorMessage(`"${file.name}" exceeds the 10MB limit.`);
        continue;
      }

      let previewUrl: string | undefined = undefined;
      if (file.type.startsWith('image/')) {
        previewUrl = URL.createObjectURL(file);
      }

      let defaultCategory: StagedFile['category'] = 'Other';
      const lower = file.name.toLowerCase();
      if (lower.includes('aadhaar') || lower.includes('passport') || lower.includes('id') || lower.includes('license')) {
        defaultCategory = 'Identity';
      } else if (lower.includes('bank') || lower.includes('salary') || lower.includes('tax') || lower.includes('bill')) {
        defaultCategory = 'Financial';
      } else if (lower.includes('med') || lower.includes('prescrip') || lower.includes('report') || lower.includes('lab')) {
        defaultCategory = 'Medical';
      } else if (file.type.startsWith('image/')) {
        defaultCategory = 'Personal';
      }

      validFiles.push({
        id: `staged-${Date.now()}-${i}`,
        file,
        defaultName: file.name,
        customName: file.name,
        category: defaultCategory,
        size: file.size,
        previewUrl,
      });
    }

    if (validFiles.length > 0) {
      setStagedFiles((prev) => [...prev, ...validFiles]);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFilesSelected(e.dataTransfer.files);
    }
  };

  const handleNameChange = (id: string, newName: string) => {
    setStagedFiles((prev) =>
      prev.map((item) => (item.id === id ? { ...item, customName: newName } : item))
    );
  };

  const handleCategoryChange = (id: string, category: StagedFile['category']) => {
    setStagedFiles((prev) =>
      prev.map((item) => (item.id === id ? { ...item, category } : item))
    );
  };

  const removeStagedFile = (id: string) => {
    setStagedFiles((prev) => {
      const removed = prev.find((item) => item.id === id);
      if (removed?.previewUrl) {
        URL.revokeObjectURL(removed.previewUrl);
      }
      return prev.filter((item) => item.id !== id);
    });
  };

  const handleFinalSave = () => {
    if (stagedFiles.length === 0) return;

    const payload = stagedFiles.map((item) => ({
      file: item.file,
      finalName: item.customName.trim() || item.defaultName,
      category: item.category,
    }));

    onConfirmUpload(payload);
    setStagedFiles([]);
  };

  return (
    <div className="max-w-xl mx-auto space-y-3.5 font-mono">
      <div className="text-center space-y-0.5">
        <h2 className="text-sm font-semibold text-stone-900 dark:text-white">upload to vault</h2>
        <p className="text-[11px] text-stone-500 dark:text-stone-400">
          Private &amp; encrypted • High-resolution document preservation
        </p>
      </div>

      {errorMessage && (
        <div className="p-2 bg-rose-500/10 border border-rose-500/20 rounded-lg text-rose-700 dark:text-rose-300 text-xs flex items-center justify-between">
          <span>{errorMessage}</span>
          <button onClick={() => setErrorMessage(null)}>
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* Hidden inputs */}
      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept="*/*"
        className="hidden"
        onChange={(e) => handleFilesSelected(e.target.files)}
      />

      <input
        ref={cameraInputRef}
        type="file"
        accept="image/*"
        capture="environment"
        className="hidden"
        onChange={(e) => handleFilesSelected(e.target.files)}
      />

      {stagedFiles.length === 0 ? (
        <div className="space-y-2.5">
          {/* Main Drop Area */}
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setIsDragging(true);
            }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`border-2 border-dashed rounded-xl p-7 flex flex-col items-center justify-center transition-all cursor-pointer ${
              isDragging
                ? 'border-stone-900 dark:border-white bg-stone-100 dark:bg-stone-900'
                : 'border-stone-300 dark:border-stone-800 hover:border-stone-400 dark:hover:border-stone-600 bg-white dark:bg-[#121216] shadow-val'
            }`}
          >
            <div className="w-8 h-8 rounded-lg bg-stone-100 dark:bg-stone-800 flex items-center justify-center text-stone-700 dark:text-stone-300 mb-2 border border-stone-200 dark:border-stone-700">
              <UploadCloud className="w-4 h-4" />
            </div>
            <p className="text-xs font-semibold text-stone-800 dark:text-stone-200 text-center">
              &gt; drag & drop files, or <span className="underline cursor-pointer">browse</span>
            </p>
            <p className="text-[10px] text-stone-400 mt-1">PDF, JPG, PNG, DOCX (max 10MB)</p>
          </div>

          {/* Quick Choice Action Grid */}
          <div className="grid grid-cols-2 gap-2.5">
            <button
              type="button"
              onClick={() => cameraInputRef.current?.click()}
              className="flex items-center space-x-2.5 p-3 bg-white dark:bg-[#121216] hover:bg-emerald-50/40 dark:hover:bg-emerald-950/20 border border-stone-200 dark:border-stone-800 hover:border-emerald-500/40 rounded-xl text-xs font-medium text-stone-800 dark:text-stone-200 shadow-val transition-all cursor-pointer active:scale-95 text-left group"
            >
              <div className="w-7 h-7 rounded-lg bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 flex items-center justify-center flex-shrink-0 group-hover:scale-105 transition-transform">
                <Camera className="w-4 h-4" />
              </div>
              <div className="min-w-0">
                <p className="font-semibold text-xs text-stone-900 dark:text-white">Camera Capture</p>
                <p className="text-[10px] text-stone-400">Direct instant scan</p>
              </div>
            </button>

            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="flex items-center space-x-2.5 p-3 bg-white dark:bg-[#121216] hover:bg-blue-50/40 dark:hover:bg-blue-950/20 border border-stone-200 dark:border-stone-800 hover:border-blue-500/40 rounded-xl text-xs font-medium text-stone-800 dark:text-stone-200 shadow-val transition-all cursor-pointer active:scale-95 text-left group"
            >
              <div className="w-7 h-7 rounded-lg bg-blue-500/10 text-blue-600 dark:text-blue-400 flex items-center justify-center flex-shrink-0 group-hover:scale-105 transition-transform">
                <FileCode2 className="w-4 h-4" />
              </div>
              <div className="min-w-0">
                <p className="font-semibold text-xs text-stone-900 dark:text-white">Browse Files</p>
                <p className="text-[10px] text-stone-400">PDF, JPG, PNG, DOCX</p>
              </div>
            </button>
          </div>
        </div>
      ) : (
        /* Staging Screen in Val Town file format */
        <div className="bg-white dark:bg-[#121216] border border-stone-200 dark:border-stone-800 rounded-xl p-3.5 shadow-val space-y-3 font-mono">
          <div className="flex items-center justify-between pb-2 border-b border-stone-100 dark:border-stone-800">
            <div>
              <h3 className="text-xs font-bold text-stone-900 dark:text-white">staged files for upload</h3>
              <p className="text-[10px] text-stone-400">set custom filename or accept default</p>
            </div>
            <span className="text-[10px] bg-stone-100 dark:bg-stone-800 px-2 py-0.5 rounded text-stone-600 dark:text-stone-300">
              {stagedFiles.length} item{stagedFiles.length > 1 ? 's' : ''}
            </span>
          </div>

          <div className="space-y-2.5 max-h-64 overflow-y-auto pr-1">
            {stagedFiles.map((item) => (
              <div
                key={item.id}
                className="p-2.5 bg-stone-50 dark:bg-[#181820] rounded-lg border border-stone-200/80 dark:border-stone-800 space-y-2"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2 min-w-0">
                    {item.previewUrl ? (
                      <img
                        src={item.previewUrl}
                        alt="Preview"
                        className="w-7 h-7 rounded object-cover border border-stone-200 dark:border-stone-700"
                      />
                    ) : (
                      <div className="w-7 h-7 rounded bg-white dark:bg-[#121216] flex items-center justify-center text-stone-500 border border-stone-200 dark:border-stone-700">
                        <FileCode2 className="w-3.5 h-3.5" />
                      </div>
                    )}
                    <div className="min-w-0">
                      <p className="text-[10px] text-stone-400 truncate">src: {item.defaultName}</p>
                      <p className="text-[10px] text-stone-500">{(item.size / (1024 * 1024)).toFixed(2)} MB</p>
                    </div>
                  </div>

                  <button
                    onClick={() => removeStagedFile(item.id)}
                    className="p-1 text-stone-400 hover:text-rose-600 transition-colors"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </div>

                {/* File Name Field */}
                <div>
                  <label className="block text-[10px] text-stone-500 mb-0.5 flex items-center">
                    <Edit3 className="w-3 h-3 mr-1 text-stone-400" /> filename:
                  </label>
                  <input
                    type="text"
                    value={item.customName}
                    onChange={(e) => handleNameChange(item.id, e.target.value)}
                    placeholder={item.defaultName}
                    className="w-full bg-white dark:bg-[#121216] border border-stone-200 dark:border-stone-700 rounded px-2 py-1 text-xs text-stone-900 dark:text-white font-mono focus:outline-none focus:border-stone-400 transition-colors"
                  />
                </div>

                {/* Category Selection with Minimalist Color Accents */}
                <div className="flex items-center space-x-1">
                  <span className="text-[10px] text-stone-400">category:</span>
                  {(['Identity', 'Financial', 'Medical', 'Personal', 'Other'] as const).map((cat) => {
                    const isSelected = item.category === cat;
                    let activeColor = 'bg-stone-900 text-white dark:bg-white dark:text-stone-950 font-bold';
                    if (isSelected) {
                      if (cat === 'Identity') activeColor = 'bg-blue-600 text-white font-bold shadow-xs';
                      else if (cat === 'Financial') activeColor = 'bg-emerald-600 text-white font-bold shadow-xs';
                      else if (cat === 'Medical') activeColor = 'bg-teal-600 text-white font-bold shadow-xs';
                      else if (cat === 'Personal') activeColor = 'bg-purple-600 text-white font-bold shadow-xs';
                    }
                    return (
                      <button
                        key={cat}
                        type="button"
                        onClick={() => handleCategoryChange(item.id, cat)}
                        className={`text-[9px] px-1.5 py-0.5 rounded font-mono transition-colors ${
                          isSelected
                            ? activeColor
                            : 'bg-white dark:bg-[#121216] text-stone-500 border border-stone-200 dark:border-stone-700 hover:border-stone-400'
                        }`}
                      >
                        {cat.toLowerCase()}
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>

          {/* Action Footer */}
          <div className="pt-2 flex items-center justify-between gap-2 border-t border-stone-100 dark:border-stone-800">
            <button
              type="button"
              onClick={() => setStagedFiles([])}
              className="px-2.5 py-1 rounded text-xs text-stone-500 hover:text-stone-900 dark:hover:text-white transition-colors"
            >
              cancel
            </button>

            <div className="flex items-center space-x-1.5">
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="px-2.5 py-1 rounded text-xs bg-stone-100 dark:bg-stone-800 border border-stone-200 dark:border-stone-700 text-stone-700 dark:text-stone-300 hover:text-stone-900"
              >
                + add
              </button>

              <button
                type="button"
                onClick={handleFinalSave}
                className="flex items-center space-x-1 px-3 py-1 rounded text-xs font-semibold bg-stone-900 text-white dark:bg-white dark:text-stone-950 shadow-sm hover:opacity-90"
              >
                <CheckCircle className="w-3 h-3 text-emerald-500" />
                <span>upload to vault</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Security Reassurance */}
      <div className="bg-white dark:bg-[#121216] border border-stone-200 dark:border-stone-800 rounded-lg p-2.5 flex items-center space-x-2 text-[10px] text-stone-500 dark:text-stone-400">
        <Shield className="w-3.5 h-3.5 text-stone-500 dark:text-stone-400 flex-shrink-0" />
        <span>End-to-end encrypted • Verified file integrity • Stored securely in your private vault</span>
      </div>
    </div>
  );
};
