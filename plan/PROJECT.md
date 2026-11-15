# 🔐 Personal Vault AI — Complete Project Reference

> **What is this?**
> A production-grade personal document vault PWA where users securely upload, store, and retrieve any personal file (Aadhaar, Passport, photos, PDFs, folders). An agentic AI chatbot powered by Anthropic Claude answers natural language questions like _"What is my Aadhaar number?"_ or _"When does my passport expire?"_ — all with enterprise-grade security, encryption, virus scanning, and full observability.

---

## 📦 Project Name

**Personal Vault AI**

- Frontend URL: `https://vault.yourdomain.com`
- Files CDN: `https://files.yourdomain.com`
- Admin Portal: `https://vault.yourdomain.com/admin`
- API Base: `https://vault.yourdomain.com/api/v1`

---

## ✅ Complete Feature List

### 🔐 Authentication & Sessions

- [ ] Email + password registration and login
- [ ] Google OAuth2 social login (one-click)
- [ ] JWT access tokens (15-minute expiry)
- [ ] Refresh tokens (7-day, stored in Redis)
- [ ] Refresh token rotation on every use
- [ ] On logout: access token blacklisted in Redis, refresh token deleted instantly
- [ ] Account lockout after 3 wrong passwords (15-minute lockout, Redis TTL)
- [ ] Email alert sent to user on account lockout
- [ ] Password reset via email (secure token, 1-hour expiry, Redis)
- [ ] Email alert when password is changed successfully
- [ ] New login from new device/IP → email alert to user
- [ ] httpOnly cookie for refresh token (not accessible by JS)
- [ ] Role-based access: `user` and `admin` roles via JWT claim
- [ ] All tokens validated server-side — no frontend trust

---

### 📤 File Upload

- [ ] Single file upload (drag-and-drop + click-to-browse)
- [ ] Folder upload (entire directory, preserves structure)
- [ ] Max file size: **10MB hard limit** (enforced at Nginx + FastAPI)
- [ ] Files ≤ 5MB: standard single-part upload
- [ ] Files > 5MB and ≤ 10MB: S3 Multipart Upload (reliable, resumable)
- [ ] SHA-256 hash computed in browser before upload starts
- [ ] Duplicate file detection: hash compared against user's existing files in DB
- [ ] Duplicate dialog: show both files, user chooses — Replace / Keep Both / Cancel
- [ ] If Replace: old file deleted from S3 + PostgreSQL + Pinecone before new upload
- [ ] If Keep Both: new file auto-renamed (e.g. `aadhaar_v2.pdf`)
- [ ] Upload progress bar per file (real-time)
- [ ] Per-file status indicator: `queued → scanning → classifying → extracting → embedding → ready / failed`
- [ ] Folder upload respects nested structure in S3
- [ ] Camera capture on mobile PWA (`capture="environment"` input)
- [ ] Allowlisted MIME types only (PDF, JPG, PNG, HEIC, WEBP, DOCX, XLSX, TXT, CSV)
- [ ] File type validated by both MIME type and magic bytes (not just extension)
- [ ] Upload rate limited: 10 uploads per minute per user

---

### 🔬 Virus Scanning (ClamAV)

- [ ] Every uploaded file scanned in isolated ClamAV Docker container
- [ ] ClamAV container has zero network access (`network_mode: none`)
- [ ] File shared via Docker volume only — no S3 credentials in scanner
- [ ] Infected files deleted from quarantine bucket immediately
- [ ] User notified by email and in-app notification on virus detection
- [ ] Security event logged with file hash and detection signature
- [ ] ClamAV virus definition database updated daily via `freshclam` cron
- [ ] Clean files moved from quarantine bucket → production S3 bucket

---

### 🧠 AI File Understanding & Classification (Claude Vision)

- [ ] Every file analyzed by Claude Vision after virus scan
- [ ] PDF → first page converted to PNG for Claude to see
- [ ] Image files → sent directly to Claude Vision
- [ ] Non-visual files (DOCX, XLSX, TXT) → content-based text classification
- [ ] Claude returns structured JSON: `document_type`, `category`, `description`, `purpose`, `likely_fields`, `language`, `confidence`, `is_pii`, `suggested_folder`, `extraction_strategy`
- [ ] High confidence (≥ 0.85): auto-classify and auto-route to right extractor
- [ ] Low confidence (< 0.85): notify user to confirm document type (email + UI)
- [ ] Document types classified: Aadhaar, PAN, Passport, Voter ID, Driving License, Bank Statement, ITR, Salary Slip, Invoice, Receipt, Prescription, Lab Report, Insurance Card, Agreement, Contract, Degree, Marksheet, Visa, Boarding Pass, RC Book, Sale Deed, Electricity Bill, Personal Photo, Screenshot, and more
- [ ] Each doc auto-assigned to suggested folder: `identity/`, `financial/`, `medical/`, `legal/`, `education/`, `travel/`, `vehicle/`, `property/`, `photos/`
- [ ] Personal photos: Claude generates descriptive text ("birthday party with cake and balloons, indoor setting") for semantic search
- [ ] AI classification metadata stored in PostgreSQL and Pinecone

