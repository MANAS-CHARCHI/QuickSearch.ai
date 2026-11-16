export type TabType = 'chat' | 'vault' | 'upload' | 'activity' | 'settings';

export type AuthMode = 'login' | 'signup' | 'forgot_password';

export interface UserProfile {
  id: string;
  email: string;
  name?: string;
  fullName?: string;
  role: 'user' | 'admin';
}

export interface DocumentPage {
  pageNumber: number;
  url: string;
  name?: string;
  size?: number;
}

export interface DocumentFile {
  id: string;
  name: string;
  originalName?: string;
  size: number;
  mimeType: string;
  uploadedAt: string;
  status: 'scanning' | 'classifying' | 'indexed' | 'failed';
  documentType?: string;
  category?: 'Identity' | 'Financial' | 'Medical' | 'Personal' | 'Other';
  description?: string;
  isPii?: boolean;
  s3Key?: string;
  sha256?: string;
  extractedSnippet?: string;
  thumbnailUrl?: string;
  previewUrl?: string;
  pages?: DocumentPage[];
  pageCount?: number;
}

export interface StagedPage {
  id: string;
  file: File;
  previewUrl?: string;
  name: string;
}

export interface StagedFile {
  id: string;
  file: File;
  defaultName: string;
  customName: string;
  category: 'Identity' | 'Financial' | 'Medical' | 'Personal' | 'Other';
  size: number;
  previewUrl?: string;
  pages?: StagedPage[];
}

export interface ChatMessage {
  id: string;
  sender: 'user' | 'assistant';
  text: string;
  timestamp: string;
  sources?: string[];
  executionTrace?: {
    step: string;
    durationMs: number;
    status: 'pass' | 'active' | 'done';
  }[];
}

export interface ActivityItem {
  id: string;
  action: string;
  target: string;
  timestamp: string;
  status: 'success' | 'warning' | 'info';
  codeHash?: string;
}
