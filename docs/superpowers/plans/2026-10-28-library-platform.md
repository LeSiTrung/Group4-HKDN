# Library Platform Implementation Plan

> For agentic workers: execute the shared API contracts below; use TDD and a fresh whole-change review. User requested continuous execution, including previously excluded features.

**Goal:** Deliver a runnable library assistant with grounded FAQ/RAG, accounts/history, administration, safe crawling, OPAC search, voice, external integration adapters and deployment documentation.

**Architecture:** React + FastAPI retained. SQLite stores users, opaque sessions, conversations/messages, curated knowledge and job/audit records. Qdrant stores embeddings from local multilingual FastEmbed; retrieval falls back explicitly to keywords when embeddings are unavailable. Ollama or an explicitly configured OpenAI-compatible endpoint generates grounded answers, with deterministic FAQ fallback. Crawled content is always draft until reviewed.

**Spec:** Earlier FAQ design plus user's explicit scope expansion on 28/10/2026; the expansion supersedes its exclusions. User requested implementation now, opting out of further design questions. Unverified fees/hours and untested external transactions must never be presented as confirmed.

## Global constraints

- Work in `D:/Github/Group4-HKDN`, branch `codex/library-platform`; user designated this checkout, preserve it instead of moving work elsewhere.
- No paid calls, public deployment, publishing, library login or live transactions without the necessary supplied configuration and authority.
- Python 3.11 local venv; one application process with persistent SQLite/Qdrant local storage; production supports remote Qdrant.
- No passwords/tokens in repository, frontend storage, logs or screenshots. Cookies HttpOnly/SameSite; unsafe browser requests require `X-Requested-With: D7` and a trusted Origin.
- No default administrator password. Bootstrap via CLI. Public registration creates reader only.
- Missing providers/integrations return explicit unavailable states; adapter contract tests are distinct from real service acceptance.

## Review focus

- Cross-account access to history/export/delete and admin elevation must be denied.
- Crawled URLs/redirects and linked OPAC content must not access private networks or create unreviewed assertions.
- Source withdrawal/expiry must immediately exclude text even when a stale vector exists.
- Concurrent chat sends, provider outages, invalid JSON and migrations must not lose user messages or invent transactions.
- Replay/signature/idempotency failures must not duplicate channel messages or library renewals.

## Shared HTTP contracts

All browser API requests use credentials and `X-Requested-With: D7` (GET harmless too). Errors use `detail` string or validation list. API prefix `/api`.

- `GET /health`: status, knowledge_count, version, capabilities (LLM/vector/crawler/channels/library readiness, no secrets).
- `POST /auth/register {name,email,password}`; `POST /auth/login {email,password}` → `{user:{id,name,email,role}}` + session cookie. `GET /auth/me` → same. `POST /auth/logout`. `POST /auth/password {current_password,new_password}`. `DELETE /auth/me {password}` removes own history/account.
- `POST /chat {message,conversation_id?:int}` → `{answer,status,sources:[{title,url,checked_at}],suggestions:[str],conversation_id:int|null,mode:'faq'|'rag'|'fallback'}`. Guest allowed; authenticated requests persist history. Need verified source for sensitive current policy/hours; no model-written transaction success.
- `GET /conversations` → array `{id,title,created_at,updated_at}`; `GET /conversations/{id}` → `{id,title,messages:[{id,role,content,sources,status,mode,created_at}]}`; `DELETE /conversations/{id}`; `GET /export` → own user and conversations.
- `POST /feedback {message_id:int,rating:int,comment?:str}` (authenticated, own assistant message, rating -1 or 1).
- `GET /catalog?q=...&kind=all|books|digital` → `{items:[{title,author,year,url,availability?:str}],search_url,warning?:str}`; upstream failure is 502/503, never empty success. Text safe, bounded results.
- `GET /admin/knowledge` → array knowledge rows. `POST /admin/knowledge` and `PUT /admin/knowledge/{id}` body `{title,question,aliases:[str],keywords:[str],answer,category,source_url,source_title,checked_at,status:'reviewed_public'|'needs_confirmation'|'verified',published:bool,valid_from?:str,valid_until?:str,verified_by?:str}` → row. `DELETE /admin/knowledge/{id}` withdraws/deletes. `POST /admin/reindex` returns state/count. `GET /admin/status` gives counts/capabilities/jobs. `GET /admin/users`, `PATCH /admin/users/{id} {active:bool}` (prevent self-disable).
- `POST /admin/crawl {url,max_pages?:int}` starts bounded crawl → `{job_id}`; `GET /admin/jobs` → rows including status/error. Imported records are unpublished, needs_confirmation. Same recurring seed can be enabled via `CRAWL_INTERVAL_HOURS`; off until sources configured.
- `GET /admin/schedules`; `POST /admin/schedules {branch,weekday,opens,closes,valid_from,valid_until,note,verified_by}`; `DELETE /admin/schedules/{id}`. No initial schedule is asserted verified.
- `POST /library/loans {access_token}` and `POST /library/renew {access_token,loan_id,confirmation:true,idempotency_key}`. Authenticated. Integration unavailable until library bridge URL supplied. Real upstream acknowledgement required; uncertain timeout held for reconciliation, never blind retry.
- Webhooks `/webhooks/messenger` GET/POST; `/webhooks/zalo` POST. Signature verification, deduplication and bounded text; no library transactions from webhook text.

