# Known technical issues

Updated 2026-10-29.

- BLOCKED external: OPAC backend requests encounter HTTP403/challenge although a normal browser can view pages. Failed access is not an empty catalog result. Do not bypass controls.
- BLOCKED external: no library-approved loans/renewal bridge or test account, Messenger/Zalo credentials, or public host/domain supplied. Contract tests do not prove real delivery/transactions.
- Content coverage:17 reviewed FAQs and one genuine public book metadata snapshot. Admin import is implemented; an approved catalog feed is needed for broad book discovery. No synthetic books/live inventory counts are seeded.
- No verified current fee/opening schedule is seeded. A library operator must verify dated sources before publishing current values.
- Deployment: Docker client is installed but cannot reach Desktop Linux Engine. Compose config was validated; full image build, Linux runtime and public TLS remain unverified. No OS/WSL/security settings were changed to bypass this.
- Capacity: SQLite/local Qdrant use one app process. The 20-request concurrency probe covers FAQ only. LLM concurrency, uptime and production hardware limits are unestablished. CPU generation showed cold latency of tens of seconds; warm probes around two seconds are not an SLA.
- Voice: feature detection/UI handling exist; physical microphone/STT/TTS/mobile acceptance remains unverified. Browser speech services may depend on external availability.
- Dependencies: direct Python versions are pinned, transitive resolution is not a cross-platform lock. One Starlette TestClient/httpx deprecation warning remains.
- Channels avoid blind resend after ambiguous delivery. A crash during send can leave a pending event requiring operator investigation.
- Conversation bounds: exclusions/mixed independent requests ask for clarification rather than implementing a complete Boolean query language. Verified schedule answers support today and one branch; additional dates require clarification. Missing catalog attributes remain unconfirmed.
- CI workflow is committed configuration only until a GitHub run is observed. Local Node24 passed; Node22/Linux runner execution is still unverified. Vitest4.1.12 resolved the npm advisories observed during this milestone; future registry advisories may change.

Fixed this milestone: provider diagnostics mismatch, launch-directory-dependent runtime path, stale-account identity races, late source withdrawal, malformed model output, contextual book follow-ups, late renewal responses overwriting manual reconciliation. Regressions remain in the suite.
