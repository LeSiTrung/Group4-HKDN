# Natural library requests

Scope: actual published catalog recommendations and source-backed borrowing guidance. No new model, schema migration, paid provider, full-text ingestion or lending transaction.

## Routing and evidence

- “hãy tìm cho tôi những sách để học IT tốt hơn” recognizes discovery and maps IT/CNTT to công nghệ thông tin. Explicit search, recommendation, reading and learning requests can use natural fillers.
- `llm_service.extract_book_topic` uses the existing local Ollama model only. The JSON schema accepts one topic of at most120characters; the returned normalized phrase must exist in the expanded question. It shares the existing prompt/concurrency/output budgets. It cannot supply book objects, authors, availability or actions. Invalid output/outage uses deterministic topic parsing.
- `search_books` prefers a complete title/subject phrase when available. Recommendations prioritize teaching material signals in titles, preserve học in subject nouns such as cơ học, deduplicate normalized title/author, and return at most5records (or the smaller requested count).
- Beginner/advanced signals come from title/description, not broad industry tags. Without evidence, related titles may be shown with `clarify`; explicit opposite-level titles are excluded. These signals are metadata hints, not independent pedagogical evaluation.
- Every recommended card includes `recommendation_reason`, original URL and checked date. React renders the reason as text. `catalog_ai` means actual local topic extraction was used; `catalog` is catalog lookup/fallback. It does not imply LLM-authored book facts.
- Follow-ups retain the prior topic; an explicit new subject/refinement replaces it. Availability selection happens after user preferences, followed by the existing at-most2public OPAC checks. Idle counts do not establish lending eligibility.

## Borrowing procedure regression

“Tôi cần chuẩn bị gì để mượn sách?” asks about procedure, not books with “chuẩn bị” in their metadata. Preparation, paperwork, reader-card and borrowing-condition phrases route to published `borrowing_guide` entries. A single relevant guide is selected by its curated category; multiple guides use keyword retrieval within that category. These filtered rows are never passed to shared vector rebuilding.

This path returns the reviewed guide answer directly. Live testing caught unsupported small-model additions even with valid source IDs, so procedural answers do not use free generation. Normal source revalidation, unconfirmed status and fee/current-policy safeguards still apply. The current guide describes presenting a card, finding materials, taking books to the librarian and checking their condition. It does not establish current limits, fees or renewal rights.

## Reproduce

Run from the repository root with the project interpreter:

```powershell
backend/.venv/Scripts/python -m pytest -q tests/test_recommendations.py tests/test_procedure_routing.py tests/test_context_level.py tests/test_catalog.py tests/test_catalog_scaling.py tests/test_query_dates.py
backend/.venv/Scripts/python scripts/evaluate.py --base-url http://127.0.0.1:8000 --cases tests/evaluation/natural-library-2026-11-03.json --output tmp/natural-library-evaluation.json
```

The live suite requires the imported UTH catalog and borrowing guide. Its12cases are development regressions from actual defects, not frozen or library-approved evaluation. The stricter local13-case probe additionally checked exact guide-answer equality, all Python results retaining Python, requested count and missing-book behavior. Results and limits: [validation summary](validation/2026-11-03-natural-library.json).

Final unit verification:608backend/51frontend tests; Vite production build passes. Browser visual verification remains unavailable under Work browser settings. Broader staff/user relevance labels and deployment capacity remain necessary; do not advertise perfect accuracy.

## Vector handoff and limits

Actual API search verifies27,964book sources/108,133chunks ready. Whole-catalog search now omits the redundant all-ID MatchAny filter; narrower kind filters and current-publication checks remain. Scrolling existing points uses4096records per page because local Qdrant sorts the full ID set per page. A cold single-user probe completed in65.008s after earlier120s timeouts; this is not a production latency target. The native cached-model process uses `HF_HUB_OFFLINE=1`.

SEARCH-02 remains open: the unmatched multi-word semantic probe returned6hits. Its successful HTTP response proves index activity, not relevance or answer accuracy. Treat semantic confidence/abstention and independent negative-query labels as a further P1 quality task. Main remains a local development deployment.
