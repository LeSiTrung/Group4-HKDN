# Public data coverage and container readiness

**Goal:** Expand auditable public-source coverage and verify the real Docker/Linux application without replacing the tested local service or manufacturing retrieval scores.

**Authority:** Continuing autonomous engineering request and AGENTS.md. Preserve all existing uncommitted work and private runtime data. No paid services, authenticated crawling, access-control bypass, model promotion or public deployment.

**Architecture:** Reuse the safe HTTP crawler boundaries and existing SQLite/FastEmbed/FastAPI stack. Stage public LIC HTML with hashes and per-source status before review/publication. OPAC collection requires permitted access; category counters are not a deduplicated export. Build the existing Dockerfile and run an isolated loopback-only trial with synthetic accounts/public data.

- [x] DATA-03: Recheck LIC inventory/robots, implement and test a minimal resumable collector in scripts/collect_lic.py and tests/test_lic_collection.py. Collect discovered permitted library HTML, quarantine suspicious/private/example-credential material, and record measured denominators/failures. No raw auto-publication.
- [x] ACCESS-02: Recheck OPAC/robots and public export options. Save actual evidence in docs/validation/2026-11-01-opac-access.json; do not turn403/denial into an empty-catalog claim or bypass controls. Identify remaining authorized export requirements.
- [x] DOCKER-01: Verify live Engine, build the existing Dockerfile under a distinct local tag, run nonroot/capability-dropped application on a new local port and trial volume, test frontend/health/catalog/chat/auth/owner isolation/backup-restore as appropriate. Never mount the main SQLite/Qdrant read-write or expose public ports. Fix only reproduced container issues, with focused regression checks.
- [x] QA-05: Review independent changes, run affected tests and the integrated suite/build when source changes justify it; record precise coverage, measured quality and remaining staff/deployment gates in technical status files. No claim of perfect accuracy or complete OPAC coverage without a reconciled inventory.

**Review focus:** Robots/global denials stop collection; cached corruption is not accepted; checkpoint counts account for every discovered URL; URLs remain on allowed public hosts; fetched instructions never become system instructions. Container build context must exclude reader data, secrets, training weights and temporary screenshots; trial accounts must not affect main users. Frozen training test scores must not drive retraining or threshold tuning.

**Outcome:** Scoped LIC frontier reconciled; reviewed additions and multi-source hours tested; actual Docker/Linux/localTLS verified. OPAC bulk remains externally blocked and production/staff acceptance is not complete. Durable evidence: docs/validation/2026-11-01-data-container.json.
