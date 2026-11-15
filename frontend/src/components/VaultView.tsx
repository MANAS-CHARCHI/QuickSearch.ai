import React, { useState } from 'react';
import { Search, FileCode2, Download, Trash2, Eye, LayoutGrid, List, Edit2, Check, X } from 'lucide-react';
import { DocumentFile } from '../types';

interface VaultViewProps {
  documents: DocumentFile[];
  onDeleteDocument: (id: string) => void;
  onPreviewDocument: (doc: DocumentFile) => void;
  onRenameDocument: (id: string, newName: string) => void;
}

export const VaultView: React.FC<VaultViewProps> = ({
  documents,
  onDeleteDocument,
  onPreviewDocument,
  onRenameDocument,
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('All');
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');

  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState<string>('');

  const categories = ['All', 'Identity', 'Financial', 'Medical', 'Personal'];

  const filteredDocs = documents.filter((doc) => {
    const matchesSearch =
      doc.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (doc.documentType && doc.documentType.toLowerCase().includes(searchTerm.toLowerCase())) ||
      (doc.description && doc.description.toLowerCase().includes(searchTerm.toLowerCase()));

    const matchesCategory =
      selectedCategory === 'All' || doc.category === selectedCategory;

    return matchesSearch && matchesCategory;
  });

  const startRename = (doc: DocumentFile) => {
    setRenamingId(doc.id);
    setRenameValue(doc.name);
  };

  const handleSaveRename = (id: string) => {
    if (renameValue.trim()) {
      onRenameDocument(id, renameValue.trim());
    }
    setRenamingId(null);
  };

  return (
    <div className="space-y-3.5">
      {/* Top Search, Category & View Controls */}
      <div className="flex flex-col sm:flex-row gap-2.5 items-stretch sm:items-center justify-between pb-1 font-mono">
        {/* Search Input */}
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-stone-400" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="filter vault (/search)..."
            className="w-full bg-white dark:bg-[#121216] border border-stone-200 dark:border-stone-800 rounded-lg pl-7 pr-3 py-1.5 text-xs text-stone-900 dark:text-white placeholder-stone-400 focus:outline-none focus:border-stone-400 dark:focus:border-stone-600 transition-colors font-mono"
          />
        </div>

        {/* Categories & View Switcher */}
        <div className="flex items-center justify-between sm:justify-end gap-2 overflow-x-auto text-xs">
          <div className="flex items-center space-x-1">
            {categories.map((cat) => (
              <button
                key={cat}
                onClick={() => setSelectedCategory(cat)}
                className={`px-2.5 py-1 rounded text-xs font-mono transition-all ${
                  selectedCategory === cat
                    ? 'bg-stone-900 text-white dark:bg-white dark:text-stone-950 font-semibold shadow-xs'
                    : 'bg-white dark:bg-[#121216] text-stone-600 dark:text-stone-400 hover:text-stone-900 dark:hover:text-stone-200 border border-stone-200 dark:border-stone-800'
                }`}
              >
                {cat.toLowerCase()}
              </button>
            ))}
          </div>

          <div className="hidden sm:flex items-center bg-stone-100 dark:bg-stone-900 p-0.5 rounded border border-stone-200 dark:border-stone-800">
            <button
              onClick={() => setViewMode('grid')}
              className={`p-1 rounded transition-all ${
                viewMode === 'grid' ? 'bg-white dark:bg-stone-800 text-stone-900 dark:text-white shadow-sm' : 'text-stone-400'
              }`}
            >
              <LayoutGrid className="w-3 h-3" />
            </button>
            <button
              onClick={() => setViewMode('list')}
              className={`p-1 rounded transition-all ${
                viewMode === 'list' ? 'bg-white dark:bg-stone-800 text-stone-900 dark:text-white shadow-sm' : 'text-stone-400'
              }`}
            >
              <List className="w-3 h-3" />
            </button>
          </div>
        </div>
      </div>

      {/* Document Grid / List without embedded images or colored borders */}
      {filteredDocs.length === 0 ? (
        <div className="py-16 text-center border border-dashed border-stone-200 dark:border-stone-800 rounded-xl bg-white/40 dark:bg-[#121216]/40 font-mono">
          <FileCode2 className="w-7 h-7 text-stone-300 dark:text-stone-600 mx-auto mb-2" />
          <p className="text-xs text-stone-500 dark:text-stone-400">no files matching query</p>
        </div>
      ) : viewMode === 'grid' ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {filteredDocs.map((doc) => (
            <div
              key={doc.id}
              className="bg-white dark:bg-[#121216] border border-stone-200 dark:border-stone-800 hover:border-stone-300 dark:hover:border-stone-700 rounded-xl p-4 transition-all flex flex-col justify-between shadow-val hover:shadow-val-hover group"
            >
              <div>
                {/* Vault City Handle Header */}
                <div className="flex items-center justify-between pb-2 mb-2.5 border-b border-stone-100 dark:border-stone-800/80 font-mono text-[10px]">
                  <span className="text-stone-400 truncate max-w-[190px]">
                    @vault.city/{doc.category?.toLowerCase() || 'docs'}
                  </span>
                  {doc.isPii && (
                    <span className="px-1.5 py-0.2 rounded bg-amber-500/10 text-amber-700 dark:text-amber-400 border border-amber-500/25 font-bold text-[9px]">
                      PII
                    </span>
                  )}
                </div>

                {/* Name & Inline Rename */}
                <div>
                  {renamingId === doc.id ? (
                    <div className="flex items-center space-x-1 my-1">
                      <input
                        type="text"
                        value={renameValue}
                        onChange={(e) => setRenameValue(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && handleSaveRename(doc.id)}
                        className="bg-stone-50 dark:bg-stone-900 border border-stone-300 dark:border-stone-600 rounded px-1.5 py-0.5 text-xs text-stone-900 dark:text-white font-mono w-full"
                        autoFocus
                      />
                      <button onClick={() => handleSaveRename(doc.id)} className="p-1 text-emerald-600">
                        <Check className="w-3.5 h-3.5" />
                      </button>
                      <button onClick={() => setRenamingId(null)} className="p-1 text-stone-400">
                        <X className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ) : (
                    <h3
                      onClick={() => onPreviewDocument(doc)}
                      className="text-xs font-semibold text-stone-900 dark:text-white font-mono truncate cursor-pointer hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors"
                      title="Click to view document"
                    >
                      {doc.name}
                    </h3>
                  )}

                  <p className="text-[10px] text-stone-400 font-mono mt-0.5">
                    {(doc.size / (1024 * 1024)).toFixed(2)} MB • {doc.documentType || 'document'}
                  </p>
                </div>

                {/* Just Description as requested: "just the name , description is enaught" */}
                {doc.description && (
                  <p className="mt-2.5 text-xs text-stone-600 dark:text-stone-300 leading-relaxed font-sans line-clamp-3">
                    {doc.description}
                  </p>
                )}
              </div>

              {/* Actions Footer */}
              <div className="mt-3.5 pt-2.5 border-t border-stone-100 dark:border-stone-800/60 flex items-center justify-between font-mono text-[10px] text-stone-400">
                <span>{new Date(doc.uploadedAt).toLocaleDateString()}</span>

                <div className="flex items-center space-x-1">
                  <button
                    onClick={() => startRename(doc)}
                    title="Rename"
                    className="p-1 rounded text-stone-400 hover:text-stone-900 dark:hover:text-white hover:bg-stone-100 dark:hover:bg-stone-800 transition-colors"
                  >
                    <Edit2 className="w-3 h-3" />
                  </button>
                  <button
                    onClick={() => onPreviewDocument(doc)}
                    title="Preview"
                    className="p-1 rounded text-stone-400 hover:text-stone-900 dark:hover:text-white hover:bg-stone-100 dark:hover:bg-stone-800 transition-colors"
                  >
                    <Eye className="w-3 h-3" />
                  </button>
                  <button
                    title="Download"
                    className="p-1 rounded text-stone-400 hover:text-stone-900 dark:hover:text-white hover:bg-stone-100 dark:hover:bg-stone-800 transition-colors"
                  >
                    <Download className="w-3 h-3" />
                  </button>
                  <button
                    onClick={() => onDeleteDocument(doc.id)}
                    title="Delete"
                    className="p-1 rounded text-stone-400 hover:text-rose-600 dark:hover:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-500/10 transition-colors"
                  >
                    <Trash2 className="w-3 h-3" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        /* List Mode */
        <div className="bg-white dark:bg-[#121216] border border-stone-200 dark:border-stone-800 rounded-xl overflow-hidden shadow-val divide-y divide-stone-100 dark:divide-stone-800 font-mono">
          {filteredDocs.map((doc) => (
            <div key={doc.id} className="p-3 sm:px-4 flex items-center justify-between hover:bg-stone-50 dark:hover:bg-stone-900/40 transition-colors text-xs">
              <div className="flex items-center space-x-3 min-w-0 flex-1">
                <FileCode2 className="w-4 h-4 text-stone-400 flex-shrink-0" />
                <div className="min-w-0 flex-1">
                  {renamingId === doc.id ? (
                    <div className="flex items-center space-x-1 max-w-xs">
                      <input
                        type="text"
                        value={renameValue}
                        onChange={(e) => setRenameValue(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && handleSaveRename(doc.id)}
                        className="bg-stone-50 dark:bg-stone-900 border border-stone-300 dark:border-stone-600 rounded px-1.5 py-0.5 text-xs text-stone-900 dark:text-white w-full"
                        autoFocus
                      />
                      <button onClick={() => handleSaveRename(doc.id)} className="p-1 text-emerald-600">
                        <Check className="w-3 h-3" />
                      </button>
                      <button onClick={() => setRenamingId(null)} className="p-1 text-stone-400">
                        <X className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ) : (
                    <p
                      onClick={() => onPreviewDocument(doc)}
                      className="text-xs font-semibold text-stone-900 dark:text-white truncate cursor-pointer hover:text-indigo-600 dark:hover:text-indigo-400"
                      title="Click to view document"
                    >
                      {doc.name}
                    </p>
                  )}
                  <p className="text-[10px] text-stone-400 flex items-center gap-1.5 mt-0.5">
                    <span>{(doc.size / (1024 * 1024)).toFixed(2)} MB</span>
                    <span>•</span>
                    <span>{doc.documentType}</span>
                    {doc.description && (
                      <>
                        <span>•</span>
                        <span className="truncate max-w-xs text-stone-500 dark:text-stone-400 font-sans">{doc.description}</span>
                      </>
                    )}
                  </p>
                </div>
              </div>

              <div className="flex items-center space-x-1 flex-shrink-0 ml-2">
                {doc.isPii && (
                  <span className="text-[9px] font-bold text-amber-700 dark:text-amber-300 bg-amber-500/10 px-1.5 py-0.5 rounded">
                    PII
                  </span>
                )}
                <button onClick={() => startRename(doc)} className="p-1 text-stone-400 hover:text-stone-900 dark:hover:text-white">
                  <Edit2 className="w-3 h-3" />
                </button>
                <button onClick={() => onPreviewDocument(doc)} className="p-1 text-stone-400 hover:text-stone-900 dark:hover:text-white">
                  <Eye className="w-3 h-3" />
                </button>
                <button onClick={() => onDeleteDocument(doc.id)} className="p-1 text-stone-400 hover:text-rose-600">
                  <Trash2 className="w-3 h-3" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