---

### 📄 Text Extraction (Smart Routing)

- [ ] AWS Textract OCR — for ID cards, scanned documents, photos with text
- [ ] AWS Textract Table Mode — for bank statements, financial tables
- [ ] PyMuPDF — for clean, text-based PDFs
- [ ] Apache Tika — for Word (DOCX), Excel (XLSX), PowerPoint, and other office formats
- [ ] Claude Vision description — for personal photos and non-document images
- [ ] Extraction strategy chosen automatically from AI classification result
- [ ] Multi-page documents chunked (512 tokens per chunk, 50 token overlap)
- [ ] Language detection and handling (English, Hindi, mixed scripts)

---

### 🛡️ PII Privacy Scanner (Presidio)

- [ ] Microsoft Presidio runs on all extracted text before embedding
- [ ] Detects: Aadhaar number, PAN, Passport number, phone, email, DOB, credit card, bank account, name, address, vehicle number
- [ ] Raw extracted text stored encrypted in S3 (source of truth for LLM)
- [ ] Text entering vector DB has PII masked (`AADHAAR_NUMBER: [REDACTED]`)
- [ ] Vector DB breach → no raw PII exposed (embeddings only point to masked text)
- [ ] LLM reads from S3 (in-memory, not persisted) only when authenticated user asks for PII
- [ ] PII presence flag stored in file metadata (`is_pii: true/false`)

---

### 🗄️ Storage — AWS S3

- [ ] Per-user folder: `s3://vault/users/{user_id}/`
- [ ] Separate quarantine bucket for unscanned files
- [ ] SSE-KMS encryption at rest for all objects
- [ ] No public access on any bucket (block all public access policy)
- [ ] Pre-signed URLs for file access (15-minute expiry, GET only)
- [ ] S3 Multipart Upload for files > 5MB
- [ ] `_manifest.json` auto-generated per user folder (index of all files)
- [ ] File deduplication by SHA-256 hash
- [ ] SHA-256 checksum stored in PostgreSQL per file for integrity verification
- [ ] Folder download as ZIP (server-side ZIP stream)
- [ ] S3 versioning enabled (accidental delete protection)
- [ ] Graceful S3 migration: feature flag switches reads/writes to new bucket, background copy job, verify checksums, cutover, cleanup
- [ ] `s3_bucket` field on every file DB record (supports multi-bucket mid-migration)

---

### 🔍 Vector Search & RAG (Pinecone + Voyage AI)

- [ ] Embeddings generated using Voyage AI `voyage-3` model (Anthropic-recommended, multilingual)
- [ ] Every text chunk embedded and stored in Pinecone with rich metadata
- [ ] Mandatory `user_id` filter on every Pinecone query — users are fully isolated
- [ ] Metadata stored per vector chunk: `user_id`, `file_id`, `file_name`, `document_type`, `category`, `description`, `likely_fields`, `s3_key`, `chunk_index`, `is_pii`, `language`, `created_at`
- [ ] Semantic search: top-K chunks retrieved (K=5–10)
- [ ] Filter by `document_type` for precise queries ("find my passport")
- [ ] Filter by `category` ("show me all financial documents")
- [ ] ChromaDB used in local dev (no Pinecone account needed)
- [ ] Pinecone namespace per user (extra isolation layer)

---

### 🤖 Agentic AI Chat (Anthropic Claude)

- [ ] Agentic loop using Claude Tool Use API
- [ ] Streaming responses (Server-Sent Events to frontend)
- [ ] Conversation history stored in PostgreSQL (per session, trimmed to context window)
- [ ] Chat messages stored encrypted (AES-256) in DB — not readable by admin
- [ ] Tools available to Claude agent:
  - `search_documents` — semantic search over user's docs
  - `search_by_document_type` — find by AI-classified type
  - `extract_field` — extract specific field (Aadhaar number, expiry date, amount)
  - `list_files` — list all files, filtered by folder or type
  - `get_view_url` — open file in browser viewer
  - `get_share_link` — generate 15-min shareable link
  - `delete_file` — delete file from S3 + DB + vector store
  - `answer_faq` — answer how-to questions about the vault
