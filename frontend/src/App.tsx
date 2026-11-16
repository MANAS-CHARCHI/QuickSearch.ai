import { useState, useEffect } from 'react';
import { Navigation } from './components/Navigation';
import { VaultView } from './components/VaultView';
import { UploadView } from './components/UploadView';
import { ChatView } from './components/ChatView';
import { ActivityView } from './components/ActivityView';
import { SettingsView } from './components/SettingsView';
import { AuthView } from './components/AuthView';
import { TabType, DocumentFile, ChatMessage, ActivityItem, StagedFile, UserProfile, StagedPage, DocumentPage } from './types';
import { checkHealth } from './services/api';
import { X, FileText, Download, ChevronLeft, ChevronRight, Layers } from 'lucide-react';

export function App() {
  // Requirement: AI Assistant chatbot is the default active view on start
  const [currentTab, setCurrentTab] = useState<TabType>('chat');
  const [previewDoc, setPreviewDoc] = useState<DocumentFile | null>(null);
  const [activePageIdx, setActivePageIdx] = useState<number>(0);

  // Day / Night Theme State (defaults to clean Day Mode)
  const [isDark, setIsDark] = useState<boolean>(() => {
    const saved = localStorage.getItem('vault_theme');
    if (saved) return saved === 'dark';
    return false;
  });

  useEffect(() => {
    const root = document.documentElement;
    if (isDark) {
      root.classList.add('dark');
      localStorage.setItem('vault_theme', 'dark');
    } else {
      root.classList.remove('dark');
      localStorage.setItem('vault_theme', 'light');
    }
  }, [isDark]);

  const toggleTheme = () => setIsDark((prev) => !prev);

  // User Authentication State
  const [currentUser, setCurrentUser] = useState<UserProfile | null>(() => {
    const saved = localStorage.getItem('vault_user');
    if (saved) {
      try {
        return JSON.parse(saved);
      } catch {
        return null;
      }
    }
    // Start on Auth page to let user experience login / sign up / password reset
    return null;
  });

  const handleLoginSuccess = (user: UserProfile) => {
    setCurrentUser(user);
    localStorage.setItem('vault_user', JSON.stringify(user));
  };

  const handleLogout = () => {
    setCurrentUser(null);
    localStorage.removeItem('vault_user');
  };

  const [systemStatus, setSystemStatus] = useState({
    postgres: 'connected',
    chromadb: 'connected',
  });

  const [documents, setDocuments] = useState<DocumentFile[]>([
    {
      id: 'doc-1',
      name: 'aadhaar_card_national_id.pdf',
      originalName: 'aadhaar_card_front_and_back.pdf',
      size: 1.8 * 1024 * 1024,
      mimeType: 'application/pdf',
      uploadedAt: '2026-11-15T10:30:00Z',
      status: 'indexed',
      documentType: 'Aadhaar Card (Front & Back)',
      category: 'Identity',
      description: 'UIDAI biometric identity card bundle (Front: 12-digit UID & DOB; Back: Permanent Address & Father Name)',
      isPii: true,
      previewUrl: '/samples/aadhaar-preview.svg',
      thumbnailUrl: '/samples/aadhaar-preview.svg',
      pageCount: 2,
      pages: [
        { pageNumber: 1, url: '/samples/aadhaar-preview.svg', name: 'Front (Identity & UID)', size: 0.9 * 1024 * 1024 },
        { pageNumber: 2, url: '/samples/aadhaar-preview.svg', name: 'Back (Address & Care of)', size: 0.9 * 1024 * 1024 },
      ],
    },
    {
      id: 'doc-2',
      name: 'passport_scan.jpg',
      originalName: 'passport_scan.jpg',
      size: 2.1 * 1024 * 1024,
      mimeType: 'image/jpeg',
      uploadedAt: '2026-11-15T11:15:00Z',
      status: 'indexed',
      documentType: 'Passport',
      category: 'Identity',
      description: 'Republic of India passport bio-page with document number and expiry date',
      isPii: true,
      previewUrl: '/samples/passport-preview.svg',
      thumbnailUrl: '/samples/passport-preview.svg',
    },
    {
      id: 'doc-3',
      name: 'medical_report_apollo.pdf',
      originalName: 'blood_panel_lab_results.pdf',
      size: 0.8 * 1024 * 1024,
      mimeType: 'application/pdf',
      uploadedAt: '2026-11-15T14:20:00Z',
      status: 'indexed',
      documentType: 'Medical Lab Report',
      category: 'Medical',
      description: 'Apollo Diagnostics comprehensive pathology panel with Hb, glucose & lipid levels',
      isPii: true,
      previewUrl: '/samples/medical-report-preview.svg',
      thumbnailUrl: '/samples/medical-report-preview.svg',
    },
    {
      id: 'doc-4',
      name: 'annual_tax_return_form16.pdf',
      originalName: 'ITR_acknowledgement_2026.pdf',
      size: 1.1 * 1024 * 1024,
      mimeType: 'application/pdf',
      uploadedAt: '2026-11-15T16:45:00Z',
      status: 'indexed',
      documentType: 'Tax Statement',
      category: 'Financial',
      description: 'Annual salary statement, gross income, deductions (80C/D), and refund details',
      isPii: true,
      previewUrl: '/samples/tax-summary-preview.svg',
      thumbnailUrl: '/samples/tax-summary-preview.svg',
    },
  ]);

  const [activities, setActivities] = useState<ActivityItem[]>([
    {
      id: 'act-1',
      action: 'File Scanned & Indexed',
      target: 'aadhaar_card_front.pdf',
      timestamp: '2026-11-15T10:30:00Z',
      status: 'success',
    },
    {
      id: 'act-2',
      action: 'PII Detection & Masking',
      target: 'Presidio masked 1 UIDAI entity before vector storage',
      timestamp: '2026-11-15T10:30:02Z',
      status: 'info',
    },
    {
      id: 'act-3',
      action: 'Document Uploaded',
      target: 'passport_scan.jpg',
      timestamp: '2026-11-15T11:15:00Z',
      status: 'success',
    },
  ]);

  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'msg-1',
      sender: 'assistant',
      text: 'Vault City ready. Ask anything about your uploaded documents, like your passport expiry, Aadhaar number, or medical reports.',
      timestamp: new Date().toISOString(),
    },
  ]);

  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    async function fetchStatus() {
      const data = await checkHealth();
      if (data && data.checks) {
        setSystemStatus({
          postgres: data.checks.postgres || 'connected',
          chromadb: data.checks.chromadb || 'connected',
        });
      }
    }
    fetchStatus();
  }, []);

  // Upload confirmation handler with custom file naming & multi-page bundling
  const handleConfirmUpload = (
    files: {
      file: File;
      finalName: string;
      category: StagedFile['category'];
      pages?: StagedPage[];
    }[]
  ) => {
    const newDocs: DocumentFile[] = files.map((item, idx) => {
      const isImg = item.file.type.startsWith('image/');
      const hasPages = item.pages && item.pages.length > 0;
      const isMultiPage = item.pages && item.pages.length > 1;

      let docPages: DocumentPage[] | undefined = undefined;
      let primaryUrl: string | undefined = undefined;

      if (hasPages && item.pages) {
        docPages = item.pages.map((p, pIdx) => {
          const url = p.previewUrl || URL.createObjectURL(p.file);
          if (pIdx === 0) primaryUrl = url;
          return {
            pageNumber: pIdx + 1,
            url,
            name: p.name || (pIdx === 0 ? 'Page 1 (Front)' : pIdx === 1 ? 'Page 2 (Back)' : `Page ${pIdx + 1}`),
            size: p.file.size,
          };
        });
      } else if (isImg) {
        primaryUrl = URL.createObjectURL(item.file);
      }

      const totalSize = hasPages && item.pages
        ? item.pages.reduce((acc, p) => acc + p.file.size, 0)
        : item.file.size;

      return {
        id: `doc-${Date.now()}-${idx}`,
        name: item.finalName,
        originalName: item.file.name,
        size: totalSize,
        mimeType: isMultiPage ? 'application/pdf' : (item.file.type || 'application/octet-stream'),
        uploadedAt: new Date().toISOString(),
        status: 'indexed',
        category: item.category,
        documentType: isMultiPage
          ? `${item.category} Document (${item.pages?.length} Pages)`
          : (item.category === 'Identity' ? 'Identity Document' : 'Verified File'),
        description: isMultiPage
          ? `Encrypted multi-page document bundle (${item.pages?.length} pages: Front & Back) ready for semantic AI search.`
          : `Encrypted vault file (${item.finalName}) ready for semantic AI search.`,
        isPii: item.category === 'Identity',
        previewUrl: primaryUrl,
        thumbnailUrl: primaryUrl,
        pages: docPages,
        pageCount: docPages ? docPages.length : 1,
      };
    });

    setDocuments((prev) => [...newDocs, ...prev]);

    setActivities((prev) => [
      {
        id: `act-${Date.now()}`,
        action: 'Files Uploaded & Encrypted',
        target: `${files.length} document record(s) saved to vault`,
        timestamp: new Date().toISOString(),
        status: 'success',
      },
      ...prev,
    ]);

    // Switch to Vault view to let user see their newly named files
    setCurrentTab('vault');
  };

  // Document Rename Handler
  const handleRenameDocument = (id: string, newName: string) => {
    setDocuments((prev) =>
      prev.map((doc) => {
        if (doc.id === id) {
          return { ...doc, name: newName };
        }
        return doc;
      })
    );

    setActivities((prev) => [
      {
        id: `act-${Date.now()}`,
        action: 'Document Renamed',
        target: `Renamed to "${newName}"`,
        timestamp: new Date().toISOString(),
        status: 'info',
      },
      ...prev,
    ]);
  };

  const handleDeleteDocument = (id: string) => {
    const docToDelete = documents.find((d) => d.id === id);
    setDocuments((prev) => prev.filter((doc) => doc.id !== id));

    if (docToDelete) {
      setActivities((prev) => [
        {
          id: `act-${Date.now()}`,
          action: 'File Deleted',
          target: docToDelete.name,
          timestamp: new Date().toISOString(),
          status: 'warning',
        },
        ...prev,
      ]);
    }
  };

  const handleSendMessage = (query: string) => {
    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      sender: 'user',
      text: query,
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);

    setTimeout(() => {
      let reply = "I analyzed your secure documents.";
      let sources: string[] = [];

      const lower = query.toLowerCase();
      if (lower.includes('aadhaar') || lower.includes('address')) {
        reply = "From 'aadhaar_card_national_id.pdf':\n• [Page 1 (Front)]: UID Number is 9876 5432 1098, DOB: 14/08/1995.\n• [Page 2 (Back)]: Registered Address is #42, Koramangala 4th Block, Bengaluru, Karnataka 560034.";
        sources = ['aadhaar_card_national_id.pdf [Page 1: Front]', 'aadhaar_card_national_id.pdf [Page 2: Back]'];
      } else if (lower.includes('passport')) {
        reply = "Your Passport Number is: Z1234567. Expiry Date: 24 Oct 2032. (Extracted from 'passport_scan.jpg')";
        sources = ['passport_scan.jpg'];
      } else if (lower.includes('blood') || lower.includes('sugar') || lower.includes('med') || lower.includes('cholesterol')) {
        reply = "From 'medical_report_apollo.pdf': Fasting blood sugar is 92 mg/dL (Normal range: 70-100), Hemoglobin is 14.8 g/dL (Normal: 13-17), and Total Cholesterol is 185 mg/dL. Vitamin D3 is mildly low at 28.4 ng/mL.";
        sources = ['medical_report_apollo.pdf'];
      } else if (lower.includes('tax') || lower.includes('salary') || lower.includes('refund') || lower.includes('income')) {
        reply = "From 'annual_tax_return_form16.pdf': Gross total income for AY 2026-27 is ₹24,50,000. Deductions under 80C/D totaled ₹3,50,000, and an income tax refund of ₹42,850 was credited to your bank.";
        sources = ['annual_tax_return_form16.pdf'];
      } else {
        reply = `Retrieved matching information from your vault city documents for query: "${query}".`;
        sources = ['aadhaar_card_front.pdf', 'passport_scan.jpg', 'medical_report_apollo.pdf'];
      }

      const assistantMsg: ChatMessage = {
        id: `asst-${Date.now()}`,
        sender: 'assistant',
        text: reply,
        timestamp: new Date().toISOString(),
        sources,
      };

      setMessages((prev) => [...prev, assistantMsg]);
      setIsLoading(false);

      setActivities((prev) => [
        {
          id: `act-${Date.now()}`,
          action: 'AI Document Query',
          target: 'Semantic RAG retrieval executed',
          timestamp: new Date().toISOString(),
          status: 'info',
        },
        ...prev,
      ]);
    }, 900);
  };

  // If not logged in, render the Auth View (Login, Sign In, Password Reset)
  if (!currentUser) {
    return (
      <AuthView
        onLoginSuccess={handleLoginSuccess}
        isDark={isDark}
        onToggleTheme={toggleTheme}
      />
    );
  }

  return (
    <div className="min-h-screen bg-[#FFF5EA] dark:bg-[#140E0A] bg-grid-pattern text-stone-900 dark:text-[#FAF5F0] flex flex-col font-sans transition-colors duration-200">
      {/* Top Navbar & Mobile Bottom Tab Switcher */}
      <Navigation
        currentTab={currentTab}
        onSelectTab={setCurrentTab}
        systemStatus={systemStatus}
        isDark={isDark}
        onToggleTheme={toggleTheme}
        currentUser={currentUser}
        onLogout={handleLogout}
      />

      {/* Main Content Area */}
      <main
        className={`flex-1 w-full mx-auto ${
          currentTab === 'chat'
            ? 'max-w-3xl px-0 sm:px-4 py-0 sm:py-5 pb-20 sm:pb-8'
            : 'max-w-5xl px-4 py-5 md:py-6 pb-24 md:pb-8'
        }`}
      >
        {currentTab === 'vault' && (
          <VaultView
            documents={documents}
            onDeleteDocument={handleDeleteDocument}
            onPreviewDocument={(doc) => {
              setPreviewDoc(doc);
              setActivePageIdx(0);
            }}
            onRenameDocument={handleRenameDocument}
          />
        )}

        {currentTab === 'upload' && (
          <UploadView onConfirmUpload={handleConfirmUpload} />
        )}

        {currentTab === 'chat' && (
          <ChatView
            messages={messages}
            onSendMessage={handleSendMessage}
            isLoading={isLoading}
          />
        )}

        {currentTab === 'activity' && (
          <ActivityView activities={activities} />
        )}

        {currentTab === 'settings' && (
          <SettingsView onLogout={handleLogout} />
        )}
      </main>

      {/* In-Browser Document Preview Modal */}
      {previewDoc && (
        <div className="fixed inset-0 z-50 bg-black/60 dark:bg-black/85 backdrop-blur-md flex items-center justify-center p-3 sm:p-4">
          <div className="bg-white dark:bg-[#1C1510] border border-orange-200/80 dark:border-[#382A20] rounded-2xl max-w-lg w-full p-4 space-y-3.5 shadow-2xl font-mono">
            <div className="flex items-center justify-between pb-2 border-b border-stone-100 dark:border-stone-800">
              <div className="flex items-center space-x-2 min-w-0">
                <FileText className="w-4 h-4 text-stone-700 dark:text-stone-300 flex-shrink-0" />
                <div className="min-w-0">
                  <h3 className="text-xs font-bold text-stone-900 dark:text-white truncate max-w-[260px] sm:max-w-sm">
                    {previewDoc.name}
                  </h3>
                  <div className="flex items-center space-x-1.5 text-[10px]">
                    <span className="text-stone-400">@vault.city/{previewDoc.category?.toLowerCase() || 'docs'}</span>
                    {previewDoc.isPii && (
                      <span className="px-1.5 py-0.2 rounded bg-amber-500/10 text-amber-700 dark:text-amber-400 border border-amber-500/25 font-bold text-[9px]">
                        PII
                      </span>
                    )}
                    <span className="px-1.5 py-0.2 rounded bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border border-emerald-500/20 text-[9px]">
                      Indexed
                    </span>
                  </div>
                </div>
              </div>
              <button
                onClick={() => setPreviewDoc(null)}
                className="p-1 rounded-md text-stone-400 hover:text-stone-900 dark:hover:text-white hover:bg-stone-100 dark:hover:bg-stone-800 transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Multi-Page Navigation Bar */}
            {previewDoc.pages && previewDoc.pages.length > 1 && (
              <div className="flex items-center justify-between bg-stone-100 dark:bg-stone-900/80 px-3 py-1.5 rounded-lg border border-stone-200 dark:border-stone-800 text-xs">
                <button
                  type="button"
                  disabled={activePageIdx === 0}
                  onClick={() => setActivePageIdx((p) => Math.max(0, p - 1))}
                  className={`flex items-center space-x-1 px-2 py-0.5 rounded transition-colors ${
                    activePageIdx === 0
                      ? 'text-stone-300 dark:text-stone-700 cursor-not-allowed'
                      : 'text-stone-700 dark:text-stone-200 hover:bg-stone-200 dark:hover:bg-stone-800'
                  }`}
                >
                  <ChevronLeft className="w-3.5 h-3.5" />
                  <span className="text-[10px]">Prev</span>
                </button>

                <div className="flex items-center space-x-1.5 font-mono text-[10px] text-stone-700 dark:text-stone-300">
                  <Layers className="w-3 h-3 text-emerald-500" />
                  <span className="font-semibold">
                    Page {activePageIdx + 1} of {previewDoc.pages.length}
                  </span>
                  <span className="text-stone-400">
                    ({previewDoc.pages[activePageIdx]?.name || `Page ${activePageIdx + 1}`})
                  </span>
                </div>

                <button
                  type="button"
                  disabled={activePageIdx >= previewDoc.pages.length - 1}
                  onClick={() => setActivePageIdx((p) => Math.min(previewDoc.pages!.length - 1, p + 1))}
                  className={`flex items-center space-x-1 px-2 py-0.5 rounded transition-colors ${
                    activePageIdx >= previewDoc.pages.length - 1
                      ? 'text-stone-300 dark:text-stone-700 cursor-not-allowed'
                      : 'text-stone-700 dark:text-stone-200 hover:bg-stone-200 dark:hover:bg-stone-800'
                  }`}
                >
                  <span className="text-[10px]">Next</span>
                  <ChevronRight className="w-3.5 h-3.5" />
                </button>
              </div>
            )}

            {/* Document Image View */}
            {((previewDoc.pages && previewDoc.pages[activePageIdx]?.url) || previewDoc.previewUrl) ? (
              <div className="relative rounded-xl overflow-hidden border border-orange-200/60 dark:border-[#382A20] bg-[#FFF5EA] dark:bg-[#140E0A] p-1 flex items-center justify-center">
                <img
                  src={(previewDoc.pages && previewDoc.pages[activePageIdx]?.url) || previewDoc.previewUrl}
                  alt={previewDoc.name}
                  className="w-full max-h-72 object-contain rounded-lg shadow-sm"
                />
              </div>
            ) : (
              <div className="bg-[#FFF5EA] dark:bg-[#140E0A] p-5 rounded-xl border border-orange-200/60 dark:border-[#382A20] text-center space-y-1.5">
                <div className="w-10 h-10 mx-auto rounded-xl bg-white dark:bg-[#1C1510] flex items-center justify-center text-stone-700 dark:text-stone-300 border border-orange-200/60 dark:border-[#382A20]">
                  <FileText className="w-5 h-5" />
                </div>
                <p className="text-xs font-semibold text-stone-900 dark:text-stone-100">{previewDoc.documentType}</p>
              </div>
            )}

            {/* Multi-Page Quick Pill Switcher */}
            {previewDoc.pages && previewDoc.pages.length > 1 && (
              <div className="flex items-center gap-1.5 overflow-x-auto pb-0.5">
                {previewDoc.pages.map((page, idx) => (
                  <button
                    key={page.pageNumber || idx}
                    type="button"
                    onClick={() => setActivePageIdx(idx)}
                    className={`flex items-center space-x-1.5 px-2.5 py-1 rounded text-[10px] font-mono transition-all ${
                      activePageIdx === idx
                        ? 'bg-stone-900 text-white dark:bg-white dark:text-stone-950 font-bold shadow-xs'
                        : 'bg-stone-100 dark:bg-stone-900 text-stone-600 dark:text-stone-400 hover:text-stone-900 dark:hover:text-white border border-stone-200 dark:border-stone-800'
                    }`}
                  >
                    <span>p.{idx + 1}</span>
                    <span className="opacity-75">{idx === 0 ? '(Front)' : idx === 1 ? '(Back)' : ''}</span>
                  </button>
                ))}
              </div>
            )}

            {/* Metadata Info */}
            <div className="space-y-1 text-xs">
              {previewDoc.originalName && previewDoc.originalName !== previewDoc.name && (
                <p className="text-[10px] text-stone-400">Original filename: {previewDoc.originalName}</p>
              )}
              {previewDoc.description && (
                <p className="text-[11px] text-stone-600 dark:text-stone-300 bg-stone-50 dark:bg-[#161820] p-2 rounded-lg border border-stone-100 dark:border-stone-800/80">
                  {previewDoc.description}
                </p>
              )}
            </div>

            <div className="flex items-center justify-between text-xs text-stone-500 dark:text-stone-400 pt-1 border-t border-stone-100 dark:border-stone-800">
              <span className="text-[11px]">Size: {(previewDoc.size / (1024 * 1024)).toFixed(2)} MB</span>
              <a
                href={(previewDoc.pages && previewDoc.pages[activePageIdx]?.url) || previewDoc.previewUrl || '#'}
                download={previewDoc.name}
                className="flex items-center space-x-1.5 px-3.5 py-1.5 bg-orange-600 hover:bg-orange-700 text-white rounded-lg text-xs font-semibold shadow-xs transition-colors"
              >
                <Download className="w-3 h-3" />
                <span>Download</span>
              </a>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
