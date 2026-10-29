# Conversation quality and feedback implementation plan

**Goal:** Continue the existing platform with concrete Vietnamese conversation fixes, a usable feedback review loop and reproducible CI.

**Architecture:** Retain React/FastAPI/SQLite/Qdrant/Ollama. Resolve deterministic catalog intent/context before retrieval. Never invent absent metadata or silently ignore unsupported exclusion/date conditions. Reuse explicit stored feedback; expose only rated answer, preceding question, comment and source snapshot to administrators, not whole conversations or reader identity. No schema migration or new dependency.

**Authority:** AGENTS.md sections 4,7,9,13 and the user's standing autonomous implementation instruction; existing platform plan. Design questions were previously waived. These implementation choices are engineering decisions within that scope.

## Scope and contracts

- Root owns services/catalog.py, services/assistant.py, conversation tests/evaluation and root status/docs.
- Feedback worker owns api/feedback_review.py (new), main.py router registration, components/FeedbackAdmin.jsx, Admin.jsx, ChatMessage.jsx disclosure, dedicated backend/frontend tests. Do not edit existing admin.py/history.py/schema.
- CI worker owns .github/workflows/verify.yml and tests/README.md only.
- No paid calls, production changes, fabricated catalog data, actual transactions, academic content or personal-data logging.

## Tasks

- [x] CONV-02: reproduce natural catalog lookup, bare follow-up author/year, unknown ISBN/shelf/availability, negation and mixed intent. Run tests/test_conversation_review.py RED; make minimal shared routing/context fixes; run regression/evaluation.
- [x] TIME-02: test invalid/ambiguous branch and relative-date requests against a verified synthetic schedule. Clarify rather than applying today's hours to another date/branch or unrelated use of “giờ”. Preserve current verified-today behavior.
- [x] FEEDBACK-01: GET /api/admin/feedback?rating=-1|1(optional)&page=1&page_size=20(max50) returns {items,total,page,page_size,summary:{positive,negative}}. Item {message_id,question,answer,rating,comment,status,mode,sources}; newest message first. No user_id/email/full conversation/token. Router requires admin. Preceding question must be in the same conversation and immediately precede that assistant turn. Cascade deletion remains effective. Tests: 401/403, filters/pagination/validation, plaintext unsafe strings, no unrelated private turns, deletion. UI filter/pagination/loading/empty/error, source links; rating controls disclose sharing scope.
- [x] QA-02: CI on push/PR/manual, least permissions, Python3.11/Node22; no model/service secrets. Backend pytest, restore self-test, deterministic evaluation; frontend npm ci/tests/build. Verify local commands and workflow syntax; never claim remote Actions ran without evidence.
- [x] RELEASE-02: fresh independent review, fix important findings using RED→GREEN, full tests/build, live local/browser smoke, update PROGRESS/ROADMAP/KNOWN_ISSUES/NEXT_STEPS and commit. Keep external acceptance blocked.

## Review focus

- Follow-up must use the most recent relevant book context; an unrelated newer question should not resurrect stale context.
- Unknown metadata/availability produces a clear limit with original book/source, never an invented shelf/ISBN/count.
- Unsupported negative/multiple intents cannot silently return contradictory matches.
- Feedback view cannot expose adjacent private conversations or unhashed identity/credentials.
- CI must not make paid/model/provider calls or publish/deploy the application.

## Evidence checkpoint

135 backend tests,29 frontend tests,restore/preflight,45 isolated cases,45 live API cases and2 real semantic probes passed. npm ci/test/build passed on Vitest4.1.12; audit0. Six final-review cases and unresolved-context cases verified RED→GREEN. No rulings or deferred minor review findings. Local deliverable is prepared for commit; external acceptance remains blocked. See docs/validation.md.