- [ ] Claude system prompt hardened: ignore embedded instructions in documents
- [ ] Claude never invents data — only uses retrieved document context
- [ ] Token usage tracked per message, stored in DB

---

### 💬 AI Token Usage & Limits

- [ ] Per-user monthly token cap (configurable, stored in DB)
- [ ] Token usage tracked: input tokens + output tokens per API call
- [ ] Usage bar shown on dashboard: `12,450 / 50,000 tokens this month`
- [ ] When cap reached: route to free/OSS model (Ollama / Groq — TBD)
- [ ] Monthly reset cron job (Celery beat, 1st of each month)
- [ ] Admin can see per-user token spend in admin portal
- [ ] Email alert when user hits token limit

---

### 👁️ In-Browser File Viewer

- [ ] PDF.js viewer — view multi-page PDFs in-browser, no download required
- [ ] Image viewer — full-size image display with zoom/pan
- [ ] Files served from `files.yourdomain.com` (separate subdomain)
- [ ] Strict `Content-Security-Policy: default-src 'none'` on file subdomain (no script execution)
- [ ] `Content-Disposition: inline` for viewer, `attachment` for download
- [ ] Download button available directly in viewer
- [ ] Share button: generates 15-min pre-signed link (stored in Redis)
- [ ] Shared links: viewable without login, expire automatically
- [ ] File viewer accessible from dashboard, chat (Claude can open file), and direct URL

---

### 🗂️ File Management

- [ ] Dashboard: folder tree view of all uploaded files
- [ ] Browse by folder: `identity/`, `financial/`, `medical/`, `photos/`, etc.
- [ ] AI-generated description shown per file
- [ ] Document type badge on each file (e.g. "Aadhaar Card", "Bank Statement")
- [ ] File status badge (ready / processing / failed)
- [ ] Single file delete (cascades: S3 → DB → Pinecone vectors)
- [ ] Bulk select + delete multiple files
- [ ] Folder download as ZIP
- [ ] Full account data purge (all S3 objects + DB records + Pinecone namespace deleted) — GDPR compliant
- [ ] `_manifest.json` downloadable as personal data export
- [ ] Storage usage shown: `2.3 GB / 5 GB used`
- [ ] Per-user storage quota enforced (block uploads when exceeded)
- [ ] File rename (update DB record + S3 object metadata)
- [ ] File move to different folder (update S3 key + DB)

---

### 🛡️ Security — Input Guard (ML)

- [ ] Every user input scanned before reaching Claude or the DB
- [ ] Layer 1: Regex rules — catch SQLi, XSS, path traversal instantly
- [ ] Layer 2: BERT classifier (`ProtectAI/deberta-v3-base-prompt-injection`) — detect prompt injection / jailbreak attempts
- [ ] Layer 3: Claude system prompt — hardened against role-play attacks and embedded instructions
- [ ] Blocked inputs logged as security events
- [ ] ML Guard runs as a separate Docker microservice (internal network only)

---

### 🌐 Security — Edge & Network

- [ ] Cloudflare WAF: OWASP Top 10, SQLi, XSS rules at the edge
- [ ] Cloudflare Turnstile: invisible CAPTCHA on login and upload forms
- [ ] Cloudflare Bot Management: block scrapers and known bad IPs
- [ ] Cloudflare DDoS protection: L3/L4/L7 mitigated before hitting servers
- [ ] Cloudflare Access: admin portal locked to email allowlist
- [ ] Nginx: SSL termination (TLS 1.3), rate limiting, security headers
- [ ] Security headers: `HSTS`, `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Content-Security-Policy`, `Referrer-Policy: no-referrer`
- [ ] CORS: explicit domain allowlist — never `*`, blocks all external scripts
- [ ] All API routes under `/api/v1/` (versioned)
- [ ] HTTPS everywhere — HTTP redirected to HTTPS
- [ ] No direct API calls from outside the backend allowed (CORS + auth enforced)

---

### ⚡ API Rate Limiting (`slowapi`)

- [ ] Rate limits stored in Redis (global across all workers)
- [ ] `POST /upload` — 10 requests/minute per user
- [ ] `POST /auth/login` — 5 requests/minute per IP
- [ ] `POST /chat` — 30 requests/minute per user
- [ ] `GET /search` — 60 requests/minute per user
- [ ] `POST /auth/forgot-password` — 3 requests/hour per IP
- [ ] Global default: 200 requests/minute
- [ ] Rate limit headers returned: `X-RateLimit-Remaining`, `Retry-After`
- [ ] Nginx layer: additional hard rate limits on login and upload endpoints

---

### 📧 Email Notifications (Resend)

