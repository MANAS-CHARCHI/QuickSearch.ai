export type TabType = 'chat' | 'vault' | 'upload' | 'activity' | 'settings';

export type AuthMode = 'login' | 'signup' | 'verify_email' | 'forgot_password' | 'reset_password';

export interface UserProfile {
  id: string;
  email: string;
  name?: string;
  fullName?: string;
  username?: string;
  role: 'user' | 'admin';
  isEmailVerified?: boolean;
  hasGoogle?: boolean;
  hasPassword?: boolean;
}

export interface AuthTokens {
  accessToken: string;
  refreshToken: string;
  tokenType?: string;
}

export interface AuthResponseData {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: {
    id: string;
    email: string;
    username?: string;
    role: string;
    is_active: boolean;
    has_google?: boolean;
    has_password?: boolean;
    created_at?: string;
  };
}

export interface DocumentPage {
  pageNumber: number;
  url: string;
  name?: string;
  size?: number;
}

export interface ScanStep {
  stage: string;
  label: string;
  status: 'passed' | 'blocked' | 'failed';
  detail: string;
  duration_ms?: number;
}

export interface ScanReport {
  summary?: string;
  extracted_text_preview?: string;
  vision_engine?: string;
  av_engine?: string;
  av_status?: string;
  av_threat?: string | null;
  sqli_status?: string;
  prompt_injection_status?: string;
  sha256_verified?: boolean;
  chunks_stored?: number;
  total_duration_ms?: number;
  steps?: ScanStep[];
}

export interface DocumentFile {
  id: string;
  name: string;
  originalName?: string;
  size: number;
  mimeType: string;
  uploadedAt: string;
  status: 'scanning' | 'classifying' | 'indexed' | 'failed';
  scanStatus?: string;
  documentType?: string;
  category?: 'Identity' | 'Financial' | 'Medical' | 'Personal' | 'Other';
  description?: string;
  scanReport?: ScanReport;
  isPii?: boolean;
  s3Key?: string;
  sha256?: string;
  extractedSnippet?: string;
  thumbnailUrl?: string;
  previewUrl?: string;
  downloadUrl?: string;
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

export interface UserSession {
  id: string;
  deviceName: string;
  deviceType: 'desktop' | 'mobile' | 'tablet';
  ipAddress?: string;
  createdAt: string;
  expiresAt: string;
  isCurrent: boolean;
}
