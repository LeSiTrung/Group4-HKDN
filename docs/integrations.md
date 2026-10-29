# External integrations

Checked 2026-10-28. The application provides contract-tested adapters. Public OPAC reads, provider approval, real channel delivery and library transactions have separate acceptance requirements below.

## Python contracts

`app.services.integrations` exports synchronous functions:

- `crawl_pages(url, max_pages=3)` returns `[{title, url, text}]`. The caller must save imports as unpublished drafts and require review before serving them.
- `search_catalog(query, kind='all')` returns `{items: [{title, author, year, url}], search_url, warning}`. Only the first 20 recognized records are returned. Availability is never inferred.
- `library_loans(token)` returns a bridge object containing `loans: [object]`.
- `library_renew(token, loan_id, idempotency_key)` returns a confirmed bridge acknowledgement.

`IntegrationError` subclasses FastAPI `HTTPException`, exposing safe Vietnamese `detail`, `status_code` and a boolean `uncertain`. No upstream response bodies, access tokens or HTTP exception strings are exposed. A renewal with `uncertain=True` must remain blocked for reconciliation in the caller's persistent idempotency store; it must never be automatically resent. The service forwards the idempotency key but does not own account identity or the durable renewal ledger.

## Crawler

`CRAWL_ALLOWED_HOSTS` is a comma-separated list of exact hostnames; the default is `lic.ut.edu.vn,opacthuvien.ut.edu.vn`. The admin caller still controls authorization. Crawls stay on the seed hostname. Configure only sources for which collection is authorized.

- HTTPS with certificate verification, port 443, no embedded credentials, controls or backslashes.
- DNS answers must all be public unicast addresses. Connections use the validated IP while preserving the original Host and TLS SNI, preventing a second DNS lookup from rebinding to a private address. Environment HTTP proxies are disabled.
- Every redirect is validated before fetching, including robots authorization for page redirects. At most four hops are requested.
- `robots.txt` is fetched first. A 404 permits reads; other unavailable/denied responses fail closed. Disallow rules, crawl delays and request rates are respected. Delays above five seconds require a separately planned crawler.
- 1–10 page attempts, at most 100 queued links, 1 MiB decompressed content per response, ten-second read/five-second connect timeouts, a thirty-second checked response budget, 40,000 extracted characters per page. HTML only; no JavaScript execution, authenticated pages, PDFs, forms or binary downloads.
- Scripts, styles, navigation, headers, footers and forms are removed. Content remains untrusted source data and must not be treated as agent instructions.

## OPAC public search

The parser uses the public search page observed in [the OPAC survey](khao-sat-opac-2026-10-28.md):

`https://opacthuvien.ut.edu.vn/opac/Oshow.aspx?rdSearchOption=0&txtSearch=...`

`all` maps to value `0`; `books` maps to `1`; `digital` maps to `-4`. These exact option values were read from the visible public homepage dropdown `#UHeader1_rdSearchOption` in Edge on 2026-10-28; its labels were Toàn bộ, Sách truyền thống and Tài liệu số (Toàn văn), respectively. No login or transaction was performed.

The public result DOM was also inspected in Edge using the query `tàu`: each result uses `li > div.item-box`, a title anchor under `h2` with `onclick="parent.showPopupDetail(itemId)"` and **no href**, followed by metadata paragraphs within `.item-info .item-intro`. The parser accepts these anchors, earlier heading handlers and same-host detail links, removes the list ordinal and generates detail URLs from numeric IDs only. It reads author from the `Tác giả` paragraph and year only from a labelled publication paragraph in the same item card. Fields stay empty when absent; a title such as `2007 ABS Annual review` is not evidence of its publication year. A multi-card regression fixture checks that one record cannot borrow another record's author/year.

No undocumented library API is assumed. A 403, timeout, challenge page or changed/unrecognized markup is an explicit 502; it never becomes a successful empty list. Only explicit Vietnamese no-result text permits an empty result.

**Live acceptance:** a direct unauthenticated HTTP request to the OPAC homepage on 2026-10-28 returned HTTP 403 with a Cloudflare challenge. The previously observed browser result does not establish that this backend can read it. Do not bypass the challenge. Obtain an authorized upstream integration or permitted backend access and verify the parser against current public results, no-result pages, special characters and each filter before claiming working live catalog search.

## Approved library bridge

Set `LIBRARY_LOANS_URL` and `LIBRARY_RENEW_URL` only after the library supplies approved, full HTTPS endpoint URLs. These are deployment-specific bridge endpoints, **not claimed EMICLIB/UTH API addresses**. No defaults, endpoint discovery, credential login, token refresh or guessed renewal pages are implemented. The URLs must resolve to public unicast addresses. Private-network bridges need a separately reviewed network deployment; the adapter does not relax SSRF protection.

Agreed bridge contract:

| Operation | Request | Required response |
| --- | --- | --- |
| Loans | GET configured URL, `Authorization: Bearer <reader token>` | HTTP 200 JSON object with `loans: [object]`, at most 500 rows |
| Renew | POST configured URL, same authorization, `Idempotency-Key` header, JSON `{ "loan_id": "..." }` | HTTP 200 JSON `{ "status": "renewed", "loan_id": "same ID", "due_date": "YYYY-MM-DD" }` |

