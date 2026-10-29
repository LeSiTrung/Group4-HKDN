# Technical roadmap

Updated 2026-10-29. Authority: AGENTS.md and docs/superpowers/plans/2026-10-28-library-platform.md. Software and operations only.

| ID | Priority | Deliverable | Status | Evidence / remaining work |
|---|---|---|---|---|
| CORE-01 | P0 | Accounts, private history/export/deletion, admin, persistence | Verified locally | Owner isolation, session revocation, stale-account races, migration and CSRF/rate/body limits |
| AI-01 | P1 | Reviewed FAQ, multilingual embedding/Qdrant, grounded Ollama | Verified locally | 27/27 deterministic and live API cases; 2/2 semantic probes. Development checks, not library acceptance |
| SEARCH-01 | P1 | Curated book CRUD/import/search, detail and follow-up | Verified locally | Keyword/fuzzy/semantic paths, draft exclusion, provenance and unknown live availability |
| UI-01 | P1 | Reader/admin interface, responsive layout, voice capability | Verified locally; voice acceptance pending | 24 tests + build; browser chat/catalog/admin/auth smoke; no physical microphone acceptance |
| OPS-01 | P1 | Launcher, container/HTTPS configuration, backup/restore | Partially verified | Windows launcher + restore pass; Compose config valid; full container runtime BLOCKED by unavailable daemon |
| QA-01 | P1 | Regression, independent review, reproducible evaluation | Verified locally | docs/validation.md and tests/evaluation; review findings fixed |
| EXT-01 | P1/external | Live OPAC, approved transactions/channels, authoritative content | BLOCKED | Backend403; no bridge/channel credentials. Seed:17 reviewed FAQs,1 real metadata snapshot |
| DEPLOY-01 | P1/external | Public HTTPS, capacity/restore rehearsal, real users | BLOCKED | Requires group-owned target and library/user acceptance |

**PROJECT NOT COMPLETE.** Local demo and tested adapters are available; external acceptance, adequate production catalog coverage and target-host verification remain required.