- [ ] Welcome email on signup
- [ ] Email verification link on signup
- [ ] New login from new device/IP alert
- [ ] Account locked (3 wrong passwords) — includes remaining lockout time
- [ ] Password reset link (1-hour expiry)
- [ ] Password successfully changed confirmation
- [ ] File upload complete (includes file name and detected document type)
- [ ] Virus detected in uploaded file — file rejected notice
- [ ] Low-confidence AI classification — user asked to confirm document type
- [ ] AI token monthly limit reached
- [ ] Unusual activity detected (anomalous download/delete volume)
- [ ] Weekly digest (optional): upcoming document expiries, storage usage

---

### 📊 Audit Logging

- [ ] Every user action logged: upload, delete, search, login, logout, chat, password reset, share
- [ ] Log schema: `user_id`, `action`, `resource_id`, `resource_name`, `ip_address`, `user_agent`, `status`, `timestamp`
- [ ] PII stripped from all log entries before storage
- [ ] File contents, extracted text, AI messages — NEVER logged
- [ ] Logs stored in PostgreSQL or OpenSearch (encrypted)
- [ ] Admin can search and filter logs by user, action, date range
- [ ] User can download their own activity log (data export)
- [ ] Log retention policy: 90 days (configurable)

---

### 🏥 Health & Reliability

- [ ] `GET /health` — basic liveness check (Docker healthcheck)
- [ ] `GET /health/ready` — checks Postgres, Redis, Pinecone connectivity; returns 503 if any fail
- [ ] `GET /health/live` — load balancer probe
- [ ] Graceful shutdown: SIGTERM handler, finishes in-flight requests before container stops
- [ ] Celery worker retry with exponential backoff (1→2→4 min, max 3 retries)
- [ ] Stuck-file reconciliation: Celery beat cron every hour (requeues files stuck > 30 min)
- [ ] All Docker containers have health checks and resource limits (CPU + RAM)

---

### 🗄️ Database (PostgreSQL + SQLAlchemy + Alembic)

- [ ] SQLAlchemy 2.0 async ORM
- [ ] Alembic for schema migrations (branch-based, versioned, reversible)
- [ ] Tables: `users`, `files`, `conversations`, `messages`, `audit_logs`, `folders`
- [ ] Row-level security: users can only access their own rows
- [ ] AI conversation messages stored AES-256 encrypted in DB
- [ ] `sha256_hash` column on files for deduplication
- [ ] `s3_bucket` column on files for multi-bucket migration support
- [ ] `status` enum column on files for pipeline tracking
- [ ] `token_usage_month` + `token_limit_month` on users for quota management
- [ ] `storage_used_bytes` on users for quota enforcement
- [ ] PostgreSQL automated backups (RDS snapshots or `pg_dump` cron)
- [ ] Migrations run before deploy in CI/CD pipeline (init container pattern)
- [ ] Never modify an existing migration file after merging

---

### ⚙️ Background Jobs (Celery + Redis)

- [ ] Upload processing worker (virus scan → classify → extract → embed)
- [ ] Retry with exponential backoff on failure
- [ ] Stuck-file reconciliation (hourly cron)
- [ ] Monthly token usage reset (1st of month cron)
- [ ] ClamAV signature update trigger (daily cron)
- [ ] Document expiry check (daily cron — passport, visa, insurance expiry alerts)
- [ ] S3 migration copy job (batch, checksummed)
- [ ] Storage usage recalculation (daily cron — sync DB with actual S3 usage)

---

### 🐳 Docker Architecture

- [ ] `nginx` — entry point, SSL, rate limiting, routing
- [ ] `frontend` — React Vite PWA
- [ ] `backend` — FastAPI + Alembic
- [ ] `worker` — Celery upload processor + beat scheduler
- [ ] `redis` — token blacklist, rate limits, session, Celery broker, share links
- [ ] `postgres` — primary database
- [ ] `chromadb` — local dev vector DB (Pinecone in production)
- [ ] `clamav` — virus scanner, `network_mode: none`, file access via shared volume only
- [ ] `ml-guard` — BERT injection + privacy classifier microservice (internal network only)
- [ ] All containers: resource limits (CPU + RAM), health checks, restart policies
- [ ] Secrets via Docker secrets or `.env` — `.env` never committed to git
- [ ] `docker-compose.yml` for local dev, `docker-compose.prod.yml` for production overrides

---

### 🚀 CI/CD Pipeline (GitHub Actions)

