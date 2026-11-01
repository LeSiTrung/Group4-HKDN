# UTH catalog access — technical findings, 31/10/2026

**Later implementation on the same date:** the fresh sitemap inventory increased to5,578 items. Collection reconciled every ID:5,569 public metadata snapshots,9 inaccessible401 items,0 technical failures/remaining. Of the public snapshots5,568 validated and were imported as published digital catalog entries after backup; one missing-title record remains quarantined. Reimport skipped all5,568 existing sources. The research-only observations below describe the earlier5,560-item snapshot; they are not the final collection totals. See [import operations](dspace-import.md) and [training results](embedding-training.md). This is public digital metadata, not printed holdings or full text.

## Confirmed public path: digital repository

The digital repository is separate from the printed-book OPAC. Direct anonymous HTTPS reads identified **DSpace 7.6** at https://thuvienso.ut.edu.vn/home and its public HAL API root at https://thuvienso.ut.edu.vn/server/api (both200).

- https://thuvienso.ut.edu.vn/sitemap_index.xml returns a valid sitemap index advertising sitemap0.xml.
- https://thuvienso.ut.edu.vn/sitemap0.xml currently lists **5721 unique URLs:5560 items,123 collections,38 communities**. These counts are sitemap coverage, not a verified full inventory or5560 printed books.
- Three item URLs from that sitemap were tested through their documented public single-item API representation. All three returned200 anonymously with title, handle, authors, issue date, publisher, language, type and other metadata fields. Sample metadata has creativework.keywords; the three records have no dc.description.abstract. Do not fabricate missing abstracts.
- Some dc.contributor.author values include a labelled thesis supervisor. Preserve source values and resolve roles before treating every entry as a book author.
- inArchive/withdrawn flags describe repository record state; they do not indicate physical copies available to borrow.
- The collection-wide REST /server/api/core/items?size=1 request returned401. No credentials, retries or impersonation were attempted. DSpace documents this listing as administrator-only and public single-item reads as a distinct interface.
- Homepage-advertised OpenSearch service description returned404; its presence in HTML does not establish a working harvesting service.

The full URL inventory is saved locally at tmp/dspace-sitemap-research.json. No bulk item metadata harvest, PDF/bitstream download or chatbot import occurred in this research task. Three sampled records are **not** a validation of all5560 links.

## OAI-PMH exists, but does not currently supply records

https://thuvienso.ut.edu.vn/server/oai/request?verb=Identify returns200 with repository THƯ VIỆN SỐ UTH and OAI-PMH2.0.

ListMetadataFormats returns formats including oai_dc, marc, mods, dim and xoai. ListSets returns27 sets. However, **ListIdentifiers and ListRecords with metadataPrefix=oai_dc both return noRecordsMatch**. Do not report this as an empty library or a working full harvest.

An unpopulated/stale OAI index is a possibility, not a confirmed diagnosis. Official DSpace7 documentation says an operator must maintain the OAI index using the dspace oai import administration command. Ask the repository operator to check the index/configuration and agree metadata scope before relying on OAI for synchronization. No server settings or maintenance commands were executed.

## Printed-book OPAC and other sources

https://opacthuvien.ut.edu.vn/robots.txt was rechecked: User-agent:*; Disallow:/; Crawl-delay:10. Do not interpret the delay as permission to crawl. OPAC/eMiclib public pages do not establish a supported bulk-export API. MARC display in the previously inspected record is not proof of an export permission or endpoint. No OPAC catalog pages were crawled in this task.

For a complete printed-book catalog, request a library-operated export (CSV/Excel, MARCXML or MARC21/ISO2709 if supported by their installed system), an approved API or a read-only approved data view. Request catalog metadata separately from current holdings and circulation. Do not request a raw database backup containing reader credentials/history.

LIC service pages, DSpace institutional documents, eMiclib holdings and licensed external databases such as ProQuest are different scopes. No one sitemap or API establishes coverage or full-text rights across all of them.

## Recommended next implementation

1. Use the DSpace sitemap inventory as the discovered set of public document IDs. Fetch anonymous single-item metadata slowly, with bounded concurrency, request/size/time limits, Retry-After handling, checkpoints and resumability. Keep provenance and fetch timestamps. Recheck robots before a harvest; stop on denial/authentication rather than changing identity.
2. Stage metadata as digital catalog records for review. Validate type/year/URL, preserve missing fields and supervisor labels, deduplicate by stable source identity, and reconcile withdrawn/missing records. Never interpret a transient request failure as deletion. Compare counts and failures against the source inventory; do not claim completeness without reconciliation.
3. Import reviewed metadata into the existing structured catalog. Use semantic retrieval for permitted descriptions, not for inventing bibliographic fields or availability. Full text is a separate, rights-dependent ingestion task.
4. Obtain an eMiclib export/API for printed books and current holdings. If staff repair/enable OAI records, prefer its datestamp/resumption/deletion mechanisms for incremental digital metadata updates.

## Evidence and primary documentation

- Local measured evidence: [catalog-discovery JSON](validation/2026-10-31-catalog-discovery.json).
- [DSpace7 item access contract](https://github.com/DSpace/RestContract/blob/dspace-7_x/items.md): administrator collection listing versus public single-item resources.
- [DSpace7 OAI configuration and index maintenance](https://wiki.lyrasis.org/spaces/DSDOC7x/pages/104566647/OAI).
- [OAI-PMH protocol](https://www.openarchives.org/OAI/openarchivesprotocol.html).

No application code/configuration or main database changed in this discovery task. No production deployment, authentication or paid API call. This document is an integration finding, not a claim of a completed data synchronization feature.