## Tasks

### Task 1 — Core persistence, security and contracts
Files: `backend/app/config.py`, `database/connection.py`, `api/auth.py`, `api/history.py`, `main.py`, `tests/test_platform.py`.
- [x] Write tests: register/login/logout, blank/oversized input, owner isolation, admin permission and cookie/origin checks; run expected failures.
- [x] Implement SQLite schema initialization and transactional operations, Argon2 password hashes, opaque expiring/revocable sessions, reader/admin roles, history/export/deletion and feedback.
- [x] Run core tests to green, retain database on restart; bootstrap admin using CLI, no shipped credentials.

### Task 2 — Knowledge, deterministic retrieval, embeddings and grounded LLM
Files: `services/knowledge.py`, `services/rag_service.py`, `services/llm_service.py`, `api/chat.py`, `api/admin.py`, `data/faq/library.json`, `tests/test_knowledge.py`, `tests/test_llm.py`.
- [x] Test Vietnamese normalization, meaningful keyword threshold, ambiguity, unsafe/expired/unpublished sources, sensitive policy gating, malformed provider responses and provider outage.
- [x] Implement published-source CRUD, schedules with Asia/Ho_Chi_Minh current date, vector index, local multilingual embedding, strict source filtering after retrieval and bounded grounded generation. Imported web text cannot override system rules.
- [x] Load reviewed seed FAQ/OPAC guidance; preserve unconfirmed policy warnings. Reindex manually/admin and on approved source changes. Separate draft ingestion from serving.
- [x] Test actual embedding/index search locally and record model/version; test generation with a real local model when available; otherwise mark unavailable explicitly.

### Task 3 — Independent integration services
Files owned by integration worker: `services/integrations.py`, `api/channels.py`, `tests/test_integrations.py`, `docs/integrations.md`.
Interfaces: `crawl_pages(url,max_pages=3)->list[dict(title,url,text)]`; `search_catalog(query,kind='all')->dict`; `library_loans(token)->dict`; `library_renew(token,loan_id,idempotency_key)->dict`. Use exceptions with safe public errors. Main stores imported drafts and applies auth. Channels can call synchronous `request.app.state.answer(text)->dict` via threadpool; dedup persists in SQLite using `request.app.state.db()` context manager (sqlite3 Row). No modification of core database/auth/routes by worker.
- [x] Write failing tests for URLs/redirects, robots, limits, OPAC parsing and upstream errors, webhook signatures/replay and renewal uncertainty/idempotency.
- [x] Implement allowlisted crawler, direct public OPAC parser, configured library bridge with safe failures, Messenger/Zalo adapters against current official docs. No live sends without credentials.
- [x] Worker reports tests and real-service limitations; root integrates routes and jobs/scheduler.

### Task 4 — Independent frontend
Files owned by frontend worker: `frontend/**` only, `tests/frontend*` if needed.
- [x] Use UI/UX Pro Max. Build polished responsive Vietnamese application: chat/sources/suggestions, login/register, persistent conversation list/deletion/export/account deletion/password change, catalog results, admin knowledge CRUD/draft review/reindex/crawl jobs/schedules/users, voice recognition/TTS with feature detection and explicit browser capability errors, library loan/renew confirmation.
- [x] Follow exact shared HTTP contracts, escape content, never store library tokens/passwords in browser persistence. Guest history only in memory; account history server-side.
- [x] Build and test real render/interactions; report contract gaps. Do not modify backend or root docs.

### Task 5 — Package, verify and review
Files: Dockerfile, compose.yaml, Caddyfile, scripts/, README, docs/api-design.md, docs/operations.md, docs/validation.md.
- [x] Automated full suite; frontend build; browser desktop/mobile flows, real local API, admin review and account isolation; development corpus and separate semantic probes; capture results (staff-reviewed held-out acceptance remains pending).
- [x] Backup/restore using SQLite backup API plus regenerable vector index; health, rate/body limits, safe production cookies, trusted hosts/origins, deployment docs and persistent volumes.
- [x] Fresh code/security review, fix serious findings, rerun affected checks; prepare local deliverable commit and report external account/deployment acceptance still outstanding.

## Verification checkpoint — 2026-10-29

101 backend tests, 24 frontend tests, production build and local API/evaluation passed. See docs/validation.md for measured evidence. All checked tasks above mean implementation/local verification, not live external acceptance. PROJECT NOT COMPLETE: approved catalog/API, real channels/transactions, physical voice and target-host Docker/HTTPS acceptance remain blocked or unverified.