- [ ] On push to `main`: run full test suite (pytest, coverage)
- [ ] Run Alembic migrations on staging DB
- [ ] Deploy to staging (AWS ECS)
- [ ] Smoke tests on staging
- [ ] Run Alembic migrations on production DB
- [ ] Deploy to production (AWS ECS)
- [ ] Health check after deploy — rollback if `/health/ready` returns 503
- [ ] Docker images built and pushed to AWS ECR
- [ ] Secrets managed via GitHub Actions secrets (never in code)
- [ ] Branch protection: no direct push to `main`, PRs required

---

### 📱 PWA Features

- [ ] Installable on desktop and mobile (Web App Manifest)
- [ ] Service Worker with Workbox (offline shell caching)
- [ ] Offline fallback page when network unavailable
- [ ] Push notifications for upload complete, virus alert, file confirmed
- [ ] Camera capture input on mobile (`capture="environment"`)
- [ ] Responsive design — works on mobile, tablet, desktop
- [ ] Add to Home Screen prompt on mobile

---

### 🖥️ Frontend Pages & Components

- [ ] `/login` — email/password + Google OAuth button + forgot password link
- [ ] `/register` — sign up form + email verification
- [ ] `/forgot-password` — email input → reset link sent
- [ ] `/reset-password/:token` — new password form
- [ ] `/dashboard` — file manager, folder tree, storage bar, token usage bar, recent files
- [ ] `/upload` — drag-drop zone + folder upload + progress per file + dedup dialog
- [ ] `/files/:id` — file viewer (PDF.js / image) + download + share button
- [ ] `/chat` — AI chatbot with streaming, conversation history, file references inline
- [ ] `/settings` — profile, change password, delete account, data export
- [ ] `/admin` — admin portal (role-gated): stats, users, logs, health, alerts

**Reusable Components:**

- [ ] `DuplicateDialog` — show both files, user picks action
- [ ] `TokenUsageBar` — progress bar with usage/limit/reset date
- [ ] `StorageUsageBar` — storage quota display
- [ ] `FileStatusBadge` — color-coded status chip
- [ ] `DocumentTypeBadge` — AI-detected type label
- [ ] `ShareButton` — copy share link with expiry shown
- [ ] `FileViewer` — PDF.js + image viewer + download button
- [ ] `UploadDropzone` — drag-drop + folder support + camera capture
- [ ] `ChatMessage` — streaming message with tool call indicators
- [ ] `ConfidenceAlert` — notification to confirm low-confidence classification

---

### 👨‍💼 Admin Portal

- [ ] Overview: total users, DAU, files uploaded today, total storage, API cost this month
- [ ] Server health: each Docker container status, CPU/RAM, response latency
- [ ] Activity log: searchable, filterable by user/action/date — no private content
- [ ] AI usage: token spend per user, model calls, cost per day chart
- [ ] Security events: failed logins, lockouts, ML guard blocks, virus detections
- [ ] Alert configuration: disk >80%, error rate >5%, stuck jobs, budget thresholds
- [ ] Admin CANNOT read: file contents, extracted text, AI conversation messages (encrypted)
- [ ] Admin can: disable a user account, trigger manual file reprocessing

---

### 🔄 S3 Graceful Migration

- [ ] `s3_bucket` field on every file record (knows exactly which bucket each file is in)
- [ ] Feature flag `MIGRATION_MODE=true`: new writes → new bucket, reads → both buckets
- [ ] Background copy job: copies all objects from old → new bucket in batches
- [ ] SHA-256 checksum verification after every copy
- [ ] Feature flag cutover: reads switch to new bucket only
- [ ] 30-day hold on old bucket before cleanup
- [ ] Zero downtime for users during entire migration

---

### 🔒 Security Summary Checklist

- [ ] Passwords: bcrypt hashed, never stored plain
- [ ] JWT: short-lived (15 min), signed with RS256
- [ ] Refresh tokens: opaque, stored hashed in Redis, rotated on every use
- [ ] Token blacklist in Redis on logout
- [ ] CORS: explicit allowlist, credentials allowed, no wildcard
- [ ] Rate limiting: `slowapi` + Nginx + Cloudflare (3 layers)
- [ ] Input guard: regex + BERT ML classifier on all user inputs
- [ ] SQL injection: SQLAlchemy parameterized queries only, no raw SQL
- [ ] File validation: MIME allowlist + magic bytes check
- [ ] Virus scanning: ClamAV, isolated, daily signature updates
- [ ] PII masking: Presidio before vector DB ingestion
- [ ] AI conversation messages: AES-256 encrypted in DB
- [ ] Admin access: role claim in JWT + server-side check on every endpoint
- [ ] Audit log: all actions logged, PII stripped, never log content
- [ ] Secrets: environment variables only, never committed to git
- [ ] TLS 1.3: enforced everywhere, HSTS with long max-age
- [ ] File serving: separate subdomain, strict CSP, no script execution
- [ ] Account lockout: 3 wrong passwords → 15 min Redis lockout
- [ ] Brute force: Nginx + Cloudflare + server-side lockout (3 layers)

