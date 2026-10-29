# Technical progress

## 2026-10-29 — library-only natural chat and long messages

- User explicitly clarified library-only scope. Removed the earlier uncommitted general-chat interpretation, service prompt, route, UI and corresponding cancelled tests; no general mode was released. Kept the requested long-message and natural library support improvements.
- CHAT-03: removed2k composer/message/voice cuts; retained full original input and whitespace. Exact chat endpoint1MiB body, other routes64KiB; existing auth/rate/CSRF remain. Accepted account messages persist whole. Over16k current/derived context gets explicit clarification before expensive retrieval.
- Scoped greetings/thanks and helpful redirects; generic email/database definitions no longer produce unrelated LIC contact/resources. Multi-turn hours follow-ups retain evidence boundary. No unsourced general-answer generator exists.
- LLM-03: grounded generation only; marked4k history, capacity2, context8192 and conservative6144-byte complete prompt budget. Full evidence/current input are not clipped to fit. Oversized assembled prompt returns source-based fallback immediately. Budget counts UTF8/history/evidence; malformed Unicode context falls back safely.
- Baseline negative control against committed b371d79 failed11 new social/scope cases; current cases pass. Revised scope tests supersede cancelled open-chat expectations, rather than masking failures. Fresh library-only review found no confirmed blocking regression; its context-budget caveat was addressed with RED→GREEN budget/Unicode tests.
- Backend188 passed in25.75s; frontend35 passed, build42 modules, audit0. Restore self-test and launcher preflight pass. Original45 library development cases pass offline/live; separate10 dialogue/long-input cases pass offline/live;2 semantic probes pass, including a real rag response.
- Measured long5133-character library request: earlier model timeout/fallback60282.63ms; complete-prompt budget now yields source fallback36.76ms. No SLA/general-accuracy claim. Sources, not a claim that the model read unlimited text, explain the answer.
- No runtime schema migration or real-user account/dataset mutation. External catalog/API/channel, Docker/HTTPS and physical voice acceptance remain blocked/unverified. See docs/validation.md; PROJECT NOT COMPLETE.

## 2026-10-29 — conversation quality, feedback and CI

- CONV-02/TIME-02: reproduced ten conversation failures plus date/branch failures before fixing shared routing/context. Added natural lookup forms, author/year follow-ups, explicit unknown ISBN/shelf/publisher/availability, topic replacement and clarification for unresolved references, negation and mixed requests. Invalid/multiple branches and additional dates cannot reuse today's verified schedule. Loan deadlines/fees retain service routing.
- FEEDBACK-01: admin-only, paginated/filterable review of explicit ratings and immediate question/answer/source. No reader identity/full conversations projected; deletion cascades tested. UI disclosure before rating. Fixed stale admin-tab rows and excessive-page overflow found by tests. No schema/dependency added for this feature.
- QA-02: GitHub Actions workflow uses verified official action majors, Python3.11/Node22, read-only permissions, offline provider settings, tests/restore/evaluation and frontend clean install/test/build. No remote Actions run or deployment claimed.
- Dependency audit during clean install reported three vulnerable dev-tool packages (two critical counts). Updated Vitest3.2.7→4.1.12 after checking compatibility/advisories; clean npm ci, 29 tests, production build and audit all passed. Final npm audit: zero advisories at check time, not a guarantee against unknown vulnerabilities. No runtime framework migration.
- Final backend: 135 passed in28.27s, one TestClient deprecation warning. Frontend: 29 passed on Vitest4.1.12, build42 modules, JS300.45kB/gzip90.51kB. Restore self-test and launcher preflight passed. Local Node24 was tested; Node22/Linux remote runner remains unverified.
- Development evaluation expanded27→45 cases; isolated deterministic45/45, live local API45/45, real semantic probes2/2. Warm semantic-author2087.93ms; first embedding init during another request10001.2ms under concurrent verification. No general accuracy/SLA claim.
- Browser smoke on a separate temporary QA database: admin login, 21 synthetic ratings, page2, positive filter resetting to page1, logout. No main runtime accounts/history modified. Temporary server/tab closed after testing.
- Independent review: six reproductions for command extraction, explicit topic switch, possessive loan query and additional dates; all RED→GREEN. Additional unresolved/stale-reference regressions also RED→GREEN. No further important feedback projection/auth finding.
- Evidence and boundaries: docs/validation.md. External catalog/bridge/channels, Docker/HTTPS and real-user/voice acceptance remain blocked/unverified; PROJECT NOT COMPLETE.

