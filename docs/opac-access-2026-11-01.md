# OPAC access and catalog coverage — 01/11/2026

Status: **BLOCKED for bulk collection**. A normal public browser page is readable; this does not establish permission or a supported interface for a full metadata harvest.

## Current observations

At 09:03 UTC, one anonymous HTTPS request to [robots.txt](https://opacthuvien.ut.edu.vn/robots.txt) returned 200 with `User-agent: *`, `Disallow: /`, and `Crawl-delay: 10`. The delay does not override the prohibition. One request to the [OPAC homepage](https://opacthuvien.ut.edu.vn/opac/) returned 403 and a Cloudflare managed challenge. No retry, challenge bypass, identity change or catalog crawl followed. The web-reading tool also returned 403 for the homepage.

The existing normal Edge browser tab displayed the public homepage without logging in. Its counters, checked again on 01/11/2026, match the supplied screenshot:

| Homepage category | Displayed count |
| --- | ---: |
| Sách truyền thống | 10,457 |
| Tài liệu số (toàn văn) | 7,510 |
| Luận văn | 3,260 |
| Báo / tạp chí | 823, including a separate label “toàn văn - 670” |
| CD-ROM | 371 |
| Video | 3 |

Only the first [traditional-book category page](https://opacthuvien.ut.edu.vn/opac/OShow.aspx?DicID=10&BrowseId=1) was inspected through visible navigation. It says “Mục 1 đến 20 của 10.457”. A single result for *"Buông" thể hiện khí phách và trí tuệ : Sống đẹp* contains two copy identifiers, `KS1V082935` and `KS2V082936`. Thus 10,457 is a result-entry count for that category, not a physical-copy count or a count currently available to borrow. This observation does not certify the completeness or currency of the underlying catalog.

## What the counters do not establish

The inspected UI does not explain whether category membership overlaps. Do not add the six counters to claim a unique-record total. The 670 fulltext label is not a seventh independent inventory; its relationship to the 7,510 digital category is unverified. Other category pagination totals were not opened.

OPAC digital records and the separate [DSpace repository](https://thuvienso.ut.edu.vn/home) must retain distinct provenance. Existing DSpace imports do not prove coverage of the OPAC digital category, printed books, journals or copies. A count difference cannot identify missing records without a stable-ID crosswalk. “Toàn văn” is a UI label, not proof that every file is anonymously accessible or licensed for ingestion.

## Bulk interfaces and integration route

No public bulk-export, sitemap, OAI or API link was found among the inspected homepage/category links. The homepage advertises search, advanced search and metadata browsing. “Lưu danh sách” is visible on results, but was not used and does not establish whole-catalog export. Detail-page export and administrator facilities remain unverified. No guessed sitemap/API endpoints, hidden calls or denied-page pagination were probed. These bounded observations do not prove that the installed system has no export capability.

The next usable route is a **library-operated metadata export or expressly approved read-only feed/API**. Ask the library operator for CSV/Excel, MARCXML, or MARC21/ISO2709 if their installation supports it. Preserve stable source record IDs, titles, contributor roles, identifiers, publication data, type/category membership, subjects/classification, public URLs and export timestamps. Request source totals and the meaning of overlapping categories so that an import can reconcile records rather than count page hits.

Obtain copy/branch/location and current circulation status as a separate approved data scope with timestamps. Do not infer availability from bibliographic records, request reader data or ingest licensed fulltext through this metadata route. Stage and validate the supplied export before import; no runtime, database, configuration or catalog content changed in this investigation.

Machine-readable evidence, request timestamps and sanitized response headers: [2026-11-01-opac-access.json](validation/2026-11-01-opac-access.json). Previous digital-repository findings and their distinct scope: [catalog-data-access.md](catalog-data-access.md).

## Follow-up: robots is not the network barrier

At the user's explicit follow-up request, revisited the existing ordinary Edge session without login or identity changes. The OPAC homepage rendered its public search/browse links and counters. Clicking the visible traditional-book category then returned a Cloudflare **522 Connection timed out**, with11:22:44UTC shown on the error page on01/11/2026. The error reports browser/Cloudflare working and the origin host failing. No repeated category requests or pagination followed. Browser Back restored the original readable homepage.

These observations distinguish three separate things: REP crawler instructions, the earlier managed403 response to automated HTTPS, and the current origin-connection522 during normal browser navigation. [RFC9309](https://www.rfc-editor.org/rfc/rfc9309.html#section-1) explicitly distinguishes robots rules from access authorization. Omitting a client's robots check cannot repair an origin timeout or establish an available bulk endpoint. [Cloudflare's522 documentation](https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-5xx-errors/error-522/) identifies a timeout contacting the origin; it does not prove which origin-side cause applies here.

The intended follow-up was inspection of public save/export functionality, not a mass browser crawl. The category failure prevented that inspection, so public bulk export remains **unverified**, not proven absent. General vendor/product search results were not used to claim the installed UTH system exposes MARC/OAI/Z39.50 or an export API. No book metadata was imported from truncated homepage titles, and no private/full-text data was acquired. No crawler protection/configuration was disabled merely to produce another failed request.

Operational options are an operator-produced bibliographic export with source totals/stable IDs, a documented read-only endpoint, or a library-configured crawler allow rule and upstream access allowance after the origin issue is repaired. They require library-side action; an app-side code switch is insufficient. Holdings/copy/availability remain a separate scope. Follow-up evidence: [opac-export-followup.json](validation/2026-11-01-opac-export-followup.json); local screenshot `tmp/opac-origin-timeout-20261101.png`. No application/database change or test rerun was necessary for this read-only investigation.