---

## 🗂️ Project Folder Structure

```
personal-vault/
│
├── nginx/
│   ├── Dockerfile
│   └── nginx.conf
│
├── frontend/
│   ├── public/
│   │   ├── manifest.json
│   │   └── icons/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Login.jsx
│   │   │   ├── Register.jsx
│   │   │   ├── ForgotPassword.jsx
│   │   │   ├── ResetPassword.jsx
│   │   │   ├── Dashboard.jsx
│   │   │   ├── Upload.jsx
│   │   │   ├── FileViewer.jsx
│   │   │   ├── Chat.jsx
│   │   │   ├── Settings.jsx
│   │   │   └── Admin.jsx
│   │   ├── components/
│   │   │   ├── DuplicateDialog.jsx
│   │   │   ├── TokenUsageBar.jsx
│   │   │   ├── StorageUsageBar.jsx
│   │   │   ├── FileStatusBadge.jsx
│   │   │   ├── DocumentTypeBadge.jsx
│   │   │   ├── ShareButton.jsx
│   │   │   ├── FileViewer.jsx
│   │   │   ├── UploadDropzone.jsx
│   │   │   ├── ChatMessage.jsx
│   │   │   └── ConfidenceAlert.jsx
│   │   ├── lib/
│   │   │   ├── api.js
│   │   │   ├── auth.js
│   │   │   └── hash.js           # SHA-256 in browser (SubtleCrypto)
│   │   └── App.jsx
│   ├── vite.config.js
│   ├── vite.pwa.config.js
│   └── Dockerfile
│
├── backend/
│   ├── api/
│   │   ├── v1/
│   │   │   ├── auth.py           # login, register, google, refresh, logout, reset
│   │   │   ├── upload.py         # upload, dedup-check, multipart
│   │   │   ├── files.py          # list, view, share, delete, zip, rename, move
│   │   │   ├── search.py         # semantic search
│   │   │   ├── chat.py           # agentic chat, streaming, history
│   │   │   ├── health.py         # /health, /health/ready, /health/live
│   │   │   └── admin.py          # admin-only endpoints
│   ├── services/
│   │   ├── s3_service.py
│   │   ├── scanner_service.py
│   │   ├── extractor_service.py
│   │   ├── classifier_service.py
│   │   ├── privacy_service.py
│   │   ├── ml_guard_service.py
│   │   ├── embedder_service.py
│   │   ├── vector_service.py
│   │   ├── token_service.py
│   │   └── email_service.py
│   ├── agents/
│   │   ├── tools.py
│   │   └── agent.py
│   ├── middleware/
│   │   ├── auth_middleware.py
│   │   ├── audit_middleware.py
│   │   ├── ml_guard_middleware.py
│   │   └── cors_middleware.py
│   ├── models/
│   │   ├── user.py
│   │   ├── file.py
│   │   ├── conversation.py
│   │   └── audit_log.py
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   │       └── 001_initial_schema.py
│   ├── workers/
│   │   ├── upload_worker.py
│   │   └── cron.py
│   ├── core/
│   │   ├── config.py             # settings via pydantic-settings
│   │   ├── security.py           # JWT, bcrypt, AES helpers
│   │   ├── rate_limit.py         # slowapi setup
│   │   └── dependencies.py       # get_db, get_redis, get_current_user
│   ├── main.py
│   └── Dockerfile
│
├── ml-guard/
│   ├── app.py
│   ├── classifier.py
│   └── Dockerfile
│
├── clamav/
│   └── Dockerfile
│
├── infra/
│   ├── s3.tf
│   ├── ecs.tf
│   ├── rds.tf
│   └── cloudflare.tf
│
├── .github/
│   └── workflows/
│       └── deploy.yml
│
├── docker-compose.yml
├── docker-compose.prod.yml
├── .env.example
├── plan-personal-vault-rag.md    ← full build plan
└── PROJECT.md                    ← this file
```

---

## 🔑 Environment Variables (`.env.example`)