## 2026-10-29 — project naming correction

- Removed the topic-list code from product branding, UI, API metadata, package/config names and documentation; product name is UTH Library / Trợ lý Thư viện UTH.
- Updated client/server CSRF marker together to LibraryAssistant and session cookie to library_session. Existing users need to sign in again; account/history records stay in the same SQLite file.
- Renamed the planning file and updated topic references. Existing report text received only the requested name correction; no academic content was added.
- Local runtime data, private backups and Git history were not rewritten. Container identity/path changed; any older external Compose installation must preserve its volumes or restore a backup before adopting the new project name.
- Verification after renaming: 101 backend tests passed (16.94s), 24 frontend tests passed, production build passed; refreshed in-app browser shows UTH Library title/brand. No topic code remains in tracked product text or filenames.

## 2026-10-29 — implementation and verification milestone

- Read AGENTS.md; kept academic reports/slides outside scope. Continued branch codex/library-platform from 087af11.
- CORE-01: Argon2/opaque sessions, reader/admin roles, private history/export/feedback/account controls, additive schema-v2 migration and bounded requests. Transactional identity checks fix account-deletion/ID-reuse races.
- AI-01: reviewed-source FAQ, multilingual FastEmbed/Qdrant, bounded Ollama generation with citation/number/URL checks and fallback. Strong lexical matches retain precise FAQ; source withdrawal/expiry is rechecked. No current fee/hour assertion without dated verified evidence.
- SEARCH-01: metadata catalog CRUD/atomic import, keyword/fuzzy/semantic search, pagination/detail/related records and guest/private follow-ups. No fabricated book/author/availability. Seed:17 FAQs and1 genuine OPAC metadata snapshot.
- UI-01: reader/admin workflows, source dates, cards/detail, private account/history, draft review/crawler/schedules/users/renewal reconciliation. Built-app browser smoke confirmed book search and follow-up uncertainty. Earlier checks covered admin/auth/import and375px layout.
- Integrations: allowlisted crawler imports drafts; periodic crawl defaults off. OPAC parser, bridge and Messenger/Zalo have contract tests; live services remain blocked.
- Independent review reproduced malformed model envelopes and late renewal responses overwriting final reconciliation. Fixed both; eight review cases plus six operations cases passed. No further concrete P0/P1 found in reviewed scope.
- OPS-01: pinned direct deps/npm lock, nonroot Dockerfile, Compose/Caddy, Windows launcher, exclusive-destination restore. Launcher/restore self-test passed. Real runtime SQLite backup→restore retained v2/books and revoked restored sessions. Removed only our synthetic accounts/drafts; private backup is ignored by Git.
- QA-01: final full suite: 101 backend tests passed in 14.45s, one TestClient deprecation warning. Frontend: 24 tests/build passed. Evaluation: 27/27 isolated, 27/27 live API, 2/2 semantic probes; not library acceptance. FAQ concurrency: 20/20 HTTP200, 10 workers; no LLM throughput claim.
- Routing improvement measured: paper guidance changed from general RAG28.446s to specific page4 FAQ10.72ms. Warm semantic probe2065.94ms. Machine/run-specific, not an SLA/accuracy estimate.
- Docker client cannot reach Linux Engine pipe; full image/runtime/public TLS acceptance unverified.

**Locally runnable and tested; PROJECT NOT COMPLETE.** EXT-01/DEPLOY-01 remain blocked. See KNOWN_ISSUES.md and NEXT_STEPS.md.
