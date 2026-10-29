# Library-only conversation and long-message plan

**Goal:** Make library chat more natural and accept longer messages while keeping every factual answer grounded in library evidence.

**Authority:** The user's latest clarification explicitly restricts answers to the library. It supersedes the earlier interpretation of any-word messaging as general knowledge. The general prompt/route/UI/tests were removed before release; no general capability is retained.

**Architecture:** React/FastAPI/SQLite/Ollama retained. No 2,000-character composer/message validator. Exact chat route has1MiB total HTTP-body bound, other mutations64KiB. Accepted original message is stored whole. Current or expanded retrieval context over16,000 characters gets explicit split/shorten guidance. Grounded LLM uses bounded marked recent history,8,192-token context, bounded output and two concurrent requests. No new dependency or migration.

- [x] CHAT-03: long-message transport/storage, context guard before expensive retrieval, friendly library greetings/clarification and redirection of unrelated definitions; no general-knowledge route. Known fee/hour/source/owner guards retained.
- [x] LLM-03: shared bounded provider helper with grounded generate_answer only, marked4,000-character history, capacity2 and original-message bound. Complete prompt is limited to6,144 UTF-8 bytes before any provider call. Source/number/URL/transaction validation preserved. General tests explicitly superseded by35 grounded capacity cases.
- [x] UI-03: composer/voice no2k cut, original text preserved, six marked guest excerpts; library-only welcome, placeholders and starters. Six new UI tests; broad AI mode removed.
- [x] QA-03:188 backend/35 frontend tests pass; production build and npm audit pass. Original45 cases and new10 library-dialogue cases pass offline and live; two semantic probes pass live, including a source-cited rag answer. Browser smoke unavailable because the CUA browser user is unavailable. No paid calls or false production/accuracy claims.

## Review focus

- Generic “Email là gì?” must not be answered with LIC contact data; unrelated knowledge is redirected.
- Short contextual service questions must not produce unsupported hours/fees from a free-form model.
- Long original messages persist unchanged; inherited history cannot bypass retrieval/context bounds.
- No request path removes global body/rate/auth protections; current-user data remains private.
- Literal infinite input/output/context is not promised; the UI explains limits and asks for smaller parts.