```bash
# App
APP_ENV=development
SECRET_KEY=your-jwt-secret-key
ADMIN_EMAIL=admin@yourdomain.com

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@postgres:5432/vault

# Redis
REDIS_URL=redis://redis:6379

# AWS
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=ap-south-1
S3_BUCKET=personal-vault-prod
S3_QUARANTINE_BUCKET=personal-vault-quarantine
S3_NEW_BUCKET=                    # set during migration
MIGRATION_MODE=false

# Anthropic
ANTHROPIC_API_KEY=

# Voyage AI (embeddings)
VOYAGE_API_KEY=

# Pinecone
PINECONE_API_KEY=
PINECONE_INDEX=personal-vault

# Google OAuth
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=https://vault.yourdomain.com/api/v1/auth/google/callback

# Resend (email)
RESEND_API_KEY=
EMAIL_FROM=vault@yourdomain.com

# Cloudflare Turnstile
TURNSTILE_SECRET_KEY=

# Limits
MAX_FILE_SIZE_MB=10
MULTIPART_THRESHOLD_MB=5
DEFAULT_STORAGE_QUOTA_GB=5
DEFAULT_MONTHLY_TOKEN_LIMIT=50000

# CORS
ALLOWED_ORIGINS=https://vault.yourdomain.com,https://www.vault.yourdomain.com
```

---

## 📦 Backend Python Dependencies (`requirements.txt`)

```
fastapi==0.115.0
uvicorn[standard]==0.32.0
sqlalchemy[asyncio]==2.0.36
alembic==1.14.0
asyncpg==0.30.0
pydantic-settings==2.6.0
python-jose[cryptography]==3.3.0  # JWT
bcrypt==4.2.0
passlib[bcrypt]==1.7.4
authlib==1.3.2                     # Google OAuth
httpx==0.27.2                      # async HTTP client
redis[asyncio]==5.2.0
celery[redis]==5.4.0
slowapi==0.1.9                     # rate limiting
anthropic==0.40.0
voyageai==0.3.2                    # embeddings
pinecone-client==5.0.1
boto3==1.35.0                      # AWS S3
pymupdf==1.24.13                   # PDF extraction
apache-tika==2.6.0                 # office docs
pdf2image==1.17.0                  # PDF → image for Claude Vision
pillow==11.0.0
presidio-analyzer==2.2.355         # PII detection
presidio-anonymizer==2.2.355
spacy==3.8.2
resend==2.4.0                      # email
python-multipart==0.0.12           # file upload
aiofiles==24.1.0
pytest==8.3.3
pytest-asyncio==0.24.0
coverage==7.6.4
```

---

## 📦 Frontend Dependencies (`package.json`)

```json
{
  "dependencies": {
    "react": "^18.3",
    "react-dom": "^18.3",
    "react-router-dom": "^6.28",
    "tailwindcss": "^3.4",
    "@react-pdf-viewer/core": "^3.12",
    "pdfjs-dist": "^4.8",
    "axios": "^1.7",
    "react-dropzone": "^14.3",
    "react-query": "^5.60",
    "zustand": "^5.0",
    "react-hot-toast": "^2.4"
  },
  "devDependencies": {
    "vite": "^6.0",
    "vite-plugin-pwa": "^0.21",
    "workbox-window": "^7.3",
    "@vitejs/plugin-react": "^4.3"
  }
}
```

---

## 🚦 Build Sprints (Ordered)

