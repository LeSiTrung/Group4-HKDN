# OPAC additional browse routes, serials and export UI

Bounded observation on **2026-11-01**. This records public metadata and UI behavior; it does not establish whole-catalog coverage, public full-text rights, or a supported bulk interface.

## Additional public browse routes

The previously saved homepage/search UI exposes `Khóa luận` with value `36` and the navigation link `gotoShowRecord(11,7)` for electronic serials. Its inline `gotoShowRecord` function constructs `OShow.aspx?DicID=…&BrowseId=…`.

| Observed listing | Listing summary | Stable OPAC record IDs |
| --- | --- | --- |
| [Khóa luận](https://opacthuvien.ut.edu.vn/opac/OShow.aspx?DicID=10&BrowseId=36) | Mục 1 đến 1 của 1 | `23325` |
| [Báo/Tạp chí điện tử](https://opacthuvien.ut.edu.vn/opac/OShow.aspx?DicID=11&BrowseId=7) | Mục 1 đến 2 của 2 | `18560`, `15869` |

These observations come from the existing ignored local HTML files `tmp/opac-dissertations.html` and `tmp/opac-electronic-serials.html`, supplied before this bounded investigation. The latter lists *Khoa học công nghệ giao thông vận tải (2021) : Xuất bản hàng quý* and *Xây dựng (2020) : Xuất bản hàng tháng*. Its “Download (Tải file)” buttons call `OpenLoginMagazine`, which displays a login notice. They were not invoked.

These are two additional publicly exposed browse routes beyond the original six document-type routes. Their counts must not be added to claim new unique records: membership may overlap the existing categories. The local collector now stages these routes as `36-…` and `11-7-…`; that local membership check does not certify coverage of unvisited source pages.

## Serial issue inspection

The public homepage/listing inline JavaScript defines `showMagazineList(ItemID)` as navigation to `OMagList.aspx?ItemId=…`. No card invocation of that function appeared in the inspected electronic-serial listing; the route was inspected because its construction is explicit in public page code.

The [issue-list route for record 18560](https://opacthuvien.ut.edu.vn/opac/OMagList.aspx?ItemId=18560) returned HTTP 200 HTML. The response contained an empty pagination container, hidden `hidMagId=0`, `hidYear=0`, and no issue entries or selectable year values. This empty shell is **not proof that issue records do not exist**; the correct operating state of this route remains unverified.

The [public detail for record 18560](https://opacthuvien.ut.edu.vn/opac/ODetail.aspx?intItemId=18560) returned HTTP 200 HTML with `hidItemID=18560` and MARC control number `GTVT210024649`. Its MARC 520 description names issues **39 (02/2021)** and **40+41 (05/2021)**. These are issue labels inside the parent bibliographic record, not independently verified issue IDs. No additional issue metadata IDs or public issue-file links were discovered by this inspection. The detail's file-download area displayed a login requirement; no login or download was attempted.

Ignored raw response for parser preflight: `tmp/opac-serial-detail-18560-research.html` (SHA-256 `46abe628ecd82f9f5de5ff8c4e0287f78d17800f342d4ff469e95ac346ed0774`). Raw HTML is outside the versioned evidence because it contains anonymous page state and unused internal catalog fields.

## Public export UI

The existing public inline function `export2File()` opens [OExport2FileUI.aspx](https://opacthuvien.ut.edu.vn/opac/OExport2FileUI.aspx). This page returned HTTP 200 HTML and offered **Microsoft Word** and **PDF** radio buttons. Its `processExport2File()` JavaScript constructs `OExport2File.aspx?intType=1` for Word or `intType=2` for PDF. Its return control calls `parent.showPopupMyList()`.

The listing's “Lưu danh sách” action updates the anonymous selected-ID list through `PageMethods.setItemToMyList`. No list mutation, export-file request, email action, or export download was performed. The inspected export UI exposes no MARC, CSV, all-results option, source total, or record-limit control. The selected-list connection is observable; export content and size limits remain unverified. There is therefore no demonstrated reduction in the metadata-harvest request count from this UI.

## Request evidence and remaining gaps

Exactly **three anonymous GET requests** were made for this investigation, using the existing `UTHLibraryBot/1.0` user agent and shared HTTPS/DNS-pinned fetcher. Each request permitted only its exact target URL. The first began after a 10-second wait, and subsequent starts were at least 10 seconds after the previous request ended. All returned HTTP 200 at the requested URL with `text/html; charset=utf-8`. No challenge workaround, authentication, POST, file retrieval, or automatic follow-up request was used.

| Target | Started, UTC | Finished, UTC | Response bytes |
| --- | --- | --- | ---: |
| `OMagList.aspx?ItemId=18560` | 13:17:06.773034 | 13:17:08.744281 | 45,889 |
| `ODetail.aspx?intItemId=18560` | 13:17:40.906309 | 13:17:42.821663 | 100,769 |
| `OExport2FileUI.aspx` | 13:17:53.109771 | 13:17:53.664495 | 4,584 |

Machine-readable request timestamps, response hashes and types are saved in ignored `tmp/opac-serials-research-request1.json` through `request3.json`; corresponding raw HTML is also ignored. No further requests were made by this investigation after **13:17:53.664495 UTC**. A separate collector may resume after **13:18:03.665 UTC** to preserve the 10-second gap.

Remaining gaps are the correct serial issue-list state and any separate issue IDs, the relationship between issue labels and independently indexed records, cross-route overlap, the contents/limits of selected-list exports, and full coverage of all publicly exposed browse modes. This bounded result does not prove that other public or operator-run export interfaces are absent.