The bridge must scope the reader token and enforce eligibility, ownership and idempotency. The API caller must also require account authentication, explicit confirmation and a persistent key bound to that account and loan. Duplicate confirmed keys return their saved result; changed payloads conflict. Save the pending request before invoking the service. Any transport error, redirect, non-200 response, malformed JSON or missing/mismatched acknowledgement after entering a renewal call is conservatively uncertain. Do not delete that ledger entry or create a new key to retry. Reconcile with the library first, including pending entries left by process termination.

Real credentials and transactions were not supplied or tested. Tokens are passed in memory and headers only; the frontend must not persist them.

## Messenger and Zalo OA

Mount `app.api.channels.router` under `/api`. Supply `app.state.answer(text) -> dict` and a transactional `app.state.db()` SQLite context manager. These routes accept bounded text and invoke the answer function; no library transaction service is exposed to channel messages.

| Channel | Required environment |
| --- | --- |
| Messenger | `MESSENGER_APP_SECRET`, `MESSENGER_VERIFY_TOKEN`, `MESSENGER_PAGE_ID`, `MESSENGER_PAGE_ACCESS_TOKEN`, `MESSENGER_GRAPH_VERSION` |
| Zalo | `ZALO_APP_ID`, `ZALO_OA_SECRET_KEY`, `ZALO_OA_ID`, `ZALO_ACCESS_TOKEN` |

Missing required configuration returns 503. Set a currently supported Graph version explicitly (the official examples checked today use `v26.0`). Store secrets outside Git. Obtain app/OA approval, required messaging permissions and approved use of any charged channel before enabling credentials. No live messages were sent during implementation.

- `GET /api/webhooks/messenger` validates `hub.mode=subscribe` and the configured verification token, then returns plain `hub.challenge`.
- Messenger POST verifies `X-Hub-Signature-256` using HMAC-SHA256 over the exact raw body with the app secret. It accepts matching page/recipient IDs and message IDs, ignores echoes and non-text events, and sends a RESPONSE message to the configured Page Send API. It requires a nonempty upstream `message_id` acknowledgement.
- Zalo POST verifies `X-ZEvent-Signature` with SHA256 of `appId + rawBody + timestamp + OAsecretKey`, accepting a plain hex digest or `mac=` prefix. It validates the configured app/OA, accepts only `user_send_text` and sends a consultation text message to the official OA endpoint. Success requires `error=0` and a `data.message_id`.
- Payloads are capped at 256 KiB; input text at 4,000 characters; outgoing text at 2,000 characters. Signed event timestamps must be within 48 hours of the server clock; NTP and provider delivery windows must be checked during acceptance.
- `channel_events` stores a SHA256 event key (channel/recipient/message ID), channel, state and creation time. SQLite's primary key prevents concurrent duplicate processing and survives restarts. Message text, reader identifiers and tokens are not stored in this ledger.
- Claims are committed before answering; `uncertain` is committed before sending. Duplicate events are acknowledged without re-answering or re-sending. Timeout, rejected/malformed acknowledgement or a crash can leave `processing`, `failed` or `uncertain` records. An operator must reconcile such events with the provider before changing their state. This deliberately favors no duplicate sends; it cannot promise exactly-once delivery or recovery of an interrupted response. No automatic network retries are performed.
- Work runs through the ASGI thread pool; the handler waits for the bounded answer/send work. A provider may retry while it waits; dedup protects sends. Production throughput or stricter provider acknowledgement deadlines require an approved durable worker/outbox design and acceptance testing. Keep the ledger with database backups; deleting event keys can allow old deliveries to be processed again.

Official sources checked:

- [Meta Messenger webhooks](https://developers.facebook.com/documentation/business-messaging/messenger-platform/webhooks): verification challenge and SHA256 signatures, retrieved with Context7.
- [Meta Send Messages](https://developers.facebook.com/documentation/business-messaging/messenger-platform/send-messages): Page Send API, `RESPONSE`, text request and `message_id`, retrieved with Context7.
- [Zalo incoming message events](https://docs.zaloplatforms.com/docs/OA/webhook/tin-nhan/su-kien-nguoi-dung-gui-tin-nhan): signature formula, millisecond timestamp and incoming text event schema, read from the current official Document Hub.
- [Zalo text consultation messages](https://docs.zaloplatforms.com/docs/OA/tin-nhan/tin-tu-van/gui-tin-tu-van-dang-van-ban): current OA consultation endpoint, token header, recipient/text structure, 2,000-character limit and acknowledgement fields, read from the current official Document Hub.

## Verification boundary

Run `backend/.venv/Scripts/python.exe -m pytest tests/test_integrations.py -q`. Contract tests use HTTPX MockTransport and synthetic tokens/events, covering unsafe URLs and DNS, pinned Host/SNI, robots/redirects/size bounds, OPAC parsing and honest errors, bridge acknowledgements and uncertain renewal timeouts, signed Messenger/Zalo events, duplicate delivery, stale/echo/wrong-page messages and uncertain outbound sends. They do not prove provider permissions, real token validity, quotas/billing, public HTTPS deployment, actual signature-byte encoding from provider events, external retry behavior or real library renewal.