| #   | Sprint                                                                      | Key Output             | Est.     |
| --- | --------------------------------------------------------------------------- | ---------------------- | -------- |
| 1   | Project scaffold: Docker Compose, Nginx, folder structure, `.env`           | Running local stack    | 2–3 days |
| 2   | PostgreSQL schema + SQLAlchemy models + Alembic initial migration           | DB ready               | 2 days   |
| 3   | Auth: register, login, Google OAuth, JWT, Redis blacklist, logout           | Full auth working      | 3–4 days |
| 4   | Brute force lockout, password reset, all auth emails (Resend)               | Secure auth            | 2 days   |
| 5   | S3 service: quarantine + production buckets, pre-signed URLs, multipart     | Storage working        | 2–3 days |
| 6   | File upload API: SHA-256 dedup check, size guard, Celery queue              | Upload pipeline stub   | 2 days   |
| 7   | ClamAV Docker sandbox, virus scan integration, quarantine → production move | Scan working           | 2–3 days |
| 8   | Claude Vision AI classifier: doc type, description, confidence, routing     | Classification working | 3–4 days |
| 9   | Text extraction: Textract + PyMuPDF + Tika + photo description              | Extraction working     | 2–3 days |
| 10  | Presidio PII scanner, masked text to Pinecone, raw text to S3               | Privacy pipeline done  | 2 days   |
| 11  | Voyage AI embedding + Pinecone ingestion with full metadata                 | RAG data ready         | 2 days   |
| 12  | RAG search API + Claude integration, streaming answers                      | Search working         | 2–3 days |
| 13  | Agentic tools: all 8 tools, Claude Tool Use API, conversation history       | Agent working          | 3–4 days |
| 14  | Token tracking, monthly cap, usage bar, fallback model routing              | Token system done      | 2 days   |
| 15  | ML Guard microservice: regex + BERT classifier + FastAPI endpoint           | Input guard live       | 2–3 days |
| 16  | `slowapi` rate limiting on all routes, Redis-backed                         | Rate limits live       | 1 day    |
| 17  | Health check endpoints + graceful shutdown + stuck file reconciler          | Reliability done       | 1–2 days |
| 18  | React frontend: auth pages, dashboard, upload, dedup dialog                 | Core UI done           | 4–5 days |
| 19  | React frontend: file viewer (PDF.js), share button, file management         | Viewer done            | 3 days   |
| 20  | React frontend: chat UI with streaming, conversation history, file refs     | Chat UI done           | 3 days   |
| 21  | Admin portal: stats, health, logs, security events, AI usage                | Admin done             | 3 days   |
| 22  | PWA: manifest, service worker, offline, push notifications, camera          | PWA done               | 2 days   |
| 23  | Cloudflare: WAF rules, Turnstile integration, Access for admin              | Edge security live     | 1–2 days |
| 24  | Alembic branch migration CI/CD: GitHub Actions full pipeline                | CI/CD done             | 2 days   |
| 25  | Audit logging middleware, privacy-safe log schema, user export              | Logging done           | 2 days   |
| 26  | S3 graceful migration system, feature flag, copy job                        | Migration system done  | 1–2 days |
| 27  | Security hardening: CORS tuning, CSP, secrets audit, pen test               | Hardened               | 2–3 days |
| 28  | Testing: unit + integration + E2E (Playwright), coverage ≥ 80%              | Tests done             | 3–4 days |
| 29  | Staging deploy + load test + bug fixes                                      | Staging validated      | 2–3 days |
| 30  | Production deploy: AWS ECS Fargate + RDS + Pinecone + CloudFront            | 🚀 Live                | 2 days   |

**Total estimated: ~10–12 weeks (solo developer)**

---

## 🧩 Post-MVP Backlog

- [ ] Document expiry alerts — "Your passport expires in 30 days" (Celery beat cron)
- [ ] File rename + move folder (basic file management)
- [ ] Bulk select + delete/move + download
- [ ] Search history — save and replay frequent searches
- [ ] End-to-end encryption — client-side encrypt before upload (zero-knowledge vault)
- [ ] Multi-language OCR — Hindi, regional Indian scripts via Textract
- [ ] Anomaly detection — alert admin if unusual download/delete volume
- [ ] Prometheus + Grafana — metrics dashboard, tracing, alerting
- [ ] Sharing — share one file via time-limited link (no login needed to view)
- [ ] Document auto-labeling — user-defined tags + AI-suggested tags
- [ ] Face/biometric detection flag — flag files containing face images (GDPR compliance helper)
- [ ] Mobile native app — React Native / Expo (reuse backend API)
- [ ] AWS KMS per-user CMK — per-user encryption keys (maximum isolation)
- [ ] Secret rotation plan — zero-downtime rotation for API keys and DB passwords
- [ ] AWS Budget alerts — `$50`, `$100` threshold notifications
- [ ] Cross-region S3 replication — disaster recovery
- [ ] OpenTelemetry tracing — trace a full upload across all services in one trace

---

## 📐 Key Design Decisions

| Decision      | Choice                 | Reason                                                        |
| ------------- | ---------------------- | ------------------------------------------------------------- |
| AI backend    | Anthropic Claude       | Best-in-class for document understanding and tool use         |
| Embeddings    | Voyage AI `voyage-3`   | Anthropic's recommended partner, multilingual (Hindi support) |
| Vector DB     | Pinecone (prod)        | Best metadata filtering for multi-tenant access control       |
| Auth          | JWT + Redis blacklist  | Stateless JWT + instant revocation on logout                  |
| File storage  | AWS S3 per-user prefix | Scalable, granular IAM + S3 policies                          |
| Queue         | Celery + Redis         | Battle-tested, Python-native, Redis already in stack          |
| Rate limiting | `slowapi`              | FastAPI-native, Redis-backed, per-route flexibility           |
| Email         | Resend                 | Simple API, great deliverability, React Email templates       |
| OCR           | AWS Textract           | Best for Indian document formats (Aadhaar, PAN)               |
| PII detection | Microsoft Presidio     | Open-source, customizable, Indian PII patterns                |
| Frontend      | React + Vite           | Fast HMR, easy Docker build, wide ecosystem                   |
| Migrations    | Alembic branch-based   | One migration per feature, never modified after merge         |
| Container     | Docker Compose         | Dev parity with production, easy local testing                |
